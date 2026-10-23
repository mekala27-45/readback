// Where the site and its API live. Both are fixed at build time by next.config.ts.
export const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export const API = process.env.NEXT_PUBLIC_READBACK_API ?? "";
export const REPO = "https://github.com/mekala27-45/readback";

/** The URL of a file under public/data. */
export function dataUrl(file: string): string {
  return `${BASE}/data/${file}`;
}

/** Fetch a JSON file under public/data once per visit. */
const cache = new Map<string, Promise<unknown>>();
export function loadJson<T>(file: string): Promise<T> {
  let hit = cache.get(file);
  if (!hit) {
    hit = fetch(dataUrl(file)).then((r) => {
      if (!r.ok) throw new Error(`${file} did not load (${r.status})`);
      return r.json();
    });
    cache.set(file, hit);
  }
  return hit as Promise<T>;
}
