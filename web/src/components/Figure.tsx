import type { ReactNode } from "react";

/**
 * Every chart: the message as its title, the conventional title demoted to a subtitle, and two
 * toggles beside it, one for the numbers as a table and one for where they come from.
 */
export function Figure({ title, subtitle, source, table, children }: { title: string; subtitle: string; source: string; table: ReactNode; children: ReactNode }) {
  return (
    <figure className="space-y-3" data-testid="figure">
      <figcaption>
        <p className="display text-xl font-bold">{title}</p>
        <p className="text-sm text-ink2">{subtitle}</p>
      </figcaption>
      {children}
      <div className="flex flex-wrap gap-4 text-sm no-print">
        <details>
          <summary className="cursor-pointer text-ink2 hover:text-ink">Show the table</summary>
          <div className="mt-2">{table}</div>
        </details>
        <details>
          <summary className="cursor-pointer text-ink2 hover:text-ink">Show the source</summary>
          <p className="mt-2 font-mono text-xs">{source}</p>
        </details>
      </div>
    </figure>
  );
}
