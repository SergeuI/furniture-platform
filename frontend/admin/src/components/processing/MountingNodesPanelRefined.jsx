import { ArrowLeft, Box, ChevronRight, Info, LayoutGrid, List, Plus, RefreshCw, Search, Trash2, X } from "lucide-react";
import { createPortal } from "react-dom";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import {
  deleteMountingNode,
  getFittingDetails,
  getFittingImageBlob,
  getMountingNode,
  getMountingNodeVersion,
  getMountingNodes,
  updateMountingNode,
} from "../../api.js";
import { getProcessingTemplateMountingVariantLabel } from "../../processingTemplates.js";
import {
  buildMountingNodeThumbnailLoadPlan,
  buildMountingNodeThumbnailState,
  isCurrentMountingNodeThumbnailRequest,
} from "../../mountingNodesThumbnailLifecycle.js";
import {
  buildMountingNodeEditorSavePayload,
  getMountingNodeSnapshotPointCount,
  resolveActiveMountingNodeVersion,
  resolveMountingNodeEditorContext,
} from "../../mountingNodesEditor.js";
import {
  getMountingNodeCategoryLabel,
  getMountingNodeCategoryOptions,
  normalizeMountingNodeCategoryCode,
} from "../../mountingNodeCategories.js";
import {
  getMountingNodeFunctionalLabel,
} from "../../mountingNodeFunctionalCodes.js";
import {
  buildMountingNodesBreadcrumbItems,
  resolveMountingNodesCategoryCode,
} from "../../mountingNodesNavigation.js";
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
const MOUNTING_NODE_CATEGORY_FILTER_NULL = "null";

function normalizeFilterValue(value) {
  return String(value || "").trim();
}

