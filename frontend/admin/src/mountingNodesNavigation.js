import { getMountingNodeCategoryLabel, normalizeMountingNodeCategoryCode } from "./mountingNodeCategories.js";

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

function normalizeMountingNodeCategoryRouteValue(value) {
  const rawValue = String(value || "").trim().toLowerCase();

  if (!rawValue) {
    return null;
  }

  if (rawValue === "null") {
    return "null";
  }

  return normalizeMountingNodeCategoryCode(rawValue) || null;
}

function hasMountingNodeCategoryRouteValue(route = {}) {
  if (!route || typeof route !== "object") {
    return false;
  }

  if (!Object.prototype.hasOwnProperty.call(route, "categoryCode")) {
    return false;
  }

  const rawCategoryCode = route.categoryCode;
  if (rawCategoryCode === null) {
    return true;
  }

  return String(rawCategoryCode || "").trim() !== "";
}

function buildMountingNodesDetailRestoreKey(nodeId) {
  const normalizedNodeId = normalizeMountingNodeId(nodeId);

  return normalizedNodeId === null ? "" : `detail:${normalizedNodeId}`;
}

export function buildMountingNodesRestoredRoute(route = {}, nodeId = null) {
  const normalizedRoute = normalizeMountingNodesRoute(route);
  const restoredNodeId = normalizeMountingNodeId(nodeId ?? normalizedRoute.nodeId);
  const restoredMode = normalizedRoute.mode === "editor" ? "editor" : "detail";

  return normalizeMountingNodesRoute({
    mode: restoredMode,
    nodeId: restoredNodeId,
    categoryCode: normalizedRoute.categoryCode,
  });
}

export function normalizeMountingNodesRoute(route = {}) {
  const mode = String(route?.mode || "").trim();
  const nodeId = normalizeMountingNodeId(route?.nodeId);
  const categoryCode = normalizeMountingNodeCategoryRouteValue(route?.categoryCode);
  const hasCategoryCode = hasMountingNodeCategoryRouteValue(route);

  if (mode === "categories") {
    return {
      mode,
      nodeId: null,
      categoryCode: null,
    };
  }

  if ((mode === "detail" || mode === "editor") && nodeId !== null) {
    return {
      mode,
      nodeId,
      categoryCode: hasCategoryCode ? categoryCode : undefined,
    };
  }

  if (mode === "create") {
    return {
      mode,
      nodeId: null,
      categoryCode: hasCategoryCode ? categoryCode : undefined,
    };
  }

  if (mode === "list") {
    if (!hasCategoryCode) {
      return {
        mode: "categories",
        nodeId: null,
        categoryCode: null,
      };
    }

    return {
      mode,
      nodeId: null,
      categoryCode,
    };
  }

  return {
    mode: "list",
    nodeId: null,
    categoryCode,
  };
}

