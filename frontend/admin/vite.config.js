import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/admin/" : "/",
  plugins: [react()],
  server: {
    fs: {
      allow: [
        path.resolve(__dirname),
        path.resolve(__dirname, "..", "shared"),
      ],
    },
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/project": "http://127.0.0.1:8000",
      "/catalog": "http://127.0.0.1:8000",
      "/audit": "http://127.0.0.1:8000",
      "/fitting-holes": "http://127.0.0.1:8000",
      "/service-drilling-rules": "http://127.0.0.1:8000",
    },
  },
  preview: {
    host: "127.0.0.1",
    port: 4173,
  },
}));
