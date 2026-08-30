import assert from "node:assert/strict";
import test from "node:test";

import {
  deleteEdgeCatalog,
  createEdgeCatalog,
  createEdgeCatalogFromSource,
  getEdgeCatalogDetail,
  getEdgesCatalog,
  previewEdgeCatalogSource,
  uploadEdgeImage,
  updateEdgeCatalog,
} from "../src/api.js";

test("edge catalog wrapper hits the explicit read-only endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, items: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await getEdgesCatalog("token-1", {
      search: "ABS",
      manufacturer_id: 6,
      supplier_id: 1,
    });

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges?search=ABS&manufacturer_id=6&supplier_id=1",
    ]);
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-1");
    assert.equal(calls[0].options.timeoutMs, 30000);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge create wrapper posts canonical edge payloads to the dedicated endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, item: { id: 77 } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await createEdgeCatalog("token-2", {
      manufacturer_id: 4,
      name: "ABS 23x0.8",
      width_mm: 23,
      thickness_mm: 0.8,
    });

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges",
    ]);
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-2");
    assert.equal(calls[0].options.method, "POST");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge source preview wrapper hits the dedicated preview endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, items: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await previewEdgeCatalogSource("token-3", {
      source_url: "https://viyar.ua/ua/catalog/material/",
    });

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges/source-preview",
    ]);
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-3");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge source create wrapper posts preview payloads to the dedicated endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, summary: { persisted: 1 } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await createEdgeCatalogFromSource("token-4", {
      preview_result: { success: true, items: [] },
      city: "kyiv",
    });

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges/source-create",
    ]);
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-4");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge image upload wrapper posts files to the dedicated endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;
  const file = new File(["edge-image"], "edge.png", { type: "image/png" });

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, image_url: "/uploads/edge-images/edge.png" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await uploadEdgeImage("token-5", file);

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges/image",
    ]);
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-5");
    assert.ok(calls[0].options.body instanceof FormData);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge detail wrapper hits the dedicated detail endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, item: { id: 9 } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await getEdgeCatalogDetail("token-6", 9);

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges/9",
    ]);
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-6");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge update wrapper patches the dedicated endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, item: { id: 9 } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await updateEdgeCatalog("token-7", 9, { name: "Updated edge" });

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges/9",
    ]);
    assert.equal(calls[0].options.method, "PATCH");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-7");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("edge delete wrapper deletes the dedicated endpoint", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, item: { id: 9 } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await deleteEdgeCatalog("token-8", 9);

    assert.equal(result.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/edges/9",
    ]);
    assert.equal(calls[0].options.method, "DELETE");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-8");
  } finally {
    globalThis.fetch = originalFetch;
  }
});
