"""The SQL guard: read only, one statement, parsed before it runs.

A statement reaches the warehouse only after sqlglot has parsed it in the DuckDB dialect and every
rule below has passed. Each refusal names the clause it refused, so the caller can fix the query
rather than guess. The read only connection behind it is the second line, not the first.

Rules, in order:
  1. it parses, and it is exactly one statement;
  2. the statement is a SELECT, a WITH over a SELECT, or a set operation of SELECTs;
  3. nothing inside it writes, attaches, copies, installs, loads, sets, pragmas or describes;
  4. it calls no table function and no function that reads a file or the environment;
  5. every table it names lives in the named warehouse schema (an unqualified name that the
     warehouse has is qualified, a name it does not have is refused with the nearest three);
  6. the outer LIMIT is at most the ceiling, and is added at the ceiling when absent.
"""

from __future__ import annotations

import difflib
from collections.abc import Collection
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

ROW_CEILING = 500
TIMEOUT_SECONDS = 10.0

# Statement kinds that are not a query, by the sqlglot class name. Any of them anywhere in the tree
# is refused, which also catches a write tucked into a CTE.
REFUSED_NODES: dict[str, str] = {
    "Insert": "INSERT",
    "Update": "UPDATE",
    "Delete": "DELETE",
    "Merge": "MERGE",
    "Create": "CREATE",
    "Drop": "DROP",
    "Alter": "ALTER",
    "TruncateTable": "TRUNCATE",
    "Copy": "COPY",
    "Attach": "ATTACH",
    "Detach": "DETACH",
    "Install": "INSTALL",
    "Pragma": "PRAGMA",
    "Set": "SET",
    "Use": "USE",
    "Describe": "DESCRIBE",
    "Show": "SHOW",
    "Command": "a command",
    "Export": "EXPORT",
    "Grant": "GRANT",
    "Transaction": "a transaction",
    "Commit": "COMMIT",
    "Rollback": "ROLLBACK",
    "Analyze": "ANALYZE",
    "Cache": "CACHE",
    "LoadData": "LOAD",
}
# Functions that read files, the network or the environment, or that change state.
REFUSED_FUNCTIONS = frozenset(
    {
        "read_parquet",
        "read_csv",
        "read_csv_auto",
        "read_json",
        "read_json_auto",
        "read_ndjson",
        "read_text",
        "read_blob",
        "parquet_scan",
        "parquet_metadata",
        "parquet_schema",
        "glob",
        "read_xlsx",
        "sniff_csv",
        "duckdb_settings",
        "duckdb_extensions",
        "duckdb_secrets",
        "getenv",
        "current_setting",
        "query",
        "query_table",
        "load_extension",
        "install_extension",
        "duckdb_databases",
        "duckdb_tables",
        "duckdb_views",
        "duckdb_columns",
        "pragma_version",
    }
)
SET_OPERATIONS = (exp.Union, exp.Intersect, exp.Except)


class Refused(ValueError):
    """The statement was refused before it ran. `clause` names what was refused."""

    def __init__(self, clause: str, reason: str) -> None:
        super().__init__(f"refused {clause}: {reason}")
        self.clause = clause
        self.reason = reason


@dataclass(frozen=True)
class Guarded:
    sql: str  # the normalized statement that runs
    unlimited: str  # the same statement with no outer limit, for the row count before the limit
    limit: int
    tables: tuple[str, ...]


def _is_query(node: exp.Expr) -> bool:
    if isinstance(node, exp.Select):
        return True
    if isinstance(node, SET_OPERATIONS):
        return _is_query(node.left) and _is_query(node.right)
    if isinstance(node, exp.Subquery):
        return _is_query(node.this)
    return False


def _function_name(node: exp.Expr) -> str | None:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    if isinstance(node, exp.Func):
        return str(node.sql_name()).lower()
    return None


def guard(
    sql: str,
    warehouse: str,
    tables: Collection[str],
    limit: int | None = None,
    *,
    ceiling: int = ROW_CEILING,
) -> Guarded:
    """Parse, check and normalize one statement against one warehouse whose tables are `tables`."""
    if not sql or not sql.strip():
        raise Refused("the statement", "it is empty")
    try:
        parsed = [p for p in sqlglot.parse(sql, read="duckdb") if p is not None]
    except ParseError as err:
        raise Refused(
            "the statement", f"it does not parse as DuckDB SQL ({str(err).splitlines()[0][:120]})"
        ) from err
    if len(parsed) != 1:
        raise Refused(
            "a second statement", f"{len(parsed)} statements were sent; one SELECT or WITH is allowed"
        )
    tree = parsed[0]
    for node in tree.walk():
        kind = type(node).__name__
        if kind in REFUSED_NODES:
            raise Refused(REFUSED_NODES[kind], "the server is read only and runs queries only")
    # Every shape _is_query accepts is an exp.Query; the isinstance check narrows the type.
    if not isinstance(tree, exp.Query) or not _is_query(tree):
        raise Refused(
            type(tree).__name__.upper(),
            "only a SELECT, a WITH over a SELECT, or a set operation of SELECTs runs",
        )
    for node in tree.walk():
        name = _function_name(node)
        if name and (name in REFUSED_FUNCTIONS or name.startswith(("read_", "pragma_", "duckdb_"))):
            raise Refused(f"the function {name}", "it reads outside the warehouse")
    cte_names = {str(c.alias_or_name).lower() for c in tree.find_all(exp.CTE)}
    known = {t.lower() for t in tables}
    used: list[str] = []
    for table in tree.find_all(exp.Table):
        if isinstance(table.this, exp.Func) or table.args.get("this") is None:
            raise Refused("a table function", "tables come from the warehouse schema, not from a function")
        name = str(table.name).lower()
        schema = str(table.db).lower() if table.db else ""
        catalog = str(table.catalog).lower() if table.catalog else ""
        if catalog:
            raise Refused(f"the reference {table.sql()}", "a catalog prefix is not allowed")
        if not schema and name in cte_names:
            continue
        if schema and schema != warehouse:
            raise Refused(f"the reference {schema}.{name}", f"this call is scoped to the {warehouse} schema")
        if name not in known:
            near = difflib.get_close_matches(name, sorted(known), n=3, cutoff=0.0)
            raise Refused(f"the table {name}", f"{warehouse} has no such table; nearest: {', '.join(near)}")
        table.set("db", exp.to_identifier(warehouse))
        used.append(name)
    requested = ceiling if limit is None else max(1, min(int(limit), ceiling))
    existing = tree.args.get("limit")
    current: int | None = None
    if existing is not None:
        expression = existing.expression if hasattr(existing, "expression") else None
        if isinstance(expression, exp.Literal) and expression.is_int:
            current = int(expression.this)
        else:
            raise Refused("the LIMIT", "the limit must be a whole number")
    final = requested if current is None else min(current, requested)
    unlimited_tree = tree.copy()
    unlimited_tree.set("limit", None)
    limited = (
        tree.limit(final, copy=True)
        if isinstance(tree, exp.Select)
        else exp.select("*").from_(tree.subquery("q")).limit(final)
    )
    return Guarded(
        sql=limited.sql(dialect="duckdb"),
        unlimited=unlimited_tree.sql(dialect="duckdb"),
        limit=final,
        tables=tuple(sorted(set(used))),
    )
