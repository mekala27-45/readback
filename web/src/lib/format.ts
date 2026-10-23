// Small display helpers. Figures that matter come formatted from the manifest; these format what
// the API streams (a latency, an evidence value) and nothing the claim gate checks.
export function ms(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${value.toFixed(value < 10 ? 1 : 0)} ms`;
}

export function evidence(value: number | null, unit: string | null): string {
  if (value === null || value === undefined) return "none";
  const digits = Math.abs(value) >= 1000 ? 0 : Math.abs(value) >= 1 ? 4 : 6;
  return `${value.toLocaleString("en-US", { maximumFractionDigits: digits })}${unit ? ` ${unit}` : ""}`;
}

/** The SQL inside a sealed result handle: r1.<base64url json>.<signature>, where json.s is the SQL. */
export function sqlOfHandle(handle: string | null): string | null {
  if (!handle) return null;
  const parts = handle.split(".");
  if (parts.length < 3 || !parts[1]) return null;
  try {
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = JSON.parse(decodeURIComponent(escape(atob(b64 + "===".slice((b64.length + 3) % 4))))) as { s?: string };
    return json.s ?? null;
  } catch {
    return null;
  }
}

export function shortId(id: string, n = 8): string {
  return id.length > n ? id.slice(0, n) : id;
}
