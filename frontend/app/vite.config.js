import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [
        path.resolve(__dirname),
        path.resolve(__dirname, "..", "shared"),
      ],
    },
    host: "127.0.0.1",
    port: 5175,
  },
  preview: {
    host: "127.0.0.1",
    port: 4175,
  },
});
