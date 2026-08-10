import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingSchemePayload,
  buildMountingSchemesRouteUrl,
  collectDistinctGroupKeys,
  createEmptyMountingSchemeDraft,
  getMountingSchemeValidationMessage,
  getMountingSchemesWorkspaceChrome,
  normalizeMountingSchemesRoute,
  parseMountingSchemesRoute,
  syncPlacementRulesWithGroupKeys,
  validateMountingSchemeDraft,
} from "../src/mountingSchemesWorkspace.js";

test("mounting-schemes route roundtrips through query params", () => {
  const parsed = parseMountingSchemesRoute("?section=mounting-schemes&mode=detail&scheme=42");
  assert.deepEqual(parsed, {
    mode: "detail",
    schemeId: "42",
  });

  const url = buildMountingSchemesRouteUrl(parsed, "?foo=bar");
  assert.equal(url, "?foo=bar&section=mounting-schemes&mode=detail&scheme=42");
});

test("mounting-schemes payload normalizes nested nodes and rules", () => {
  const payload = buildMountingSchemePayload({
    code: "  demo-scheme  ",
    name: "  Demo scheme  ",
    description: "  ",
    is_active: false,
    nodes: [
      {
        node_id: "12",
        group_key: "primary",
        quantity_per_group: "2",
        role_code: "",
        order_index: "3",
        is_required: 1,
      },
    ],
    placement_rules: [
      {
        group_key: "primary",
        distribution_mode: "equal",
        min_group_count: "2",
        max_group_count: "",
        fixed_group_count: "",
        start_offset_mm: "50",
        end_offset_mm: "",
        max_spacing_mm: "400",
        fixed_spacing_mm: "",
      },
    ],
  });

  assert.equal(payload.code, "demo-scheme");
  assert.equal(payload.name, "Demo scheme");
  assert.equal(payload.description, undefined);
  assert.equal(payload.is_active, false);
  assert.deepEqual(payload.nodes[0], {
    node_id: 12,
    group_key: "primary",
    quantity_per_group: 2,
    role_code: undefined,
    order_index: 3,
    is_required: true,
  });
  assert.equal(payload.placement_rules[0].group_key, "primary");
  assert.equal(payload.placement_rules[0].start_offset_mm, 50);
  assert.equal(payload.placement_rules[0].end_offset_mm, undefined);
});

test("mounting-schemes validation catches obvious frontend mistakes", () => {
  const errors = validateMountingSchemeDraft({
    name: "",
    nodes: [
      {
        node_id: "",
        group_key: "",
        quantity_per_group: 0,
      },
    ],
    placement_rules: [
      {
        group_key: "missing",
        distribution_mode: "bogus",
        min_group_count: 0,
      },
    ],
  });

  assert(errors.some((message) => message.includes("Name is required")));
  assert(errors.some((message) => message.includes("node is required")));
  assert(errors.some((message) => message.includes("group key is required")));
  assert(errors.some((message) => message.includes("quantity per group must be greater than 0")));
  assert(errors.some((message) => message.includes("distribution mode is invalid")));
});

test("mounting-schemes helper keeps placement rules aligned with node groups", () => {
  const synced = syncPlacementRulesWithGroupKeys(
    [{ group_key: "secondary", distribution_mode: "equal" }],
    ["primary", "joint"],
  );

  assert.deepEqual(
    collectDistinctGroupKeys([{ group_key: "joint" }, { group_key: "primary" }, { group_key: "primary" }]),
    ["joint", "primary"],
  );
  assert.deepEqual(
    synced.map((rule) => rule.group_key),
    ["primary", "joint"],
  );
});

test("mounting-schemes route normalization defaults to list", () => {
  assert.deepEqual(normalizeMountingSchemesRoute({}), {
    mode: "list",
    schemeId: "",
  });
});

test("mounting-schemes dev proxy forwards to the backend route", async () => {
  const viteConfigModule = await import("../vite.config.js");
  const config = viteConfigModule.default({ command: "serve" });

  assert.equal(config.server.proxy["/mounting-schemes"], "http://127.0.0.1:8000");
});

test("mounting-schemes list helper uses the canonical endpoint and treats HTML as transport error", async () => {
  const { listMountingSchemes } = await import("../src/api.js");
  const originalFetch = global.fetch;
  let seenUrl = "";

  global.fetch = async (url) => {
    seenUrl = String(url);
    return {
      ok: true,
      status: 200,
      text: async () => "<!doctype html><html><body>App shell</body></html>",
    };
  };

  try {
    const result = await listMountingSchemes("token");

    assert.equal(seenUrl.endsWith("/mounting-schemes"), true);
    assert.equal(result.success, false);
    assert.equal(result.error, "Server returned an HTML error page (HTTP 200)");
  } finally {
    global.fetch = originalFetch;
  }
});

test("mounting-schemes list helper keeps an empty JSON response as an empty list", async () => {
  const { listMountingSchemes } = await import("../src/api.js");
  const originalFetch = global.fetch;
  let seenUrl = "";

  global.fetch = async (url) => {
    seenUrl = String(url);
    return {
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ success: true, schemes: [], error: null }),
    };
  };

  try {
    const result = await listMountingSchemes("token");

    assert.equal(seenUrl.endsWith("/mounting-schemes"), true);
    assert.equal(result.success, true);
    assert.deepEqual(result.schemes, []);
    assert.equal(result.error, null);
  } finally {
    global.fetch = originalFetch;
  }
});

test("mounting-schemes validation stays hidden until submit and localizes the first error", () => {
  const draft = createEmptyMountingSchemeDraft();

  assert.equal(getMountingSchemeValidationMessage(draft, { language: "uk", visible: false }), "");
  assert.equal(getMountingSchemeValidationMessage(draft, { language: "uk", visible: true }), "Вкажіть назву схеми.");
});

test("mounting-schemes workspace chrome keeps only the expected actions per mode", () => {
  assert.deepEqual(getMountingSchemesWorkspaceChrome("list"), {
    showHero: false,
    listPanelTitleVisible: false,
    listCreateActionCount: 1,
    emptyStateCreateActionCount: 0,
    backActionCount: 0,
    saveActionCount: 0,
    editActionCount: 0,
    nodeEmptyStateAddActionCount: 0,
    ruleEmptyStateAddActionCount: 0,
  });

  assert.deepEqual(getMountingSchemesWorkspaceChrome("create"), {
    showHero: false,
    listPanelTitleVisible: true,
    listCreateActionCount: 0,
    emptyStateCreateActionCount: 0,
    backActionCount: 1,
    saveActionCount: 1,
    editActionCount: 0,
    nodeEmptyStateAddActionCount: 0,
    ruleEmptyStateAddActionCount: 0,
  });

  assert.deepEqual(getMountingSchemesWorkspaceChrome("detail"), {
    showHero: false,
    listPanelTitleVisible: true,
    listCreateActionCount: 0,
    emptyStateCreateActionCount: 0,
    backActionCount: 1,
    saveActionCount: 0,
    editActionCount: 1,
    nodeEmptyStateAddActionCount: 0,
    ruleEmptyStateAddActionCount: 0,
  });
});
