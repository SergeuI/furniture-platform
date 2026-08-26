import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  API_BASE_URL,
  applyEntitlementRegistrySync,
  createMaterial,
  refreshMaterialGallery,
  refreshMaterialRecommendedEdges,
  deleteMountingNode,
  createMountingNode,
  getMountingNode,
  getMountingNodes,
  importMaterialFromViyar,
  previewEntitlementRegistrySync,
  listProjects,
  getProjectQuota,
  updateMountingNode,
  updateMaterial,
} from "../src/api.js";

test("material create and source import wrappers keep the 120 second timeout semantics", () => {
  const source = readFileSync(new URL("../src/api.js", import.meta.url), "utf8");

  assert.match(source, /export async function importMaterialFromViyar[\s\S]*timeoutMs: 120000,/);
  assert.match(source, /export async function createMaterial[\s\S]*timeoutMs: 120000,/);
});

test("material import wrappers resolve immediately when the backend returns a fast failure payload", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: false, error: "Не вдалося отримати дані товару від VIYAR..." }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await createMaterial("token-1", {
      article: "K533",
      category: "dsp",
      city: "kyiv",
      source_url: "https://viyar.ua/ua/catalog/example/",
    });

    assert.equal(result.success, false);
    assert.equal(result.error, "Не вдалося отримати дані товару від VIYAR...");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/catalog/materials");
    assert.equal(calls[0].options.method, "POST");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("material import wrappers surface immediate network rejection without waiting for a timeout", async () => {
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async () => {
    throw new TypeError("fetch failed");
  };

  try {
    const result = await importMaterialFromViyar(
      "token-1",
      "K533",
      "dsp",
      "https://viyar.ua/ua/catalog/example/",
      false,
    );

    assert.equal(result.success, false);
    assert.equal(result.status, 0);
    assert.match(result.error, /fetch failed/i);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("material source import dev timing logs request lifecycle", async () => {
  const originalFetch = globalThis.fetch;
  const originalTimingFlag = globalThis.__FURNITURE_ADMIN_DEV_TIMING__;
  const originalConsoleInfo = console.info;
  const logs = [];

  globalThis.__FURNITURE_ADMIN_DEV_TIMING__ = true;
  console.info = (...args) => {
    logs.push(args.join(" "));
  };

  globalThis.fetch = async () =>
    new Response(JSON.stringify({ success: false, error: "Material not found or unavailable." }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  try {
    const result = await createMaterial("token-1", {
      article: "K533",
      category: "dsp",
      city: "kyiv",
      source_url: "https://viyar.ua/ua/catalog/example/",
    });

    assert.equal(result.success, false);
    assert.ok(logs.some((line) => line.includes("material-source-import request started")));
    assert.ok(logs.some((line) => line.includes("material-source-import request resolved")));
    assert.ok(logs.some((line) => line.includes("elapsed_ms=")));
    assert.ok(logs.some((line) => line.includes("status=200")));
    assert.ok(logs.some((line) => line.includes("success=false")));
  } finally {
    globalThis.fetch = originalFetch;
    console.info = originalConsoleInfo;
    globalThis.__FURNITURE_ADMIN_DEV_TIMING__ = originalTimingFlag;
  }
});

test("material import submit handler stops after gallery for source imports", () => {
  const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
  const handlerStart = source.indexOf("async function handleImportMaterial(event) {");
  assert.ok(handlerStart >= 0, "handleImportMaterial not found");

  const handlerSnippet = source.slice(handlerStart, handlerStart + 12000);
  assert.match(handlerSnippet, /await createMaterial\(token, payload\);/);
  assert.match(handlerSnippet, /await refreshMaterialGallery\(token, refreshedMaterialId\);/);
  assert.match(handlerSnippet, /Отримуємо дані матеріалу/);
  assert.match(handlerSnippet, /Завантажуємо фотографії/);
  assert.match(handlerSnippet, /Матеріал готовий/);
  assert.match(handlerSnippet, /Матеріал додано, але не всі фотографії вдалося завантажити\./);
  assert.doesNotMatch(handlerSnippet, /refreshMaterialRecommendedEdges/);
  assert.doesNotMatch(handlerSnippet, /Шукаємо рекомендовані крайки/);
  assert.ok(
    handlerSnippet.indexOf("setMaterialImportWorking(false);") < handlerSnippet.indexOf("await loadMaterialsCatalog(token);"),
    "material import overlay should close before catalog reload",
  );
  assert.match(handlerSnippet, /finally \{[\s\S]*setLoading\(false\);[\s\S]*setMaterialImportWorking\(false\);[\s\S]*resetMaterialImportProgress\(\);/);
});

test("material import handler no longer references recommended-edge warnings", () => {
  const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
  const handlerStart = source.indexOf("async function handleImportMaterial(event) {");
  assert.ok(handlerStart >= 0, "handleImportMaterial not found");

  const handlerSnippet = source.slice(handlerStart, handlerStart + 12000);
  assert.doesNotMatch(handlerSnippet, /edgesSummary\.needs_review/);
  assert.doesNotMatch(handlerSnippet, /edgesHasIssues/);
  assert.doesNotMatch(handlerSnippet, /рекомендована крайка потребує перевірки/);
  assert.doesNotMatch(handlerSnippet, /Recommended edges could not be updated yet/);
});

test("material refresh handler stops after gallery for existing materials", () => {
  const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
  const handlerStart = source.indexOf("async function handleRefreshMaterial(item) {");
  assert.ok(handlerStart >= 0, "handleRefreshMaterial not found");

  const handlerSnippet = source.slice(handlerStart, handlerStart + 12000);
  assert.match(handlerSnippet, /await refreshMaterialGallery\(token, refreshedMaterialId\);/);
  assert.match(handlerSnippet, /Фотографії збережено/);
  assert.match(handlerSnippet, /Матеріал готовий/);
  assert.match(handlerSnippet, /Матеріал додано, але не всі фотографії вдалося завантажити\./);
  assert.doesNotMatch(handlerSnippet, /refreshMaterialRecommendedEdges/);
  assert.doesNotMatch(handlerSnippet, /Шукаємо рекомендовані крайки/);
  assert.ok(
    handlerSnippet.indexOf("setMaterialImportWorking(false);") < handlerSnippet.indexOf("await loadMaterialsCatalog(token);"),
    "material refresh overlay should close before catalog reload",
  );
});

test("material refresh handler no longer references recommended-edge warnings", () => {
  const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
  const handlerStart = source.indexOf("async function handleRefreshMaterial(item) {");
  assert.ok(handlerStart >= 0, "handleRefreshMaterial not found");

  const handlerSnippet = source.slice(handlerStart, handlerStart + 12000);
  assert.doesNotMatch(handlerSnippet, /edgesSummary\.needs_review/);
  assert.doesNotMatch(handlerSnippet, /edgesHasIssues/);
  assert.doesNotMatch(handlerSnippet, /рекомендована крайка потребує перевірки/);
  assert.doesNotMatch(handlerSnippet, /Recommended edges could not be updated yet/);
});

test("background material catalog refresh keeps already visible data intact", () => {
  const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
  const loaderStart = source.indexOf("async function loadMaterialsCatalog(");
  assert.ok(loaderStart >= 0, "loadMaterialsCatalog not found");

  const loaderSnippet = source.slice(loaderStart, loaderStart + 7000);
  assert.doesNotMatch(loaderSnippet, /setMaterialItems\(\[\]\)/);
  assert.doesNotMatch(loaderSnippet, /setSelectedMaterialDetail\(null\)/);
  assert.doesNotMatch(loaderSnippet, /setSelectedMaterialSupplierOffers\(\[\]\)/);
  assert.match(loaderSnippet, /setMaterialItems\(result\.items \|\| \[\]\);/);
});

test("material detail releases core loading before supplier and owners hydration finishes", () => {
  const source = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
  const detailStart = source.indexOf("async function openMaterialDetails(item, options = {}) {");
  assert.ok(detailStart >= 0, "openMaterialDetails not found");

  const detailSnippet = source.slice(detailStart, detailStart + 11000);
  assert.ok(
    detailSnippet.indexOf("setMaterialDetailLoading(false);") < detailSnippet.indexOf("await listMaterialSupplierOffers"),
    "core material detail should stop loading before supplier offers hydration",
  );
  assert.ok(
    detailSnippet.indexOf("setMaterialDetailLoading(false);") < detailSnippet.indexOf("await loadMaterialOwners"),
    "core material detail should stop loading before owners hydration",
  );
});

test("material phase refresh wrappers hit the explicit gallery and edge refresh endpoints", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, material_id: 2126, summary: { discovered: 3, persisted: 3, failed: 0 } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const gallery = await refreshMaterialGallery("token-1", 2126);
    const edges = await refreshMaterialRecommendedEdges("token-1", 2126);

    assert.equal(gallery.success, true);
    assert.equal(edges.success, true);
    assert.deepEqual(calls.map((call) => call.url), [
      "/api/catalog/materials/2126/images/refresh",
      "/api/catalog/materials/2126/recommended-edges/refresh",
    ]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

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
      category_code: "hinges",
      is_active: false,
    });

    assert.equal(result.success, true);
    assert.deepEqual(result.nodes.map((node) => node.code), ["inactive-node"]);
    assert.equal(
      calls[0].url,
      "/api/mounting-nodes?search=confirmat&fitting_id=1&mounting_variant_key=face_to_edge&category_code=hinges&is_active=false&include_inactive=true",
    );
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-5");
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("mounting node list wrapper forwards the null category filter", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, nodes: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await getMountingNodes("token-5", {
      category_code: "null",
    });

    assert.equal(result.success, true);
    assert.equal(calls[0].url, "/api/mounting-nodes?category_code=null");
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

test("mounting node create wrapper sends a POST request with the create payload", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, node: { id: 42, code: "mn_confirmat_7x50" } }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await createMountingNode("token-7", {
      name: "Confirmat 7x50",
      description: "Demo node",
      is_active: true,
      items: [
        {
          fitting_id: 11,
          quantity: 2,
          role: "primary",
          is_required: true,
          affects_processing: true,
          order_index: 0,
        },
      ],
      templates: [
        {
          is_default: true,
          order_index: 0,
          template: {
            fitting_id: 11,
            name: "Confirmat 7x50 · Face to edge",
            template_type: "manual",
            mounting_variant_key: "face_to_edge",
            is_default: true,
            is_active: true,
            sync_points: true,
            points: [],
          },
        },
      ],
    });

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/mounting-nodes");
    assert.equal(calls[0].options.method, "POST");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-7");
    assert.deepEqual(JSON.parse(calls[0].options.body), {
      name: "Confirmat 7x50",
      description: "Demo node",
      is_active: true,
      items: [
        {
          fitting_id: 11,
          quantity: 2,
          role: "primary",
          is_required: true,
          affects_processing: true,
          order_index: 0,
        },
      ],
      templates: [
        {
          is_default: true,
          order_index: 0,
          template: {
            fitting_id: 11,
            name: "Confirmat 7x50 · Face to edge",
            template_type: "manual",
            mounting_variant_key: "face_to_edge",
            is_default: true,
            is_active: true,
            sync_points: true,
            points: [],
          },
        },
      ],
    });
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

test("mounting node delete wrapper sends a DELETE request with no extra payload", async () => {
  const calls = [];
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await deleteMountingNode("token-8", 17);

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/api/mounting-nodes/17");
    assert.equal(calls[0].options.method, "DELETE");
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-8");
    assert.equal(calls[0].options.body, undefined);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
