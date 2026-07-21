import assert from "node:assert/strict";
import test from "node:test";

import {
  API_BASE_URL,
  applyEntitlementRegistrySync,
  previewEntitlementRegistrySync,
} from "../src/api.js";

test("admin entitlement sync wrappers use the shared API base URL", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, can_apply: true, summary: {} }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    assert.equal(API_BASE_URL, "/api");

    const preview = await previewEntitlementRegistrySync("token-1");
    const apply = await applyEntitlementRegistrySync("token-1");

    assert.equal(preview.success, true);
    assert.equal(apply.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/admin/entitlements/registry-sync/preview",
      "/api/admin/entitlements/registry-sync/apply",
    ]);
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-1");
    assert.equal(calls[1].options.method, "POST");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("admin entitlement sync wrappers surface HTML responses as readable errors", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response("<html><body>error</body></html>", {
      status: 200,
      headers: { "Content-Type": "text/html" },
    });

  try {
    const result = await previewEntitlementRegistrySync("token-1");
    assert.equal(result.success, false);
    assert.match(result.error, /Server returned an HTML error page \(HTTP 200\)/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
