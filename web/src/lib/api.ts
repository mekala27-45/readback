// The live API and its recorded stand in.
//
// The first call on a page probes /health with an eight second limit, twice, four seconds apart,
// because a Vercel function starts cold and its first answer can be a 503. If both probes fail, the
// desk answers from recorded_session.json for the rest of the visit and says so beside the box. A
// live turn that fails partway is not silently swapped for a recording: the desk shows the error.
import { API, loadJson } from "./site";
import type { ChatEvent, Health, RecordedSession, Span } from "./types";

export type Source = "live" | "recorded";

const PROBE_TIMEOUT_MS = 8000;
const PROBE_ATTEMPTS = 2;
const PROBE_PAUSE_MS = 4000;

let probe: Promise<{ source: Source; health: Health | null }> | null = null;

async function probeOnce(): Promise<Health | null> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);
  try {
    const r = await fetch(`${API}/health`, { signal: controller.signal, cache: "no-store" });
    if (!r.ok) return null;
    const body = (await r.json()) as Health;
    return body.status === "ok" ? body : null;
  } catch {
    return null;
  } finally {
    window.clearTimeout(timer);
  }
}

/** Whether this visit talks to the live API or to the recording. Probed twice, then fixed. */
export function apiSource(): Promise<{ source: Source; health: Health | null }> {
  probe ??= (async () => {
    if (!API) return { source: "recorded" as Source, health: null };
    for (let attempt = 1; attempt <= PROBE_ATTEMPTS; attempt += 1) {
      if (attempt > 1) await new Promise((r) => window.setTimeout(r, PROBE_PAUSE_MS));
      const health = await probeOnce();
      if (health) return { source: "live" as Source, health };
    }
    return { source: "recorded" as Source, health: null };
  })();
  return probe;
}

export function recordedSession(): Promise<RecordedSession> {
  return loadJson<RecordedSession>("recorded_session.json");
}

/** Read a server sent event stream into events, one callback per event. */
async function readStream(response: Response, onEvent: (e: ChatEvent) => void): Promise<void> {
  if (!response.body) throw new Error("the response has no body");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut = buffer.indexOf("\n\n");
    while (cut >= 0) {
      const block = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      const data = block
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5))
        .join("\n");
      const kind = block.split("\n").find((l) => l.startsWith("event:"))?.slice(6).trim();
      if (data) {
        const parsed = JSON.parse(data) as Record<string, unknown>;
        onEvent({ event: kind ?? parsed.event, ...parsed } as ChatEvent);
      }
      cut = buffer.indexOf("\n\n");
    }
  }
}

async function replay(events: ChatEvent[], onEvent: (e: ChatEvent) => void): Promise<void> {
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  for (const e of events) {
    if (e.event === "done") continue;
    if (!reduced) await new Promise((r) => window.setTimeout(r, e.event === "tool" ? 160 : 260));
    onEvent(e);
  }
  const s = await recordedSession();
  onEvent({ event: "done", statement: s.health.statement });
}

/** One turn: the question streamed through the live API, or replayed from the recording. */
export async function ask(question: string, threadId: string | null, onEvent: (e: ChatEvent) => void): Promise<Source> {
  const { source } = await apiSource();
  if (source === "live") {
    try {
      const r = await fetch(`${API}/v1/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, thread_id: threadId }),
      });
      if (!r.ok) {
        const body = (await r.json().catch(() => ({}))) as { error?: string };
        onEvent({ event: "error", message: body.error ?? `the API answered ${r.status}` });
        return source;
      }
      await readStream(r, onEvent);
    } catch (err) {
      onEvent({ event: "error", message: `the stream broke: ${(err as Error).message}` });
    }
    return source;
  }
  const s = await recordedSession();
  const turn = s.turns.find((t) => t.question.toLowerCase() === question.trim().toLowerCase());
  if (!turn) {
    onEvent({ event: "error", message: "The API is asleep, and the recording has no answer for that question. Pick one of the recorded questions below." });
    return source;
  }
  await replay(turn.events, onEvent);
  return source;
}

/** The choice for an interrupt, on the thread that asked. */
export async function resume(threadId: string, choice: string, onEvent: (e: ChatEvent) => void): Promise<void> {
  const { source } = await apiSource();
  if (source === "live") {
    try {
      const r = await fetch(`${API}/v1/chat/${threadId}/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ choice }),
      });
      if (!r.ok) {
        onEvent({ event: "error", message: `the API answered ${r.status}` });
        return;
      }
      await readStream(r, onEvent);
    } catch (err) {
      onEvent({ event: "error", message: `the stream broke: ${(err as Error).message}` });
    }
    return;
  }
  const s = await recordedSession();
  const turn = s.turns.find((t) => t.events.some((e) => "thread_id" in e && e.thread_id === threadId));
  const events = turn?.resume ?? [];
  if (!turn || turn.choice !== choice) {
    onEvent({ event: "error", message: `The recording continues this turn with ${turn?.choice ?? "the first candidate"} only; the live API takes either.` });
    if (!turn) return;
  }
  await replay(events, onEvent);
}

/** A turn's spans: from the recording when it has them, else from the live API. */
export async function traceSpans(traceId: string): Promise<{ spans: Span[]; from: string }> {
  const s = await recordedSession();
  if (s.traces[traceId]) return { spans: s.traces[traceId], from: "the recorded session" };
  const { source } = await apiSource();
  if (source !== "live") return { spans: [], from: "nowhere: the API is asleep and the recording does not hold this trace" };
  const r = await fetch(`${API}/v1/traces/${traceId}`, { cache: "no-store" });
  if (!r.ok) return { spans: [], from: `the live API, which answered ${r.status}` };
  const body = (await r.json()) as { spans: Span[] };
  return { spans: body.spans, from: "the live API" };
}
