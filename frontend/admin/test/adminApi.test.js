import assert from "node:assert/strict";
import test from "node:test";

import {
  API_BASE_URL,
  applyEntitlementRegistrySync,
  previewEntitlementRegistrySync,
  listProjects,
  getProjectQuota,
  updateMaterial,
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

test("project quota wrapper uses the shared API base URL", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, usage: 2, limit: 5, can_create: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await getProjectQuota("token-3");

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/project/quota");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-3");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("project list wrapper forwards ownership scope as a query parameter", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, projects: [], total: 0, offset: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await listProjects("token-4", 20, 40, {
      search: "desk",
      ownership_scope: "mine",
    });

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/project?limit=20&offset=40&search=desk&ownership_scope=mine");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-4");
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

test("material update wrapper sends a PATCH request with the edited fields only", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, item: { article: "A-100" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await updateMaterial("token-2", "A-100", {
      name: "New panel",
      description: "Updated description",
      price: 125.5,
    });

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/catalog/materials/A-100");
    assert.equal(calls[0].options.method, "PATCH");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-2");
    assert.deepEqual(JSON.parse(calls[0].options.body), {
      name: "New panel",
      description: "Updated description",
      price: 125.5,
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("material update wrapper surfaces not-found responses from the backend", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () =>
    new Response(JSON.stringify({ success: false, error: "Material not found or unavailable." }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });

  try {
    const result = await updateMaterial("token-2", "A-404", { name: "New panel" });
    assert.equal(result.success, false);
    assert.equal(result.status, 404);
    assert.equal(result.error, "Material not found or unavailable.");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
