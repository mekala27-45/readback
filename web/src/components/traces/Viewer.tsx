"use client";

import { useEffect, useMemo, useState } from "react";

import { traceSpans } from "@/lib/api";
import { ms } from "@/lib/format";
import { evalSpans } from "@/lib/parquet";
import { loadJson } from "@/lib/site";
import type { Span } from "@/lib/types";

interface EvalTurn {
  provider: string;
  id: string;
  question: string;
  family: string;
  split: string;
  verdict: string | null;
  passed: boolean | null;
  trace_id: string | null;
  text: string;
  claims: { display: string; verdict: string; evidence: number | null; unit: string }[];
}

function role(name: string): { color: string; label: string } {
  if (name.startsWith("chat")) return { color: "var(--model)", label: "model" };
  if (name.startsWith("execute_tool") || name.startsWith("tools/call")) return { color: "var(--warehouse)", label: "tool" };
  if (name.startsWith("gate") || name.includes("readback.gate")) return { color: "var(--person)", label: "gate" };
  return { color: "var(--control)", label: "other" };
}

function clean(attrs: Record<string, unknown>): [string, string][] {
  return Object.entries(attrs ?? {})
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => [k, typeof v === "object" ? JSON.stringify(v) : String(v)]);
}

function depthOf(spans: Span[]): Map<string, number> {
  const byId = new Map(spans.map((s) => [s.span_id, s]));
  const depth = new Map<string, number>();
  const get = (s: Span): number => {
    if (depth.has(s.span_id)) return depth.get(s.span_id) as number;
    const parent = s.parent_id ? byId.get(s.parent_id) : undefined;
    const d = parent ? get(parent) + 1 : 0;
    depth.set(s.span_id, d);
    return d;
  };
  spans.forEach(get);
  return depth;
}

