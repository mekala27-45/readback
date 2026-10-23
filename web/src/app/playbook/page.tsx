import { Pushback } from "@/components/Pushback";
import type { Metadata } from "next";

import { REPO } from "@/lib/site";
import data from "../../../public/data/playbook.json";

export const metadata: Metadata = { title: "Playbook" };

export default function Page() {
  return (
    <>
      <div className="space-y-12">
        <header className="space-y-2">
          <h1 className="display text-4xl font-extrabold measure">How this repository is worked in, by a person and by a coding agent</h1>
          <p className="measure text-ink2">
            AGENTS.md is the one source for setup, tests and the rules. The three skills are the procedures. The{" "}
            <a className="underline" href={`${REPO}/blob/main/docs/SPEC.md`}>
              specification
            </a>{" "}
            came first; the decisions record what changed and why.
          </p>
        </header>
        <section className="doc" dangerouslySetInnerHTML={{ __html: data.agents }} data-testid="agents" />
        <section className="space-y-6">
          <h2 className="display text-2xl font-bold">The skills</h2>
          {data.skills.map((s) => (
            <details key={s.name} className="border border-hairline rounded p-3" data-testid="skill">
              <summary className="cursor-pointer">
                <span className="font-mono font-bold">{s.name}</span> <span className="text-ink2 text-sm">{s.description}</span>
              </summary>
              <div className="doc mt-3" dangerouslySetInnerHTML={{ __html: s.html }} />
            </details>
          ))}
        </section>
        <section className="space-y-4">
          <h2 className="display text-2xl font-bold">Decisions, dated</h2>
          <ol className="space-y-4" data-testid="decisions">
            {data.decisions.map((d, i) => (
              <li key={i} className="border-l-2 border-hairline pl-3">
                <p className="font-mono text-xs text-ink2">{d.date}</p>
                <p className="font-bold">{d.title}</p>
                <div className="doc text-sm" dangerouslySetInnerHTML={{ __html: d.html }} />
              </li>
            ))}
          </ol>
        </section>
      </div>
      <Pushback>
        A skill and an AGENTS.md file make an agent's work consistent, not correct. The gates are what hold the line, and they only check what they were written to check.
      </Pushback>
    </>
  );
}
