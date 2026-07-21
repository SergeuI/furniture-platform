import assert from "node:assert/strict";
import test from "node:test";

import viteConfig from "../vite.config.js";

test("admin dev proxy routes entitlement requests to the API server", () => {
  const config = viteConfig({ command: "serve" });

  assert.equal(config.server.proxy["/admin"], "http://127.0.0.1:8000");
  assert.equal(config.server.proxy["/auth"], "http://127.0.0.1:8000");
  assert.equal(config.base, "/");
});

test("build keeps the admin base path", () => {
  const config = viteConfig({ command: "build" });
  assert.equal(config.base, "/admin/");
});

