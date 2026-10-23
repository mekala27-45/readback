import type { Metadata } from "next";

import data from "../../../public/data/briefing.json";

export const metadata: Metadata = { title: "Briefing" };

export default function Page() {
  return (
    <article className="briefing doc" data-testid="briefing">
      <div dangerouslySetInnerHTML={{ __html: data.html }} />
      <p className="no-print text-sm text-ink2 mt-8">The page prints on one sheet of light paper whichever theme you read it in.</p>
    </article>
  );
}