function Waterfall({ spans }: { spans: Span[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const sorted = useMemo(() => [...spans].sort((a, b) => a.start_ns - b.start_ns), [spans]);
  const depth = useMemo(() => depthOf(spans), [spans]);
  if (!sorted.length) return null;
  const t0 = Math.min(...sorted.map((s) => s.start_ns));
  const t1 = Math.max(...sorted.map((s) => s.end_ns));
  const total = Math.max(t1 - t0, 1);
  return (
    <div className="space-y-1" data-testid="waterfall" role="list" aria-label="Spans in start order">
      <div className="flex justify-between text-xs text-ink2 font-mono pl-[38%]">
        <span>0</span>
        <span>{ms(total / 1e6)}</span>
      </div>
      {sorted.map((s) => {
        const r = role(s.name);
        const left = ((s.start_ns - t0) / total) * 100;
        const width = Math.max(((s.end_ns - s.start_ns) / total) * 100, 0.4);
        const attrs = clean(s.attributes);
        const tokensIn = s.attributes?.["gen_ai.usage.input_tokens"];
        const tokensOut = s.attributes?.["gen_ai.usage.output_tokens"];
        const isOpen = open === s.span_id;
        return (
          <div key={s.span_id} role="listitem" data-testid="span" data-role={r.label}>
            <button
              type="button"
              onClick={() => setOpen(isOpen ? null : s.span_id)}
              aria-expanded={isOpen}
              title={`${s.name}: ${ms((s.end_ns - s.start_ns) / 1e6)}`}
              className="w-full grid grid-cols-[38%_1fr] items-center gap-2 text-left hover:bg-raised rounded"
            >
              <span className="font-mono text-xs truncate" style={{ paddingLeft: `${(depth.get(s.span_id) ?? 0) * 10}px` }}>
                {s.name}
              </span>
              <span className="relative h-4 block">
                <span
                  className="absolute top-0.5 h-3 rounded-sm"
                  style={{
                    left: `${left}%`,
                    width: `${width}%`,
                    background: r.color,
                    backgroundImage: r.label === "other" ? "repeating-linear-gradient(45deg, transparent 0 3px, rgba(0,0,0,.25) 3px 5px)" : undefined,
                  }}
                />
                {r.label === "model" && tokensIn !== undefined && tokensIn !== null && (
                  <span className="absolute text-[10px] font-mono text-ink2" style={{ left: `calc(${left + width}% + 4px)` }}>
                    {String(tokensIn)} in · {String(tokensOut ?? 0)} out
                  </span>
                )}
              </span>
            </button>
            {isOpen && (
              <dl className="ml-4 my-1 grid grid-cols-[auto_1fr] gap-x-3 text-xs font-mono border-l border-hairline pl-3" data-testid="span-attributes">
                <dt className="text-ink2">duration</dt>
                <dd>{ms((s.end_ns - s.start_ns) / 1e6)}</dd>
                {attrs.map(([k, val]) => (
                  <div key={k} className="contents">
                    <dt className="text-ink2">{k}</dt>
                    <dd className="break-all">{val}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        );
      })}
      <p className="text-xs text-ink2 pt-2 flex flex-wrap gap-4">
        <span>
          <span className="inline-block w-3 h-2 mr-1 align-middle" style={{ background: "var(--model)" }} />
          model
        </span>
        <span>
          <span className="inline-block w-3 h-2 mr-1 align-middle" style={{ background: "var(--warehouse)" }} />
          tool
        </span>
        <span>
          <span className="inline-block w-3 h-2 mr-1 align-middle" style={{ background: "var(--person)" }} />
          gate
        </span>
        <span>
          <span className="inline-block w-3 h-2 mr-1 align-middle" style={{ background: "var(--control)" }} />
          other, hatched
        </span>
      </p>
    </div>
  );
}

export function Viewer() {
  const [turns, setTurns] = useState<EvalTurn[]>([]);
  const [all, setAll] = useState<Span[] | null>(null);
  const [traceId, setTraceId] = useState<string>("");
  const [pasted, setPasted] = useState("");
  const [spans, setSpans] = useState<Span[]>([]);
  const [from, setFrom] = useState("");
  const [filter, setFilter] = useState("");

  useEffect(() => {
    void loadJson<{ turns: EvalTurn[] }>("turns.json").then((t) => setTurns(t.turns.filter((x) => x.trace_id)));
    void evalSpans().then(setAll);
    const fromUrl = new URLSearchParams(window.location.search).get("trace");
    if (fromUrl) setTraceId(fromUrl);
  }, []);

  useEffect(() => {
    if (!traceId && turns.length && all) setTraceId(turns[0]?.trace_id ?? "");
  }, [turns, all, traceId]);

  useEffect(() => {
    if (!traceId || !all) return;
    const local = all.filter((s) => s.trace_id === traceId);
    if (local.length) {
      setSpans(local);
      setFrom("the eval run's trace parquet");
      return;
    }
    void traceSpans(traceId).then((r) => {
      setSpans(r.spans);
      setFrom(r.from);
    });
  }, [traceId, all]);

  const turn = turns.find((t) => t.trace_id === traceId);
  const shown = turns.filter((t) => !filter || `${t.id} ${t.question}`.toLowerCase().includes(filter.toLowerCase())).slice(0, 200);

  return (
    <div className="grid gap-8 lg:grid-cols-[320px_minmax(0,1fr)]">
      <section aria-label="Pick a turn" className="space-y-3 min-w-0">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (pasted.trim()) setTraceId(pasted.trim());
          }}
        >
          <label htmlFor="trace" className="sr-only">
            A trace id from the desk
          </label>
          <input id="trace" value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="Paste a trace id" className="flex-1 min-w-0 bg-raised border border-hairline rounded px-2 py-1 font-mono text-xs" />
          <button type="submit" className="text-xs px-2 border border-hairline rounded">
            Open
          </button>
        </form>
        <label htmlFor="filter" className="sr-only">
          Filter the eval turns
        </label>
        <input id="filter" value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Filter the eval turns" className="w-full bg-raised border border-hairline rounded px-2 py-1 text-sm" />
        <ul className="max-h-[60vh] overflow-y-auto space-y-1 text-sm" data-testid="turn-list">
          {!turns.length && <li className="skeleton h-40" />}
          {shown.map((t) => (
            <li key={`${t.provider}-${t.id}`}>
              <button
                type="button"
                onClick={() => setTraceId(t.trace_id ?? "")}
                aria-current={t.trace_id === traceId}
                className={`w-full text-left px-2 py-1 rounded ${t.trace_id === traceId ? "bg-raised border-l-2 border-person" : "hover:bg-raised"}`}
              >
                <span className="font-mono text-xs text-ink2">
                  {t.id} · {t.provider} · {t.split}
                </span>
                <span className={`ml-2 text-xs ${t.passed ? "text-good" : "text-critical"}`}>{t.passed ? "✓ passed" : "✕ missed"}</span>
                <span className="block truncate">{t.question}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
      <section aria-label="The waterfall" className="space-y-4 min-w-0">
        <header>
          <h1 className="display text-3xl font-extrabold">One turn, span by span</h1>
          <p className="text-sm text-ink2 font-mono break-all">
            trace {traceId || "none"} {from && `· from ${from}`}
          </p>
        </header>
        {turn && (
          <div className="text-sm space-y-1 border-l-2 border-model pl-3">
            <p className="text-ink2">{turn.question}</p>
            <p>{turn.text}</p>
            {turn.claims.length > 0 && (
              <p className="font-mono text-xs" data-testid="readback-verdicts">
                {turn.claims.map((c, i) => (
                  <span key={i} className={`mr-3 ${c.verdict === "agree" ? "text-warehouse" : "text-critical"}`}>
                    {c.verdict === "agree" ? "✓" : "✕"} {c.display}
                  </span>
                ))}
              </p>
            )}
          </div>
        )}
        {!all && <div className="skeleton h-64" aria-label="Loading the spans" />}
        {all && spans.length === 0 && traceId && <p className="text-sm text-ink2">No spans for this trace in {from || "any source"}.</p>}
        <Waterfall spans={spans} />
      </section>
    </div>
  );
}
