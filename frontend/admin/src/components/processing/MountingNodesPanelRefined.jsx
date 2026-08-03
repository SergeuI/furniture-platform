import { ArrowLeft, Box, ChevronRight, Info, LayoutGrid, List, Plus, RefreshCw, Search, Trash2, X } from "lucide-react";
import { createPortal } from "react-dom";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import {
  deleteMountingNode,
  getFittingDetails,
  getFittingImageBlob,
  getMountingNode,
  getMountingNodes,
  updateMountingNode,
} from "../../api.js";
import { getProcessingTemplateMountingVariantLabel } from "../../processingTemplates.js";
import { buildMountingNodeEditorSavePayload } from "../../mountingNodesEditor.js";
import surfaceMountIcon from "../../assets/hole-mounting/surface_mount.png";
import faceToEdgeIcon from "../../assets/hole-mounting/face_to_edge.png";
import edgeToEdgeIcon from "../../assets/hole-mounting/edge_to_edge.png";
import angledTwoPlanesIcon from "../../assets/hole-mounting/angled_two_planes.png";
import drawerSlidesIcon from "../../assets/hole-mounting/drawer_slides.png";

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

function clampNumber(value, min, max) {
  return Math.min(Math.max(Number(value) || 0, min), max);
}

function findNearestVerticalScrollAncestor(element) {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return null;
  }

  let current = element?.parentElement || null;
  while (current && current !== document.body) {
    const overflowY = window.getComputedStyle(current).overflowY || "";
    if (/(auto|scroll|overlay)/i.test(overflowY) && current.scrollHeight > current.clientHeight + 1) {
      return current;
    }

    current = current.parentElement;
  }

  return document.scrollingElement || document.documentElement || document.body || null;
}

function scrollNearestVerticalAncestorBy(ancestor, delta) {
  const nextDelta = Math.max(0, Number(delta) || 0);
  if (!ancestor || nextDelta <= 0) {
    return;
  }

  if (typeof window === "undefined") {
    return;
  }

  if (ancestor === document.scrollingElement || ancestor === document.documentElement || ancestor === document.body) {
    window.scrollBy({ behavior: "auto", top: nextDelta });
    return;
  }

  if (typeof ancestor.scrollBy === "function") {
    ancestor.scrollBy({ behavior: "auto", top: nextDelta });
    return;
  }

  ancestor.scrollTop += nextDelta;
}

function calculateVariantDropdownScrollDelta(anchorRect, viewportHeight, desiredHeight) {
  const margin = 10;
  const gap = 6;
  const requestedHeight = Number(desiredHeight || 0) > 0 ? Number(desiredHeight || 0) : 340;
  const availableBelow = Math.max(0, viewportHeight - Number(anchorRect?.bottom || 0) - gap - margin);

  return Math.max(0, requestedHeight - availableBelow);
}

function calculateVariantDropdownPosition(anchorRect, viewportWidth, viewportHeight, desiredHeight) {
  const margin = 10;
  const gap = 6;
  const rect = anchorRect || {};
  const requestedHeight = Number(desiredHeight || 0) > 0 ? Number(desiredHeight || 0) : 340;
  const availableBelow = Math.max(0, viewportHeight - Number(rect.bottom || 0) - gap - margin);
  const width = clampNumber(rect.width || 0, 0, viewportWidth - margin * 2);
  const left = clampNumber(rect.left || 0, margin, Math.max(margin, viewportWidth - width - margin));
  return {
    left,
    maxHeight: Math.min(340, availableBelow, requestedHeight),
    top: Number(rect.bottom || 0) + gap,
    width,
  };
}

function getNodeVariantDescription(variantKey, language) {
  const descriptions = {
    angled_two_planes:
      language === "uk"
        ? "Кріплення між двома непаралельними площинами."
        : "Mounting between two non-parallel planes.",
    drawer_slides:
      language === "uk"
        ? "Напрямні для висувних елементів."
        : "Slides for pull-out elements.",
    edge_to_edge:
      language === "uk"
        ? "Установлення фурнітури по торцях панелей."
        : "Hardware mounted on the edges of panels.",
    face_to_edge:
      language === "uk"
        ? "Установлення на площині однієї та торці іншої панелі."
        : "Mounting on one panel face and another panel edge.",
    surface_mount:
      language === "uk"
        ? "Установлення фурнітури на площині."
        : "Hardware mounted on a panel face.",
  };

  return descriptions[variantKey] || "";
}

function getNodeVariantIcon(variantKey) {
  const icons = {
    angled_two_planes: angledTwoPlanesIcon,
    drawer_slides: drawerSlidesIcon,
    edge_to_edge: edgeToEdgeIcon,
    face_to_edge: faceToEdgeIcon,
    surface_mount: surfaceMountIcon,
  };

  return icons[variantKey] || surfaceMountIcon;
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

function formatMountingNodeRoleLabel(value, language, t) {
  const normalizedRole = String(value || "").trim().toLowerCase();

  if (["primary", "main", "основний"].includes(normalizedRole)) {
    return language === "uk" ? "Основний" : "Primary";
  }

  if (["additional", "додатковий"].includes(normalizedRole)) {
    return language === "uk" ? "Додатковий" : "Additional";
  }

  if (["replacement", "substitute", "заміна"].includes(normalizedRole)) {
    return language === "uk" ? "Заміна" : "Replacement";
  }

  return String(value || "").trim() || t.notSet;
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

function getOwnershipLabel(node, language) {
  const ownershipType = String(node?.ownership_type || "").trim().toLowerCase();

  if (ownershipType === "system" || node?.is_system) {
    return language === "uk" ? "Системний" : "System";
  }

  if (node?.is_owner) {
    return language === "uk" ? "Власний" : "Owned";
  }

  if (ownershipType === "private" || node?.owner_user_id) {
    return language === "uk" ? "Користувацький" : "Custom";
  }

  return language === "uk" ? "Невідомий доступ" : "Unknown ownership";
}

function buildNodeEditorContext(nodeDetail, fallbackNodeId = "") {
  if (!nodeDetail || typeof nodeDetail !== "object") {
    return null;
  }

  const primaryTemplate =
    nodeDetail.templates?.find((template) => template?.is_default) || nodeDetail.templates?.[0] || null;
  const primaryItem = nodeDetail.items?.[0] || null;
  const mountingNodeId = String(nodeDetail.id || nodeDetail.node_id || fallbackNodeId || "").trim();

  if (!mountingNodeId) {
    return null;
  }

  return {
    mountingNodeId,
    nodeCode: String(nodeDetail.code || "").trim(),
    nodeName: String(nodeDetail.name || "").trim(),
    fittingId: String(primaryTemplate?.fitting_id || primaryItem?.fitting_id || "").trim(),
    templateId: String(primaryTemplate?.template_id || "").trim(),
    mountingVariantKey: String(primaryTemplate?.mounting_variant_key || "").trim(),
    nodeDetail,
  };
}

function buildNodeReturnState({
  activeStatusFilter,
  activeVariantFilter,
  appliedSearch,
  displayMode,
  listError,
  listLoading,
  nodeDetailErrorsById,
  nodeDetailsById,
  nodes,
  restoreScrollOnMount,
  scrollPosition,
  searchInput,
  selectedNodeDetail,
  selectedNodeId,
  selectedNodeLoading,
  nextViewMode,
}) {
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
    scrollPosition,
    searchInput,
    selectedNodeDetail,
    selectedNodeId,
    selectedNodeLoading,
  });
}

