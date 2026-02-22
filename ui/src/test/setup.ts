/**
 * Vitest global setup: extend expect with @testing-library/jest-dom matchers
 * and ensure RTL cleanup runs after every test regardless of globals setting.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
