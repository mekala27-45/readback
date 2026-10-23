import type { Metadata } from "next";

import { Figure } from "@/components/Figure";
import { site, v } from "@/lib/data";
import registration from "../../../public/data/registration.json";
import session from "../../../public/data/recorded_session.json";
import scorecard from "../../../public/data/scorecard.json";

export const metadata: Metadata = { title: "Scorecard" };

interface Row {
  provider: string;
  model: string;
  graded: number;
  total: number;
  passed: number;
  accuracy: number | null;
  low: number | null;
  high: number | null;
  readback_rate: number | null;
  claims: number;
  repair_rate: number | null;
  refusal_accuracy: number | null;
  median_tool_calls: number | null;
  p50_ms: number | null;
  p99_ms: number | null;
  live_share: number;
  cassette_dates: string[];
  families: Record<string, { n: number; passed: number; accuracy: number | null; low: number; high: number }>;
}

const pct = (x: number | null | undefined, d = 1) => (x === null || x === undefined ? "none" : `${(x * 100).toFixed(d)}%`);
const card = scorecard as unknown as {
  test: { rows: Row[] };
  dev: { rows: Row[] };
  floor_note: string;
  default_provider: string;
  default_reason: string;
  providers_not_run: string[];
  prompt_hash: string | null;
  catches: { provider: string; id: string; caught: string[]; draft: string; shipped: string }[];
  comparisons: { provider: string; difference: number; low: number; high: number; p: number; significant_bh: boolean }[];
  interior: Record<string, unknown> & { ranking: Record<string, string>; not_measured: Record<string, string> };
  redteam: Record<string, { graded: number; passed: number; cases: { id: string; kind: string; passed: boolean; verdict: string; note?: string }[] }>;
  judge: { run: boolean; reason: string };
};
const PROVIDER_COLOR: Record<string, string> = {
  floor: "var(--control)",
  gemini: "var(--gemini)",
  groq: "var(--groq)",
  openrouter: "var(--openrouter)",
  sambanova: "var(--sambanova)",
  ollama: "var(--ollama)",
};

function DotPlot({ rows, notRun }: { rows: Row[]; notRun: string[] }) {
  const W = 640;
  const left = 120;
  const right = 24;
  const rowH = 34;
  const x = (p: number) => left + p * (W - left - right);
  const ticks = [0, 0.25, 0.5, 0.75, 1];
  return (
    <svg viewBox={`0 0 ${W} ${(rows.length + notRun.length) * rowH + 36}`} className="w-full max-w-[720px]" role="img" aria-label="Accuracy on the test split with its Wilson interval, one row per provider" data-testid="dot-plot">
      <defs>
        <pattern id="hatch" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="5" height="5" fill="var(--control)" />
          <line x1="0" y1="0" x2="0" y2="5" stroke="var(--surface)" strokeWidth="2" />
        </pattern>
      </defs>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={6} y2={(rows.length + notRun.length) * rowH + 10} stroke="var(--hairline)" />
          <text x={x(t)} y={(rows.length + notRun.length) * rowH + 28} textAnchor="middle" fontSize="11" fill="var(--ink2)">
            {t * 100}%
          </text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y = 10 + i * rowH + rowH / 2;
        const color = PROVIDER_COLOR[r.provider] ?? "var(--control)";
        return (
          <g key={r.provider} data-testid="dot-row" data-provider={r.provider}>
            <title>{`${r.provider}: ${pct(r.accuracy)} (${pct(r.low)} to ${pct(r.high)}), ${r.passed} of ${r.graded}`}</title>
            <text x={0} y={y + 4} fontSize="13" fill="var(--ink)">
              {r.provider}
            </text>
            {r.low !== null && r.high !== null && <rect x={x(r.low)} y={y - 5} width={Math.max(x(r.high) - x(r.low), 2)} height={10} rx={2} fill={r.provider === "floor" ? "url(#hatch)" : color} opacity={0.55} />}
            {r.accuracy !== null && <circle cx={x(r.accuracy)} cy={y} r={6} fill={color} stroke="var(--surface)" strokeWidth={2} />}
            {r.accuracy !== null && (
              <text x={x(r.low ?? r.accuracy) - 8} y={y + 4} fontSize="12" fill="var(--ink)" textAnchor="end">
                {pct(r.accuracy)}
              </text>
            )}
          </g>
        );
      })}
      {notRun.map((name, j) => {
        const y = 10 + (rows.length + j) * rowH + rowH / 2;
        return (
          <g key={name} data-testid="dot-row" data-provider={name} data-run="no">
            <text x={0} y={y + 4} fontSize="13" fill="var(--ink2)">
              {name}
            </text>
            <line x1={x(0)} x2={x(1)} y1={y} y2={y} stroke={PROVIDER_COLOR[name]} strokeDasharray="2 6" opacity={0.7} />
            <text x={x(0) + 6} y={y - 6} fontSize="10" fill="var(--ink2)">
              not run yet
            </text>
          </g>
        );
      })}
    </svg>
  );
}

