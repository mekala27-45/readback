"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

export const THEME_KEY = "readback-theme";

// Dark is the default: a flight deck at night. Light is a true theme the reader chooses.
function current(): Theme {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");
  useEffect(() => setTheme(current()), []);
  const flip = () => {
    const next: Theme = current() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    setTheme(next);
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch {
      // Blocked storage: the choice lasts for this page only.
    }
  };
  return (
    <button
      type="button"
      onClick={flip}
      className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1.5 border border-hairline rounded text-ink2 hover:text-ink hover:border-control shrink-0"
      aria-label={`Switch to the ${theme === "dark" ? "light" : "dark"} theme`}
      data-testid="theme-toggle"
    >
      <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M8 2a6 6 0 0 1 0 12z" fill="currentColor" />
      </svg>
      {theme === "dark" ? "Light" : "Dark"}
    </button>
  );
}

/** Runs first in <body>: a stored choice wins; otherwise dark. */
export const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_KEY}");if(t!=="light"&&t!=="dark"){t="dark";}document.documentElement.setAttribute("data-theme",t);}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`;
