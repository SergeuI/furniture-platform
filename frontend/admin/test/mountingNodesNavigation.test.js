import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingNodesBreadcrumbItems,
  buildMountingNodesRestoreState,
  buildMountingNodesRestoredRoute,
  buildMountingNodesRouteUrl,
  createMountingNodesDetailRestoreCoordinator,
  normalizeMountingNodesRoute,
  parseMountingNodesRoute,
  shouldPreserveMountingNodeEditorWorkspace,
  shouldHydrateMountingNodeDetail,
} from "../src/mountingNodesNavigation.js";

test("mounting nodes route parser normalizes the list URL to categories", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=list"), {
    mode: "categories",
    nodeId: null,
    categoryCode: null,
  });
});

test("mounting nodes route parser recognizes the detail URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail&node=9"), {
    mode: "detail",
    nodeId: 9,
    categoryCode: null,
  });
});

test("mounting nodes route parser recognizes the editor URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=editor&node=9"), {
    mode: "editor",
    nodeId: 9,
    categoryCode: null,
  });
});

test("mounting nodes route parser recognizes the create URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=create"), {
    mode: "create",
    nodeId: null,
    categoryCode: null,
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
    "?foo=bar&section=mounting-nodes&mode=categories",
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

test("mounting nodes route builder keeps the detail node in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "detail", nodeId: 9, categoryCode: "hinges" }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=detail&node=9&category=hinges",
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

test("mounting nodes breadcrumb builder renders the all list page", () => {
  const items = buildMountingNodesBreadcrumbItems({
    allListLabel: "Усі монтажні вузли",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "list",
    onOpenCategories: () => {},
  });

  assert.equal(items.length, 2);
  assert.equal(items[0].label, "Монтажні вузли");
  assert.equal(typeof items[0].onClick, "function");
  assert.equal(items[1].current, true);
  assert.equal(items[1].label, "Усі монтажні вузли");
});

test("mounting nodes breadcrumb builder renders a categorized detail page", () => {
  const clicked = [];
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "hinges",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "detail",
    nodeName: "петля",
    onOpenCategories: () => clicked.push("categories"),
    onOpenCategoryList: () => clicked.push("category"),
  });

  assert.equal(items.length, 3);
  assert.equal(items[1].label, "Завіси");
  assert.equal(items[1].current, undefined);
  items[1].onClick();
  assert.deepEqual(clicked, ["category"]);
  assert.equal(items[2].label, "петля");
  assert.equal(items[2].current, true);
});

test("mounting nodes breadcrumb builder renders the editor page", () => {
  const clicked = [];
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "hinges",
    editingLabel: "Редагування вузла",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "editor",
    nodeName: "петля",
    onOpenCategoryList: () => clicked.push("category"),
    onOpenNodeDetail: () => clicked.push("detail"),
  });

  assert.equal(items.length, 4);
  assert.equal(items[1].label, "Завіси");
  assert.equal(items[2].label, "петля");
  items[2].onClick();
  assert.deepEqual(clicked, ["detail"]);
  assert.equal(items[3].current, true);
  assert.equal(items[3].label, "Редагування вузла");
});

test("mounting nodes breadcrumb builder renders uncategorized detail pages", () => {
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "null",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "detail",
    nodeName: "Безіменний вузол",
  });

  assert.equal(items.length, 3);
  assert.equal(items[1].label, "Без категорії");
  assert.equal(items[2].label, "Безіменний вузол");
});

test("mounting nodes breadcrumb builder renders create pages inside a category", () => {
  const items = buildMountingNodesBreadcrumbItems({
    categoryCode: "hinges",
    createLabel: "Створення вузла",
    language: "uk",
    listLabel: "Монтажні вузли",
    mode: "create",
  });

  assert.equal(items.length, 3);
  assert.equal(items[1].label, "Завіси");
  assert.equal(items[2].current, true);
  assert.equal(items[2].label, "Створення вузла");
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
    categoryCode: null,
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
    categoryCode: null,
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
    categoryCode: null,
  });
});

test("mounting nodes restore state uses the fresh node detail for detail URLs", () => {
  const nodeDetail = {
    id: 9,
    name: "РџРµС‚Р»СЏ",
  };

  assert.deepEqual(
    buildMountingNodesRestoreState({ mode: "detail", nodeId: 9 }, nodeDetail),
    {
      activeStatusFilter: "all",
      activeCategoryFilter: "all",
      activeVariantFilter: "all",
      appliedSearch: "",
      displayMode: "grid",
      listError: "",
      listLoading: false,
      mountingNodesViewMode: "detail",
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

test("mounting nodes restore state uses the fresh node detail for editor URLs", () => {
  const nodeDetail = {
    id: 9,
    name: "РџРµС‚Р»СЏ",
  };

  assert.deepEqual(
    buildMountingNodesRestoreState({ mode: "editor", nodeId: 9 }, nodeDetail),
    {
      activeStatusFilter: "all",
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
      categoryCode: null,
    },
  );
});

test("mounting nodes restored route falls back to detail mode for detail requests", () => {
  assert.deepEqual(
    buildMountingNodesRestoredRoute({ mode: "detail", nodeId: 9 }, 9),
    {
      mode: "detail",
      nodeId: 9,
      categoryCode: null,
    },
  );
});

test("mounting nodes restore state keeps create mode isolated from node details", () => {
  assert.deepEqual(
    buildMountingNodesRestoreState({ mode: "create", nodeId: null }, null),
    {
      activeStatusFilter: "all",
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

test("mounting nodes hydration guard requires a fresh detail fetch for editor and detail routes without node data", () => {
  const hydratedNodeDetail = {
    id: 9,
    items: [],
    templates: [],
  };

  assert.equal(shouldHydrateMountingNodeDetail({ mode: "detail", nodeId: 9 }, null), true);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "editor", nodeId: 9 }, null), true);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "detail", nodeId: 9 }, hydratedNodeDetail), false);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "editor", nodeId: 9 }, hydratedNodeDetail), false);
  assert.equal(shouldHydrateMountingNodeDetail({ mode: "detail", nodeId: 9 }, { id: 10, items: [], templates: [] }), true);
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
