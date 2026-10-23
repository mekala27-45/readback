import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { Shell } from "@/components/Shell";
import { THEME_SCRIPT } from "@/components/ThemeToggle";
import palette from "@/theme/palette.json";

import { b612, b612mono, bricolage } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "readback: every number read back", template: "%s | readback" },
  description:
    "An analyst agent over three published warehouses, served as an MCP server, where every number is read back to the warehouse before you see it.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: palette.dark.surface },
    { media: "(prefers-color-scheme: light)", color: palette.light.surface },
  ],
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning className={`${bricolage.variable} ${b612.variable} ${b612mono.variable}`}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
