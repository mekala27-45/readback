"""A BM25 index over the catalog, in plain Python.

Built once when the catalog is built and committed as catalog/index.parquet: one row per document
(a table, a column, a metric or a manifest key) with its tokens. The server loads it into memory at
start, so no DuckDB extension is ever loaded at request time. The query is expanded through the
synonym table before it is scored, and the expanded query is returned so a caller can see what was
searched.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from readback_catalog.tokens import tokens

K1 = 1.2
B = 0.75


@dataclass(frozen=True)
class Doc:
    id: str
    kind: str  # table, column, metric, manifest
    warehouse: str
    name: str
    text: str
    unit: str | None
    definition: str | None


@dataclass(frozen=True)
class Hit:
    doc: Doc
    score: float


class Synonyms:
    """Words a person uses, mapped to the words the catalog uses."""

    def __init__(self, table: Mapping[str, Sequence[str]]) -> None:
        self.table: dict[tuple[str, ...], list[str]] = {}
        for phrase, targets in table.items():
            self.table[tuple(tokens(phrase))] = [t for target in targets for t in tokens(target)]

    def expand(self, query: str) -> list[str]:
        words = tokens(query)
        out = list(words)
        for phrase, targets in sorted(self.table.items(), key=lambda kv: -len(kv[0])):
            n = len(phrase)
            if n == 0:
                continue
            for i in range(len(words) - n + 1):
                if tuple(words[i : i + n]) == phrase:
                    out.extend(t for t in targets if t not in out)
                    break
        return out

    def unmapped(self, vocabulary: set[str]) -> list[str]:
        """Synonyms whose targets name no word the catalog contains: a quarantine rule."""
        bad: list[str] = []
        for phrase, targets in self.table.items():
            if targets and not any(t in vocabulary for t in targets):
                bad.append(" ".join(phrase))
        return sorted(bad)


class Index:
    def __init__(self, docs: Sequence[Doc]) -> None:
        if not docs:
            raise ValueError("the index was given no documents")
        self.docs = list(docs)
        self.doc_tokens = [Counter(tokens(d.text)) for d in self.docs]
        self.lengths = [sum(c.values()) for c in self.doc_tokens]
        self.avg = sum(self.lengths) / len(self.lengths)
        df: Counter[str] = Counter()
        for c in self.doc_tokens:
            df.update(c.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    @property
    def vocabulary(self) -> set[str]:
        return set(self.idf)

    def score(self, query_tokens: Iterable[str], i: int) -> float:
        c = self.doc_tokens[i]
        length = self.lengths[i]
        s = 0.0
        for t in set(query_tokens):
            f = c.get(t, 0)
            if f == 0:
                continue
            s += self.idf.get(t, 0.0) * f * (K1 + 1) / (f + K1 * (1 - B + B * length / self.avg))
        return s

    def search(
        self, query_tokens: Sequence[str], k: int, *, warehouse: str | None = None, kinds: Sequence[str] = ()
    ) -> list[Hit]:
        hits = []
        for i, d in enumerate(self.docs):
            if warehouse and d.warehouse != warehouse:
                continue
            if kinds and d.kind not in kinds:
                continue
            s = self.score(query_tokens, i)
            if s > 0:
                hits.append(Hit(d, round(s, 6)))
        # A stable tie break: score, then id, so the same query returns the same order everywhere.
        hits.sort(key=lambda h: (-h.score, h.doc.id))
        return hits[:k]

    def write(self, path: Path) -> None:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pa.table(
            {
                "id": [d.id for d in self.docs],
                "kind": [d.kind for d in self.docs],
                "warehouse": [d.warehouse for d in self.docs],
                "name": [d.name for d in self.docs],
                "text": [d.text for d in self.docs],
                "unit": [d.unit for d in self.docs],
                "definition": [d.definition for d in self.docs],
            }
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path, compression="zstd")

    @classmethod
    def read(cls, path: Path) -> Index:
        import pyarrow.parquet as pq

        t = pq.read_table(path).to_pylist()
        return cls([Doc(**row) for row in t])
