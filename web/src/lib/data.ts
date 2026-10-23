// What the server rendered pages read at build time. Every figure is a formatted manifest value.
import siteJson from "../../public/data/site.json";

export interface SiteData {
  as_of: string;
  statement: string;
  values: Record<string, string>;
  tables: Record<string, { columns: string[]; formats: string[]; rows: string[][] }>;
}

export const site = siteJson as SiteData;

/** A formatted manifest value; a missing key fails the build, the way the claim gate does. */
export function v(key: string): string {
  const value = site.values[key];
  if (value === undefined) throw new Error(`the manifest has no value ${key}`);
  return value;
}
