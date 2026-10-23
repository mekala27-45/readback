import { Pushback } from "@/components/Pushback";
import type { Metadata } from "next";

import { Catalog } from "@/components/catalog/Catalog";
import { v } from "@/lib/data";

export const metadata: Metadata = { title: "Catalog" };

export default function Page() {
  return (
    <>
      <div className="space-y-6">
        <header className="space-y-2">
          <h1 className="display text-4xl font-extrabold measure">
            {v("data.tables")} tables, and {v("catalog.with_unit")} measure columns with a unit
          </h1>
          <p className="measure text-ink2">
            The three warehouses as the agent sees them. {v("catalog.with_definition")} measure columns carry a definition cited to the line of
            the build&apos;s own documents; the rest sit in a quarantine of {v("catalog.quarantine")} named rows.
          </p>
        </header>
        <Catalog />
      </div>
      <Pushback>
        A definition cited to a line is only as good as the build's own document, and a quarantine row is a gap, not a fix. The units come from committed rules that a person wrote; the range check catches a wrong one only when its values do not fit.
      </Pushback>
    </>
  );
}
