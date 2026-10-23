import { Pushback } from "@/components/Pushback";
import type { Metadata } from "next";

import { CopyBlock } from "@/components/CopyBlock";
import data from "../../../public/data/connect.json";

export const metadata: Metadata = { title: "Connect a host" };

interface Host {
  name: string;
  where: string;
  language: string;
  config: string;
}

export default function Page() {
  const hosts = data.source.hosts as Host[];
  const c = data.conformance;
  return (
    <>
      <div className="space-y-10">
        <header className="space-y-2">
          <h1 className="display text-4xl font-extrabold measure">Connect any MCP host to the same seven tools the agent uses</h1>
          <p className="measure text-ink2">
            Streamable HTTP at protocol revision {c.revision}, stateless, read only. Every block below renders from docs/connect.yaml, the same
            source as docs/connect.md, so the two cannot drift.
          </p>
          <p className="font-mono text-sm break-all" data-testid="live-url">
            {data.source.url}
          </p>
        </header>
  
        <section className="space-y-6">
          {hosts.map((h) => (
            <div key={h.name} className="space-y-1">
              <h2 className="font-bold">{h.name}</h2>
              <p className="text-sm text-ink2 font-mono">{h.where}</p>
              <CopyBlock code={h.config.trimEnd()} label={h.name} />
              <span className="hidden" data-language={h.language} />
            </div>
          ))}
        </section>
  
        <section className="space-y-2">
          <h2 className="display text-2xl font-bold">server.json</h2>
          <p className="text-sm text-ink2">
            For the MCP registry, remote only. Registry name <span className="font-mono">{data.server.name}</span>.
          </p>
          <CopyBlock code={JSON.stringify(data.server, null, 2)} label="server.json" />
        </section>
  
        <section className="space-y-2">
          <h2 className="display text-2xl font-bold">Conformance</h2>
          <table className="dense max-w-[640px]" data-testid="conformance">
            <tbody>
              <tr>
                <td>Revision</td>
                <td className="font-mono">{c.revision}</td>
              </tr>
              <tr>
                <td>Discovery</td>
                <td className="font-mono">
                  {c.discovery.server}, versions {c.discovery.supported_versions.join(", ")}, {c.discovery.capabilities.join(", ")}
                </td>
              </tr>
              <tr>
                <td>Tools, each with an output schema</td>
                <td className="font-mono">
                  {c.output_schemas} of {c.tool_count}: {c.tools.join(", ")}
                </td>
              </tr>
              <tr>
                <td>Two lists byte identical</td>
                <td>{c.lists_identical ? "✓ yes" : "✕ no"}</td>
              </tr>
              <tr>
                <td>Hour long public cache hints</td>
                <td>{c.cache_hints ? "✓ on every list" : "✕ missing"}</td>
              </tr>
              <tr>
                <td>Unsupported version</td>
                <td className="font-mono">error {c.unsupported_version_error}</td>
              </tr>
              <tr>
                <td>Trace context through _meta</td>
                <td>{c.trace_context ? "✓ the server span is a child of the caller's" : "✕ broken"}</td>
              </tr>
              <tr>
                <td>Transports answering the same list</td>
                <td className="font-mono">
                  {Object.entries(c.transports)
                    .filter(([, ok]) => ok)
                    .map(([k]) => k.replace("_", " "))
                    .join(", ")}
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
      <Pushback>
        The endpoint is a free container function with a cold start and a per client budget, so it suits a demonstration and a few hosts, not a team. It is read only by construction; nothing here was designed for writes.
      </Pushback>
    </>
  );
}
