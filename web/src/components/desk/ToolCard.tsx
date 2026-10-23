"use client";

import { useState } from "react";

import type { ChatEvent } from "@/lib/types";

type ToolEvent = Extract<ChatEvent, { event: "tool" }>;

function summary(e: ToolEvent): string {
  const a = e.args;
  if (e.tool === "run_sql") return String(a.warehouse ?? "");
  if (e.tool === "readback") {
    const c = (a.claim ?? {}) as { display?: string };
    return c.display ? `claim ${c.display}` : "a claim";
  }
  if (e.tool === "search_catalog" || e.tool === "lookup") return String(a.query ?? a.name ?? "");
  if (e.tool === "describe") return `${String(a.warehouse ?? "")}.${String(a.table ?? "")}`;
  return Object.values(a).filter((x) => typeof x === "string").join(" ");
}

/** A tool call as a card: a monospaced header, and on demand the SQL, the schema and the rows. */
export function ToolCard({ e }: { e: ToolEvent }) {
  const [open, setOpen] = useState(false);
  const sql = typeof e.args.sql === "string" ? e.args.sql : null;
  const expandable = Boolean(sql || e.preview || e.error);
  return (
    <div className="rounded border border-hairline bg-raised" data-testid="tool-card" data-tool={e.tool}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={!expandable}
        aria-expanded={expandable ? open : undefined}
        className="w-full flex items-center gap-3 px-3 py-1.5 font-mono text-xs text-left"
      >
        <span className={e.ok ? "text-warehouse" : "text-critical"}>{e.ok ? "◆" : "✕"}</span>
        <span className="text-ink font-bold">{e.tool}</span>
        <span className="text-ink2 truncate flex-1">{summary(e)}</span>
        <span className="text-ink2">{e.id}</span>
        {expandable && <span className="text-ink2">{open ? "−" : "+"}</span>}
      </button>
      {open && (
        <div className="border-t border-hairline px-3 py-2 space-y-2 text-xs" data-testid="tool-detail">
          {e.error && <p className="text-critical">{e.error}</p>}
          {sql && (
            <pre className="font-mono whitespace-pre-wrap break-words text-ink" data-testid="tool-sql">
              {sql}
            </pre>
          )}
          {e.preview && (
            <div className="overflow-x-auto">
              <table className="dense" data-testid="tool-rows">
                <thead>
                  <tr>
                    {e.preview.columns.map((c) => (
                      <th key={c.name} title={c.type}>
                        {c.name} <span className="font-normal opacity-70">{c.type}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {e.preview.rows.map((r, i) => (
                    <tr key={i}>
                      {r.map((cell, j) => (
                        <td key={j} className={typeof cell === "number" ? "num" : ""}>
                          {cell === null ? "null" : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-ink2 mt-1">
                {e.preview.row_count} row{e.preview.row_count === 1 ? "" : "s"}
                {e.preview.row_count > e.preview.rows.length ? `, the first ${e.preview.rows.length} shown` : ""}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
