import { Pushback } from "@/components/Pushback";
import type { Metadata } from "next";

import { Viewer } from "@/components/traces/Viewer";

export const metadata: Metadata = { title: "Traces" };

export default function Page() {
  return (
    <>
      <Viewer />
      <Pushback>
        These spans come from a single process on a laptop or a cold function, so the durations show where time goes in a turn, not what a warm service would do under load. Message content is never captured, which keeps the traces safe to publish and also means a trace alone cannot replay a turn.
      </Pushback>
    </>
  );
}
