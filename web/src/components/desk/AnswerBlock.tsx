"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type { Answer, Claim } from "@/lib/types";

export function chipStatus(answer: Answer, claim: Claim): { word: string; icon: string; tone: string } {
  if (claim.verdict !== "agree") return { word: "refused", icon: "✕", tone: "critical" };
  if (answer.verdict === "repaired") return { word: "repaired", icon: "▲", tone: "warning" };
  return { word: "verified", icon: "✓", tone: "warehouse" };
}

const TONE: Record<string, string> = {
  warehouse: "border-warehouse text-warehouse bg-warehouse/10",
  warning: "border-warning text-warning bg-warning/10",
  critical: "border-critical text-critical bg-critical/10",
};

/** The answer, with a chip on every number the gate checked. */
export function AnswerBlock({ answer, recorded, onClaim }: { answer: Answer; recorded: boolean; onClaim: (a: Answer, c: Claim) => void }) {
  const parts: ReactNode[] = [];
  const claims = answer.claims.filter((c) => c.span).sort((a, b) => (a.span?.[0] ?? 0) - (b.span?.[0] ?? 0));
  let at = 0;
  claims.forEach((c, i) => {
    const [start, end] = c.span as [number, number];
    if (start < at) return;
    parts.push(answer.text.slice(at, start));
    const s = chipStatus(answer, c);
    parts.push(
      <button
        key={i}
        type="button"
        onClick={() => onClaim(answer, c)}
        data-testid="chip"
        data-verdict={s.word}
        aria-label={`${answer.text.slice(start, end)}, ${s.word}. Open the evidence.`}
        className={`inline-flex items-baseline gap-0.5 px-1 mx-0.5 rounded border num text-[0.95em] font-bold ${TONE[s.tone]}`}
      >
        {answer.text.slice(start, end)}
        <span aria-hidden="true" className="text-[0.7em]">
          {s.icon}
        </span>
      </button>,
    );
    at = end;
  });
  parts.push(answer.text.slice(at));
  const floor = answer.provider === "floor";
  return (
    <div className={`border-l-2 pl-3 space-y-2 ${answer.verdict === "refused" ? "border-critical" : "border-model"}`} data-testid="answer" data-verdict={answer.verdict}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="uppercase tracking-wide font-bold text-model">readback</span>
        {floor ? (
          <span className="px-1.5 py-0.5 rounded border border-control text-ink2 font-mono" data-testid="no-model">
            no model · the floor
          </span>
        ) : (
          <span className="px-1.5 py-0.5 rounded border border-model text-model font-mono" data-testid="model-badge">
            {answer.provider} · {answer.model}
          </span>
        )}
        {recorded && (
          <span className="px-1.5 py-0.5 rounded border border-warning text-warning font-mono" data-testid="recorded-badge">
            ▲ recorded
          </span>
        )}
        <span className={`font-mono ${answer.verdict === "refused" ? "text-critical" : answer.verdict === "repaired" ? "text-warning" : "text-good"}`}>
          {answer.verdict === "refused" ? "✕ refused" : answer.verdict === "repaired" ? "▲ repaired" : "✓ verified"}
        </span>
      </div>
      <p className="whitespace-pre-wrap measure">{parts}</p>
      {answer.refusal_reason && <p className="text-sm text-ink2">{answer.refusal_reason}</p>}
      <p className="text-xs text-ink2 font-mono">
        {answer.tool_calls} tool calls · {answer.model_calls} model calls · {Math.round(answer.latency_ms)} ms
        {answer.trace_id && (
          <>
            {" · "}
            <Link prefetch={false} className="underline" href={`/traces/?trace=${answer.trace_id}`} data-testid="trace-link">
              trace {answer.trace_id.slice(0, 8)}
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
