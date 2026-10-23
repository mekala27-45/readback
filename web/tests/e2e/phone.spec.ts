import { expect, test } from "@playwright/test";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "/readback";

test("on a phone the transcript is full width and the evidence opens as a sheet", async ({ page }) => {
  await page.goto(`${BASE}/`);
  await expect(page.getByTestId("source")).toHaveAttribute("data-source", "live", { timeout: 30_000 });
  await page.getByTestId("question").fill("What was the price to income ratio in Minneapolis in 2016?");
  await page.getByTestId("ask").click();
  await page.getByTestId("chip").first().click();
  const sheet = page.getByTestId("evidence");
  await expect(sheet).toBeVisible();
  const box = await sheet.boundingBox();
  expect(box?.width).toBeGreaterThan(380);
  const scroll = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(scroll).toBeLessThanOrEqual(0);
});
