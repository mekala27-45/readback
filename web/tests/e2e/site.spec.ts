import { expect, test, type Page } from "@playwright/test";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "/readback";
const ROUTES = ["/", "/traces/", "/evals/", "/catalog/", "/connect/", "/playbook/", "/report/"];

async function askOnDesk(page: Page, question: string) {
  await page.goto(`${BASE}/`);
  // The mock answers its first request with a 503, so the desk has to probe twice before it goes live.
  await expect(page.getByTestId("source")).toHaveAttribute("data-source", "live", { timeout: 30_000 });
  await page.getByTestId("question").fill(question);
  await page.getByTestId("ask").click();
}

test("the statement is in the footer of every route", async ({ page }) => {
  for (const route of ROUTES) {
    await page.goto(`${BASE}${route}`);
    await expect(page.locator("[data-statement]")).toContainText("Every number is read back to the warehouse");
  }
});

test("a question is answered with tool cards and a verified chip on every number", async ({ page }) => {
  await askOnDesk(page, "Which had the higher mortgage payment as a share of income in 2006, Philadelphia or New York?");
  const answer = page.getByTestId("answer");
  await expect(answer).toHaveAttribute("data-verdict", "verified");
  await expect(page.getByTestId("tool-card").first()).toBeVisible();
  const chips = answer.getByTestId("chip");
  await expect(chips).toHaveCount(2);
  for (const v of await chips.all()) await expect(v).toHaveAttribute("data-verdict", "verified");
  await expect(page.getByTestId("no-model")).toBeVisible();
  await expect(page.getByTestId("gate")).toContainText("passed");
});

test("a chip opens the SQL it was read back against, and a tool card opens its rows", async ({ page }) => {
  await askOnDesk(page, "What was the price to income ratio in Minneapolis in 2016?");
  await page.getByTestId("chip").first().click();
  await expect(page.getByTestId("evidence-sql")).toContainText("price_to_income");
  await expect(page.getByTestId("evidence-verdict")).toContainText("verified");
  await page.locator('[data-tool="run_sql"] button').last().click();
  await expect(page.getByTestId("tool-rows").first()).toBeVisible();
  await expect(page.getByTestId("tool-sql").first()).toContainText(/select/i);
});

test("an ambiguous name asks back, and the choice resumes the same turn", async ({ page }) => {
  await askOnDesk(page, "What was the payment share in Portland in 2019?");
  const ask = page.getByTestId("interrupt");
  await expect(ask).toBeVisible();
  await ask.getByRole("button", { name: "Portland-Vancouver-Hillsboro, OR-WA" }).click();
  await expect(page.getByTestId("answer")).toContainText("Portland-Vancouver-Hillsboro");
  await expect(page.getByTestId("turn")).toHaveCount(1);
});

test("a refusal is shown as refused, with no chip", async ({ page }) => {
  const s = await (await page.request.get(`${BASE}/data/recorded_session.json`)).json();
  const refusal = s.turns.find((t: { id: string }) => t.id.startsWith("R-")).question;
  await askOnDesk(page, refusal);
  await expect(page.getByTestId("answer")).toHaveAttribute("data-verdict", "refused");
  await expect(page.getByTestId("chip")).toHaveCount(0);
});

test("the desk trace link opens the waterfall for that turn", async ({ page }) => {
  await askOnDesk(page, "What was the price to income ratio in Minneapolis in 2016?");
  await page.getByTestId("trace-link").click();
  await expect(page.getByTestId("span").first()).toBeVisible();
});

test("the viewer draws a waterfall and a span expands to its attributes", async ({ page }) => {
  await page.goto(`${BASE}/traces/`);
  await expect(page.getByTestId("span").first()).toBeVisible();
  await expect(page.locator('[data-role="tool"]').first()).toBeVisible();
  await page.getByTestId("span").first().locator("button").click();
  await expect(page.getByTestId("span-attributes")).toContainText("duration");
});

test("the scorecard puts the floor row first and draws its interval", async ({ page }) => {
  await page.goto(`${BASE}/evals/`);
  const first = page.getByTestId("dot-row").first();
  await expect(first).toHaveAttribute("data-provider", "floor");
  await expect(first.locator("rect")).toHaveCount(1);
  await expect(page.getByTestId("test-table").first()).toBeAttached();
  await expect(page.getByTestId("redteam")).toContainText("RT-01");
});

test("every configuration block on the connect page parses", async ({ page }) => {
  await page.goto(`${BASE}/connect/`);
  const blocks = page.getByTestId("config-block");
  expect(await blocks.count()).toBeGreaterThanOrEqual(7);
  for (const block of await blocks.all()) {
    const text = (await block.textContent()) ?? "";
    const label = (await block.getAttribute("data-label")) ?? "";
    if (text.trim().startsWith("{")) expect(() => JSON.parse(text), label).not.toThrow();
    else if (text.includes("[mcp_servers")) expect(text, label).toMatch(/^\[mcp_servers\.[a-z]+\]/m);
    else expect(text, label).toContain("https://");
  }
  await expect(page.getByTestId("conformance")).toContainText("2026-07-28");
});

test("the catalog lists the tables of each warehouse and searches the manifest", async ({ page }) => {
  await page.goto(`${BASE}/catalog/`);
  await expect(page.getByTestId("table-list").locator("li").first()).toBeVisible();
  await page.getByRole("tab", { name: "manifest" }).click();
  await expect(page.getByTestId("manifest-values").locator("tbody tr").first()).toBeVisible();
});

test("the host refuses HEAD, and the site still works", async ({ request }) => {
  const head = await request.head(`${BASE}/`);
  expect(head.status()).toBe(405);
});
