import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingNodesBreadcrumbItems,
  buildMountingNodesRestoreState,
  buildMountingNodesRestoredRoute,
  buildMountingNodesListRestoreState,
  buildMountingNodesRouteForMode,
  buildMountingNodesRouteUrl,
  createMountingNodesDetailRestoreCoordinator,
  normalizeMountingNodesRoute,
  parseMountingNodesRoute,
  resolveMountingNodesCategoryCode,
  shouldPreserveMountingNodeEditorWorkspace,
  shouldHydrateMountingNodeDetail,
} from "../src/mountingNodesNavigation.js";

test("mounting nodes route parser keeps the all-nodes list URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=list"), {
    mode: "list",
    nodeId: null,
    categoryCode: undefined,
  });
});

test("legacy detail URL is normalized to the unified list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail&node=9"), {
    mode: "list",
    nodeId: null,
    categoryCode: undefined,
  });
});

test("mounting nodes route parser recognizes the editor URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=editor&node=9"), {
    mode: "editor",
    nodeId: 9,
    categoryCode: undefined,
  });
});

test("mounting nodes route parser recognizes the create URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=create"), {
    mode: "create",
    nodeId: null,
    categoryCode: undefined,
  });
});

test("mounting nodes route parser recognizes the categories URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=categories"), {
    mode: "categories",
    nodeId: null,
    categoryCode: null,
  });
});

test("mounting nodes route builder preserves unrelated query params", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "list", nodeId: null }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=list",
  );
});

test("mounting nodes route keeps a legacy fastening type as a catalog filter", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=list&fastening_type=confirmat"), {
    mode: "list",
    nodeId: null,
    categoryCode: undefined,
    fasteningType: "confirmat",
  });
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "list", nodeId: null, fasteningType: "confirmat" }),
    "?section=mounting-nodes&mode=list&fastening_type=confirmat",
  );
});

test("mounting nodes route parser keeps the NULL category list as a list URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=list&category=null"), {
    mode: "list",
    nodeId: null,
    categoryCode: "null",
  });
});

test("mounting nodes route builder keeps the category filter in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "list", nodeId: null, categoryCode: "hinges" }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=list&category=hinges",
  );
});

test("mounting nodes route builder keeps the NULL category list in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "list", nodeId: null, categoryCode: "null" }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=list&category=null",
  );
});

test("legacy detail route builder normalizes to the unified list", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "detail", nodeId: 9, categoryCode: "hinges" }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=list&category=hinges",
  );
});

test("mounting nodes route builder keeps the editor node in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "editor", nodeId: 9, categoryCode: "hinges" }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=editor&node=9&category=hinges",
  );
});

test("mounting nodes route builder keeps the create mode in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "create", nodeId: null, categoryCode: "hinges" }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=create&category=hinges",
  );
});

test("fastening list context survives detail and toolbar returns", () => {
  const list = normalizeMountingNodesRoute({ mode: "list", categoryCode: "fastening", fasteningType: "confirmat" });
  const detail = buildMountingNodesRouteForMode(list, "detail", 9);
  const returned = buildMountingNodesRouteForMode(detail, "list");

  assert.equal(detail.categoryCode, "fastening");
  assert.equal(detail.fasteningType, "confirmat");
  assert.deepEqual(returned, list);
  assert.equal(buildMountingNodesRouteUrl(returned), "?section=mounting-nodes&mode=list&category=fastening&fastening_type=confirmat");
});

test("browser history restores fastening context through editor and back", () => {
  const editor = parseMountingNodesRoute("?section=mounting-nodes&mode=editor&node=9&category=fastening&fastening_type=confirmat");
  const restored = buildMountingNodesRestoredRoute(editor, 9);
  const list = buildMountingNodesRouteForMode(restored, "list");

  assert.equal(restored.categoryCode, "fastening");
  assert.equal(restored.fasteningType, "confirmat");
  assert.equal(buildMountingNodesListRestoreState(list, { activeCategoryFilter: "all", selectedFasteningType: null }).activeCategoryFilter, "fastening");
  assert.equal(buildMountingNodesListRestoreState(list).selectedFasteningType, "confirmat");
});

