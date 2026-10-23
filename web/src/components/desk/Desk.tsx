"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { apiSource, ask, recordedSession, resume, type Source } from "@/lib/api";
import type { Answer, ChatEvent, Claim, Health } from "@/lib/types";

import { AnswerBlock } from "./AnswerBlock";
import { Evidence } from "./Evidence";
import { ToolCard } from "./ToolCard";

interface Turn {
  key: number;
  question: string;
  events: ChatEvent[];
  busy: boolean;
}

function SourceLine({ source, health }: { source: Source | null; health: Health | null }) {
  if (!source)
    return (
      <p className="text-sm text-ink2" data-testid="source" data-source="probing">
        Waking the API. A cold start takes a few seconds.
      </p>
    );
  if (source === "live")
    return (
      <p className="text-sm text-ink2" data-testid="source" data-source="live">
        <span className="text-good" aria-hidden="true">
          ●
        </span>{" "}
        Live. The router would pick <span className="font-mono text-ink">{health?.provider}</span> now ({health?.provider_reason}).
      </p>
    );
  return (
    <p className="text-sm text-ink2" data-testid="source" data-source="recorded">
      <span className="text-warning" aria-hidden="true">
        ▲
      </span>{" "}
      <strong className="text-ink">Recorded session.</strong> The API did not answer two probes, so the desk replays a recording of
      the floor answering the questions below. It says so on every turn.
    </p>
  );
}

function Classified({ e }: { e: Extract<ChatEvent, { event: "classified" }> }) {
  return (
    <p className="font-mono text-xs text-ink2" data-testid="classified">
      <span className="text-model">classify</span> {e.family} <span className="opacity-70">by {e.rule}</span>
      {Object.keys(e.redactions ?? {}).length > 0 && <span className="text-warning"> · redacted {Object.keys(e.redactions).join(", ")}</span>}
    </p>
  );
}

function GateLine({ e }: { e: Extract<ChatEvent, { event: "gate" }> }) {
  const agree = e.claims.filter((c) => c.verdict === "agree").length;
  return (
    <p className="font-mono text-xs" data-testid="gate">
      <span className="text-person">gate</span>{" "}
      <span className={e.passed ? "text-good" : "text-critical"}>{e.passed ? "✓ passed" : "✕ held"}</span>{" "}
      <span className="text-ink2">
        {agree} of {e.claims.length} numbers read back, {e.unsupported} unsupported
      </span>
    </p>
  );
}

function Interrupt({ e, onChoose, chosen }: { e: Extract<ChatEvent, { event: "interrupt" }>; onChoose: (c: string) => void; chosen: string | null }) {
  return (
    <div className="border-l-2 border-person pl-3 py-1 space-y-2" data-testid="interrupt">
      <p className="text-sm">
        <span className="text-person font-bold">One question back.</span> {e.name} names more than one {e.kind}. Which one?
      </p>
      <div className="flex flex-wrap gap-2">
        {e.candidates.map((c) => (
          <button
            key={c}
            type="button"
            disabled={chosen !== null}
            onClick={() => onChoose(c)}
            aria-pressed={chosen === c}
            className={`text-sm px-3 py-1.5 rounded border ${chosen === c ? "border-person bg-person/15 text-ink" : "border-hairline hover:border-person"} disabled:opacity-60`}
          >
            {c}
          </button>
        ))}
      </div>
    </div>
  );
}

function TurnView({ turn, source, onChoose, onClaim }: { turn: Turn; source: Source | null; onChoose: (thread: string, c: string) => void; onClaim: (a: Answer, c: Claim) => void }) {
  const [chosen, setChosen] = useState<string | null>(null);
  return (
    <li className="space-y-3" data-testid="turn">
      <div className="border-l-2 border-person pl-3">
        <p className="text-xs uppercase tracking-wide text-person font-bold">You</p>
        <p>{turn.question}</p>
      </div>
      <div className="space-y-2 pl-3">
        {turn.events.map((e, i) => {
          switch (e.event) {
            case "classified":
              return <Classified key={i} e={e} />;
            case "tool":
              return <ToolCard key={i} e={e} />;
            case "gate":
              return <GateLine key={i} e={e} />;
            case "interrupt":
              return (
                <Interrupt
                  key={i}
                  e={e}
                  chosen={chosen}
                  onChoose={(c) => {
                    setChosen(c);
                    onChoose(e.thread_id, c);
                  }}
                />
              );
            case "answer":
              return <AnswerBlock key={i} answer={{ ...e.answer, trace_id: e.answer.trace_id ?? e.trace_id }} recorded={source === "recorded"} onClaim={onClaim} />;
            case "error":
              return (
                <p key={i} className="text-sm border-l-2 border-critical pl-3" role="alert" data-testid="turn-error">
                  <span className="text-critical font-bold">✕ </span>
                  {e.message}
                </p>
              );
            default:
              return null;
          }
        })}
        {turn.busy && (
          <p className="text-xs text-ink2 font-mono" aria-live="polite">
            working…
          </p>
        )}
      </div>
    </li>
  );
}

