/**
 * Playwright config for opt-in responsiveness and layout verification.
 *
 * REQ: ACC-UX-001, ACC-UX-002, ACC-UX-003, ACC-UX-004
 */

import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.GODZILLA_PERF_BASE_URL ?? "http://127.0.0.1:1420";

export default defineConfig({
  testDir: "./perf",
  reporter: [["list"], ["json", { outputFile: "perf-results/metrics.json" }]],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  outputDir: "perf-results/artifacts",
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
