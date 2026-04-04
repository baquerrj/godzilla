/**
 * Vite development proxy configuration.
 *
 * REQ: TECH-SEC-ACC-004, TECH-SEC-DATA-001
 */

/// <reference types="vitest" />
import { configDefaults } from "vitest/config";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;
// Bind all interfaces by default for container/remote dev; Tauri can still override.
const devHost = host || "0.0.0.0";
// REQ: TECH-SEC-ACC-004, TECH-SEC-DATA-001
const apiToken = process.env.GODZILLA_API_TOKEN ?? "";

// Godzilla Python API sidecar runs on loopback port 8787.
// In development the Vite proxy forwards /api/* to it so the frontend
// can use relative URLs consistently across dev and production builds.
const API_SIDECAR = "http://127.0.0.1:8787";

// https://vite.dev/config/
export default defineConfig(async () => ({
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    globals: false,
    exclude: [...configDefaults.exclude, "perf/**"],
  },
  plugins: [react()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: devHost,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
    proxy: {
      // Forward /api/* → Python sidecar, stripping the /api prefix.
      // e.g. GET /api/accounts  →  GET http://127.0.0.1:8787/accounts
      "/api": {
        target: API_SIDECAR,
        changeOrigin: false,
        rewrite: (path) => path.replace(/^\/api/, ""),
        configure: (proxy) => {
          proxy.on("proxyReq", (proxyReq) => {
            // REQ: TECH-SEC-ACC-004, TECH-SEC-DATA-001
            // Inject auth server-side so secrets are not embedded in browser bundles.
            if (apiToken) {
              proxyReq.setHeader("X-API-Key", apiToken);
            }
          });
        },
      },
    },
  },
}));
