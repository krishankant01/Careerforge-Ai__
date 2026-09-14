import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy /api calls to the FastAPI backend during dev.
// Uses BACKEND_URL env var if set (e.g. "http://backend:8000" in Docker),
// or defaults to "http://localhost:8000" for host dev.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