function getNodeItemImageUrl(item, fittingThumbnailState) {
  const thumbnailUrl = String(fittingThumbnailState?.src || "").trim();
  if (fittingThumbnailState?.status === "loaded" && thumbnailUrl) {
    return thumbnailUrl;
  }

  return String(item?.image_url || item?.image || item?.thumbnail_url || "").trim();
}

function getNodeItemLabel(item, t) {
  return String(item?.fitting_name || item?.name || item?.fitting_article || item?.fitting_code || "").trim() || t.notSet;
}

function renderNodeItemGallery(items, language, t, fittingThumbnailStateById) {
  const nodeItems = Array.isArray(items) ? items : [];
  const renderedItems = nodeItems.map((item, index) => {
    const fittingId = String(item?.fitting_id || "").trim();
    const fittingThumbnailState = fittingId ? fittingThumbnailStateById?.[fittingId] || null : null;
    const imageUrl = getNodeItemImageUrl(item, fittingThumbnailState);

    return {
      fittingId,
      fittingThumbnailState,
      imageUrl,
      itemLabel: getNodeItemLabel(item, t),
      itemKey: String(item?.id || item?.fitting_id || item?.fitting_article || item?.fitting_code || index),
    };
  });
  const visibleItems = renderedItems.filter((item) => item.fittingThumbnailState?.status === "loaded" && item.imageUrl);
  const hasLoadingImages = renderedItems.some((item) => item.fittingThumbnailState?.status === "loading");

  if (!nodeItems.length || !visibleItems.length && !hasLoadingImages) {
    return (
      <div className="mounting-node-item-gallery is-empty" aria-label={language === "uk" ? "Немає зображень" : "No images"}>
        <div className="mounting-node-item-thumb is-empty">
          <span>{t.holeWorkspaceNoImage || (language === "uk" ? "Без зображення" : "No image")}</span>
        </div>
      </div>
    );
  }

  if (!visibleItems.length) {
    return (
      <div className="mounting-node-item-gallery is-empty" aria-label={language === "uk" ? "Завантаження зображень" : "Loading images"}>
        <div className="mounting-node-item-thumb is-empty">
          <span>{t.mountingNodesLoading || (language === "uk" ? "Завантаження..." : "Loading...")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="mounting-node-item-gallery" aria-label={language === "uk" ? "Зображення фурнітури" : "Fitting images"}>
      {visibleItems.map((item) => {
        return (
          <div className="mounting-node-item-thumb" key={item.itemKey}>
            <img alt={item.itemLabel} loading="lazy" src={item.imageUrl} />
          </div>
        );
      })}
    </div>
  );
}

function renderNodeCardActions(node, nodeDetail, language, t, onOpenNodeDetail, onOpenNodeEditor) {
  const canEdit = Boolean((nodeDetail || node)?.can_edit);
  const openNodeDetailLabel = language === "uk" ? "Інформація про вузол" : "Node info";
  const openNodeEditorLabel = language === "uk" ? "Отвори та 3D" : "Open editor and 3D";

  return (
    <div className="mounting-node-card-actions">
      <button
        aria-label={openNodeDetailLabel}
        className="ghost-button compact-button detail-info-button mounting-node-card-action"
        onClick={(event) => {
          event.stopPropagation();
          onOpenNodeDetail(node.id);
        }}
        title={openNodeDetailLabel}
        type="button"
      >
        <Info size={16} />
      </button>
      {canEdit ? (
        <button
          aria-label={openNodeEditorLabel}
          className="ghost-button compact-button detail-info-button mounting-node-card-action"
          onClick={(event) => {
            event.stopPropagation();
            onOpenNodeEditor(nodeDetail || node);
          }}
          title={openNodeEditorLabel}
          type="button"
        >
          <Box size={16} />
        </button>
      ) : null}
    </div>
  );
}

function getNodePrimaryTemplate(nodeDetail) {
  if (!nodeDetail || typeof nodeDetail !== "object") {
    return null;
  }

  return nodeDetail.templates?.find((template) => template?.is_default) || nodeDetail.templates?.[0] || null;
}

function getNodeVariantOptions(language) {
  return KNOWN_MOUNTING_VARIANT_KEYS.map((variantKey) => ({
    description: getNodeVariantDescription(variantKey, language),
    icon: getNodeVariantIcon(variantKey),
    key: variantKey,
    label: getProcessingTemplateMountingVariantLabel(variantKey, language) || humanizeVariantKey(variantKey),
    value: variantKey,
  }));
}

function getNodeVariantChangeWarning(language) {
  if (language === "uk") {
    return "У вузлі вже є налаштовані точки. Зміна варіанта кріплення може змінити їх відображення. Після збереження перевірте точки у розділі «Отвори та 3D». Продовжити?";
  }

  return 'This node already has configured points. Changing the mounting variant may affect how they are shown. After saving, check the points in the "Openings and 3D" section. Continue?';
}

function getNodeVariantChangeTitle(language) {
  return language === "uk" ? "Змінити варіант кріплення" : "Change mounting variant";
}


function renderNodeDetailItemCard(
  item,
  index,
  language,
  t,
  fittingThumbnailStateById,
  onOpenFittingDetail,
  token,
  openFittingDetailLoadingId,
  setOpenFittingDetailLoadingId,
  setOpenFittingDetailError,
) {
  const fittingId = String(item?.fitting_id || "").trim();
  const fittingThumbnailState = fittingId ? fittingThumbnailStateById?.[fittingId] || null : null;
  const imageUrl = getNodeItemImageUrl(item, fittingThumbnailState);
  const itemLabel = getNodeItemLabel(item, t);
  const detailLabel = language === "uk" ? "Відкрити картку фурнітури" : "Open fitting details";
  const quantityLabel = language === "uk" ? "Кількість" : "Quantity";
  const roleLabel = language === "uk" ? "Роль" : "Role";
  const isLoaded = fittingThumbnailState?.status === "loaded" && imageUrl;
  const roleValue = formatMountingNodeRoleLabel(item?.role, language, t);
  const isDetailLoading = Boolean(fittingId && openFittingDetailLoadingId === fittingId);

  return (
    <button
      aria-label={`${itemLabel}. ${detailLabel}`}
      className="mounting-node-detail-item-card"
      disabled={isDetailLoading}
      key={String(item?.id || item?.fitting_id || item?.fitting_article || item?.fitting_code || index)}
      onClick={async (event) => {
        if (!fittingId || typeof onOpenFittingDetail !== "function") {
          return;
        }

        if (typeof setOpenFittingDetailError === "function") {
          setOpenFittingDetailError("");
        }

        if (typeof setOpenFittingDetailLoadingId === "function") {
          setOpenFittingDetailLoadingId(fittingId);
        }

        try {
          const result = await getFittingDetails(token, fittingId);
          if (!result.success || !result.item) {
            if (typeof setOpenFittingDetailError === "function") {
              setOpenFittingDetailError(result.error || t.fittingDetailsFailed || "Failed to open fitting details");
            }
            return;
          }

          onOpenFittingDetail(result.item, event.currentTarget);
        } finally {
          if (typeof setOpenFittingDetailLoadingId === "function") {
            setOpenFittingDetailLoadingId("");
          }
        }
      }}
      type="button"
    >
      <div className={`mounting-node-detail-item-thumb${isLoaded ? "" : " is-empty"}`}>
        {isLoaded ? <img alt={itemLabel} loading="lazy" src={imageUrl} /> : <span>{t.holeWorkspaceNoImage || (language === "uk" ? "Без зображення" : "No image")}</span>}
      </div>
      <div className="mounting-node-detail-item-copy">
        <strong>{itemLabel}</strong>
        <div className="mounting-node-detail-item-meta">
          <span>
            {language === "uk" ? "Артикул" : "Article"}: {item.fitting_article || item.fitting_code || item.fitting_name || t.notSet}
          </span>
          <span>
            {roleLabel}: {roleValue}
          </span>
          <span>
            {quantityLabel}: × {item.quantity ?? 0}
          </span>
        </div>
      </div>
    </button>
  );
}

export default function MountingNodesPanelRefined({
  language = "uk",
  editorMode = false,
  initialState = null,
  onOpenMountingNodeCreate = null,
  onOpenMountingNodeDetail = null,
  onCloseMountingNodeDetail = null,
  onOpenFittingDetail = null,
  onOpenMountingNodeEditor = null,
  listRequestToken = 0,
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
  const [fittingThumbnailStateById, setFittingThumbnailStateById] = useState({});
  const [deleteConfirmNode, setDeleteConfirmNode] = useState(null);
  const [deleteConfirmError, setDeleteConfirmError] = useState("");
  const [deleteConfirmLoading, setDeleteConfirmLoading] = useState(false);
  const [selectedNodeVariantKey, setSelectedNodeVariantKey] = useState("");
  const [variantDropdownOpen, setVariantDropdownOpen] = useState(false);
  const [variantDropdownPosition, setVariantDropdownPosition] = useState(null);
  const [variantSaveError, setVariantSaveError] = useState("");
  const [variantSaveLoading, setVariantSaveLoading] = useState(false);
  const [variantConfirmOpen, setVariantConfirmOpen] = useState(false);
  const [variantDropdownPreparing, setVariantDropdownPreparing] = useState(false);
  const [openFittingDetailLoadingId, setOpenFittingDetailLoadingId] = useState("");
  const [openFittingDetailError, setOpenFittingDetailError] = useState("");
  const [openEditorError, setOpenEditorError] = useState("");
  const listRequestIdRef = useRef(0);
  const detailRequestIdRef = useRef(0);
  const listRequestTokenRef = useRef(Number(listRequestToken || 0));
  const selectedNodeIdRef = useRef(String(initialReturnState.selectedNodeId || ""));
  const variantDropdownRef = useRef(null);
  const variantDropdownMenuRef = useRef(null);
  const variantDropdownOpenFrameRef = useRef(0);
  const pendingReturnStateRef = useRef(
    initialReturnState.scrollPosition === null ? null : initialReturnState,
  );

  useEffect(() => {
    selectedNodeIdRef.current = String(selectedNodeId || "");
  }, [selectedNodeId]);

  useEffect(() => {
    const nextToken = Number(listRequestToken || 0);
    if (!nextToken || listRequestTokenRef.current === nextToken) {
      return;
    }

    listRequestTokenRef.current = nextToken;
    setMountingNodesViewMode("list");
  }, [listRequestToken]);

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
    setOpenEditorError("");
  }, [selectedNodeId]);

  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && variantDropdownOpenFrameRef.current) {
        window.cancelAnimationFrame(variantDropdownOpenFrameRef.current);
        variantDropdownOpenFrameRef.current = 0;
      }
    };
  }, []);

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

  useEffect(() => {
    if (!token) {
      setFittingThumbnailStateById({});
      return undefined;
    }

    let cancelled = false;

    const fittingIds = [];
    const seenFittingIds = new Set();

    Object.values(nodeDetailsById || {}).forEach((nodeDetail) => {
      const items = Array.isArray(nodeDetail?.items) ? nodeDetail.items : [];

      items.forEach((item) => {
        const fittingId = String(item?.fitting_id || "").trim();
        if (!fittingId || seenFittingIds.has(fittingId)) {
          return;
        }

        const existingState = fittingThumbnailStateById[fittingId] || null;
        if (existingState?.status === "loading" || existingState?.status === "loaded" || existingState?.status === "no-image" || existingState?.status === "error") {
          return;
        }

        seenFittingIds.add(fittingId);
        fittingIds.push(fittingId);
      });
    });

    if (!fittingIds.length) {
      return undefined;
    }

    setFittingThumbnailStateById((current) => {
      const next = { ...current };
      fittingIds.forEach((fittingId) => {
        next[fittingId] = {
          status: "loading",
          src: null,
        };
      });
      return next;
    });

    fittingIds.forEach((fittingId) => {
      (async () => {
        try {
          const result = await getFittingDetails(token, fittingId);
          if (cancelled) {
            return;
          }

          if (!result.success || !result.item) {
            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                status: "error",
                src: null,
              },
            }));
            return;
          }

          const galleryImages = Array.isArray(result.item.images)
            ? [...result.item.images]
                .filter((image) => String(image?.id || "").trim())
                .sort((left, right) => {
                  const leftSort = Number(left?.sort_order ?? 0);
                  const rightSort = Number(right?.sort_order ?? 0);

                  if (leftSort !== rightSort) {
                    return leftSort - rightSort;
                  }

                  return Number(left?.id ?? 0) - Number(right?.id ?? 0);
                })
            : [];
          const primaryImage = galleryImages.find((image) => Boolean(image?.is_primary)) || galleryImages[0] || null;

          if (!primaryImage?.id) {
            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                status: "no-image",
                src: null,
              },
            }));
            return;
          }

          const imageResult = await getFittingImageBlob(token, fittingId, primaryImage.id);
          if (cancelled) {
            return;
          }

          if (!imageResult.success || !imageResult.blob) {
            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                status: "error",
                src: null,
              },
            }));
            return;
          }

          let imageUrl = "";
          try {
            imageUrl = await new Promise((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result || ""));
              reader.onerror = () => reject(reader.error || new Error("Unable to load fitting image"));
              reader.onabort = () => reject(new Error("Unable to load fitting image"));
              reader.readAsDataURL(imageResult.blob);
            });
          } catch {
            if (cancelled) {
              return;
            }

            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                status: "error",
                src: null,
              },
            }));
            return;
          }

          if (cancelled) {
            return;
          }

          if (!imageUrl) {
            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                status: "error",
                src: null,
              },
            }));
            return;
          }

          setFittingThumbnailStateById((current) => ({
            ...current,
            [fittingId]: {
              status: "loaded",
              src: imageUrl,
            },
          }));
        } catch {
          if (cancelled) {
            return;
          }

          setFittingThumbnailStateById((current) => ({
            ...current,
            [fittingId]: {
              status: "error",
              src: null,
            },
          }));
        }
      })();
    });

    return () => {
      cancelled = true;
    };
  }, [nodeDetailsById, t.mountingNodesError, token]);

  const selectedNode = useMemo(() => nodes.find((node) => String(node.id) === String(selectedNodeId)) || null, [nodes, selectedNodeId]);
  const selectedNodeDetail = selectedNode ? nodeDetailsById[String(selectedNode.id)] || null : null;
  const selectedNodeError = selectedNode ? nodeDetailErrorsById[String(selectedNode.id)] || "" : "";
  const selectedNodeLoading = Boolean(selectedNode && !selectedNodeDetail && !selectedNodeError && !listLoading);
  const selectedNodePrimaryTemplate = useMemo(() => getNodePrimaryTemplate(selectedNodeDetail), [selectedNodeDetail]);
  const selectedNodeCurrentVariantKey = String(selectedNodePrimaryTemplate?.mounting_variant_key || "").trim();
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
  const detailVariantOptions = useMemo(() => getNodeVariantOptions(language), [language]);
  const selectedNodeVariantModel = useMemo(
    () => detailVariantOptions.find((option) => option.value === selectedNodeVariantKey) || detailVariantOptions[0] || null,
    [detailVariantOptions, selectedNodeVariantKey],
  );
  const selectedNodeTemplatePoints = Array.isArray(selectedNodePrimaryTemplate?.points) ? selectedNodePrimaryTemplate.points : [];
  const selectedNodeCurrentVariantLabel =
    getProcessingTemplateMountingVariantLabel(selectedNodeCurrentVariantKey, language) ||
    humanizeVariantKey(selectedNodeCurrentVariantKey) ||
    t.notSet;
  const variantChangeRequiresConfirm =
    Number(selectedNodePrimaryTemplate?.points_count || 0) > 0 || selectedNodeTemplatePoints.length > 0;
  const canEditVariant = Boolean(selectedNodeDetail?.can_edit);
  const canSaveVariant =
    canEditVariant &&
    !variantSaveLoading &&
    Boolean(selectedNodeDetail) &&
    Boolean(selectedNodePrimaryTemplate) &&
    Boolean(selectedNodeVariantKey) &&
    selectedNodeVariantKey !== selectedNodeCurrentVariantKey;

  useEffect(() => {
    setSelectedNodeVariantKey(selectedNodeCurrentVariantKey);
    setVariantSaveError("");
    setVariantConfirmOpen(false);
    setVariantDropdownOpen(false);
    setVariantDropdownPreparing(false);
    setVariantDropdownPosition(null);
  }, [selectedNodeCurrentVariantKey, selectedNodeId]);

  const updateVariantDropdownPosition = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }

    const anchor = variantDropdownRef.current;
    if (!anchor) {
      return;
    }

    const menuScrollHeight = variantDropdownMenuRef.current?.scrollHeight || 0;
    const measuredHeight = menuScrollHeight || detailVariantOptions.length * 68 + 16;

    setVariantDropdownPosition(
      calculateVariantDropdownPosition(anchor.getBoundingClientRect(), window.innerWidth, window.innerHeight, measuredHeight),
    );
  }, [detailVariantOptions.length, variantDropdownOpen]);

  const closeVariantDropdown = useCallback(
    (restoreFocus = true) => {
      if (typeof window !== "undefined" && variantDropdownOpenFrameRef.current) {
        window.cancelAnimationFrame(variantDropdownOpenFrameRef.current);
        variantDropdownOpenFrameRef.current = 0;
      }

      setVariantDropdownOpen(false);
      setVariantDropdownPreparing(false);
      setVariantDropdownPosition(null);

      if (restoreFocus && typeof window !== "undefined") {
        window.requestAnimationFrame(() => {
          variantDropdownRef.current?.focus?.();
        });
      }
    },
    [],
  );

  const openVariantDropdown = useCallback(() => {
    if (!canEditVariant) {
      return;
    }

    if (variantDropdownOpen || variantDropdownPreparing) {
      closeVariantDropdown();
      return;
    }

    if (typeof window === "undefined") {
      return;
    }

    const anchor = variantDropdownRef.current;
    if (!anchor) {
      return;
    }

    setVariantDropdownPreparing(true);

    const anchorRect = anchor.getBoundingClientRect();
    const menuScrollHeight = variantDropdownMenuRef.current?.scrollHeight || 0;
    const measuredHeight = menuScrollHeight || detailVariantOptions.length * 68 + 16;
    const requiredScroll = calculateVariantDropdownScrollDelta(anchorRect, window.innerHeight, measuredHeight);
    const scrollAncestor = findNearestVerticalScrollAncestor(anchor);

    if (requiredScroll > 0) {
      scrollNearestVerticalAncestorBy(scrollAncestor, requiredScroll);
    }

    if (variantDropdownOpenFrameRef.current) {
      window.cancelAnimationFrame(variantDropdownOpenFrameRef.current);
    }

    variantDropdownOpenFrameRef.current = window.requestAnimationFrame(() => {
      variantDropdownOpenFrameRef.current = 0;
      updateVariantDropdownPosition();
      setVariantDropdownOpen(true);
      setVariantDropdownPreparing(false);
    });
  }, [canEditVariant, closeVariantDropdown, detailVariantOptions.length, updateVariantDropdownPosition, variantDropdownOpen, variantDropdownPreparing]);

  useLayoutEffect(() => {
    if (!variantDropdownOpen) {
      return undefined;
    }

    updateVariantDropdownPosition();
    return undefined;
  }, [updateVariantDropdownPosition, variantDropdownOpen, selectedNodeVariantKey, selectedNodeId]);

  useLayoutEffect(() => {
    if ((!variantDropdownOpen && !variantDropdownPreparing) || typeof window === "undefined") {
      return undefined;
    }

    const frameId = window.requestAnimationFrame(() => {
      const menu = variantDropdownMenuRef.current;
      const activeOption = menu?.querySelector('[aria-pressed="true"]');
      activeOption?.scrollIntoView({ block: "nearest" });
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [selectedNodeVariantKey, variantDropdownOpen, variantDropdownPreparing]);

  useEffect(() => {
    if ((!variantDropdownOpen && !variantDropdownPreparing) || typeof document === "undefined") {
      return undefined;
    }

    const handlePointerDown = (event) => {
      const target = event?.target;
      if (!(target instanceof Node)) {
        return;
      }

      if (variantDropdownRef.current?.contains(target) || variantDropdownMenuRef.current?.contains(target)) {
        return;
      }

      closeVariantDropdown(false);
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeVariantDropdown(true);
      }
    };

    const handleResize = () => updateVariantDropdownPosition();
    const handleScroll = () => updateVariantDropdownPosition();

    document.addEventListener("pointerdown", handlePointerDown, true);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("resize", handleResize);
    window.addEventListener("scroll", handleScroll, true);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown, true);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [closeVariantDropdown, updateVariantDropdownPosition, variantDropdownOpen, variantDropdownPreparing]);

  function captureReturnState(nextViewMode, restoreScrollOnMount = false) {
    return buildNodeReturnState({
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
      nextViewMode,
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
    const resolvedNodeId = String(nodeId || "").trim();
    const selectedNode = nodes.find((node) => String(node.id) === resolvedNodeId) || null;
    const resolvedNodeName = String(selectedNode?.name || "").trim();

    if (typeof onOpenMountingNodeDetail === "function" && resolvedNodeId && resolvedNodeName) {
      onOpenMountingNodeDetail(resolvedNodeId, resolvedNodeName);
    }

    pendingReturnStateRef.current = captureReturnState("list", false);
    setSelectedNodeId(resolvedNodeId);
    setMountingNodesViewMode("detail");
  }

  function handleBackToList() {
    if (typeof onCloseMountingNodeDetail === "function") {
      onCloseMountingNodeDetail();
    }

    setMountingNodesViewMode("list");
  }

  function handleSelectVariantKey(value) {
    setSelectedNodeVariantKey(String(value || ""));
    setVariantSaveError("");
    closeVariantDropdown();
  }

  async function handleSaveVariantKey(nextVariantKey = selectedNodeVariantKey) {
    if (!selectedNodeDetail || !selectedNodePrimaryTemplate || !canEditVariant || variantSaveLoading) {
      return;
    }

    const normalizedVariantKey = String(nextVariantKey || "").trim();
    if (!normalizedVariantKey || normalizedVariantKey === selectedNodeCurrentVariantKey) {
      return;
    }

    const context = buildNodeEditorContext(selectedNodeDetail);
    if (!context) {
      return;
    }

    const nextTemplate = {
      ...selectedNodePrimaryTemplate,
      mounting_variant_key: normalizedVariantKey,
    };

    setVariantSaveLoading(true);
    setVariantSaveError("");

    try {
      const payload = buildMountingNodeEditorSavePayload({
        context,
        points: selectedNodeTemplatePoints,
        pointsLoaded: true,
        selectedTemplate: nextTemplate,
      });
      const result = await updateMountingNode(token, selectedNodeDetail.id, payload);

      if (!result.success || !result.node) {
        setVariantSaveError(result.error || (language === "uk" ? "Не вдалося зберегти варіант кріплення." : "Unable to save mounting variant."));
        return;
      }

      const nextNode = result.node || selectedNodeDetail;
      const nextNodeId = String(nextNode.id || selectedNodeDetail.id);
      setNodeDetailsById((current) => ({
        ...current,
        [nextNodeId]: nextNode,
      }));
      setNodes((current) =>
        current.map((node) => (String(node.id) === nextNodeId ? { ...node, ...nextNode } : node)),
      );
      setSelectedNodeVariantKey(normalizedVariantKey);
      closeVariantDropdown(false);
      setVariantConfirmOpen(false);
    } catch (error) {
      setVariantSaveError(error?.message || (language === "uk" ? "Не вдалося зберегти варіант кріплення." : "Unable to save mounting variant."));
    } finally {
      setVariantSaveLoading(false);
    }
  }

  function handleVariantSubmit() {
    if (!canSaveVariant) {
      return;
    }

    if (variantChangeRequiresConfirm && !variantConfirmOpen) {
      setVariantConfirmOpen(true);
      return;
    }

    void handleSaveVariantKey(selectedNodeVariantKey);
  }

  function handleCloseVariantConfirm() {
    if (variantSaveLoading) {
      return;
    }

    setVariantConfirmOpen(false);
  }

  function handleOpenCreate() {
    if (typeof onOpenMountingNodeCreate !== "function") {
      return;
    }

    const returnState = captureReturnState("list", true);
    pendingReturnStateRef.current = returnState;
    onOpenMountingNodeCreate(returnState);
  }

  function handleOpenEditor(nodeDetail = selectedNodeDetail) {
    if (!nodeDetail || typeof onOpenMountingNodeEditor !== "function") {
      setOpenEditorError(language === "uk" ? "Не вдалося відкрити редактор: відсутній ідентифікатор монтажного вузла." : "Unable to open the editor: missing mounting node identifier.");
      return;
    }

    const resolvedNodeId = String(nodeDetail.id || nodeDetail.node_id || selectedNodeId || "").trim();
    if (!resolvedNodeId) {
      setOpenEditorError(language === "uk" ? "Не вдалося відкрити редактор: відсутній ідентифікатор монтажного вузла." : "Unable to open the editor: missing mounting node identifier.");
      return;
    }

    const nextReturnState = buildNodeReturnState({
      activeStatusFilter,
      activeVariantFilter,
      appliedSearch,
      displayMode,
      listError,
      listLoading,
      nodeDetailErrorsById,
      nodeDetailsById,
      nodes,
      restoreScrollOnMount: true,
      scrollPosition: typeof window !== "undefined" ? window.scrollY : 0,
      searchInput,
      selectedNodeDetail: nodeDetail,
      selectedNodeId: resolvedNodeId,
      selectedNodeLoading: false,
      nextViewMode: "detail",
    });
    pendingReturnStateRef.current = nextReturnState;
    setOpenEditorError("");
    onOpenMountingNodeEditor(buildNodeEditorContext(nodeDetail, resolvedNodeId), nextReturnState);
  }

  function handleOpenDeleteConfirm() {
    if (!selectedNodeDetail?.can_delete) {
      return;
    }

    setDeleteConfirmError("");
    setDeleteConfirmNode(selectedNodeDetail);
  }

  function closeDeleteConfirm() {
    if (deleteConfirmLoading) {
      return;
    }

    setDeleteConfirmNode(null);
    setDeleteConfirmError("");
  }

  async function handleConfirmDelete() {
    if (!deleteConfirmNode || deleteConfirmLoading) {
      return;
    }

    setDeleteConfirmLoading(true);
    setDeleteConfirmError("");

    try {
      const result = await deleteMountingNode(token, deleteConfirmNode.id);
      if (!result.success) {
        setDeleteConfirmError(result.error || (language === "uk" ? "Не вдалося видалити монтажний вузол." : "Unable to delete mounting node."));
        return;
      }

      if (typeof onCloseMountingNodeDetail === "function") {
        onCloseMountingNodeDetail();
      }

      setDeleteConfirmNode(null);
      setMountingNodesViewMode("list");
      setSelectedNodeId("");
      handleRefresh();
    } catch (error) {
      setDeleteConfirmError(error?.message || (language === "uk" ? "Не вдалося видалити монтажний вузол." : "Unable to delete mounting node."));
    } finally {
      setDeleteConfirmLoading(false);
    }
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
              <p>{t.mountingNodesDescription || ""}</p>
            </div>
            <div className="mounting-nodes-toolbar">
              <span className="service-tree-badge subtle">{language === "uk" ? `Знайдено: ${nodes.length}` : `Found: ${nodes.length}`}</span>
              {typeof onOpenMountingNodeCreate === "function" ? (
                <button
                  className="primary-button mounting-node-create-button"
                  onClick={handleOpenCreate}
                  type="button"
                >
                  <Plus size={16} />
                  {language === "uk" ? "Створити монтажний вузол" : "Create mounting node"}
                </button>
              ) : null}
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
                  const isSelected = String(selectedNodeId) === String(node.id);
                  const ownershipLabel = getOwnershipLabel(nodeDetail || node, language);

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
                      <div className="mounting-node-card-layout">
                        <div className="mounting-node-card-copy">
                          <strong>{node.name || t.notSet}</strong>
                          <p className="mounting-node-card-type">{ownershipLabel}</p>
                        </div>
                        <div className="mounting-node-card-visuals">
                          {renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById)}
                          {renderNodeCardActions(
                            node,
                            nodeDetail,
                            language,
                            t,
                            handleSelectNode,
                            handleOpenEditor,
                          )}
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
                  const isSelected = String(selectedNodeId) === String(node.id);
                  const ownershipLabel = getOwnershipLabel(nodeDetail || node, language);

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
                      <div className="mounting-node-row-layout">
                        <div className="mounting-node-row-copy">
                          <strong>{node.name || t.notSet}</strong>
                          <p className="mounting-node-card-type">{ownershipLabel}</p>
                        </div>
                        <div className="mounting-node-row-visuals">
                          {renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById)}
                          <div className="mounting-node-row-actions">
                            {renderNodeCardActions(
                              node,
                              nodeDetail,
                              language,
                              t,
                              handleSelectNode,
                              handleOpenEditor,
                            )}
                          </div>
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
        <>
        <article className="catalog-card service-catalog-card service-catalog-card-full holes-view-card mounting-node-detail-screen">
          <div className="catalog-page-header mounting-node-detail-header">
            <div className="service-catalog-title">
              <p>{t.mountingNodeDetailsDescription || (language === "uk" ? "Переглядайте склад вузла, варіант кріплення та переходьте до редактора за потреби." : "Inspect the node fittings, mounting variant, and open the editor when needed.")}</p>
            </div>
            <div className="service-catalog-header-actions mounting-node-detail-actions">
              <button className="ghost-button mounting-node-detail-action-button mounting-node-return-button" onClick={handleBackToList} type="button">
                <ArrowLeft size={16} />
                {t.mountingNodeBackToList || (language === "uk" ? "Повернутися до монтажних вузлів" : "Return to mounting nodes")}
              </button>
              {selectedNodeDetail ? (
                <>
                  {/*
                    Keep the DETAIL editor button label local so we can update the visible text
                    without changing the shared translations in App.jsx.
                  */}
                  <button className="primary-button mounting-node-detail-action-button mounting-node-editor-button" onClick={handleOpenEditor} type="button">
                    {language === "uk" ? "Отвори та 3D" : "Open editor and 3D"}
                  </button>
                  {selectedNodeDetail.can_delete ? (
                    <button className="danger-button mounting-node-detail-action-button mounting-node-delete-button" onClick={handleOpenDeleteConfirm} type="button">
                      <Trash2 size={16} />
                      {language === "uk" ? "Видалити" : "Delete"}
                    </button>
                  ) : null}
                </>
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
              <div className="mounting-node-detail-hero">
                <div className="mounting-node-detail-hero-copy">
                  <strong>{language === "uk" ? "Опис" : "Description"}</strong>
                  <p>{selectedNodeDetail.description ? selectedNodeDetail.description : (language === "uk" ? "Опис не вказано" : "Description not set")}</p>
                </div>
              </div>
              {openEditorError ? <p className="form-error mounting-node-detail-open-error">{openEditorError}</p> : null}

              <div className="settings-grid mounting-node-detail-grid">
                {openFittingDetailError ? <p className="form-error mounting-node-detail-open-error">{openFittingDetailError}</p> : null}
                <article className="settings-card mounting-node-detail-items-card">
                  <div className="settings-card-header">
                    <div>
                      <strong>{language === "uk" ? "Фурнітура вузла" : "Node fittings"}</strong>
                      <p>{language === "uk" ? "Клікніть картку, щоб відкрити ту саму картку фурнітури в модалі." : "Click a card to open the same fitting details modal."}</p>
                    </div>
                  </div>
                  <div className="mounting-node-detail-item-list">
                    {selectedNodeDetail.items?.length ? (
                      selectedNodeDetail.items.map((item, index) =>
                        renderNodeDetailItemCard(
                          item,
                          index,
                          language,
                          t,
                          fittingThumbnailStateById,
                          onOpenFittingDetail,
                          token,
                          openFittingDetailLoadingId,
                          setOpenFittingDetailLoadingId,
                          setOpenFittingDetailError,
                        ),
                      )
                    ) : (
                      <div className="empty-state compact-empty-state">
                        <span>{t.notSet}</span>
                      </div>
                    )}
                  </div>
                </article>

                <article className="settings-card mounting-node-detail-variant-card">
                  <div className="settings-card-header">
                    <div>
                      <strong>{language === "uk" ? "Варіант кріплення" : "Mounting variant"}</strong>
                      <p>{language === "uk" ? "Змініть варіант кріплення поточного вузла та збережіть зміни." : "Change the current node mounting variant and save the update."}</p>
                    </div>
                  </div>
                  <div className="mounting-node-detail-variant-body">
                    <div
                      className={`holes-mounting-variant-dropdown-shell mounting-node-detail-variant-shell${variantDropdownOpen ? " is-open" : ""}`}
                    >
                      <button
                        aria-expanded={canEditVariant ? variantDropdownOpen : false}
                        aria-haspopup={canEditVariant ? "listbox" : undefined}
                        className="holes-mounting-variant-toggle mounting-node-detail-variant-toggle"
                        ref={variantDropdownRef}
                        disabled={!canEditVariant}
                        onClick={openVariantDropdown}
                        type="button"
                      >
                        <span className="holes-mounting-variant-toggle-mark" aria-hidden="true">
                          {selectedNodeVariantModel?.icon ? <img alt="" src={selectedNodeVariantModel.icon} /> : <span>⋯</span>}
                        </span>
                        <span className="holes-mounting-variant-toggle-copy">
                          <strong>{selectedNodeVariantModel?.label || selectedNodeCurrentVariantLabel}</strong>
                          <span>
                            {selectedNodeVariantModel?.description ||
                              (language === "uk" ? "Без опису" : "No description")}
                          </span>
                        </span>
                        {canEditVariant ? <ChevronRight className="holes-mounting-variant-toggle-arrow" size={16} /> : null}
                      </button>
                    </div>
                    {canEditVariant && variantSaveError ? <p className="form-error">{variantSaveError}</p> : null}
                    {canEditVariant ? (
                      <div className="mounting-node-detail-variant-actions">
                        <button
                          className="primary-button"
                          disabled={!canSaveVariant}
                          onClick={handleVariantSubmit}
                          type="button"
                        >
                          {variantSaveLoading
                            ? (language === "uk" ? "Збереження..." : "Saving...")
                            : (language === "uk" ? "Зберегти варіант кріплення" : "Save mounting variant")}
                        </button>
                      </div>
                    ) : null}
                  </div>
                </article>
              </div>
              {canEditVariant && variantDropdownOpen && variantDropdownPosition && typeof document !== "undefined"
                ? createPortal(
                    <div
                      className="mounting-node-detail-variant-portal"
                      style={{
                        left: `${variantDropdownPosition.left}px`,
                        position: "fixed",
                        zIndex: 19,
                        top: `${variantDropdownPosition.top}px`,
                        width: `${variantDropdownPosition.width}px`,
                      }}
                    >
                      <div
                        className="holes-mounting-variant-menu mounting-node-detail-variant-menu"
                        ref={variantDropdownMenuRef}
                        role="listbox"
                        style={{
                          maxHeight: `${variantDropdownPosition.maxHeight}px`,
                          minHeight: 0,
                          overflowX: "hidden",
                          overflowY: "auto",
                          overscrollBehavior: "contain",
                          position: "static",
                          scrollbarGutter: "stable",
                          width: "100%",
                        }}
                      >
                        {detailVariantOptions.map((option, index) => {
                          const isActive = selectedNodeVariantKey === option.value;

                          return (
                            <button
                              aria-pressed={isActive}
                              className={`holes-mounting-variant-option mounting-node-detail-variant-option${isActive ? " active" : ""}`}
                              key={`mounting-node-variant-${index}-${option.value}`}
                              onClick={() => handleSelectVariantKey(option.value)}
                              type="button"
                            >
                              <span className="holes-mounting-variant-option-mark" aria-hidden="true">
                                {option.icon ? <img alt="" src={option.icon} /> : <span>⋯</span>}
                              </span>
                              <span className="holes-mounting-variant-option-copy">
                                <strong>{option.label}</strong>
                                <span>{option.description || (language === "uk" ? "Без опису" : "No description")}</span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </div>,
                    document.body,
                  )
                : null}
            </>
          ) : (
            <div className="empty-state compact-empty-state">
              <span>{t.mountingNodesEmpty || (language === "uk" ? "Монтажні вузли ще не створені." : "Mounting nodes have not been created yet.")}</span>
            </div>
          )}
      {deleteConfirmNode ? (
        <div aria-modal="true" className="modal-backdrop" onClick={closeDeleteConfirm} role="dialog">
          <section className="confirm-modal" onClick={(event) => event.stopPropagation()}>
            <header className="confirm-header">
              <h2>{language === "uk" ? "Видалити монтажний вузол" : "Delete mounting node"}</h2>
              <button aria-label={language === "uk" ? "Закрити підтвердження" : "Close confirmation"} className="icon-button" disabled={deleteConfirmLoading} onClick={closeDeleteConfirm} type="button">
                <X size={18} />
              </button>
            </header>
            <p>
              {language === "uk"
                ? `Видалити вузол "${deleteConfirmNode.name || deleteConfirmNode.code || deleteConfirmNode.id}"?`
                : `Delete mounting node "${deleteConfirmNode.name || deleteConfirmNode.code || deleteConfirmNode.id}"?`}
            </p>
            {deleteConfirmError ? <p className="form-error">{deleteConfirmError}</p> : null}
            <div className="confirm-actions">
              <button className="ghost-button" disabled={deleteConfirmLoading} onClick={closeDeleteConfirm} type="button">
                {language === "uk" ? "Скасувати" : "Cancel"}
              </button>
              <button className="danger-button" disabled={deleteConfirmLoading} onClick={handleConfirmDelete} type="button">
                {deleteConfirmLoading ? (language === "uk" ? "Видалення..." : "Deleting...") : (language === "uk" ? "Видалити" : "Delete")}
              </button>
            </div>
          </section>
        </div>
      ) : null}
      {variantConfirmOpen ? (
        <div aria-modal="true" className="modal-backdrop" onClick={handleCloseVariantConfirm} role="dialog">
          <section className="confirm-modal" onClick={(event) => event.stopPropagation()}>
            <header className="confirm-header">
              <h2>{getNodeVariantChangeTitle(language)}</h2>
              <button
                aria-label={language === "uk" ? "Закрити підтвердження" : "Close confirmation"}
                className="icon-button"
                disabled={variantSaveLoading}
                onClick={handleCloseVariantConfirm}
                type="button"
              >
                <X size={18} />
              </button>
            </header>
            <p>{getNodeVariantChangeWarning(language)}</p>
            {variantSaveError ? <p className="form-error">{variantSaveError}</p> : null}
            <div className="confirm-actions">
              <button className="ghost-button" disabled={variantSaveLoading} onClick={handleCloseVariantConfirm} type="button">
                {language === "uk" ? "Скасувати" : "Cancel"}
              </button>
              <button
                className="primary-button"
                disabled={variantSaveLoading}
                onClick={() => void handleSaveVariantKey(selectedNodeVariantKey)}
                type="button"
              >
                {variantSaveLoading ? (language === "uk" ? "Збереження..." : "Saving...") : (language === "uk" ? "Продовжити" : "Continue")}
              </button>
            </div>
          </section>
        </div>
      ) : null}
        </article>
        </>
      )}
    </section>
  );
}
