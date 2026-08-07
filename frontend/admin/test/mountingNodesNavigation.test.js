import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingNodesRestoreState,
  buildMountingNodesRestoredRoute,
  buildMountingNodesRouteUrl,
  createMountingNodesDetailRestoreCoordinator,
  normalizeMountingNodesRoute,
  parseMountingNodesRoute,
  shouldPreserveMountingNodeEditorWorkspace,
  shouldHydrateMountingNodeDetail,
} from "../src/mountingNodesNavigation.js";

test("mounting nodes route parser recognizes the list URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=list"), {
    mode: "list",
    nodeId: null,
  });
});

test("mounting nodes route parser recognizes the detail URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail&node=9"), {
    mode: "detail",
    nodeId: 9,
  });
});

test("mounting nodes route parser recognizes the editor URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=editor&node=9"), {
    mode: "editor",
    nodeId: 9,
  });
});

test("mounting nodes route parser recognizes the create URL", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=create"), {
    mode: "create",
    nodeId: null,
  });
});

test("mounting nodes route builder preserves unrelated query params", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "list", nodeId: null }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=list",
  );
});

test("mounting nodes route builder keeps the detail node in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "detail", nodeId: 9 }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=detail&node=9",
  );
});

test("mounting nodes route builder keeps the editor node in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "editor", nodeId: 9 }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=editor&node=9",
  );
});

test("mounting nodes route builder keeps the create mode in the URL", () => {
  assert.equal(
    buildMountingNodesRouteUrl({ mode: "create", nodeId: null }, "?foo=bar"),
    "?foo=bar&section=mounting-nodes&mode=create",
  );
});

test("mounting nodes route parser normalizes unknown modes to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=grid"), {
    mode: "list",
    nodeId: null,
  });
});

test("mounting nodes route parser normalizes detail without node to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail"), {
    mode: "list",
    nodeId: null,
  });
});

test("mounting nodes route parser normalizes editor without node to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=editor"), {
    mode: "list",
    nodeId: null,
  });
});

test("mounting nodes route parser normalizes invalid node ids to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail&node=abc"), {
    mode: "list",
    nodeId: null,
  });
});

test("mounting nodes route parser normalizes editor with invalid node ids to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=editor&node=0"), {
    mode: "list",
    nodeId: null,
  });
});

test("mounting nodes route normalizer returns the safe default shape", () => {
  assert.deepEqual(normalizeMountingNodesRoute({ mode: "detail", nodeId: 0 }), {
    mode: "list",
    nodeId: null,
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

test("mounting nodes restored route keeps editor mode for editor requests", () => {
  assert.deepEqual(
    buildMountingNodesRestoredRoute({ mode: "editor", nodeId: 9 }, 9),
    {
      mode: "editor",
      nodeId: 9,
    },
  );
});

test("mounting nodes restored route falls back to detail mode for detail requests", () => {
  assert.deepEqual(
    buildMountingNodesRestoredRoute({ mode: "detail", nodeId: 9 }, 9),
    {
      mode: "detail",
      nodeId: 9,
    },
  );
});

test("mounting nodes restore state keeps create mode isolated from node details", () => {
  assert.deepEqual(
    buildMountingNodesRestoreState({ mode: "create", nodeId: null }, null),
    {
      activeStatusFilter: "all",
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
