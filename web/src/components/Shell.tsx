import Link from "next/link";
import type { ReactNode } from "react";

import { site } from "@/lib/data";
import { REPO } from "@/lib/site";

import { NavLinks } from "./NavLinks";
import { ThemeToggle } from "./ThemeToggle";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col">
      <a href="#content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 bg-raised px-3 py-2 rounded">
        Skip to the content
      </a>
      <header className="no-print border-b border-hairline bg-surface sticky top-0 z-30">
        <div className="mx-auto max-w-[1240px] px-4 sm:px-6 py-3 flex flex-wrap items-center gap-x-6 gap-y-2">
          <Link prefetch={false} href="/" className="flex items-baseline gap-2 shrink-0 no-underline" aria-label="readback, the desk">
            <span className="display text-2xl leading-none font-extrabold">readback</span>
            <span className="text-xs text-ink2 font-mono">as of {site.as_of}</span>
          </Link>
          <nav aria-label="Pages" className="order-3 w-full md:order-none md:w-auto md:flex-1">
            <NavLinks />
          </nav>
          <div className="ml-auto md:ml-0">
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main id="content" className="flex-1 mx-auto w-full max-w-[1240px] px-4 sm:px-6 py-8">
        {children}
      </main>
      <footer className="border-t border-hairline mt-12" data-testid="footer">
        <div className="mx-auto max-w-[1240px] px-4 sm:px-6 py-6 text-sm text-ink2 space-y-2">
          <p className="measure text-ink" data-statement>
            {site.statement}
          </p>
          <p className="no-print text-xs">
            Built by Ajay Mekala.{" "}
            <a className="underline" href={REPO}>
              Source on GitHub
            </a>
            , Apache 2.0. Every figure on these pages is read from the published manifest, the committed results, or the warehouse
            through the API.
          </p>
        </div>
      </footer>
    </div>
  );
}
