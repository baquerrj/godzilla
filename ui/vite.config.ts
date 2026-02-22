import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// Godzilla Python API sidecar runs on loopback port 8787.
// In development the Vite proxy forwards /api/* to it so the frontend
// can use relative URLs consistently across dev and production builds.
const API_SIDECAR = "http://127.0.0.1:8787";

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react()],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
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
      },
    },
  },
}));