export function Desk() {
  const [source, setSource] = useState<Source | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [queue, setQueue] = useState<string[]>([]);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const [evidence, setEvidence] = useState<{ answer: Answer; claim: Claim } | null>(null);
  const counter = useRef(0);
  const busy = turns.some((t) => t.busy);

  useEffect(() => {
    void apiSource().then((r) => {
      setSource(r.source);
      setHealth(r.health);
    });
    void recordedSession().then((s) => setQueue(s.turns.map((t) => t.question)));
  }, []);

  const push = useCallback((key: number, e: ChatEvent) => {
    setTurns((all) => all.map((t) => (t.key === key ? { ...t, events: [...t.events, e], busy: e.event === "done" || e.event === "error" ? false : t.busy } : t)));
  }, []);

  const finish = useCallback((key: number) => setTurns((all) => all.map((t) => (t.key === key ? { ...t, busy: false } : t))), []);

  const submit = useCallback(
    async (question: string) => {
      const q = question.trim();
      if (!q || busy) return;
      const key = ++counter.current;
      setTurns((all) => [...all, { key, question: q, events: [], busy: true }]);
      setText("");
      await ask(q, null, (e) => push(key, e));
      finish(key);
    },
    [busy, push, finish],
  );

  const choose = useCallback(
    async (thread: string, choice: string) => {
      const key = turns.find((t) => t.events.some((e) => "thread_id" in e && e.thread_id === thread))?.key;
      if (key === undefined) return;
      setTurns((all) => all.map((t) => (t.key === key ? { ...t, busy: true } : t)));
      await resume(thread, choice, (e) => push(key, e));
      finish(key);
    },
    [turns, push, finish],
  );

  return (
    <div className="desk grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
      <section aria-label="The transcript" className="space-y-6 min-w-0">
        <header className="space-y-2">
          <h1 className="display text-4xl sm:text-5xl font-extrabold leading-[1.05]">Ask the warehouse. Every number is read back.</h1>
          <p className="measure text-ink2">
            Housing from doorstep, flights from turnaround, a fictional bank from ledger. The agent finds the table, writes the SQL, and a
            gate made of plain code re-runs every number before the answer leaves. Tap a number to see its evidence.
          </p>
          <SourceLine source={source} health={health} />
        </header>

        <form
          className="flex gap-2"
          onSubmit={(ev) => {
            ev.preventDefault();
            void submit(text);
          }}
        >
          <label htmlFor="question" className="sr-only">
            Your question
          </label>
          <input
            id="question"
            data-testid="question"
            value={text}
            onChange={(ev) => setText(ev.target.value)}
            placeholder="What was the on time rate for Spirit in 2018?"
            className="flex-1 min-w-0 bg-raised border border-hairline rounded px-3 py-2 focus:border-person"
            autoComplete="off"
          />
          <button type="submit" disabled={busy || !text.trim()} className="px-4 py-2 rounded bg-person text-surface font-bold disabled:opacity-50" data-testid="ask">
            Ask
          </button>
        </form>

        <div>
          <p className="text-xs text-ink2 mb-2">{source === "recorded" ? "Recorded questions" : "Try one"}</p>
          <ul className="flex flex-wrap gap-2" data-testid="chips">
            {queue.map((q) => (
              <li key={q}>
                <button type="button" disabled={busy} onClick={() => void submit(q)} className="text-left text-sm px-3 py-1.5 rounded-full border border-hairline hover:border-person disabled:opacity-50">
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <ol className="space-y-8" data-testid="transcript" aria-live="polite">
          {turns.map((t) => (
            <TurnView key={t.key} turn={t} source={source} onChoose={(th, c) => void choose(th, c)} onClaim={(answer, claim) => setEvidence({ answer, claim })} />
          ))}
        </ol>
      </section>
      <Evidence selected={evidence} onClose={() => setEvidence(null)} />
      <p className="lg:col-span-2 text-xs text-ink2">
        Read how the gate works in the <Link prefetch={false} className="underline" href="/playbook/">playbook</Link>, or how often it is right on the{" "}
        <Link prefetch={false} className="underline" href="/evals/">scorecard</Link>.
      </p>
    </div>
  );
}
