"use client";

import { useEffect, useMemo, useState } from "react";

import { readParquet, type Row } from "@/lib/parquet";
import { loadJson } from "@/lib/site";

interface Column {
  name: string;
  type: string;
  role: string;
  unit: string;
  definition: string | null;
  citation: { file: string; line: number } | string | null;
  manifest_keys: string[];
}
interface Table {
  name: string;
  rows: number;
  grain: string[];
  description: string;
  columns: Column[];
}
interface Warehouse {
  name: string;
  repository: string;
  tag: string;
  commit: string;
  as_of: string | null;
  files: number;
  metrics: { name: string; table: string; definition: string; sql: string }[];
  tables: Table[];
  lock: { path: string; sha256: string }[];
}
interface CatalogData {
  warehouses: Warehouse[];
  synonyms: Record<string, string[]>;
  quarantine: { counts: Record<string, Record<string, number>>; rows: { warehouse: string; rule: string; subject: string; detail: string }[] };
}

const TABS = ["tables", "manifest", "synonyms", "quarantine", "lock"] as const;
type Tab = (typeof TABS)[number];

function Columns({ table }: { table: Table }) {
  return (
    <div className="overflow-x-auto">
      <table className="dense" data-testid="columns">
        <thead>
          <tr>
            <th>Column</th>
            <th>Type</th>
            <th>Role</th>
            <th>Unit</th>
            <th>Definition</th>
            <th>Manifest keys</th>
          </tr>
        </thead>
        <tbody>
          {table.columns.map((c) => (
            <tr key={c.name}>
              <td className="font-mono">{c.name}</td>
              <td className="font-mono text-ink2">{c.type}</td>
              <td>{c.role}</td>
              <td>{c.unit}</td>
              <td className="max-w-[48ch]">
                {c.definition ?? <span className="text-ink2">quarantined: no cited definition</span>}
                {c.citation && <span className="block text-xs text-ink2 font-mono">{typeof c.citation === "string" ? c.citation : `${c.citation.file}:${c.citation.line}`}</span>}
              </td>
              <td className="font-mono text-xs">{c.manifest_keys.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ManifestSearch({ warehouse }: { warehouse: string }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    void readParquet("manifest_index.parquet").then(setRows);
  }, []);
  const shown = useMemo(
    () => (rows ?? []).filter((r) => r.warehouse === warehouse && (!q || String(r.key).toLowerCase().includes(q.toLowerCase()))).slice(0, 150),
    [rows, q, warehouse],
  );
  if (!rows) return <div className="skeleton h-48" aria-label="Loading the manifest index" />;
  const total = rows.filter((r) => r.warehouse === warehouse).length;
  return (
    <div className="space-y-2">
      <label className="text-sm text-ink2 block">
        Filter {total} manifest keys{" "}
        <input value={q} onChange={(e) => setQ(e.target.value)} className="ml-2 bg-raised border border-hairline rounded px-2 py-1 font-mono text-xs" data-testid="manifest-filter" />
      </label>
      <div className="overflow-x-auto">
        <table className="dense" data-testid="manifest-values">
          <thead>
            <tr>
              <th>Key</th>
              <th className="num">Value</th>
              <th>Text</th>
              <th>Population</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={String(r.key)}>
                <td className="font-mono text-xs">{String(r.key)}</td>
                <td className="num">{r.value === null || r.value === undefined ? "" : Number(r.value).toLocaleString("en-US", { maximumFractionDigits: 6 })}</td>
                <td>{r.text ? String(r.text) : ""}</td>
                <td className="text-ink2">{r.population ? String(r.population) : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Catalog() {
  const [data, setData] = useState<CatalogData | null>(null);
  const [wh, setWh] = useState("doorstep");
  const [tab, setTab] = useState<Tab>("tables");
  const [tableName, setTableName] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  useEffect(() => {
    void loadJson<CatalogData>("catalog.json").then(setData);
  }, []);
  if (!data) return <div className="skeleton h-96" aria-label="Loading the catalog" />;
  const w = data.warehouses.find((x) => x.name === wh) as Warehouse;
  const tables = w.tables.filter((t) => !filter || `${t.name} ${t.description}`.toLowerCase().includes(filter.toLowerCase()));
  const table = w.tables.find((t) => t.name === tableName) ?? tables[0];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Warehouse">
        {data.warehouses.map((x) => (
          <button
            key={x.name}
            role="tab"
            aria-selected={x.name === wh}
            onClick={() => {
              setWh(x.name);
              setTableName(null);
            }}
            className={`px-3 py-1.5 rounded border text-sm ${x.name === wh ? "border-warehouse text-ink" : "border-hairline text-ink2"}`}
          >
            {x.name} <span className="font-mono text-xs">{x.tables.length} tables</span>
          </button>
        ))}
      </div>
      <p className="text-sm text-ink2 font-mono break-all">
        {w.repository} at {w.tag}, commit {w.commit.slice(0, 12)}, {w.files} files checked by SHA-256
      </p>
      <div className="flex flex-wrap gap-1 border-b border-hairline" role="tablist" aria-label="Section">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={t === tab} onClick={() => setTab(t)} className={`px-3 py-1.5 text-sm ${t === tab ? "border-b-2 border-warehouse text-ink font-bold" : "text-ink2"}`}>
            {t}
          </button>
        ))}
      </div>

      {tab === "tables" && (
        <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="space-y-2">
            <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter tables" aria-label="Filter tables" className="w-full bg-raised border border-hairline rounded px-2 py-1 text-sm" />
            <ul className="max-h-[60vh] overflow-y-auto text-sm" data-testid="table-list">
              {tables.map((t) => (
                <li key={t.name}>
                  <button type="button" onClick={() => setTableName(t.name)} className={`w-full text-left px-2 py-1 rounded font-mono text-xs ${t.name === table?.name ? "bg-raised border-l-2 border-warehouse" : "hover:bg-raised"}`}>
                    {t.name} <span className="text-ink2">{t.rows.toLocaleString("en-US")}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          {table && (
            <div className="space-y-3 min-w-0">
              <h2 className="font-mono text-lg">
                {w.name}.{table.name}
              </h2>
              <p className="text-sm text-ink2">
                {table.description} Grain: <span className="font-mono">{table.grain.join(", ")}</span>.
              </p>
              <Columns table={table} />
              {w.metrics.filter((m) => m.table === table.name).length > 0 && (
                <div>
                  <h3 className="font-bold mt-4 mb-1">Metrics on this table</h3>
                  <ul className="text-sm space-y-1">
                    {w.metrics
                      .filter((m) => m.table === table.name)
                      .map((m, i) => (
                        <li key={i}>
                          <span className="font-mono">{m.name}</span> {m.definition}
                          <code className="block font-mono text-xs text-ink2">{m.sql}</code>
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {tab === "manifest" && <ManifestSearch warehouse={wh} />}
      {tab === "synonyms" && (
        <table className="dense max-w-[720px]" data-testid="synonyms">
          <thead>
            <tr>
              <th>A person says</th>
              <th>The catalog reads</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.synonyms).map(([k, vals]) => (
              <tr key={k}>
                <td>{k}</td>
                <td className="font-mono text-xs">{vals.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {tab === "quarantine" && (
        <div className="space-y-3">
          <table className="dense max-w-[560px]" data-testid="quarantine-counts">
            <tbody>
              {Object.entries(data.quarantine.counts[wh] ?? {}).map(([rule, n]) => (
                <tr key={rule}>
                  <td>{rule}</td>
                  <td className="num">{n}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-sm text-ink2 measure">A column without a definition cited to the build&apos;s own documents is named here instead of getting one I made up.</p>
          <table className="dense">
            <tbody>
              {data.quarantine.rows
                .filter((r) => r.warehouse === wh)
                .slice(0, 200)
                .map((r, i) => (
                  <tr key={i}>
                    <td className="font-mono text-xs">{r.subject}</td>
                    <td>{r.rule}</td>
                    <td className="text-ink2">{r.detail}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === "lock" && (
        <table className="dense" data-testid="lock">
          <thead>
            <tr>
              <th>File</th>
              <th>SHA-256</th>
            </tr>
          </thead>
          <tbody>
            {w.lock.map((f) => (
              <tr key={f.path}>
                <td className="font-mono text-xs">{f.path}</td>
                <td className="font-mono text-xs break-all">{f.sha256}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
