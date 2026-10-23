"use client";

import { useEffect, useRef } from "react";

import { evidence, sqlOfHandle } from "@/lib/format";
import type { Answer, Claim } from "@/lib/types";

import { chipStatus } from "./AnswerBlock";

/** The evidence for one number: a side panel on a wide screen, a sheet from the bottom on a phone. */
export function Evidence({ selected, onClose }: { selected: { answer: Answer; claim: Claim } | null; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (selected) close.current?.focus();
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [selected, onClose]);

  if (!selected)
    return (
      <aside className="hidden lg:block text-sm text-ink2 border-l border-hairline pl-6 self-start sticky top-24" aria-label="Evidence">
        <p className="display text-lg text-ink font-bold mb-1">Evidence</p>
        <p>Tap a number in an answer. Its query, the value the warehouse returned, the tolerance and the verdict show here.</p>
      </aside>
    );
  const { answer, claim } = selected;
  const s = chipStatus(answer, claim);
  const sql = claim.sql ?? sqlOfHandle(claim.result_id);
  const rows: [string, string][] = [
    ["Said", claim.display],
    ["Read back", evidence(claim.evidence, claim.unit)],
    ["Tolerance", claim.tolerance === null ? "none" : `${claim.tolerance} ${claim.unit}`],
    ["Warehouse", claim.warehouse ?? "none"],
  ];
  if (claim.manifest_key) rows.push(["Manifest key", claim.manifest_key]);
  if (claim.catalog_key) rows.push(["Catalog key", claim.catalog_key]);
  if (claim.definition_id) rows.push(["Definition", claim.definition_id]);
  return (
    <aside
      aria-label="Evidence"
      data-testid="evidence"
      className="fixed inset-x-0 bottom-0 z-40 max-h-[70vh] overflow-y-auto bg-raised border-t border-hairline p-4 shadow-2xl lg:static lg:z-auto lg:max-h-none lg:bg-transparent lg:border-t-0 lg:border-l lg:pl-6 lg:p-0 lg:shadow-none lg:self-start lg:sticky lg:top-24"
    >
      <div className="flex items-center justify-between mb-3">
        <p className="display text-lg font-bold">Evidence</p>
        <button ref={close} type="button" onClick={onClose} className="text-xs px-2 py-1 border border-hairline rounded">
          Close
        </button>
      </div>
      <p className={`font-mono text-sm mb-3 ${s.tone === "warehouse" ? "text-warehouse" : s.tone === "warning" ? "text-warning" : "text-critical"}`} data-testid="evidence-verdict">
        {s.icon} {s.word}
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm mb-3">
        {rows.map(([k, val]) => (
          <div key={k} className="contents">
            <dt className="text-ink2">{k}</dt>
            <dd className="font-mono break-words">{val}</dd>
          </div>
        ))}
      </dl>
      <p className="text-sm text-ink2 mb-3">{claim.reason}</p>
      {sql && (
        <>
          <p className="text-xs text-ink2 mb-1">The query it was read back against</p>
          <pre className="font-mono text-xs whitespace-pre-wrap break-words bg-surface border border-hairline rounded p-2" data-testid="evidence-sql">
            {sql}
          </pre>
        </>
      )}
    </aside>
  );
}