function FamilyTable({ rows, testid }: { rows: Row[]; testid: string }) {
  const families = Object.keys(rows[0]?.families ?? {});
  return (
    <div className="overflow-x-auto">
      <table className="dense" data-testid={testid}>
        <thead>
          <tr>
            <th>Provider</th>
            <th>Model</th>
            {families.map((f) => (
              <th key={f} className="num">
                {f.replace("_", " ")}
              </th>
            ))}
            <th className="num">All</th>
            <th className="num">Interval</th>
            <th className="num">Live share</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.provider}>
              <td>{r.provider}</td>
              <td className="font-mono">{r.model}</td>
              {families.map((f) => {
                const c = r.families[f];
                return (
                  <td key={f} className="num" title={c ? `${c.passed} of ${c.n}, interval ${pct(c.low)} to ${pct(c.high)}` : ""}>
                    {c ? `${c.passed}/${c.n}` : "none"}
                  </td>
                );
              })}
              <td className="num">{pct(r.accuracy)}</td>
              <td className="num">
                {pct(r.low)} to {pct(r.high)}
              </td>
              <td className="num">{pct(r.live_share, 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Page() {
  const test = card.test.rows;
  const dev = card.dev.rows;
  const floor = test.find((r) => r.provider === "floor");
  const budgets = session.health.budgets;
  return (
    <div className="space-y-12">
      <header className="space-y-3">
        <h1 className="display text-4xl sm:text-5xl font-extrabold leading-[1.05] measure">
          The floor answers {v("eval.floor.accuracy")} of the test split, and every number it ships reads back.
        </h1>
        <p className="measure text-ink2">
          {v("golden.test")} test questions whose answers were known before the agent existed, graded in code. The default live provider
          is <strong className="text-ink">{card.default_provider}</strong>, chosen on the development split: {card.default_reason}.{" "}
          {v("eval.providers_not_run")} have not run yet, and a row never extrapolates from a partial run.
        </p>
      </header>

      <Figure
        title={`Floor accuracy ${v("eval.floor.accuracy")}, interval ${v("eval.floor.low")} to ${v("eval.floor.high")}`}
        subtitle="Accuracy on the test split by provider, with the Wilson interval as a bar. The floor row is first and hatched."
        source="results/evals/scorecard.json, test.rows"
        table={<FamilyTable rows={test} testid="test-table" />}
      >
        <DotPlot rows={test} notRun={card.providers_not_run} />
        <p className="text-sm text-ink2 measure mt-2">{card.floor_note}</p>
      </Figure>

      <section className="space-y-3">
        <h2 className="display text-2xl font-bold">By family, test split</h2>
        <FamilyTable rows={test} testid="family-table" />
        {floor && (
          <p className="text-sm text-ink2 measure">
            The floor read back {pct(floor.readback_rate)} of its {floor.claims} shipped numbers, refused correctly on {pct(floor.refusal_accuracy)} of the
            refusal questions, and made a median of {floor.median_tool_calls} tool calls a question, {floor.p50_ms} ms at the median.
          </p>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="display text-2xl font-bold">Development split, for the gap</h2>
        <FamilyTable rows={dev} testid="dev-table" />
        <p className="text-sm text-ink2 measure">
          Floor on development: {v("eval.floor.dev_accuracy")}. The gap to the test split is what tuning on development bought.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="display text-2xl font-bold">Differences from the floor</h2>
        {card.comparisons.length === 0 ? (
          <p className="text-sm text-ink2">No model has a test run yet, so there is no difference to test. Benjamini-Hochberg runs across them when there are.</p>
        ) : (
          <table className="dense" data-testid="comparisons">
            <thead>
              <tr>
                <th>Provider</th>
                <th className="num">Difference</th>
                <th className="num">Interval</th>
                <th className="num">p</th>
                <th>Significant after BH</th>
              </tr>
            </thead>
            <tbody>
              {card.comparisons.map((c) => (
                <tr key={c.provider}>
                  <td>{c.provider}</td>
                  <td className="num">{pct(c.difference)}</td>
                  <td className="num">
                    {pct(c.low)} to {pct(c.high)}
                  </td>
                  <td className="num">{c.p.toFixed(3)}</td>
                  <td>{c.significant_bh ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="display text-2xl font-bold">The red team</h2>
        <p className="text-sm text-ink2 measure">
          {v("redteam.floor.passed")} of {v("redteam.floor.graded")} injection cases passed on the floor. A pass is a refusal, or an answer that ignores the
          planted instruction and still reads back.
        </p>
        <div className="overflow-x-auto">
          <table className="dense" data-testid="redteam">
            <thead>
              <tr>
                {site.tables["redteam.cases"]?.columns.map((c) => <th key={c}>{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {site.tables["redteam.cases"]?.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j} className={c === "fail" ? "text-critical" : c === "pass" ? "text-good" : ""}>
                      {c === "pass" ? "✓ pass" : c === "fail" ? "✕ fail" : c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="display text-2xl font-bold">What the gate caught</h2>
        <p className="text-sm text-ink2 measure">
          {v("eval.catches")} catches on the test split. The floor writes its numbers from the rows it read, so it has nothing for the gate to catch;
          a model&apos;s catches appear here with the first draft beside what shipped.
        </p>
        {card.catches.length > 0 && (
          <table className="dense">
            <tbody>
              {card.catches.map((c) => (
                <tr key={`${c.provider}-${c.id}`}>
                  <td>{c.provider}</td>
                  <td className="font-mono">{c.id}</td>
                  <td>{c.caught.join(", ")}</td>
                  <td>{c.draft}</td>
                  <td>{c.shipped}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="display text-2xl font-bold">Interior tests</h2>
        <p className="text-sm text-ink2 measure">
          Each setting moved one step either way. Ranking of providers: tolerance {card.interior.ranking.tolerance}, tool call ceiling {card.interior.ranking.ceiling},
          development split size {card.interior.ranking.split_size}.
        </p>
        <table className="dense max-w-[640px]" data-testid="interior">
          <thead>
            <tr>
              <th>Setting</th>
              <th>Values</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries((card.interior.floor ?? {}) as Record<string, Record<string, number>>).map(([k, vals]) => (
              <tr key={k}>
                <td>floor, {k}</td>
                <td className="font-mono">
                  {Object.entries(vals)
                    .map(([a, b]) => `${a}: ${pct(b)}`)
                    .join(" · ")}
                </td>
              </tr>
            ))}
            {Object.entries(card.interior.not_measured).map(([k, why]) => (
              <tr key={k}>
                <td>{k}</td>
                <td className="text-ink2">{why}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="space-y-3">
        <h2 className="display text-2xl font-bold">Budgets, cassettes and hashes</h2>
        <table className="dense max-w-[720px]" data-testid="budgets">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Model</th>
              <th className="num">Used today</th>
              <th className="num">Cap</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {budgets.map((b) => (
              <tr key={b.provider}>
                <td>{b.provider}</td>
                <td className="font-mono">{b.model}</td>
                <td className="num">{b.used_today}</td>
                <td className="num">{b.daily_budget ?? "none"}</td>
                <td className={b.eligible ? "text-good" : "text-ink2"}>{b.eligible ? "✓ eligible" : b.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-ink2">Budgets as the API reported them when the session was recorded, {session.recorded_at}; the desk shows the live pick.</p>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm font-mono max-w-[720px]">
          <dt className="text-ink2">cassette dates</dt>
          <dd>{test.flatMap((r) => r.cassette_dates).join(", ") || "none: no model has recorded yet"}</dd>
          <dt className="text-ink2">prompt registry hash</dt>
          <dd className="break-all">{card.prompt_hash ?? "none"}</dd>
          <dt className="text-ink2">pre-registered plan hash</dt>
          <dd className="break-all">{registration.plan_hash}</dd>
          <dt className="text-ink2">registered at</dt>
          <dd>{registration.registered_at}</dd>
          <dt className="text-ink2">secondary judge</dt>
          <dd className="font-sans">{card.judge.reason}</dd>
        </dl>
      </section>
    </div>
  );
}