export function parseMountingNodesRoute(search = "") {
  const params = normalizeSearchParams(search);

  if (String(params.get("section") || "").trim() !== MOUNTING_NODES_SECTION) {
    return null;
  }

  const categoryParam = String(params.get("category") || "").trim();
  const route = {
    mode: params.get("mode"),
    nodeId: params.get("node"),
  };

  if (params.has("category") && categoryParam) {
    route.categoryCode = params.get("category");
  } else if (params.has("category") && categoryParam === "null") {
    route.categoryCode = "null";
  }

  return normalizeMountingNodesRoute(route);
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

  if (normalizedRoute.categoryCode) {
    params.set("category", normalizedRoute.categoryCode);
  } else {
    params.delete("category");
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
    activeCategoryFilter: normalizedRoute.categoryCode || "all",
    activeVariantFilter: "all",
    appliedSearch: "",
    displayMode: "grid",
    listError: "",
    listLoading: false,
    mountingNodesViewMode: normalizedRoute.mode === "categories" ? "list" : normalizedRoute.mode,
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

export function resolveMountingNodesCategoryCode(categoryCode, fallbackCategoryCode = undefined) {
  if (categoryCode === "null" || categoryCode === null) {
    return "null";
  }

  if (categoryCode !== undefined) {
    const normalizedCategoryCode = normalizeMountingNodeCategoryCode(categoryCode);
    if (normalizedCategoryCode) {
      return normalizedCategoryCode;
    }

    if (String(categoryCode || "").trim()) {
      return fallbackCategoryCode === undefined
        ? null
        : resolveMountingNodesCategoryCode(fallbackCategoryCode);
    }
  }

  if (fallbackCategoryCode !== undefined) {
    return resolveMountingNodesCategoryCode(fallbackCategoryCode);
  }

  return null;
}

export function buildMountingNodesBreadcrumbItems({
  allListLabel = "",
  categoryLabel = "",
  categoryCode = undefined,
  createLabel = "",
  editingLabel = "",
  language = "en",
  listLabel = "",
  mode = "list",
  nodeName = "",
  onOpenCategories = null,
  onOpenCategoryList = null,
  onOpenNodeDetail = null,
} = {}) {
  const normalizedMode = String(mode || "").trim();
  const normalizedListLabel = String(listLabel || "").trim();
  const normalizedAllListLabel = String(allListLabel || "").trim();
  const resolvedCategoryCode = resolveMountingNodesCategoryCode(categoryCode);
  const normalizedCategoryLabel =
    String(categoryLabel || "").trim() ||
    (resolvedCategoryCode === "null"
      ? (language === "uk" ? "Без категорії" : "Uncategorized")
      : resolvedCategoryCode
        ? getMountingNodeCategoryLabel(resolvedCategoryCode, language)
        : "");
  const normalizedNodeName = String(nodeName || "").trim();
  const normalizedCreateLabel = String(createLabel || "").trim();
  const normalizedEditingLabel = String(editingLabel || "").trim();
  const items = [];

  if (normalizedMode === "categories") {
    return normalizedListLabel
      ? [
          {
            current: true,
            label: normalizedListLabel,
            title: normalizedListLabel,
          },
        ]
      : [];
  }

  if (normalizedListLabel) {
    items.push({
      label: normalizedListLabel,
      onClick: onOpenCategories || undefined,
      title: normalizedListLabel,
    });
  }

  if (normalizedMode === "list") {
    items.push({
      current: true,
      label: normalizedCategoryLabel || normalizedAllListLabel,
      title: normalizedCategoryLabel || normalizedAllListLabel,
    });
    return items;
  }

  if (normalizedCategoryLabel) {
    items.push({
      label: normalizedCategoryLabel,
      onClick: onOpenCategoryList || undefined,
      title: normalizedCategoryLabel,
    });
  }

  if (normalizedMode === "detail") {
    items.push({
      current: true,
      label: normalizedNodeName || normalizedListLabel,
      title: normalizedNodeName || normalizedListLabel,
    });
    return items;
  }

  if (normalizedMode === "editor") {
    items.push({
      label: normalizedNodeName,
      onClick: onOpenNodeDetail || undefined,
      title: normalizedNodeName,
    });
    items.push({
      current: true,
      label: normalizedEditingLabel,
      title: normalizedEditingLabel,
    });
    return items;
  }

  if (normalizedMode === "create") {
    items.push({
      current: true,
      label: normalizedCreateLabel,
      title: normalizedCreateLabel,
    });
    return items;
  }

  return items;
}

export function shouldHydrateMountingNodeDetail(route = {}, nodeDetail = null) {
  const normalizedRoute = normalizeMountingNodesRoute(route);
  if (normalizedRoute.mode !== "detail" && normalizedRoute.mode !== "editor") {
    return false;
  }

  if (normalizedRoute.nodeId === null) {
    return false;
  }

  if (!nodeDetail || typeof nodeDetail !== "object") {
    return true;
  }

  const restoredNodeId = String(nodeDetail.id || nodeDetail.node_id || "").trim();

  if (!restoredNodeId || restoredNodeId !== String(normalizedRoute.nodeId)) {
    return true;
  }

  if (!Array.isArray(nodeDetail.items) || !Array.isArray(nodeDetail.templates)) {
    return true;
  }

  return false;
}

export function shouldPreserveMountingNodeEditorWorkspace(route = {}, openContext = null) {
  const normalizedRoute = normalizeMountingNodesRoute(route);
  if (normalizedRoute.mode !== "editor") {
    return false;
  }

  const resolvedMountingNodeId = String(openContext?.mountingNodeId || "").trim();
  const resolvedNodeDetail =
    openContext?.nodeDetail && typeof openContext.nodeDetail === "object" ? openContext.nodeDetail : null;

  return Boolean(resolvedMountingNodeId && resolvedNodeDetail);
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
