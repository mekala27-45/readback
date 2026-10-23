// The shapes the API streams and the pages read. They mirror packages/core/answer.py and the
// events of packages/agent/run.py; the recorded session is the same events, saved.

export interface Claim {
  value: number;
  unit: string;
  display: string;
  warehouse: string | null;
  result_id: string | null;
  column: string | null;
  row: number;
  evidence_unit: string | null;
  manifest_key: string | null;
  catalog_key: string | null;
  definition_id: string | null;
  sql: string | null;
  span: [number, number] | null;
  verdict: string;
  evidence: number | null;
  tolerance: number | null;
  reason: string;
}

export interface Answer {
  id: string | null;
  question: string;
  family: string;
  text: string;
  claims: Claim[];
  warehouses: string[];
  verdict: "verified" | "repaired" | "refused";
  refusal_reason: string | null;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  tool_calls: number;
  model_calls: number;
  trace_id?: string;
  gate?: { tokens: number; caught: string[]; first_draft: string | null; unsupported_before: number; unsupported_after: number };
}

export interface Preview {
  columns: { name: string; type: string }[];
  rows: unknown[][];
  row_count: number;
}

interface Meta {
  thread_id: string;
  trace_id: string;
  redactions: Record<string, number>;
}

export type ChatEvent =
  | (Meta & { event: "classified"; family: string; rule: string; provider: string; reason: string })
  | (Meta & { event: "tool"; id: string; tool: string; ok: boolean; args: Record<string, unknown>; result_id: string | null; error: string | null; preview: Preview | null })
  | (Meta & { event: "gate"; passed: boolean; unsupported: number; claims: { index: number; verdict: string; reason: string }[] })
  | (Meta & { event: "interrupt"; kind: string; name: string; candidates: string[] })
  | (Meta & { event: "answer"; answer: Answer; answer_id?: string })
  | { event: "done"; statement: string }
  | { event: "error"; message: string };

export interface RecordedTurn {
  id: string;
  question: string;
  events: ChatEvent[];
  choice?: string;
  resume?: ChatEvent[];
}

export interface Span {
  span_id: string;
  trace_id: string;
  parent_id: string | null;
  name: string;
  start_ns: number;
  end_ns: number;
  attributes: Record<string, unknown>;
}

export interface Health {
  status: string;
  version: string;
  protocol_revision: string;
  provider: string;
  provider_reason: string;
  budgets: { provider: string; model: string; eligible: boolean; reason: string; used_today: number; daily_budget: number | null }[];
  statement: string;
}

export interface RecordedSession {
  recorded: boolean;
  recorded_at: string;
  provider: string;
  health: Health;
  turns: RecordedTurn[];
  traces: Record<string, Span[]>;
}
