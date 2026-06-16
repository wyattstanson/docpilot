import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the built bundle works when served by FastAPI from /dist.
export default defineConfig({
  plugins: [react()],
  base: "./",
  server: {
    port: 5173,
    proxy: {
      // In dev, forward API calls to the FastAPI bridge.
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