test("explicit reset is the only transition to the all-nodes route", () => {
  const filtered = normalizeMountingNodesRoute({ mode: "list", categoryCode: "fastening", fasteningType: "confirmat" });
  const reset = normalizeMountingNodesRoute({ mode: "list", categoryCode: undefined, fasteningType: null });

  assert.equal(buildMountingNodesRouteForMode(filtered, "list").categoryCode, "fastening");
  assert.equal(reset.categoryCode, undefined);
  assert.equal(buildMountingNodesRouteUrl(reset), "?section=mounting-nodes&mode=list");
  assert.equal(buildMountingNodesListRestoreState(reset, { activeCategoryFilter: "fastening" }).activeCategoryFilter, "all");
});

test("mounting nodes breadcrumb builder renders the categories page", () => {
  assert.deepEqual(
    buildMountingNodesBreadcrumbItems({
      language: "uk",
      listLabel: "Монтажні вузли",
      mode: "categories",
    }),
    [
      {
        current: true,
        label: "Монтажні вузли",
        title: "Монтажні вузли",
      },
    ],
  );
});

test("mounting nodes breadcrumb builder renders the unified list page", () => {
  const items = buildMountingNodesBreadcrumbItems({
    allListLabel: "Усі монтажні вузли",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "list",
    onOpenCategories: () => {},
  });

  assert.equal(items.length, 1);
  assert.equal(items[0].label, "Монтажні вузли");
  assert.equal(items[0].current, true);
});

test("legacy categorized detail breadcrumb contains only the unified list entry", () => {
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "hinges",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "detail",
    nodeName: "петля",
  });

  assert.equal(items.length, 1);
  assert.equal(items[0].label, "Монтажні вузли");
  assert.equal(items[0].current, false);
});

test("mounting nodes breadcrumb builder renders list and node in the editor", () => {
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "hinges",
    editingLabel: "Редагування вузла",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "editor",
    nodeName: "петля",
  });

  assert.equal(items.length, 2);
  assert.equal(items[0].label, "Монтажні вузли");
  assert.equal(items[1].label, "петля");
  assert.equal(items[1].current, true);
});

test("legacy uncategorized detail breadcrumb contains only the unified list entry", () => {
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "null",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "detail",
    nodeName: "Безіменний вузол",
  });

  assert.equal(items.length, 1);
  assert.equal(items[0].label, "Монтажні вузли");
  assert.equal(items[0].current, false);
});

test("mounting nodes breadcrumb builder renders create directly under the unified list", () => {
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "hinges",
    createLabel: "Створення вузла",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "create",
  });

  assert.equal(items.length, 2);
  assert.equal(items[0].label, "Монтажні вузли");
  assert.equal(items[1].current, true);
  assert.equal(items[1].label, "Створення вузла");
});

test("mounting nodes route parser normalizes unknown modes to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=grid"), {
    mode: "list",
    nodeId: null,
    categoryCode: null,
  });
});

test("mounting nodes route parser normalizes detail without node to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail"), {
    mode: "list",
    nodeId: null,
    categoryCode: undefined,
  });
});

test("mounting nodes route parser normalizes editor without node to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=editor"), {
    mode: "list",
    nodeId: null,
    categoryCode: null,
  });
});

test("mounting nodes route parser normalizes invalid node ids to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail&node=abc"), {
    mode: "list",
    nodeId: null,
    categoryCode: undefined,
  });
});

test("mounting nodes route parser normalizes editor with invalid node ids to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=editor&node=0"), {
    mode: "list",
    nodeId: null,
    categoryCode: null,
  });
});

