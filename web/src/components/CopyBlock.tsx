"use client";

import { useState } from "react";

export function CopyBlock({ code, label }: { code: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        className="absolute right-2 top-2 text-xs px-2 py-0.5 border border-hairline rounded bg-surface"
        aria-label={`Copy the ${label} configuration`}
        onClick={() => {
          void navigator.clipboard?.writeText(code).then(() => {
            setDone(true);
            window.setTimeout(() => setDone(false), 1500);
          });
        }}
      >
        {done ? "Copied" : "Copy"}
      </button>
      <pre className="font-mono text-xs bg-raised border border-hairline rounded p-3 pr-16 overflow-x-auto" data-testid="config-block" data-label={label}>
        {code}
      </pre>
    </div>
  );
}
