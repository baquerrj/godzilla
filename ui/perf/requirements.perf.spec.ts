/**
 * Perf and layout verification for responsiveness requirements.
 *
 * REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
 */

import { expect, test } from "@playwright/test";

async function gotoUnlockedApp(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByTestId("app-tabs")).toBeVisible();
}

async function measure<T>(page: import("@playwright/test").Page, action: () => Promise<T>) {
  return page.evaluate(async () => performance.now()).then(async (started) => {
    await action();
    const finished = await page.evaluate(async () => performance.now());
    return finished - started;
  });
}

test("ACC-UX-001 primary views render within target budget", async ({ page }) => {
  await gotoUnlockedApp(page);
  const checks: Array<[string, string]> = [
    ["overview", "sync-state-panel"],
    ["transactions", "transactions-panel"],
    ["reports", "reports-panel"],
    ["data", "data-management-panel"],
  ];
  for (const [tabId, panelId] of checks) {
    const elapsed = await measure(page, async () => {
      await page.getByTestId(`tab-${tabId}`).click();
      await expect(page.getByTestId(`tab-panel-${tabId}`)).not.toHaveAttribute("hidden");
      await expect(page.getByTestId(panelId)).toBeVisible();
    });
    test.info().annotations.push({ type: "metric", description: `${tabId}:${elapsed.toFixed(2)}ms` });
    expect(elapsed).toBeLessThanOrEqual(1000);
  }
});

test("ACC-UX-002 transaction filtering responds within target budget", async ({ page }) => {
  await gotoUnlockedApp(page);
  await page.getByTestId("tab-transactions").click();
  await expect(page.getByTestId("transactions-panel")).toBeVisible();
  const elapsed = await measure(page, async () => {
    await page.getByTestId("filter-merchant").fill("Benchmark Merchant 01");
    await expect(page.getByText("Benchmark Merchant 01").first()).toBeVisible();
  });
  test.info().annotations.push({ type: "metric", description: `filter:${elapsed.toFixed(2)}ms` });
  expect(elapsed).toBeLessThanOrEqual(500);
});

test("ACC-UX-003 report and dashboard switches stay responsive", async ({ page }) => {
  await gotoUnlockedApp(page);
  const elapsed = await measure(page, async () => {
    await page.getByTestId("tab-reports").click();
    await expect(page.getByTestId("reports-panel")).toBeVisible();
    await page.getByTestId("tab-overview").click();
    await expect(page.getByTestId("sync-state-panel")).toBeVisible();
  });
  test.info().annotations.push({ type: "metric", description: `switch:${elapsed.toFixed(2)}ms` });
  expect(elapsed).toBeLessThanOrEqual(500);
});

async function expectLayoutIntegrity(
  page: import("@playwright/test").Page,
  viewport: { width: number; height: number },
) {
  await page.setViewportSize(viewport);
  await gotoUnlockedApp(page);
  await page.getByTestId("tab-transactions").click();
  await expect(page.getByTestId("transaction-filters")).toBeVisible();
  const tabsBox = await page.getByTestId("app-tabs").boundingBox();
  const filtersBox = await page.getByTestId("transaction-filters").boundingBox();
  expect(tabsBox).not.toBeNull();
  expect(filtersBox).not.toBeNull();
  expect(tabsBox?.width ?? 0).toBeGreaterThan(0);
  expect(filtersBox?.height ?? 0).toBeGreaterThan(0);
}

test("ACC-UX-004 layout integrity at 1024x700", async ({ page }) => {
  await expectLayoutIntegrity(page, { width: 1024, height: 700 });
});

test("ACC-UX-004 layout integrity at 1280x800", async ({ page }) => {
  await expectLayoutIntegrity(page, { width: 1280, height: 800 });
});

test("ACC-UX-004 layout integrity at 1440x900", async ({ page }) => {
  await expectLayoutIntegrity(page, { width: 1440, height: 900 });
});