test("mounting nodes route normalizer returns the safe default shape", () => {
  assert.deepEqual(normalizeMountingNodesRoute({ mode: "detail", nodeId: 0 }), {
    mode: "list",
    nodeId: null,
    categoryCode: undefined,
  });
});

test("legacy detail restore state collapses to the unified list", () => {
  const state = buildMountingNodesRestoreState({ mode: "detail", nodeId: 9 }, { id: 9, name: "РџРµС‚Р»СЏ" });
  assert.equal(state.mountingNodesViewMode, "list");
  assert.equal(state.selectedNodeId, "");
  assert.equal(state.selectedNodeDetail, null);
  assert.deepEqual(state.nodes, []);
  assert.deepEqual(state.nodeDetailsById, {});
});

test("mounting nodes restore state uses the fresh node detail for editor URLs", () => {
  const nodeDetail = {
    id: 9,
    name: "РџРµС‚Р»СЏ",
  };

  assert.deepEqual(
    buildMountingNodesRestoreState({ mode: "editor", nodeId: 9 }, nodeDetail),
    {
      activeStatusFilter: "all",
      ownershipFilter: "all",
      sortOrder: "name-asc",
      selectedFasteningType: null,
      activeCategoryFilter: "all",
      activeVariantFilter: "all",
      appliedSearch: "",
      displayMode: "grid",
      listError: "",
      listLoading: false,
      mountingNodesViewMode: "editor",
      nodeDetailErrorsById: {},
      nodeDetailsById: {
        9: nodeDetail,
      },
      nodes: [nodeDetail],
      restoreScrollOnMount: false,
      scrollPosition: null,
      searchInput: "",
      selectedNodeDetail: nodeDetail,
      selectedNodeId: "9",
      selectedNodeLoading: false,
    },
  );
});

test("mounting nodes restore state keeps the category filter when restoring a filtered list", () => {
  assert.deepEqual(
    buildMountingNodesRestoreState({ mode: "list", nodeId: null, categoryCode: "hinges" }, null),
    {
      activeStatusFilter: "all",
      ownershipFilter: "all",
      sortOrder: "name-asc",
      selectedFasteningType: null,
      activeCategoryFilter: "hinges",
      activeVariantFilter: "all",
      appliedSearch: "",
      displayMode: "grid",
      listError: "",
      listLoading: false,
      mountingNodesViewMode: "list",
      nodeDetailErrorsById: {},
      nodeDetailsById: {},
      nodes: [],
      restoreScrollOnMount: false,
      scrollPosition: null,
      searchInput: "",
      selectedNodeDetail: null,
      selectedNodeId: "",
      selectedNodeLoading: false,
    },
  );
});

test("mounting nodes restored route keeps editor mode for editor requests", () => {
  assert.deepEqual(
    buildMountingNodesRestoredRoute({ mode: "editor", nodeId: 9 }, 9),
    {
      mode: "editor",
      nodeId: 9,
      categoryCode: undefined,
    },
  );
});

test("legacy detail restored route falls back to the unified list", () => {
  assert.deepEqual(
    buildMountingNodesRestoredRoute({ mode: "detail", nodeId: 9 }, 9),
    {
      mode: "list",
      nodeId: null,
      categoryCode: undefined,
    },
  );
});

test("mounting nodes category resolver keeps absent and null categories separate", () => {
  assert.equal(resolveMountingNodesCategoryCode(undefined, "hinges"), "hinges");
  assert.equal(resolveMountingNodesCategoryCode(null, "hinges"), "null");
  assert.equal(resolveMountingNodesCategoryCode(undefined, "null"), "null");
});

