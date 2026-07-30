import { ArrowLeft, LayoutGrid, List, RefreshCw, Search } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { getMountingNode, getMountingNodes } from "../../api.js";
import { getProcessingTemplateMountingVariantLabel } from "../../processingTemplates.js";

const KNOWN_MOUNTING_VARIANT_KEYS = [
  "surface_mount",
  "face_to_edge",
  "edge_to_edge",
  "angled_two_planes",
  "drawer_slides",
];

const DISPLAY_MODE_STORAGE_KEY = "admin.mountingNodesDisplayMode";

function normalizeFilterValue(value) {
  return String(value || "").trim();
}

function normalizeNumberValue(value) {
  const parsedValue = Number(value);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function normalizeObjectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function normalizeViewMode(value) {
  return value === "detail" ? "detail" : "list";
}

function normalizeDisplayMode(value) {
  return value === "list" ? "list" : "grid";
}

function humanizeVariantKey(variantKey) {
  return String(variantKey || "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function readPersistedDisplayMode() {
  if (typeof window === "undefined") {
    return "grid";
  }

  try {
    return normalizeDisplayMode(window.localStorage.getItem(DISPLAY_MODE_STORAGE_KEY) || "grid");
  } catch {
    return "grid";
  }
}

export function buildMountingNodesReturnState(payload = {}) {
  const normalizedPayload = payload && typeof payload === "object" ? payload : {};

  return {
    activeStatusFilter: normalizeFilterValue(normalizedPayload.activeStatusFilter || "all") || "all",
    activeVariantFilter: normalizeFilterValue(normalizedPayload.activeVariantFilter || "all") || "all",
    appliedSearch: normalizeFilterValue(normalizedPayload.appliedSearch),
    displayMode: normalizeDisplayMode(normalizedPayload.displayMode),
    listError: normalizeFilterValue(normalizedPayload.listError),
    listLoading: Boolean(normalizedPayload.listLoading),
    mountingNodesViewMode: normalizeViewMode(normalizedPayload.mountingNodesViewMode),
    nodeDetailErrorsById: normalizeObjectValue(normalizedPayload.nodeDetailErrorsById),
    nodeDetailsById: normalizeObjectValue(normalizedPayload.nodeDetailsById),
    nodes: Array.isArray(normalizedPayload.nodes) ? normalizedPayload.nodes : [],
    restoreScrollOnMount: Boolean(normalizedPayload.restoreScrollOnMount),
    scrollPosition: normalizeNumberValue(normalizedPayload.scrollPosition),
    searchInput: normalizeFilterValue(normalizedPayload.searchInput),
    selectedNodeDetail:
      normalizedPayload.selectedNodeDetail && typeof normalizedPayload.selectedNodeDetail === "object"
        ? normalizedPayload.selectedNodeDetail
        : null,
    selectedNodeId: normalizeFilterValue(normalizedPayload.selectedNodeId),
    selectedNodeLoading: Boolean(normalizedPayload.selectedNodeLoading),
  };
}

function formatBooleanLabel(value, t) {
  return value ? (t.holePointSelectionYes || "Yes") : (t.holePointSelectionNo || "No");
}

function formatItemSummary(item, t) {
  const label = String(item?.fitting_article || item?.fitting_code || item?.fitting_name || "").trim() || t.notSet;
  const quantity = Number(item?.quantity || 0) || 0;
  return quantity > 0 ? `${label} x ${quantity}` : label;
}

function formatTemplateSummary(template, t, language) {
  const templateLabel = String(template?.template_name || "").trim() || `#${template?.template_id || t.notSet}`;
  const variantLabel =
    getProcessingTemplateMountingVariantLabel(template?.mounting_variant_key, language) ||
    humanizeVariantKey(template?.mounting_variant_key) ||
    t.notSet;
  const templateState = template?.is_default
    ? (t.mountingNodeTemplateDefault || "Default")
    : (t.mountingNodeTemplateAdditional || "Additional");

  return {
    label: templateLabel,
    meta: `${variantLabel} · ${templateState}`,
    pointsCount: Number(template?.points_count || 0) || 0,
  };
}

function getNodeCardPreviewText(nodeDetail, t, language) {
  const items = Array.isArray(nodeDetail?.items) ? nodeDetail.items : [];
  const templates = Array.isArray(nodeDetail?.templates) ? nodeDetail.templates : [];
  const itemText = items.slice(0, 2).map((item) => formatItemSummary(item, t)).filter(Boolean);
  const templateText = templates.slice(0, 2).map((template) => {
    const summary = formatTemplateSummary(template, t, language);
    return `${summary.label} · ${summary.meta}`;
  });

  return [itemText.length ? itemText.join(" · ") : "", templateText.length ? templateText.join(" · ") : ""].filter(Boolean);
}

function DetailField({ label, value }) {
  return (
    <div className="mounting-node-meta-field">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function MountingNodesPanelRefined({
  language = "uk",
  editorMode = false,
  initialState = null,
  onOpenMountingNodeEditor = null,
  t,
  token = "",
}) {
  const initialReturnState = buildMountingNodesReturnState(initialState);
  const [searchInput, setSearchInput] = useState(initialReturnState.searchInput);
  const [appliedSearch, setAppliedSearch] = useState(initialReturnState.appliedSearch);
  const [activeStatusFilter, setActiveStatusFilter] = useState(initialReturnState.activeStatusFilter);
  const [activeVariantFilter, setActiveVariantFilter] = useState(initialReturnState.activeVariantFilter);
  const [mountingNodesViewMode, setMountingNodesViewMode] = useState(initialReturnState.mountingNodesViewMode);
  const [displayMode, setDisplayMode] = useState(() => (
    initialState && typeof initialState === "object" && Object.prototype.hasOwnProperty.call(initialState, "displayMode")
      ? initialReturnState.displayMode
      : readPersistedDisplayMode()
  ));
  const [reloadToken, setReloadToken] = useState(0);
  const [nodes, setNodes] = useState(initialReturnState.nodes);
  const [listLoading, setListLoading] = useState(initialReturnState.listLoading);
  const [listError, setListError] = useState(initialReturnState.listError);
  const [selectedNodeId, setSelectedNodeId] = useState(initialReturnState.selectedNodeId);
  const [nodeDetailsById, setNodeDetailsById] = useState(initialReturnState.nodeDetailsById);
  const [nodeDetailErrorsById, setNodeDetailErrorsById] = useState(initialReturnState.nodeDetailErrorsById);
  const listRequestIdRef = useRef(0);
  const detailRequestIdRef = useRef(0);
  const selectedNodeIdRef = useRef(String(initialReturnState.selectedNodeId || ""));
  const pendingReturnStateRef = useRef(
    initialReturnState.scrollPosition === null ? null : initialReturnState,
  );

  useEffect(() => {
    selectedNodeIdRef.current = String(selectedNodeId || "");
  }, [selectedNodeId]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    try {
      window.localStorage.setItem(DISPLAY_MODE_STORAGE_KEY, displayMode);
    } catch {
      // Ignore storage errors and keep the UI usable.
    }

    return undefined;
  }, [displayMode]);

  useLayoutEffect(() => {
    if (editorMode) {
      return undefined;
    }

    const returnState = pendingReturnStateRef.current;
    if (!returnState) {
      return undefined;
    }

    if (mountingNodesViewMode === "detail" && !returnState.restoreScrollOnMount) {
      return undefined;
    }

    pendingReturnStateRef.current = null;

    const frameId = window.requestAnimationFrame(() => {
      const nextScrollPosition = Number(returnState.scrollPosition);
      if (Number.isFinite(nextScrollPosition) && nextScrollPosition >= 0) {
        window.scrollTo({ behavior: "auto", top: nextScrollPosition });
      }
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [editorMode, mountingNodesViewMode, nodes.length, selectedNodeId]);

  useEffect(() => {
    if (!token) {
      setNodes([]);
      setListLoading(false);
      setListError("");
      setSelectedNodeId("");
      return undefined;
    }

    const requestId = ++listRequestIdRef.current;
    setListLoading(true);
    setListError("");

    getMountingNodes(token, {
      search: appliedSearch,
      is_active: activeStatusFilter === "all" ? undefined : activeStatusFilter === "active",
      mounting_variant_key: activeVariantFilter === "all" ? undefined : activeVariantFilter,
    })
      .then((result) => {
        if (requestId !== listRequestIdRef.current) {
          return;
        }

        if (!result.success) {
          setNodes([]);
          setSelectedNodeId("");
          setNodeDetailsById({});
          setNodeDetailErrorsById({});
          setListError(result.error || t.mountingNodesError || "Unable to load mounting nodes");
          return;
        }

        const nextNodes = Array.isArray(result.nodes) ? result.nodes : [];
        setNodes(nextNodes);

        const currentSelectedId = String(selectedNodeIdRef.current || "");
        const hasSelectedNode = currentSelectedId && nextNodes.some((node) => String(node.id) === currentSelectedId);
        if (!hasSelectedNode) {
          setSelectedNodeId(nextNodes[0] ? String(nextNodes[0].id) : "");
        }
      })
      .catch((error) => {
        if (requestId !== listRequestIdRef.current) {
          return;
        }

        setNodes([]);
        setSelectedNodeId("");
        setNodeDetailsById({});
        setNodeDetailErrorsById({});
        setListError(error?.message || t.mountingNodesError || "Unable to load mounting nodes");
      })
      .finally(() => {
        if (requestId === listRequestIdRef.current) {
          setListLoading(false);
        }
      });

    return undefined;
  }, [activeStatusFilter, activeVariantFilter, appliedSearch, reloadToken, t.mountingNodesError, token]);

  useEffect(() => {
    if (!token || !nodes.length) {
      return undefined;
    }

    const requestId = ++detailRequestIdRef.current;
    let cancelled = false;

    Promise.allSettled(
      nodes.map(async (node) => {
        const result = await getMountingNode(token, node.id);
        if (!result.success || !result.node) {
          throw new Error(result.error || t.mountingNodesError || "Unable to load mounting nodes");
        }

        return [String(node.id), result.node];
      }),
    ).then((results) => {
      if (cancelled || requestId !== detailRequestIdRef.current) {
        return;
      }

      const nextDetails = {};
      const nextErrors = {};
      const successNodeIds = new Set();
      const failedNodeIds = new Set();

      results.forEach((result, index) => {
        const nodeId = String(nodes[index]?.id || "");
        if (!nodeId) {
          return;
        }

        if (result.status === "fulfilled") {
          const [resolvedNodeId, nodeDetail] = result.value;
          nextDetails[resolvedNodeId] = nodeDetail;
          successNodeIds.add(resolvedNodeId);
        } else {
          nextErrors[nodeId] = result.reason?.message || t.mountingNodesError || "Unable to load mounting nodes";
          failedNodeIds.add(nodeId);
        }
      });

      if (Object.keys(nextDetails).length) {
        setNodeDetailsById((current) => ({
          ...current,
          ...nextDetails,
        }));
      }

      setNodeDetailErrorsById((current) => {
        const next = { ...current };
        successNodeIds.forEach((nodeId) => {
          delete next[nodeId];
        });
        failedNodeIds.forEach((nodeId) => {
          next[nodeId] = nextErrors[nodeId];
        });
        return next;
      });
    });

    return () => {
      cancelled = true;
    };
  }, [nodes, t.mountingNodesError, token]);

  const selectedNode = useMemo(() => nodes.find((node) => String(node.id) === String(selectedNodeId)) || null, [nodes, selectedNodeId]);
  const selectedNodeDetail = selectedNode ? nodeDetailsById[String(selectedNode.id)] || null : null;
  const selectedNodeError = selectedNode ? nodeDetailErrorsById[String(selectedNode.id)] || "" : "";
  const selectedNodeLoading = Boolean(selectedNode && !selectedNodeDetail && !selectedNodeError && !listLoading);
  const variantOptions = useMemo(
    () => [
      {
        value: "all",
        label: language === "uk" ? "Усі варіанти" : "All variants",
      },
      ...KNOWN_MOUNTING_VARIANT_KEYS.map((variantKey) => ({
        value: variantKey,
        label: getProcessingTemplateMountingVariantLabel(variantKey, language) || humanizeVariantKey(variantKey),
      })),
    ],
    [language],
  );

  function captureReturnState(nextViewMode, restoreScrollOnMount = false) {
    return buildMountingNodesReturnState({
      activeStatusFilter,
      activeVariantFilter,
      appliedSearch,
      displayMode,
      listError,
      listLoading,
      mountingNodesViewMode: nextViewMode,
      nodeDetailErrorsById,
      nodeDetailsById,
      nodes,
      restoreScrollOnMount,
      scrollPosition: typeof window !== "undefined" ? window.scrollY : 0,
      searchInput,
      selectedNodeDetail,
      selectedNodeId,
      selectedNodeLoading,
    });
  }

  function handleSearchSubmit(event) {
    event.preventDefault();
    setAppliedSearch(searchInput.trim());
  }

  function handleRefresh() {
    setReloadToken((current) => current + 1);
  }

  function handleStatusFilterChange(value) {
    setActiveStatusFilter(String(value || "all"));
  }

  function handleVariantFilterChange(value) {
    setActiveVariantFilter(String(value || "all"));
  }

  function handleSelectNode(nodeId) {
    pendingReturnStateRef.current = captureReturnState("list", false);
    setSelectedNodeId(String(nodeId || ""));
    setMountingNodesViewMode("detail");
  }

  function handleBackToList() {
    setMountingNodesViewMode("list");
  }

  function handleOpenEditor() {
    if (!selectedNodeDetail || typeof onOpenMountingNodeEditor !== "function") {
      return;
    }

    pendingReturnStateRef.current = captureReturnState("detail", true);

    const primaryTemplate = selectedNodeDetail.templates?.find((template) => template?.is_default) || selectedNodeDetail.templates?.[0] || null;
    const primaryItem = selectedNodeDetail.items?.[0] || null;

    onOpenMountingNodeEditor({
      mountingNodeId: selectedNodeDetail.id,
      nodeCode: selectedNodeDetail.code,
      nodeName: selectedNodeDetail.name,
      fittingId: primaryTemplate?.fitting_id || primaryItem?.fitting_id || "",
      templateId: primaryTemplate?.template_id || "",
      mountingVariantKey: primaryTemplate?.mounting_variant_key || "",
      nodeDetail: selectedNodeDetail,
    }, pendingReturnStateRef.current);
  }

  if (!token) {
    return null;
  }

  return (
    <section aria-hidden={editorMode} className="dashboard-panel" hidden={editorMode} id="mounting-nodes-panel">
      {mountingNodesViewMode === "list" ? (
        <>
          <div className="dashboard-panel-head mounting-nodes-panel-head">
            <div>
              <h3>{t.mountingNodesTitle || "Mounting nodes"}</h3>
              <p>{t.mountingNodesDescription || ""}</p>
            </div>
            <div className="mounting-nodes-toolbar">
              <span className="service-tree-badge subtle">{language === "uk" ? `Знайдено: ${nodes.length}` : `Found: ${nodes.length}`}</span>
              <div className="mounting-nodes-display-toggle materials-mode-switch" role="group" aria-label={language === "uk" ? "Вигляд каталогу" : "Catalog view mode"}>
                <button
                  aria-pressed={displayMode === "grid"}
                  className={`ghost-button compact-button${displayMode === "grid" ? " active" : ""}`}
                  onClick={() => setDisplayMode("grid")}
                  title={language === "uk" ? "Плитка" : "Grid"}
                  type="button"
                >
                  <LayoutGrid size={16} />
                  <span>{language === "uk" ? "Плитка" : "Grid"}</span>
                </button>
                <button
                  aria-pressed={displayMode === "list"}
                  className={`ghost-button compact-button${displayMode === "list" ? " active" : ""}`}
                  onClick={() => setDisplayMode("list")}
                  title={language === "uk" ? "Список" : "List"}
                  type="button"
                >
                  <List size={16} />
                  <span>{language === "uk" ? "Список" : "List"}</span>
                </button>
              </div>
            </div>
          </div>

          <form className="project-filter-form mounting-nodes-filters" onSubmit={handleSearchSubmit}>
            <label className="mounting-nodes-search mounting-nodes-search-field">
              {t.mountingNodesSearchPlaceholder || "Search mounting nodes"}
              <input
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder={t.mountingNodesSearchPlaceholder || "Search mounting nodes"}
                type="search"
                value={searchInput}
              />
            </label>
            <label className="mounting-nodes-filter-field">
              {language === "uk" ? "Статус" : "Status"}
              <select onChange={(event) => handleStatusFilterChange(event.target.value)} value={activeStatusFilter}>
                <option value="all">{language === "uk" ? "Усі" : "All"}</option>
                <option value="active">{t.active || (language === "uk" ? "Активний" : "Active")}</option>
                <option value="inactive">{t.inactive || (language === "uk" ? "Неактивний" : "Inactive")}</option>
              </select>
            </label>
            <label className="mounting-nodes-filter-field">
              {language === "uk" ? "Варіант кріплення" : "Mounting variant"}
              <select onChange={(event) => handleVariantFilterChange(event.target.value)} value={activeVariantFilter}>
                {variantOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button className="primary-button mounting-nodes-search-button" type="submit">
              <Search size={16} />
              {language === "uk" ? "Шукати" : "Search"}
            </button>
            <button className="ghost-button mounting-nodes-refresh-button" onClick={handleRefresh} type="button">
              <RefreshCw size={16} />
              {t.mountingNodesRetry || (language === "uk" ? "Повторити" : "Retry")}
            </button>
          </form>

          {listLoading ? (
            <div className="empty-state compact-empty-state">
              <span>{t.mountingNodesLoading || (language === "uk" ? "Завантаження монтажних вузлів…" : "Loading mounting nodes…")}</span>
            </div>
          ) : listError ? (
            <div className="empty-state compact-empty-state">
              <span>{listError}</span>
              <button className="primary-button" onClick={handleRefresh} type="button">
                {t.mountingNodesRetry || (language === "uk" ? "Повторити" : "Retry")}
              </button>
            </div>
          ) : nodes.length ? (
            displayMode === "grid" ? (
              <div className="settings-grid mounting-nodes-grid">
                {nodes.map((node) => {
                  const nodeDetail = nodeDetailsById[String(node.id)] || null;
                  const previewLines = nodeDetail ? getNodeCardPreviewText(nodeDetail, t, language) : [];
                  const isSelected = String(selectedNodeId) === String(node.id);

                  return (
                    <article
                      aria-selected={isSelected}
                      className={`settings-card mounting-node-card${isSelected ? " is-selected" : ""}`}
                      key={node.id}
                      onClick={() => handleSelectNode(node.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleSelectNode(node.id);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="settings-card-header">
                        <div>
                          <strong>{node.name || t.notSet}</strong>
                          <p>{node.code || t.notSet}</p>
                        </div>
                        <div className="mounting-node-badges">
                          <span className="service-tree-badge subtle">
                            {node.is_active ? (t.active || "Active") : (t.inactive || "Inactive")}
                          </span>
                          <span className="service-tree-badge subtle">
                            {t.mountingNodeItems || (language === "uk" ? "Артикулів" : "Articles")}: {node.items_count ?? 0}
                          </span>
                          <span className="service-tree-badge subtle">
                            {t.mountingNodeTemplates || (language === "uk" ? "Шаблонів" : "Templates")}: {node.templates_count ?? 0}
                          </span>
                        </div>
                      </div>

                      <div className="settings-info-grid mounting-node-card-summary">
                        <div>
                          <span>{t.mountingNodeItemsSummary || (language === "uk" ? "Склад" : "Composition")}</span>
                          <strong>{previewLines[0] || (nodeDetail ? t.notSet : (t.mountingNodesLoading || "Loading"))}</strong>
                        </div>
                        <div>
                          <span>{t.mountingNodeTemplatesSummary || (language === "uk" ? "Шаблони" : "Templates")}</span>
                          <strong>{previewLines[1] || (nodeDetail ? t.notSet : (t.mountingNodesLoading || "Loading"))}</strong>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="mounting-nodes-list">
                {nodes.map((node) => {
                  const nodeDetail = nodeDetailsById[String(node.id)] || null;
                  const previewLines = nodeDetail ? getNodeCardPreviewText(nodeDetail, t, language) : [];
                  const isSelected = String(selectedNodeId) === String(node.id);

                  return (
                    <article
                      aria-selected={isSelected}
                      className={`settings-card mounting-node-row${isSelected ? " is-selected" : ""}`}
                      key={node.id}
                      onClick={() => handleSelectNode(node.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleSelectNode(node.id);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="mounting-node-row-header">
                        <div>
                          <strong>{node.name || t.notSet}</strong>
                          <p>{node.code || t.notSet}</p>
                        </div>
                        <div className="mounting-node-badges">
                          <span className="service-tree-badge subtle">
                            {node.is_active ? (t.active || "Active") : (t.inactive || "Inactive")}
                          </span>
                          <span className="service-tree-badge subtle">
                            {t.mountingNodeItems || (language === "uk" ? "Артикулів" : "Articles")}: {node.items_count ?? 0}
                          </span>
                          <span className="service-tree-badge subtle">
                            {t.mountingNodeTemplates || (language === "uk" ? "Шаблонів" : "Templates")}: {node.templates_count ?? 0}
                          </span>
                        </div>
                      </div>
                      <div className="mounting-node-row-body">
                        <div>
                          <span>{t.mountingNodeItemsSummary || (language === "uk" ? "Склад" : "Composition")}</span>
                          <strong>{previewLines[0] || (nodeDetail ? t.notSet : (t.mountingNodesLoading || "Loading"))}</strong>
                        </div>
                        <div>
                          <span>{t.mountingNodeTemplatesSummary || (language === "uk" ? "Шаблони" : "Templates")}</span>
                          <strong>{previewLines[1] || (nodeDetail ? t.notSet : (t.mountingNodesLoading || "Loading"))}</strong>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )
          ) : (
            <div className="empty-state compact-empty-state">
              <span>{t.mountingNodesEmpty || (language === "uk" ? "Монтажні вузли ще не створені." : "Mounting nodes have not been created yet.")}</span>
            </div>
          )}
        </>
      ) : (
        <article className="catalog-card service-catalog-card service-catalog-card-full holes-view-card mounting-node-detail-screen">
          <div className="catalog-page-header mounting-node-detail-header">
            <div className="service-catalog-title">
              <h3>{selectedNode?.name || t.mountingNodeDetailsTitle || (language === "uk" ? "Деталі монтажного вузла" : "Mounting node details")}</h3>
              <p>{t.mountingNodeDetailsDescription || (language === "uk" ? "Переглядайте склад, шаблони та відкривайте вузол у редакторі." : "Review the composition, linked templates, and open the node in the editor.")}</p>
            </div>
            <div className="service-catalog-header-actions mounting-node-detail-actions">
              <button className="ghost-button mounting-node-detail-action-button mounting-node-return-button" onClick={handleBackToList} type="button">
                <ArrowLeft size={16} />
                {t.mountingNodeBackToList || (language === "uk" ? "Повернутися до монтажних вузлів" : "Return to mounting nodes")}
              </button>
              {selectedNodeDetail ? (
                <button className="primary-button mounting-node-detail-action-button mounting-node-editor-button" onClick={handleOpenEditor} type="button">
                  {t.mountingNodeOpenEditor || (language === "uk" ? "Відкрити у редакторі" : "Open in editor")}
                </button>
              ) : null}
            </div>
          </div>

          {selectedNodeLoading ? (
            <div className="empty-state compact-empty-state">
              <span>{t.mountingNodeLoading || (language === "uk" ? "Завантаження монтажного вузла…" : "Loading mounting node…")}</span>
            </div>
          ) : selectedNodeError ? (
            <div className="empty-state compact-empty-state">
              <span>{selectedNodeError}</span>
              <button className="primary-button" onClick={handleRefresh} type="button">
                {t.mountingNodesRetry || (language === "uk" ? "Повторити" : "Retry")}
              </button>
            </div>
          ) : selectedNodeDetail ? (
            <>
              <div className="settings-info-grid mounting-node-detail-summary">
                <DetailField label={language === "uk" ? "Назва" : "Name"} value={selectedNodeDetail.name || t.notSet} />
                <DetailField label={language === "uk" ? "Код" : "Code"} value={selectedNodeDetail.code || t.notSet} />
                <DetailField label={t.status || "Status"} value={selectedNodeDetail.is_active ? (t.active || "Active") : (t.inactive || "Inactive")} />
                <DetailField label={language === "uk" ? "Опис" : "Description"} value={selectedNodeDetail.description || t.notSet} />
                <DetailField label={t.mountingNodeItems || (language === "uk" ? "Артикулів" : "Articles")} value={selectedNodeDetail.items_count ?? 0} />
                <DetailField label={t.mountingNodeTemplates || (language === "uk" ? "Шаблонів" : "Templates")} value={selectedNodeDetail.templates_count ?? 0} />
              </div>

              <div className="settings-grid mounting-node-detail-grid" style={{ marginTop: "1rem" }}>
                <article className="settings-card">
                  <div className="settings-card-header">
                    <div>
                      <strong>{language === "uk" ? "Склад артикулів" : "Item composition"}</strong>
                      <p>{language === "uk" ? "Кожен рядок показує артикул, кількість, роль і ознаки впливу." : "Each row shows the article, quantity, role, and processing flags."}</p>
                    </div>
                  </div>
                  <div className="settings-info-grid mounting-node-detail-list">
                    {selectedNodeDetail.items?.length ? (
                      selectedNodeDetail.items.map((item) => (
                        <div className="mounting-node-detail-line" key={item.id}>
                          <span>{item.fitting_name || item.fitting_code || item.fitting_article || t.notSet}</span>
                          <strong>
                            {item.fitting_article || item.fitting_code || item.fitting_name || t.notSet}
                            {" "}
                            x {item.quantity ?? 0}
                          </strong>
                          <div>{language === "uk" ? "Роль" : "Role"}: {item.role || t.notSet}</div>
                          <div>{language === "uk" ? "Обов'язковий" : "Required"}: {formatBooleanLabel(item.is_required, t)}</div>
                          <div>{language === "uk" ? "Впливає на обробку" : "Affects processing"}: {formatBooleanLabel(item.affects_processing, t)}</div>
                        </div>
                      ))
                    ) : (
                      <div>{t.notSet}</div>
                    )}
                  </div>
                </article>

                <article className="settings-card">
                  <div className="settings-card-header">
                    <div>
                      <strong>{language === "uk" ? "Пов'язані шаблони" : "Linked templates"}</strong>
                      <p>{language === "uk" ? "Тут показані шаблони, точки та призначений варіант кріплення." : "Templates, point counts, and the assigned mounting variant are shown here."}</p>
                    </div>
                  </div>
                  <div className="settings-info-grid mounting-node-detail-list">
                    {selectedNodeDetail.templates?.length ? (
                      selectedNodeDetail.templates.map((template) => {
                        const templateSummary = formatTemplateSummary(template, t, language);
                        return (
                          <div className="mounting-node-detail-line" key={template.id}>
                            <span>{templateSummary.label}</span>
                            <strong>{template.template_id}</strong>
                            <div>{t.mountingNodeTemplateVariant || (language === "uk" ? "Варіант кріплення" : "Mounting variant")}: {templateSummary.meta}</div>
                            <div>{t.mountingNodeTemplatePointsCount || (language === "uk" ? "Точок" : "Points")}: {templateSummary.pointsCount}</div>
                            <div>{template.is_default ? (t.mountingNodeTemplateDefault || (language === "uk" ? "За замовчуванням" : "Default")) : (t.mountingNodeTemplateAdditional || (language === "uk" ? "Додатковий" : "Additional"))}</div>
                          </div>
                        );
                      })
                    ) : (
                      <div>{t.notSet}</div>
                    )}
                  </div>
                </article>
              </div>
            </>
          ) : (
            <div className="empty-state compact-empty-state">
              <span>{t.mountingNodesEmpty || (language === "uk" ? "Монтажні вузли ще не створені." : "Mounting nodes have not been created yet.")}</span>
            </div>
          )}
        </article>
      )}
    </section>
  );
}