function normalizeCategoryFilterValue(value) {
  const normalizedValue = normalizeFilterValue(value);

  if (!normalizedValue) {
    return "all";
  }

  if (normalizedValue === "all" || normalizedValue === MOUNTING_NODE_CATEGORY_FILTER_NULL) {
    return normalizedValue;
  }

  return normalizeMountingNodeCategoryCode(normalizedValue) ? normalizedValue : "all";
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
    activeCategoryFilter: normalizeCategoryFilterValue(normalizedPayload.activeCategoryFilter || "all"),
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

function formatMountingNodeVersionDate(value, language) {
  if (!value) {
    return "";
  }

  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return parsed.toLocaleString(language === "uk" ? "uk-UA" : "en-US");
}

function getMountingNodeVersionSummary(version, language, t) {
  const snapshot = version?.snapshot && typeof version.snapshot === "object" ? version.snapshot : {};
  const templates = Array.isArray(snapshot.templates) ? snapshot.templates : [];
  const primaryTemplateLink = templates.find((template) => template?.is_default) || templates[0] || null;
  const templateSource =
    primaryTemplateLink?.template && typeof primaryTemplateLink.template === "object"
      ? primaryTemplateLink.template
      : primaryTemplateLink;
  const variantKey = String(
    templateSource?.mounting_variant_key ||
      primaryTemplateLink?.mounting_variant_key ||
      snapshot.mounting_variant_key ||
      "",
  ).trim();
  const variantLabel =
    getProcessingTemplateMountingVariantLabel(variantKey, language) ||
    humanizeVariantKey(variantKey) ||
    t.notSet;
  const itemsCount = Number(version?.items_count ?? snapshot.items?.length ?? 0) || 0;
  const templatesCount = Number(version?.templates_count ?? templates.length ?? 0) || 0;
  const pointCount = Number(getMountingNodeSnapshotPointCount(snapshot)) || 0;
  const dateLabel = formatMountingNodeVersionDate(version?.created_at, language) || t.notSet;
  const normalizedEventType = String(version?.event_type || "").trim();
  const eventLabel =
    normalizedEventType === "create"
      ? (language === "uk" ? "Створення" : "Created")
      : normalizedEventType === "delete" || normalizedEventType === "archive"
        ? (language === "uk" ? "Архів" : "Archived")
        : (language === "uk" ? "Редагування" : "Updated");

  return {
    dateLabel,
    eventLabel,
    itemsCount,
    pointCount,
    templatesCount,
    variantLabel,
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

function getNodeCategoryLabel(node, language) {
  return (
    getMountingNodeCategoryLabel(node?.category_code, language) ||
    (language === "uk" ? "Категорію не вказано" : "Category not set")
  );
}

function getNodeFunctionalLabel(node, language) {
  return (
    getMountingNodeFunctionalLabel(node?.functional_code, language) ||
    (language === "uk" ? "Не вказано" : "Not set")
  );
}

export function buildNodeEditorContext(nodeDetail, fallbackNodeId = "") {
  const resolvedContext = resolveMountingNodeEditorContext(
    nodeDetail && typeof nodeDetail === "object" ? nodeDetail : null,
    fallbackNodeId,
  );

  if (!resolvedContext) {
    return null;
  }

  return {
    ...resolvedContext,
    nodeCode: String(nodeDetail?.code || "").trim(),
    functional_code: resolvedContext?.functional_code ?? null,
  };
}

function buildNodeReturnState({
  activeStatusFilter,
  activeCategoryFilter,
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
    activeCategoryFilter,
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

function getNodeEditorTemplateSource(nodeDetail) {
  const templateLink = getNodePrimaryTemplate(nodeDetail);
  const actualTemplate =
    templateLink?.template && typeof templateLink.template === "object"
      ? templateLink.template
      : templateLink?.fitting_hole_template && typeof templateLink.fitting_hole_template === "object"
        ? templateLink.fitting_hole_template
        : templateLink || null;
  const points = Array.isArray(actualTemplate?.points)
    ? actualTemplate.points
    : Array.isArray(templateLink?.points)
      ? templateLink.points
      : [];

  return {
    actualTemplate,
    points,
    templateLink,
  };
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

function readBlobAsDataUrl(blob, isCurrentRequest) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    let settled = false;

    const cleanup = () => {
      reader.onload = null;
      reader.onloadend = null;
      reader.onerror = null;
      reader.onabort = null;
    };

    const resolveOnce = (value) => {
      if (settled) {
        return;
      }

      settled = true;
      cleanup();
      resolve(value);
    };

    const rejectOnce = (error) => {
      if (settled) {
        return;
      }

      settled = true;
      cleanup();
      reject(error);
    };

    reader.onload = () => {
      if (!isCurrentRequest()) {
        rejectOnce(new Error("Unable to load fitting image"));
        return;
      }

      resolveOnce(String(reader.result || ""));
    };

    reader.onloadend = () => {
      if (!settled && !isCurrentRequest()) {
        rejectOnce(new Error("Unable to load fitting image"));
      }
    };

    reader.onerror = () => {
      if (!isCurrentRequest()) {
        rejectOnce(new Error("Unable to load fitting image"));
        return;
      }

      rejectOnce(reader.error || new Error("Unable to load fitting image"));
    };

    reader.onabort = () => {
      if (!isCurrentRequest()) {
        rejectOnce(new Error("Unable to load fitting image"));
        return;
      }

      rejectOnce(new Error("Unable to load fitting image"));
    };

    reader.readAsDataURL(blob);
  });
}

export default function MountingNodesPanelRefined({
  language = "uk",
  editorMode = false,
  initialState = null,
  onOpenConnectionsOverview = null,
  onOpenMountingNodeCreate = null,
  onOpenMountingNodeCategories = null,
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
  const [activeCategoryFilter, setActiveCategoryFilter] = useState(initialReturnState.activeCategoryFilter);
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
  const [selectedNodeVersionDetail, setSelectedNodeVersionDetail] = useState(null);
  const [selectedNodeVersionLoadingId, setSelectedNodeVersionLoadingId] = useState("");
  const [selectedNodeVersionError, setSelectedNodeVersionError] = useState("");
  const listRequestIdRef = useRef(0);
  const detailRequestIdRef = useRef(0);
  const thumbnailRequestGenerationRef = useRef(0);
  const listRequestTokenRef = useRef(Number(listRequestToken || 0));
  const selectedNodeIdRef = useRef(String(initialReturnState.selectedNodeId || ""));
  const variantDropdownRef = useRef(null);
  const variantDropdownMenuRef = useRef(null);
  const variantDropdownOpenFrameRef = useRef(0);
  const mountingNodeHistoryCardRef = useRef(null);
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
      category_code:
        activeCategoryFilter === "all"
          ? undefined
          : activeCategoryFilter === MOUNTING_NODE_CATEGORY_FILTER_NULL
            ? "null"
            : activeCategoryFilter,
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
  }, [activeCategoryFilter, activeStatusFilter, activeVariantFilter, appliedSearch, reloadToken, t.mountingNodesError, token]);

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
      thumbnailRequestGenerationRef.current += 1;
      setFittingThumbnailStateById({});
      return undefined;
    }

    const currentGeneration = ++thumbnailRequestGenerationRef.current;
    let cancelled = false;

    const fittingIds = buildMountingNodeThumbnailLoadPlan({
      currentGeneration,
      fittingThumbnailStateById,
      nodeDetailsById,
    });

    if (!fittingIds.length) {
      return undefined;
    }

    setFittingThumbnailStateById((current) => {
      const next = { ...current };
      fittingIds.forEach((fittingId) => {
        next[fittingId] = buildMountingNodeThumbnailState("loading", currentGeneration);
      });
      return next;
    });

    fittingIds.forEach((fittingId) => {
      (async () => {
        try {
          const result = await getFittingDetails(token, fittingId);
          if (!isCurrentMountingNodeThumbnailRequest(currentGeneration, thumbnailRequestGenerationRef.current, cancelled)) {
            return;
          }

          if (!result.success || !result.item) {
            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                ...buildMountingNodeThumbnailState("error", currentGeneration),
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
                ...buildMountingNodeThumbnailState("no-image", currentGeneration),
              },
            }));
            return;
          }

          const imageResult = await getFittingImageBlob(token, fittingId, primaryImage.id);
          if (!isCurrentMountingNodeThumbnailRequest(currentGeneration, thumbnailRequestGenerationRef.current, cancelled)) {
            return;
          }

          if (!imageResult.success || !imageResult.blob) {
            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                ...buildMountingNodeThumbnailState("error", currentGeneration),
              },
            }));
            return;
          }

          let imageUrl = "";
          try {
            imageUrl = await readBlobAsDataUrl(imageResult.blob, () =>
              isCurrentMountingNodeThumbnailRequest(currentGeneration, thumbnailRequestGenerationRef.current, cancelled),
            );
          } catch {
            if (!isCurrentMountingNodeThumbnailRequest(currentGeneration, thumbnailRequestGenerationRef.current, cancelled)) {
              return;
            }

            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                ...buildMountingNodeThumbnailState("error", currentGeneration),
              },
            }));
            return;
          }

          if (!isCurrentMountingNodeThumbnailRequest(currentGeneration, thumbnailRequestGenerationRef.current, cancelled)) {
            return;
          }

          if (!imageUrl) {
            setFittingThumbnailStateById((current) => ({
              ...current,
              [fittingId]: {
                ...buildMountingNodeThumbnailState("error", currentGeneration),
              },
            }));
            return;
          }

          setFittingThumbnailStateById((current) => ({
            ...current,
            [fittingId]: {
              ...buildMountingNodeThumbnailState("loaded", currentGeneration, imageUrl),
            },
          }));
        } catch {
          if (!isCurrentMountingNodeThumbnailRequest(currentGeneration, thumbnailRequestGenerationRef.current, cancelled)) {
            return;
          }

          setFittingThumbnailStateById((current) => ({
            ...current,
            [fittingId]: {
              ...buildMountingNodeThumbnailState("error", currentGeneration),
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
  const selectedNodeActiveVersion = useMemo(
    () => resolveActiveMountingNodeVersion(selectedNodeDetail),
    [selectedNodeDetail],
  );
  const selectedNodeViewDetail =
    selectedNodeVersionDetail?.snapshot && typeof selectedNodeVersionDetail.snapshot === "object"
      ? selectedNodeVersionDetail.snapshot
      : selectedNodeDetail;
  const selectedNodeResolvedContext = useMemo(
    () => resolveMountingNodeEditorContext(selectedNodeDetail, selectedNode?.id || selectedNodeId),
    [selectedNodeDetail, selectedNode?.id, selectedNodeId],
  );
  const selectedNodeDetailForDisplay = selectedNodeVersionDetail
    ? selectedNodeViewDetail
    : selectedNodeResolvedContext?.nodeDetail || selectedNodeDetail;
  const selectedNodeVersionBanner = selectedNodeVersionDetail || null;
  const selectedNodeVersionBannerSummary = selectedNodeVersionBanner
    ? getMountingNodeVersionSummary(selectedNodeVersionBanner, language, t)
    : null;
  const selectedNodePrimaryTemplate = useMemo(
    () => getNodePrimaryTemplate(selectedNodeDetailForDisplay),
    [selectedNodeDetailForDisplay],
  );
  const selectedNodeActiveVariantKey = String(selectedNodePrimaryTemplate?.mounting_variant_key || "").trim();
  const selectedNodeActiveVariantLabel =
    getProcessingTemplateMountingVariantLabel(selectedNodeActiveVariantKey, language) ||
    humanizeVariantKey(selectedNodeActiveVariantKey) ||
    t.notSet;
  const selectedNodeCurrentVariantKey = String(
    (selectedNodeVersionBanner ? getNodePrimaryTemplate(selectedNodeViewDetail) : selectedNodePrimaryTemplate)?.mounting_variant_key || "",
  ).trim();
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
  const categoryFilterOptions = useMemo(
    () => [
      {
        value: "all",
        label: language === "uk" ? "Усі категорії" : "All categories",
      },
      {
        value: MOUNTING_NODE_CATEGORY_FILTER_NULL,
        label: language === "uk" ? "Категорію не вказано" : "Category not set",
      },
      ...getMountingNodeCategoryOptions(language).map((category) => ({
        value: category.code,
        label: category.label,
      })),
    ],
    [language],
  );
  const activeMountingCategoryLabel = useMemo(() => {
    if (activeCategoryFilter === MOUNTING_NODE_CATEGORY_FILTER_NULL) {
      return language === "uk" ? "Категорію не вказано" : "Category not set";
    }

    return (
      getMountingNodeCategoryLabel(activeCategoryFilter, language) ||
      (language === "uk" ? "Усі категорії" : "All categories")
    );
  }, [activeCategoryFilter, language]);
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
  const selectedNodeDisplayPointCount = Number(getMountingNodeSnapshotPointCount(selectedNodeDetailForDisplay)) || 0;
  const selectedNodeActivePointCount = selectedNodeDisplayPointCount;
  const variantChangeRequiresConfirm =
    Number(selectedNodePrimaryTemplate?.points_count || 0) > 0 || selectedNodeActivePointCount > 0;
  const canEditVariant = Boolean(selectedNodeDetail?.can_edit) && !selectedNodeVersionBanner;
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
  }, [selectedNodeCurrentVariantKey, selectedNodeId, selectedNodeVersionDetail]);

  useEffect(() => {
    setSelectedNodeVersionDetail(null);
    setSelectedNodeVersionLoadingId("");
    setSelectedNodeVersionError("");
  }, [selectedNodeId]);

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
      activeCategoryFilter,
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

  function handleCategoryFilterChange(value) {
    setActiveCategoryFilter(normalizeCategoryFilterValue(value));
  }

  function handleVariantFilterChange(value) {
    setActiveVariantFilter(String(value || "all"));
  }

  function handleSelectNode(nodeId) {
    const resolvedNodeId = String(nodeId || "").trim();
    const selectedNode = nodes.find((node) => String(node.id) === resolvedNodeId) || null;
    const resolvedNodeName = String(selectedNode?.name || "").trim();

    if (typeof onOpenMountingNodeDetail === "function" && resolvedNodeId && resolvedNodeName) {
      onOpenMountingNodeDetail(resolvedNodeId, resolvedNodeName, selectedNode?.category_code ?? null);
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

  function handleReturnToCategories() {
    if (typeof onOpenMountingNodeCategories === "function") {
      onOpenMountingNodeCategories();
      return;
    }

    setActiveCategoryFilter("all");
    setMountingNodesViewMode("list");
  }

  function handleScrollToVersionHistory() {
    mountingNodeHistoryCardRef.current?.scrollIntoView?.({
      behavior: "smooth",
      block: "start",
    });
  }

  async function handleOpenVersion(version) {
    const versionId = String(version?.id || "").trim();
    const nodeId = String(selectedNodeDetail?.id || selectedNode?.id || "").trim();

    if (!nodeId || !versionId || versionId === String(selectedNodeVersionDetail?.id || "")) {
      return;
    }

    if (version?.is_current) {
      setSelectedNodeVersionDetail(null);
      setSelectedNodeVersionLoadingId("");
      setSelectedNodeVersionError("");
      return;
    }

    setSelectedNodeVersionLoadingId(versionId);
    setSelectedNodeVersionError("");

    try {
      const result = await getMountingNodeVersion(token, nodeId, versionId);
      if (!result.success || !result.version) {
        setSelectedNodeVersionError(result.error || (language === "uk" ? "Не вдалося відкрити версію." : "Unable to open version."));
        return;
      }

      setSelectedNodeVersionDetail(result.version);
    } catch (error) {
      setSelectedNodeVersionError(error?.message || (language === "uk" ? "Не вдалося відкрити версію." : "Unable to open version."));
    } finally {
      setSelectedNodeVersionLoadingId("");
    }
  }

  function handleReturnToActiveVersion() {
    setSelectedNodeVersionDetail(null);
    setSelectedNodeVersionLoadingId("");
    setSelectedNodeVersionError("");
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

    const selectedTemplateSource =
      selectedNodePrimaryTemplate?.template && typeof selectedNodePrimaryTemplate.template === "object"
        ? selectedNodePrimaryTemplate.template
        : selectedNodePrimaryTemplate;
    const nextTemplate = {
      ...selectedTemplateSource,
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
        setSelectedNodeVariantKey(selectedNodeCurrentVariantKey);
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
      setSelectedNodeVariantKey(selectedNodeCurrentVariantKey);
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

  function handleOpenEditor(nodeDetail = selectedNodeDetail || nodeDetailsById[String(selectedNodeId)] || null) {
    const resolvedNodeDetail = nodeDetail || selectedNodeDetail || nodeDetailsById[String(selectedNodeId)] || null;

    if (!resolvedNodeDetail || typeof onOpenMountingNodeEditor !== "function") {
      setOpenEditorError(language === "uk" ? "Не вдалося відкрити редактор: відсутній ідентифікатор монтажного вузла." : "Unable to open the editor: missing mounting node identifier.");
      return;
    }

    const resolvedNodeId = String(resolvedNodeDetail.id || resolvedNodeDetail.node_id || selectedNodeId || "").trim();
    if (!resolvedNodeId) {
      setOpenEditorError(language === "uk" ? "Не вдалося відкрити редактор: відсутній ідентифікатор монтажного вузла." : "Unable to open the editor: missing mounting node identifier.");
      return;
    }

    const nextReturnState = buildNodeReturnState({
      activeStatusFilter,
      activeCategoryFilter,
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
      selectedNodeDetail: resolvedNodeDetail,
      selectedNodeId: resolvedNodeId,
      selectedNodeLoading: false,
      nextViewMode: "detail",
    });
    pendingReturnStateRef.current = nextReturnState;
    setOpenEditorError("");
    onOpenMountingNodeEditor(buildNodeEditorContext(resolvedNodeDetail, resolvedNodeId), nextReturnState);
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
        setDeleteConfirmError(result.error || (language === "uk" ? "Не вдалося архівувати монтажний вузол." : "Unable to archive mounting node."));
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
      setDeleteConfirmError(error?.message || (language === "uk" ? "Не вдалося архівувати монтажний вузол." : "Unable to archive mounting node."));
    } finally {
      setDeleteConfirmLoading(false);
    }
  }

  const mountingNodesHeaderBreadcrumbItems = useMemo(() => {
    const rootLabel = language === "uk" ? "Кріплення та з'єднання" : "Connections";
    const nodesLabel = language === "uk" ? "Монтажні вузли" : "Mounting nodes";
    const categoryLabel = activeCategoryFilter === "all" ? nodesLabel : activeMountingCategoryLabel;
    const detailNodeName = String(selectedNodeDetailForDisplay?.name || selectedNodeDetail?.name || "").trim();
    const isDetailMode = mountingNodesViewMode === "detail";
    const baseTrail = buildMountingNodesBreadcrumbItems({
      allListLabel: language === "uk" ? "Усі монтажні вузли" : "All mounting nodes",
      categoryCode: activeCategoryFilter === "all" ? undefined : activeCategoryFilter,
      categoryLabel,
      createLabel: language === "uk" ? "Створення вузла" : "Node creation",
      editingLabel: language === "uk" ? "Редагування вузла" : "Node editing",
      language,
      listLabel: nodesLabel,
      mode: isDetailMode ? "detail" : "list",
      nodeName: detailNodeName,
      onOpenCategories: onOpenMountingNodeCategories || undefined,
      onOpenCategoryList: handleBackToList,
      onOpenNodeDetail: handleBackToList,
    });

    return [
      {
        current: false,
        label: rootLabel,
        onClick: typeof onOpenConnectionsOverview === "function" ? onOpenConnectionsOverview : undefined,
        title: rootLabel,
      },
      ...baseTrail,
    ];
  }, [
    activeCategoryFilter,
    activeMountingCategoryLabel,
    handleBackToList,
    language,
    mountingNodesViewMode,
    onOpenConnectionsOverview,
    onOpenMountingNodeCategories,
    selectedNodeDetail,
    selectedNodeDetailForDisplay,
  ]);

  if (!token) {
    return null;
  }

  return (
    <section aria-hidden={editorMode} className="dashboard-panel" hidden={editorMode} id="mounting-nodes-panel">
      {mountingNodesViewMode === "list" ? (
        <>
          <div className="catalog-page-header material-taxonomy-page-header mounting-nodes-page-header">
            <div className="service-catalog-title material-taxonomy-page-title">
              <div className="fitting-category-breadcrumb fitting-category-breadcrumb-top">
                {mountingNodesHeaderBreadcrumbItems.map((item, index) => {
                  const isLast = index === mountingNodesHeaderBreadcrumbItems.length - 1;
                  const isCurrent = Boolean(item?.current);
                  const label = String(item?.label || "").trim();
                  const title = String(item?.title || label || "").trim();

                  return (
                    <span className="fitting-category-breadcrumb-item" key={`${label || "crumb"}-${index}`}>
                      <h3 className="catalog-breadcrumb-title">
                        {isCurrent || !item?.onClick ? (
                          <span aria-current={isCurrent ? "page" : undefined} title={title || label}>
                            {label}
                          </span>
                        ) : (
                          <button className="catalog-breadcrumb-link" onClick={item.onClick} title={title || label} type="button">
                            {label}
                          </button>
                        )}
                      </h3>
                      {!isLast ? <span className="fitting-breadcrumb-separator">/</span> : null}
                    </span>
                  );
                })}
              </div>
              <p>{t.mountingNodesDescription || "Переглядайте монтажні вузли у компактній плитці або списку та відкривайте деталі окремо."}</p>
            </div>
            <div className="service-catalog-header-actions mounting-nodes-header-actions">
              <span className="service-tree-badge subtle">{language === "uk" ? `Знайдено: ${nodes.length}` : `Found: ${nodes.length}`}</span>
              {activeCategoryFilter !== "all" ? (
                <span className="service-tree-badge subtle">
                  {language === "uk" ? "Категорія:" : "Category:"} {activeMountingCategoryLabel}
                </span>
              ) : null}
              {activeCategoryFilter !== "all" ? (
                <button
                  className="primary-button mounting-node-detail-action-button mounting-node-return-button"
                  onClick={handleReturnToCategories}
                  type="button"
                >
                  <ArrowLeft size={16} />
                  {language === "uk" ? "Повернутися до категорій" : "Return to categories"}
                </button>
              ) : null}
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
            </div>
          </div>
          <div className="mounting-nodes-panel-head">
            <div className="mounting-nodes-controls-row">
              <form className="project-filter-form mounting-nodes-filter-form" onSubmit={handleSearchSubmit}>
                <label className="mounting-nodes-search mounting-nodes-search-field">
                  {t.mountingNodesSearchPlaceholder || "Пошук монтажних вузлів"}
                  <input
                    onChange={(event) => setSearchInput(event.target.value)}
                    placeholder={t.mountingNodesSearchPlaceholder || "Пошук монтажних вузлів"}
                    type="search"
                    value={searchInput}
                  />
                </label>
                {activeCategoryFilter === "all" ? (
                  <label className="mounting-nodes-filter-field">
                    {language === "uk" ? "Категорія" : "Category"}
                    <select onChange={(event) => handleCategoryFilterChange(event.target.value)} value={activeCategoryFilter}>
                      {categoryFilterOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
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
              <div className="mounting-nodes-view-toggle materials-mode-switch" role="group" aria-label={language === "uk" ? "Вигляд каталогу" : "Catalog view mode"}>
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
                  const categoryLabel = getNodeCategoryLabel(nodeDetail || node, language);

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
                          <p className="mounting-node-card-type">{categoryLabel}</p>
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
                  const categoryLabel = getNodeCategoryLabel(nodeDetail || node, language);

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
                          <p className="mounting-node-card-type">{categoryLabel}</p>
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
          ) : activeCategoryFilter !== "all" ? (
            <div className="empty-state compact-empty-state">
              <span>
                {language === "uk"
                  ? "У цій категорії монтажних вузлів поки немає"
                  : "There are no mounting nodes in this category yet"}
              </span>
              <button className="primary-button" onClick={handleRefresh} type="button">
                {t.mountingNodesRetry || (language === "uk" ? "Повторити" : "Retry")}
              </button>
            </div>
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
              <div className="fitting-category-breadcrumb fitting-category-breadcrumb-top">
                {mountingNodesHeaderBreadcrumbItems.map((item, index) => {
                  const isLast = index === mountingNodesHeaderBreadcrumbItems.length - 1;
                  const isCurrent = Boolean(item?.current);
                  const label = String(item?.label || "").trim();
                  const title = String(item?.title || label || "").trim();

                  return (
                    <span className="fitting-category-breadcrumb-item" key={`${label || "crumb"}-${index}`}>
                      <h3 className="catalog-breadcrumb-title">
                        {isCurrent || !item?.onClick ? (
                          <span aria-current={isCurrent ? "page" : undefined} title={title || label}>
                            {label}
                          </span>
                        ) : (
                          <button className="catalog-breadcrumb-link" onClick={item.onClick} title={title || label} type="button">
                            {label}
                          </button>
                        )}
                      </h3>
                      {!isLast ? <span className="fitting-breadcrumb-separator">/</span> : null}
                    </span>
                  );
                })}
              </div>
              <p>{t.mountingNodeDetailsDescription || (language === "uk" ? "Переглядайте склад вузла, варіант кріплення та переходьте до редактора за потреби." : "Inspect the node fittings, mounting variant, and open the editor when needed.")}</p>
            </div>
            <div className="service-catalog-header-actions mounting-node-detail-actions">
              <button className="ghost-button mounting-node-detail-action-button mounting-node-return-button" onClick={handleBackToList} type="button">
                <ArrowLeft size={16} />
                {t.mountingNodeBackToList || (language === "uk" ? "Повернутися до монтажних вузлів" : "Return to mounting nodes")}
              </button>
              {selectedNodeVersionBanner ? (
                <button className="ghost-button mounting-node-detail-action-button mounting-node-version-back-button" onClick={handleReturnToActiveVersion} type="button">
                  {language === "uk" ? "Повернутися до активної версії" : "Return to active version"}
                </button>
              ) : selectedNodeDetail ? (
                <>
                  {/*
                    Keep the DETAIL editor button label local so we can update the visible text
                    without changing the shared translations in App.jsx.
                  */}
                  <button className="primary-button mounting-node-detail-action-button mounting-node-editor-button" onClick={() => handleOpenEditor()} type="button">
                    {language === "uk" ? "Редагувати склад та отвори" : "Edit composition and openings"}
                  </button>
                  {selectedNodeDetail.can_delete ? (
                    <button className="danger-button mounting-node-detail-action-button mounting-node-delete-button" onClick={handleOpenDeleteConfirm} type="button">
                      <Trash2 size={16} />
                      {language === "uk" ? "Архівувати" : "Archive"}
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
                  <p>
                    {selectedNodeDetailForDisplay?.description
                      ? selectedNodeDetailForDisplay.description
                      : (language === "uk" ? "Опис не вказано" : "Description not set")}
                  </p>
                </div>

                <div className={`mounting-node-detail-version-summary-card${selectedNodeVersionBanner ? " is-preview" : ""}`}>
                  <div className="mounting-node-detail-version-summary-head">
                    <div>
                      <strong>
                        {language === "uk"
                          ? `Активна версія: ${selectedNodeActiveVersion?.version_number || 1}`
                          : `Active version: ${selectedNodeActiveVersion?.version_number || 1}`}
                      </strong>
                      <p>
                        {language === "uk"
                          ? "Кожне збереження створює окрему версію монтажного вузла."
                          : "Each save creates a separate mounting node version."}
                      </p>
                    </div>
                    <div className="mounting-node-detail-version-summary-actions">
                      <button className="ghost-button compact-button" onClick={handleScrollToVersionHistory} type="button">
                        {language === "uk" ? "Історія версій" : "Version history"}
                      </button>
                      {selectedNodeVersionBanner ? (
                        <button className="ghost-button compact-button" onClick={handleReturnToActiveVersion} type="button">
                          {language === "uk" ? "Повернутися до активної версії" : "Return to active version"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <div className="mounting-node-detail-version-summary-grid">
                    <DetailField
                      label={language === "uk" ? "Дата створення" : "Created"}
                      value={selectedNodeVersionBannerSummary?.dateLabel || formatMountingNodeVersionDate(selectedNodeActiveVersion?.created_at, language) || t.notSet}
                    />
                    <DetailField
                      label={language === "uk" ? "Позиції фурнітури" : "Items"}
                      value={selectedNodeActiveVersion?.items_count ?? selectedNodeDetail?.items?.length ?? 0}
                    />
                    <DetailField
                      label={language === "uk" ? "Точки" : "Points"}
                      value={selectedNodeActivePointCount}
                    />
                    <DetailField
                      label={language === "uk" ? "Варіант кріплення" : "Mounting variant"}
                      value={selectedNodeActiveVariantLabel}
                    />
                    <DetailField
                      label={language === "uk" ? "Категорія" : "Category"}
                      value={getNodeCategoryLabel(selectedNodeDetailForDisplay, language)}
                    />
                    <DetailField
                      label={language === "uk" ? "Функціональне призначення" : "Functional purpose"}
                      value={getNodeFunctionalLabel(selectedNodeDetailForDisplay, language)}
                    />
                  </div>
                  {selectedNodeVersionBanner ? (
                    <div className="mounting-node-detail-version-preview-note">
                      <strong>
                        {language === "uk"
                          ? `Перегляд версії ${selectedNodeVersionBanner.version_number}`
                          : `Viewing version ${selectedNodeVersionBanner.version_number}`}
                      </strong>
                      <p>
                        {language === "uk"
                          ? `Ця версія відкрита лише для перегляду. Позиції: ${selectedNodeVersionBannerSummary?.itemsCount || 0}, шаблони: ${selectedNodeVersionBannerSummary?.templatesCount || 0}, точки: ${selectedNodeVersionBannerSummary?.pointCount || 0}.`
                          : `This version is read-only. Items: ${selectedNodeVersionBannerSummary?.itemsCount || 0}, templates: ${selectedNodeVersionBannerSummary?.templatesCount || 0}, points: ${selectedNodeVersionBannerSummary?.pointCount || 0}.`}
                      </p>
                      <p>
                        {language === "uk"
                          ? "Поверніться до активної версії, щоб редагувати вузол."
                          : "Return to the active version to edit the node."}
                      </p>
                    </div>
                  ) : null}
                  {!selectedNodeDetail?.can_edit ? (
                    <p className="mounting-node-detail-readonly-note">
                      {language === "uk"
                        ? "Системний монтажний вузол доступний лише для перегляду."
                        : "This mounting node is read-only."}
                    </p>
                  ) : null}
                  {selectedNodeVersionError ? <p className="form-error mounting-node-detail-open-error">{selectedNodeVersionError}</p> : null}
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
                    {selectedNodeDetailForDisplay?.items?.length ? (
                      selectedNodeDetailForDisplay.items.map((item, index) =>
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
                      <p>
                        {selectedNodeVersionBanner
                          ? (language === "uk"
                            ? "Ви переглядаєте read-only snapshot версії."
                            : "You are viewing a read-only version snapshot.")
                          : (language === "uk"
                            ? "Змініть варіант кріплення поточного вузла та збережіть зміни."
                            : "Change the current node mounting variant and save the update.")}
                      </p>
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
              {Array.isArray(selectedNodeDetail.versions) && selectedNodeDetail.versions.length ? (
                <article className="settings-card mounting-node-detail-history-card" ref={mountingNodeHistoryCardRef}>
                  <div className="settings-card-header">
                    <div>
                      <strong>{language === "uk" ? "Історія версій" : "Version history"}</strong>
                      <p>
                        {language === "uk"
                          ? "Кожне збереження створює окрему версію монтажного вузла."
                          : "Each save creates a separate mounting node version."}
                      </p>
                    </div>
                  </div>
                  <div className="mounting-node-version-list">
                    {selectedNodeDetail.versions.map((version) => {
                      const summary = getMountingNodeVersionSummary(version, language, t);
                      const versionId = String(version.id || "").trim();
                      const isLoadingVersion = selectedNodeVersionLoadingId === versionId;

                      return (
                        <div
                          className={`mounting-node-version-item${version.is_current ? " is-current" : ""}`}
                          key={version.id}
                        >
                          <div className="mounting-node-version-item-head">
                            <strong>
                              {language === "uk" ? "Версія" : "Version"} {version.version_number}
                            </strong>
                            <div className="mounting-node-version-item-actions">
                              {version.is_current ? (
                                <span className="service-tree-badge subtle">
                                  {language === "uk" ? "Поточна" : "Current"}
                                </span>
                              ) : (
                                <button
                                  className="ghost-button compact-button"
                                  disabled={isLoadingVersion}
                                  onClick={() => void handleOpenVersion(version)}
                                  type="button"
                                >
                                  {isLoadingVersion
                                    ? (language === "uk" ? "Відкриття..." : "Opening...")
                                    : (language === "uk" ? "Переглянути" : "View")}
                                </button>
                              )}
                            </div>
                          </div>
                          <div className="mounting-node-version-item-meta">
                            <span>{summary.eventLabel}</span>
                            <span>{summary.dateLabel}</span>
                            <span>{summary.variantLabel}</span>
                            <span>
                              {language === "uk" ? "Фурнітура" : "Items"}: {summary.itemsCount}
                            </span>
                            <span>
                              {language === "uk" ? "Шаблони" : "Templates"}: {summary.templatesCount}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </article>
              ) : null}
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
              <h2>{language === "uk" ? "Архівувати монтажний вузол" : "Archive mounting node"}</h2>
              <button aria-label={language === "uk" ? "Закрити підтвердження" : "Close confirmation"} className="icon-button" disabled={deleteConfirmLoading} onClick={closeDeleteConfirm} type="button">
                <X size={18} />
              </button>
            </header>
            <p>
              {language === "uk"
                ? `Архівувати вузол "${deleteConfirmNode.name || deleteConfirmNode.code || deleteConfirmNode.id}"?`
                : `Archive mounting node "${deleteConfirmNode.name || deleteConfirmNode.code || deleteConfirmNode.id}"?`}
            </p>
            {deleteConfirmError ? <p className="form-error">{deleteConfirmError}</p> : null}
            <div className="confirm-actions">
              <button className="ghost-button" disabled={deleteConfirmLoading} onClick={closeDeleteConfirm} type="button">
                {language === "uk" ? "Скасувати" : "Cancel"}
              </button>
              <button className="danger-button" disabled={deleteConfirmLoading} onClick={handleConfirmDelete} type="button">
                {deleteConfirmLoading ? (language === "uk" ? "Архівування..." : "Archiving...") : (language === "uk" ? "Архівувати" : "Archive")}
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