test("mounting nodes restore state keeps create mode isolated from node details", () => {
  assert.deepEqual(
    buildMountingNodesRestoreState({ mode: "create", nodeId: null }, null),
    {
      activeStatusFilter: "all",
      ownershipFilter: "all",
      sortOrder: "name-asc",
      selectedFasteningType: null,
      activeCategoryFilter: "all",
      activeVariantFilter: "all",
      appliedSearch: "",
      displayMode: "grid",
      listError: "",
      listLoading: false,
      mountingNodesViewMode: "create",
      nodeDetailErrorsById: {},
      nodeDetailsById: {},
      nodes: [],
      restoreScrollOnMount: false,
      scrollPosition: null,
      searchInput: "",
      selectedNodeDetail: null,
      selectedNodeId: "",
      selectedNodeLoading: false,
    },
  );
});

test("mounting nodes hydration guard hydrates only editor routes", () => {
  const hydratedNodeDetail = {
    id: 9,
    items: [],
    templates: [],
  };

  assert.equal(shouldHydrateMountingNodeDetail({ mode: "detail", nodeId: 9 }, null), false);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "editor", nodeId: 9 }, null), true);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "detail", nodeId: 9 }, hydratedNodeDetail), false);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "editor", nodeId: 9 }, hydratedNodeDetail), false);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "detail", nodeId: 9 }, { id: 10, items: [], templates: [] }), false);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "create", nodeId: null }, null), false);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "list", nodeId: null }, null), false);
});

test("mounting node editor workspace guard preserves hydrated editor context", () => {
  assert.equal(
    shouldPreserveMountingNodeEditorWorkspace(
      {
        mode: "editor",
        nodeId: 13,
      },
      {
        mountingNodeId: "13",
        nodeDetail: { id: 13, items: [], templates: [] },
      },
    ),
    true,
  );

  assert.equal(
    shouldPreserveMountingNodeEditorWorkspace(
      {
        mode: "editor",
        nodeId: 13,
      },
      {
        mountingNodeId: "13",
        nodeDetail: null,
      },
    ),
    false,
  );

  assert.equal(
    shouldPreserveMountingNodeEditorWorkspace(
      {
        mode: "detail",
        nodeId: 13,
      },
      {
        mountingNodeId: "13",
        nodeDetail: { id: 13, items: [], templates: [] },
      },
    ),
    false,
  );
});

test("mounting nodes detail restore coordinator reuses the active request for the same node", async () => {
  const coordinator = createMountingNodesDetailRestoreCoordinator();
  let resolveRestore;

  const firstPromise = coordinator.run(9, () => new Promise((resolve) => {
    resolveRestore = resolve;
  }));
  const secondPromise = coordinator.run(9, () => Promise.resolve({ success: true, marker: "second" }));

  assert.strictEqual(firstPromise, secondPromise);

  await Promise.resolve();
  resolveRestore({ success: true, marker: "first" });
  assert.deepEqual(await firstPromise, { success: true, marker: "first" });
});

test("mounting nodes detail restore coordinator allows the same node after completion", async () => {
  const coordinator = createMountingNodesDetailRestoreCoordinator();
  let runCount = 0;

  await coordinator.run(9, async ({ requestId, isCurrent, restoreKey }) => {
    runCount += 1;
    assert.equal(requestId, 1);
    assert.equal(restoreKey, "detail:9");
    assert.equal(isCurrent(), true);
    return { success: true, requestId };
  });

  const result = await coordinator.run(9, async ({ requestId, isCurrent }) => {
    runCount += 1;
    assert.equal(requestId, 2);
    assert.equal(isCurrent(), true);
    return { success: true, requestId };
  });

  assert.equal(runCount, 2);
  assert.deepEqual(result, { success: true, requestId: 2 });
});

test("returning to list invalidates an unfinished detail restore", async () => {
  const coordinator = createMountingNodesDetailRestoreCoordinator();
  let resolveRestore;
  const pending = coordinator.run(9, async ({ isCurrent }) => {
    await new Promise((resolve) => { resolveRestore = resolve; });
    return { applied: isCurrent() };
  });

  await Promise.resolve();
  coordinator.reset();
  resolveRestore();
  assert.deepEqual(await pending, { applied: false });
});
