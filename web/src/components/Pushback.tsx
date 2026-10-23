import type { ReactNode } from "react";

/** What a careful reviewer would push back on, said on the page it applies to. */
export function Pushback({ children }: { children: ReactNode }) {
  return (
    <aside className="measure mt-12 border-l-2 border-control pl-4 text-sm text-ink2 no-print" data-testid="pushback">
      <p className="font-bold text-ink mb-1">What a platform engineer would push back on</p>
      <p>{children}</p>
    </aside>
  );
}
