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

export function normalizeMountingNodesRoute(route = {}) {
  const mode = String(route?.mode || "").trim();
  const nodeId = normalizeMountingNodeId(route?.nodeId);

  if (mode === "detail" && nodeId !== null) {
    return {
      mode: "detail",
      nodeId,
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

  return {
    activeStatusFilter: "all",
    activeVariantFilter: "all",
    appliedSearch: "",
    displayMode: "grid",
    listError: "",
    listLoading: false,
    mountingNodesViewMode: normalizedRoute.mode,
    nodeDetailErrorsById: {},
    nodeDetailsById: {},
    nodes: [],
    restoreScrollOnMount: false,
    scrollPosition: null,
    searchInput: "",
    selectedNodeDetail:
      normalizedRoute.mode === "detail" && nodeDetail && typeof nodeDetail === "object"
        ? nodeDetail
        : null,
    selectedNodeId: normalizedRoute.mode === "detail" ? String(normalizedRoute.nodeId || "") : "",
    selectedNodeLoading: false,
  };
}
