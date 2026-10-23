// The two parquet files the browser reads: the eval run's trace spans and the manifest index.
//
// Read with hyparquet over HTTP byte ranges (the footer first, then the column chunks), zstd
// decoded by fzstd. DuckDB-WASM was the plan; DECISIONS.md says why it was dropped for these two
// files. The host refuses HEAD, so a file's length comes from a one byte range request.
import type { Span } from "./types";
import { dataUrl } from "./site";

export type Row = Record<string, unknown>;

async function byteLength(url: string): Promise<number> {
  const r = await fetch(url, { headers: { Range: "bytes=0-0" } });
  const total = r.headers.get("Content-Range")?.split("/")[1];
  if (r.status === 206 && total && Number.isFinite(Number(total))) return Number(total);
  if (r.status === 200) return (await r.arrayBuffer()).byteLength;
  throw new Error(`cannot size ${url}: ${r.status}`);
}

const cache = new Map<string, Promise<Row[]>>();

export function readParquet(file: string): Promise<Row[]> {
  let hit = cache.get(file);
  if (!hit) {
    hit = (async () => {
      const [{ asyncBufferFromUrl, parquetReadObjects }, { decompress }] = await Promise.all([import("hyparquet"), import("fzstd")]);
      const url = dataUrl(file);
      const buffer = await asyncBufferFromUrl({ url, byteLength: await byteLength(url) });
      const compressors = { ZSTD: (input: Uint8Array, outputLength: number) => decompress(input, new Uint8Array(outputLength)) };
      const rows = (await parquetReadObjects({ file: buffer, compressors })) as Row[];
      return rows.map((r) => Object.fromEntries(Object.entries(r).map(([k, v]) => [k, typeof v === "bigint" ? Number(v) : v])));
    })();
    cache.set(file, hit);
  }
  return hit;
}

/** Every span of the floor's eval run, as the viewer draws them. */
export async function evalSpans(): Promise<Span[]> {
  return (await readParquet("traces/floor.parquet")) as unknown as Span[];
}
