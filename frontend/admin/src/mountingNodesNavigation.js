const MOUNTING_NODES_SECTION = "mounting-nodes";

function normalizeSearchParams(value) {
  if (value instanceof URLSearchParams) {
    return new URLSearchParams(value.toString());
  }

  return new URLSearchParams(String(value || "").replace(/^[?#]/, ""));
}

function normalizeMountingNodeId(value) {
  const rawValue = String(value || "").trim();

  if (!rawValue) {
    return null;
  }

  const parsedValue = Number(rawValue);

  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null;
}

function buildMountingNodesDetailRestoreKey(nodeId) {
  const normalizedNodeId = normalizeMountingNodeId(nodeId);

  return normalizedNodeId === null ? "" : `detail:${normalizedNodeId}`;
}

export function normalizeMountingNodesRoute(route = {}) {
  const mode = String(route?.mode || "").trim();
  const nodeId = normalizeMountingNodeId(route?.nodeId);

  if ((mode === "detail" || mode === "editor") && nodeId !== null) {
    return {
      mode,
      nodeId,
    };
  }

  if (mode === "create") {
    return {
      mode,
      nodeId: null,
    };
  }

  return {
    mode: "list",
    nodeId: null,
  };
}

export function parseMountingNodesRoute(search = "") {
  const params = normalizeSearchParams(search);

  if (String(params.get("section") || "").trim() !== MOUNTING_NODES_SECTION) {
    return null;
  }

  return normalizeMountingNodesRoute({
    mode: params.get("mode"),
    nodeId: params.get("node"),
  });
}

export function buildMountingNodesRouteUrl(route = {}, currentSearch = "") {
  const params = normalizeSearchParams(currentSearch);
  const normalizedRoute = normalizeMountingNodesRoute(route);

  params.set("section", MOUNTING_NODES_SECTION);
  params.set("mode", normalizedRoute.mode);

  if (normalizedRoute.nodeId === null) {
    params.delete("node");
  } else {
    params.set("node", String(normalizedRoute.nodeId));
  }

  const queryString = params.toString();
  return queryString ? `?${queryString}` : "";
}

export function buildMountingNodesRestoreState(route = {}, nodeDetail = null) {
  const normalizedRoute = normalizeMountingNodesRoute(route);
  const restoredNodeDetail =
    nodeDetail && typeof nodeDetail === "object" && normalizedRoute.mode !== "list" ? nodeDetail : null;
  const restoredNodeId = restoredNodeDetail ? String(restoredNodeDetail.id || restoredNodeDetail.node_id || normalizedRoute.nodeId || "") : "";

  return {
    activeStatusFilter: "all",
    activeVariantFilter: "all",
    appliedSearch: "",
    displayMode: "grid",
    listError: "",
    listLoading: false,
    mountingNodesViewMode: normalizedRoute.mode,
    nodeDetailErrorsById: {},
    nodeDetailsById: restoredNodeDetail && restoredNodeId ? { [restoredNodeId]: restoredNodeDetail } : {},
    nodes: restoredNodeDetail ? [restoredNodeDetail] : [],
    restoreScrollOnMount: false,
    scrollPosition: null,
    searchInput: "",
    selectedNodeDetail: restoredNodeDetail,
    selectedNodeId: normalizedRoute.mode === "list" ? "" : String(normalizedRoute.nodeId || restoredNodeId || ""),
    selectedNodeLoading: false,
  };
}

export function createMountingNodesDetailRestoreCoordinator() {
  let activeKey = "";
  let activePromise = null;
  let generation = 0;

  return {
    run(nodeId, runner) {
      const restoreKey = buildMountingNodesDetailRestoreKey(nodeId);

      if (!restoreKey) {
        return Promise.resolve({ success: false, reason: "invalid-node" });
      }

      if (activePromise && activeKey === restoreKey) {
        return activePromise;
      }

      const requestId = generation + 1;
      generation = requestId;
      activeKey = restoreKey;

      const promise = Promise.resolve()
        .then(() =>
          runner({
            isCurrent: () => generation === requestId && activeKey === restoreKey,
            requestId,
            restoreKey,
          }),
        )
        .finally(() => {
          if (generation === requestId && activeKey === restoreKey) {
            activeKey = "";
            activePromise = null;
          }
        });

      activePromise = promise;
      return promise;
    },
    reset() {
      generation += 1;
      activeKey = "";
      activePromise = null;
    },
  };
}
