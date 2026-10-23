// The type, self hosted at build time through next/font from the Fontsource packages (the sandbox
// that built this cannot reach Google Fonts, and the site fetches nothing from anywhere else).
// Bricolage Grotesque for display, with its optical size axis; B612 for the interface and body, its
// digits all one width so figures line up; B612 Mono for tool cards, SQL, hashes and dense tables.
import localFont from "next/font/local";

export const bricolage = localFont({
  src: "../../node_modules/@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-standard-normal.woff2",
  weight: "200 800",
  variable: "--font-bricolage",
  display: "swap",
});

export const b612 = localFont({
  src: [
    { path: "../../node_modules/@fontsource/b612/files/b612-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../../node_modules/@fontsource/b612/files/b612-latin-400-italic.woff2", weight: "400", style: "italic" },
    { path: "../../node_modules/@fontsource/b612/files/b612-latin-700-normal.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-b612",
  display: "swap",
});

export const b612mono = localFont({
  src: [
    { path: "../../node_modules/@fontsource/b612-mono/files/b612-mono-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../../node_modules/@fontsource/b612-mono/files/b612-mono-latin-700-normal.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-b612mono",
  display: "swap",
});
