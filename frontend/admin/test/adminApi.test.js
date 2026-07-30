import assert from "node:assert/strict";
import test from "node:test";

import {
  API_BASE_URL,
  applyEntitlementRegistrySync,
  getMountingNode,
  getMountingNodes,
  previewEntitlementRegistrySync,
  listProjects,
  getProjectQuota,
  updateMountingNode,
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

test("mounting node list wrapper forwards filters and keeps inactive filtering readable", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(
      JSON.stringify({
        success: true,
        nodes: [
          { id: 1, code: "active-node", is_active: true },
          { id: 2, code: "inactive-node", is_active: false },
        ],
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      },
    );
  };

  try {
    const result = await getMountingNodes("token-5", {
      search: "confirmat",
      fitting_id: 1,
      mounting_variant_key: "face_to_edge",
      is_active: false,
    });

    assert.equal(result.success, true);
    assert.deepEqual(result.nodes.map((node) => node.code), ["inactive-node"]);
    assert.equal(
      calls[0].url,
      "/api/mounting-nodes?search=confirmat&fitting_id=1&mounting_variant_key=face_to_edge&is_active=false&include_inactive=true",
    );
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-5");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("mounting node detail wrapper loads a single node by id", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, node: { id: 1, code: "mn_confirmat_7x50" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await getMountingNode("token-6", 1);

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/mounting-nodes/1");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-6");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("mounting node update wrapper sends a PATCH request with the nested atomic payload", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, node: { id: 1 } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await updateMountingNode("token-7", 1, {
      code: "node-1",
      name: "Node 1",
      items: [
        {
          fitting_id: 11,
          quantity: 2,
          role: "primary",
          is_required: true,
          affects_processing: true,
          order_index: 1,
        },
      ],
      templates: [
        {
          template_id: 7428,
          is_default: true,
          order_index: 0,
          template: {
            template_id: 7428,
            fitting_id: 11,
            name: "Main template",
            template_type: "manual",
            mounting_variant_key: "face_to_edge",
            is_default: true,
            points: [
              { id: 29, template_id: 7428, diameter_mm: 7, order_index: 0, quantity: 1 },
              { id: 30, template_id: 7428, diameter_mm: 4.5, order_index: 1, quantity: 1 },
            ],
          },
        },
      ],
    });

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/mounting-nodes/1");
    assert.equal(calls[0].options.method, "PATCH");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-7");
    assert.deepEqual(JSON.parse(calls[0].options.body), {
      code: "node-1",
      name: "Node 1",
      items: [
        {
          fitting_id: 11,
          quantity: 2,
          role: "primary",
          is_required: true,
          affects_processing: true,
          order_index: 1,
        },
      ],
      templates: [
        {
          template_id: 7428,
          is_default: true,
          order_index: 0,
          template: {
            template_id: 7428,
            fitting_id: 11,
            name: "Main template",
            template_type: "manual",
            mounting_variant_key: "face_to_edge",
            is_default: true,
            points: [
              { id: 29, template_id: 7428, diameter_mm: 7, order_index: 0, quantity: 1 },
              { id: 30, template_id: 7428, diameter_mm: 4.5, order_index: 1, quantity: 1 },
            ],
          },
        },
      ],
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});
