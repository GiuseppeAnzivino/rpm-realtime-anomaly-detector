import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// In sviluppo le chiamate /auth vengono inoltrate all'auth-service (porta host 8001):
// il browser vede una sola origine, quindi non serve configurare CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/auth": { target: "http://localhost:8001", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./tests/test-setup.js",
  },
});