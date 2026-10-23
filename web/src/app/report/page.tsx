import { Pushback } from "@/components/Pushback";
import type { Metadata } from "next";

import data from "../../../public/data/briefing.json";

export const metadata: Metadata = { title: "Briefing" };

export default function Page() {
  return (
    <>
      <article className="briefing doc" data-testid="briefing">
        <div dangerouslySetInnerHTML={{ __html: data.html }} />
        <p className="no-print text-sm text-ink2 mt-8">The page prints on one sheet of light paper whichever theme you read it in.</p>
      </article>
      <Pushback>
        The briefing is short on purpose and leaves out the failure analysis a production review would want; the scorecard and DECISIONS.md carry that detail.
      </Pushback>
    </>
  );
}
