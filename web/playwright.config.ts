import { existsSync } from "node:fs";

import { defineConfig, devices } from "@playwright/test";

// The exported site, served the way GitHub Pages serves it: under the base path, with byte ranges,
// refusing HEAD, with a mock API whose first answer is a 503. Build once with `npm run build:e2e`.
const PORT = Number(process.env.READBACK_E2E_PORT ?? 4174);
const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "/readback";
// The sandbox that built this ships a Chromium outside Playwright's cache; CI installs its own.
const chromium = process.env.READBACK_CHROMIUM ?? "/opt/pw-browsers/chromium";

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    ...(existsSync(chromium) ? { launchOptions: { executablePath: chromium } } : {}),
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1360, height: 900 } }, testIgnore: /phone\.spec\.ts/ },
    { name: "phone", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } }, testMatch: /phone\.spec\.ts/ },
  ],
  webServer: {
    command: "node scripts/serve.mjs",
    url: `http://127.0.0.1:${PORT}${BASE}/`,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});
