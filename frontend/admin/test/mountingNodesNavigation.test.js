import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingNodesRestoreState,
  buildMountingNodesRouteUrl,
  normalizeMountingNodesRoute,
  parseMountingNodesRoute,
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

test("mounting nodes route parser normalizes invalid node ids to list", () => {
  assert.deepEqual(parseMountingNodesRoute("?section=mounting-nodes&mode=detail&node=abc"), {
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
    name: "Петля",
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
      nodeDetailsById: {},
      nodes: [],
      restoreScrollOnMount: false,
      scrollPosition: null,
      searchInput: "",
      selectedNodeDetail: nodeDetail,
      selectedNodeId: "9",
      selectedNodeLoading: false,
    },
  );
});
