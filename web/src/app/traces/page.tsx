import type { Metadata } from "next";

import { Viewer } from "@/components/traces/Viewer";

export const metadata: Metadata = { title: "Traces" };

export default function Page() {
  return <Viewer />;
}
