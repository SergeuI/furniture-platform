const DEFAULT_MOUNTING_NODE_CREATE_ROLE = "Основний елемент";
const SECONDARY_MOUNTING_NODE_CREATE_ROLE = "Додатковий елемент";
const DEFAULT_MOUNTING_NODE_CREATE_TEMPLATE_NAME = "Основний шаблон";

export const MOUNTING_NODE_CREATE_ROLE_OPTIONS = [
  DEFAULT_MOUNTING_NODE_CREATE_ROLE,
  SECONDARY_MOUNTING_NODE_CREATE_ROLE,
];

import { getAngledTwoPlanesPointFormPreset } from "./angledTwoPlanesThreePreview.js";
import { normalizeMountingNodeCategoryCode } from "./mountingNodeCategories.js";
import { normalizeMountingNodeFunctionalCode } from "./mountingNodeFunctionalCodes.js";
import { getSurfaceMountPointFormPreset } from "./surfaceMountThreePreview.js";

export const MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY = "mountingNodesCreateDraft";
export const MOUNTING_NODE_CREATE_DRAFT_STORAGE_VERSION = 1;

let mountingNodeCreateClientKeyCounter = 0;

function normalizeText(value) {
  return String(value ?? "").trim();
}

function normalizeBoolean(value, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }

  if (value === null || value === undefined) {
    return fallback;
  }

  const normalized = normalizeText(value).toLowerCase();
  if (!normalized) {
    return fallback;
  }

  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }

  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }

  return Boolean(value);
}

function normalizeOwnershipType(value) {
  return String(value ?? "").trim().toLowerCase() === "system" ? "system" : "mine";
}

function normalizeQuantity(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? Math.max(1, Math.floor(parsed)) : 1;
}

function normalizeNumberOrEmpty(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  const parsed = Number(String(value).replace(",", "."));
  return Number.isFinite(parsed) ? parsed : "";
}

function normalizeItemId(value) {
  return normalizeText(value);
}

function normalizeDraftArrayItem(item, normalizer) {
  if (!item || typeof item !== "object") {
    return null;
  }

  return normalizer(item);
}

function generateClientKey() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `mounting-node-create-${crypto.randomUUID()}`;
  }

  mountingNodeCreateClientKeyCounter += 1;
  return `mounting-node-create-${Date.now()}-${mountingNodeCreateClientKeyCounter}`;
}

function normalizePointPanelKey(point = {}) {
  return (
    normalizeText(point.panel_key) ||
    normalizeText(point.panelKey) ||
    normalizeText(point.panelId) ||
    normalizeText(point.panel_id) ||
    normalizeText(point.target_panel)
  );
}

function normalizePointTargetSurface(point = {}) {
  return normalizeText(point.target_surface || point.targetSurface);
}

function normalizePointTargetSide(point = {}) {
  return normalizeText(point.target_side || point.targetSide);
}

function getMountingNodeCreateDraftStorage() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.sessionStorage || null;
  } catch {
    return null;
  }
}

function pickMountingNodeCreateDraftStorageFields(draft = {}) {
  return {
    category_code: normalizeMountingNodeCategoryCode(draft.category_code),
    functional_code: normalizeMountingNodeFunctionalCode(draft.functional_code),
    name: normalizeText(draft.name),
    description: normalizeText(draft.description),
    is_active: normalizeBoolean(draft.is_active, true),
    ownership_type: normalizeOwnershipType(draft.ownership_type),
    items: Array.isArray(draft.items)
      ? draft.items.filter(Boolean).map((item) => normalizeMountingNodeCreateDraftItem(item))
      : [],
    points: Array.isArray(draft.points)
      ? draft.points.filter(Boolean).map((point) => normalizeMountingNodeCreateDraftPoint(point))
      : [],
    mounting_variant_key: normalizeText(draft.mounting_variant_key),
    template_name: normalizeText(draft.template_name),
    is_dirty: normalizeBoolean(draft.is_dirty, false),
  };
}

export function saveMountingNodeCreateDraft(draft = createMountingNodeCreateDraft()) {
  const storage = getMountingNodeCreateDraftStorage();
  if (!storage) {
    return;
  }

  try {
    storage.setItem(
      MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY,
      JSON.stringify({
        version: MOUNTING_NODE_CREATE_DRAFT_STORAGE_VERSION,
        draft: pickMountingNodeCreateDraftStorageFields(draft),
      }),
    );
  } catch {
    // Ignore storage failures in private browsing or sandboxed environments.
  }
}

export function clearMountingNodeCreateDraft() {
  const storage = getMountingNodeCreateDraftStorage();
  if (!storage) {
    return;
  }

  try {
    storage.removeItem(MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY);
  } catch {
    // Ignore storage failures in private browsing or sandboxed environments.
  }
}

export function loadMountingNodeCreateDraft() {
  const storage = getMountingNodeCreateDraftStorage();
  if (!storage) {
    return createMountingNodeCreateDraft({
      category_code: "",
      functional_code: "",
      mounting_variant_key: "",
    });
  }

  try {
    const storedValue = storage.getItem(MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY);
    if (!storedValue) {
      return createMountingNodeCreateDraft({
        category_code: "",
        functional_code: "",
        mounting_variant_key: "",
      });
    }

    const parsedValue = JSON.parse(storedValue);
    const storedDraft =
      parsedValue && typeof parsedValue === "object" && parsedValue.draft && typeof parsedValue.draft === "object"
        ? parsedValue.draft
        : parsedValue;

    if (
      !parsedValue ||
      typeof parsedValue !== "object" ||
      (Object.prototype.hasOwnProperty.call(parsedValue, "version") &&
        Number(parsedValue.version) !== MOUNTING_NODE_CREATE_DRAFT_STORAGE_VERSION)
    ) {
      return createMountingNodeCreateDraft({
        category_code: "",
        functional_code: "",
        mounting_variant_key: "",
      });
    }

    return createMountingNodeCreateDraft({
      ...pickMountingNodeCreateDraftStorageFields(storedDraft),
    });
  } catch {
    clearMountingNodeCreateDraft();
    return createMountingNodeCreateDraft({
      category_code: "",
      mounting_variant_key: "",
    });
  }
}

export function createMountingNodeCreateDraft(overrides = {}) {
  const items = Array.isArray(overrides.items)
    ? overrides.items
        .filter(Boolean)
        .map((item) => normalizeDraftArrayItem(item, normalizeMountingNodeCreateDraftItem))
        .filter(Boolean)
    : [];
  const points = Array.isArray(overrides.points)
    ? overrides.points
        .filter(Boolean)
        .map((point) => normalizeDraftArrayItem(point, normalizeMountingNodeCreateDraftPoint))
        .filter(Boolean)
    : [];

  return {
    category_code: normalizeMountingNodeCategoryCode(overrides.category_code),
    functional_code: normalizeMountingNodeFunctionalCode(overrides.functional_code),
    name: normalizeText(overrides.name),
    description: normalizeText(overrides.description),
    is_active: normalizeBoolean(overrides.is_active, true),
    ownership_type: normalizeOwnershipType(overrides.ownership_type),
    items,
    points,
    mounting_variant_key: normalizeText(overrides.mounting_variant_key),
    template_name: normalizeText(overrides.template_name) || DEFAULT_MOUNTING_NODE_CREATE_TEMPLATE_NAME,
    is_dirty: Boolean(overrides.is_dirty),
  };
}

export function normalizeMountingNodeCreateDraftItem(item = {}) {
  return {
    fitting_id: normalizeItemId(item.fitting_id),
    article: normalizeText(item.article),
    name: normalizeText(item.name),
    image_url: normalizeText(item.image_url),
    quantity: normalizeQuantity(item.quantity),
    role: normalizeText(item.role) || DEFAULT_MOUNTING_NODE_CREATE_ROLE,
    is_required: normalizeBoolean(item.is_required, true),
    affects_processing: normalizeBoolean(item.affects_processing, true),
  };
}

export function createMountingNodeCreateDraftItemFromFitting(fitting = {}, overrides = {}) {
  return normalizeMountingNodeCreateDraftItem({
    fitting_id: fitting.id,
    article: fitting.article || fitting.code || "",
    name: fitting.name || fitting.article || fitting.code || "",
    image_url: fitting.image_url || fitting.image || "",
    quantity: 1,
    role: normalizeText(overrides.role) || DEFAULT_MOUNTING_NODE_CREATE_ROLE,
    is_required: true,
    affects_processing: true,
  });
}

export function addMountingNodeCreateDraftItem(draft = createMountingNodeCreateDraft(), fitting = {}) {
  const fittingId = normalizeItemId(fitting.id);
  const existingItem = Array.isArray(draft.items)
    ? draft.items.find((item) => normalizeItemId(item.fitting_id) === fittingId)
    : null;

  if (existingItem) {
    return {
      draft,
      duplicate: true,
    };
  }

  const role = Array.isArray(draft.items) && draft.items.length > 0
    ? SECONDARY_MOUNTING_NODE_CREATE_ROLE
    : DEFAULT_MOUNTING_NODE_CREATE_ROLE;

  return {
    draft: {
      ...draft,
      items: [
        ...(Array.isArray(draft.items) ? draft.items : []),
        createMountingNodeCreateDraftItemFromFitting(fitting, { role }),
      ],
      is_dirty: true,
    },
    duplicate: false,
  };
}

export function updateMountingNodeCreateDraftItem(draft = createMountingNodeCreateDraft(), fittingId, patch = {}) {
  const normalizedFittingId = normalizeItemId(fittingId);
  return {
    ...draft,
    items: (Array.isArray(draft.items) ? draft.items : []).map((item) => {
      if (normalizeItemId(item.fitting_id) !== normalizedFittingId) {
        return item;
      }

      const nextItem = {
        ...item,
      };

      if (Object.prototype.hasOwnProperty.call(patch, "quantity")) {
        nextItem.quantity = normalizeQuantity(patch.quantity);
      }

      if (Object.prototype.hasOwnProperty.call(patch, "role")) {
        nextItem.role = normalizeText(patch.role) || DEFAULT_MOUNTING_NODE_CREATE_ROLE;
      }

      if (Object.prototype.hasOwnProperty.call(patch, "is_required")) {
        nextItem.is_required = normalizeBoolean(patch.is_required, true);
      }

      if (Object.prototype.hasOwnProperty.call(patch, "affects_processing")) {
        nextItem.affects_processing = normalizeBoolean(patch.affects_processing, true);
      }

      if (Object.prototype.hasOwnProperty.call(patch, "name")) {
        nextItem.name = normalizeText(patch.name);
      }

      if (Object.prototype.hasOwnProperty.call(patch, "article")) {
        nextItem.article = normalizeText(patch.article);
      }

      if (Object.prototype.hasOwnProperty.call(patch, "image_url")) {
        nextItem.image_url = normalizeText(patch.image_url);
      }

      return nextItem;
    }),
    is_dirty: true,
  };
}

export function removeMountingNodeCreateDraftItem(draft = createMountingNodeCreateDraft(), fittingId) {
  const normalizedFittingId = normalizeItemId(fittingId);
  return {
    ...draft,
    items: (Array.isArray(draft.items) ? draft.items : []).filter(
      (item) => normalizeItemId(item.fitting_id) !== normalizedFittingId,
    ),
    points: (Array.isArray(draft.points) ? draft.points : []).filter(
      (point) => normalizeItemId(point.fitting_id) !== normalizedFittingId,
    ),
    is_dirty: true,
  };
}

export function normalizeMountingNodeCreateDraftPoint(point = {}) {
  const fittingId = normalizeItemId(point.fitting_id);
  return {
    client_key: normalizeText(point.client_key) || generateClientKey(),
    id: point.id === undefined ? null : point.id,
    fitting_id: fittingId,
    fitting_name: normalizeText(point.fitting_name),
    article: normalizeText(point.article),
    image_url: normalizeText(point.image_url),
    label: normalizeText(point.label),
    panel_key: normalizePointPanelKey(point),
    target_panel: normalizeText(point.target_panel || point.panel_key || point.panelKey || point.panelId || point.panel_id),
    target_surface: normalizePointTargetSurface(point),
    target_side: normalizePointTargetSide(point),
    side: normalizeText(point.side) || "front",
    x_mm: normalizeNumberOrEmpty(point.x_mm ?? point.x),
    y_mm: normalizeNumberOrEmpty(point.y_mm ?? point.y),
    z_mm: normalizeNumberOrEmpty(point.z_mm ?? point.z),
    diameter_mm: normalizeNumberOrEmpty(point.diameter_mm ?? point.diameter),
    depth_mm: normalizeNumberOrEmpty(point.depth_mm ?? point.depth),
    operation: normalizeText(point.operation) || "drill",
    order_index: normalizeNumberOrEmpty(point.order_index ?? point.orderIndex),
    quantity: normalizeQuantity(point.quantity),
    mirrored: normalizeBoolean(point.mirrored, false),
    is_through: normalizeBoolean(point.is_through, false),
    notes: normalizeText(point.notes),
  };
}

function getDefaultPointGeometry(index, total) {
  const safeTotal = Math.max(Number(total) || 0, 1);
  const angle = (Math.PI * 2 * index) / safeTotal - Math.PI / 2;
  const radiusX = 214;
  const radiusY = 126;
  const centerX = 380;
  const centerY = 236;
  const previewX = Math.round(centerX + Math.cos(angle) * radiusX);
  const previewY = Math.round(centerY + Math.sin(angle) * radiusY);

  return {
    previewX,
    previewY,
    x_mm: previewX - centerX,
    y_mm: previewY - centerY,
    z_mm: Math.round((index - safeTotal / 2) * 18),
  };
}

function getMountingNodeCreatePointPreset(variantKey = "") {
  const normalizedVariantKey = normalizeText(variantKey);

  if (normalizedVariantKey === "surface_mount") {
    return getSurfaceMountPointFormPreset();
  }

  if (normalizedVariantKey === "angled_two_planes") {
    return getAngledTwoPlanesPointFormPreset("vertical_panel");
  }

  return {};
}

export function createMountingNodeCreateDraftPointFromFitting(
  fitting = {},
  overrides = {},
  index = 0,
  total = 1,
) {
  const geometry = getDefaultPointGeometry(index, total);
  const resolvedPanelKey = normalizeText(overrides.panel_key) || normalizeText(overrides.target_panel) || "vertical_panel";
  const resolvedTargetPanel = normalizeText(overrides.target_panel) || resolvedPanelKey;
  const resolvedTargetSurface = normalizeText(overrides.target_surface) || "plane";
  const resolvedTargetSide = normalizeText(overrides.target_side) || "inner_face";
  return normalizeMountingNodeCreateDraftPoint({
    client_key: overrides.client_key,
    id: null,
    fitting_id: fitting.id,
    fitting_name: fitting.name || fitting.article || fitting.code || "",
    article: fitting.article || fitting.code || "",
    image_url: fitting.image_url || fitting.image || "",
    label: normalizeText(overrides.label) || `P${index + 1}`,
    panel_key: resolvedPanelKey,
    target_panel: resolvedTargetPanel,
    target_surface: resolvedTargetSurface,
    target_side: resolvedTargetSide,
    side: normalizeText(overrides.side) || resolvedTargetSide,
    x_mm: overrides.x_mm ?? geometry.x_mm,
    y_mm: overrides.y_mm ?? geometry.y_mm,
    z_mm: overrides.z_mm ?? geometry.z_mm,
    diameter_mm: overrides.diameter_mm ?? 8,
    depth_mm: overrides.depth_mm ?? "",
    operation: normalizeText(overrides.operation) || "drill",
    order_index: overrides.order_index ?? index,
    quantity: overrides.quantity ?? 1,
    mirrored: overrides.mirrored ?? false,
    is_through: overrides.is_through ?? false,
    notes: overrides.notes ?? "",
  });
}

export function prepareMountingNodeCreateDraftPointForm(
  draft = createMountingNodeCreateDraft(),
  fitting = {},
  overrides = {},
) {
  const pointCount = Array.isArray(draft.points) ? draft.points.length : 0;
  const variantPreset = getMountingNodeCreatePointPreset(draft?.mounting_variant_key);
  const resolvedPanelKey = normalizeText(overrides.panel_key) || normalizeText(overrides.target_panel) || normalizeText(variantPreset.panel_key);

  return createMountingNodeCreateDraftPointFromFitting(
    fitting,
    {
      ...variantPreset,
      ...overrides,
      panel_key: resolvedPanelKey || normalizeText(variantPreset.panel_key),
      target_panel:
        normalizeText(overrides.target_panel) ||
        resolvedPanelKey ||
        normalizeText(variantPreset.target_panel),
    },
    pointCount,
    Math.max(pointCount + 1, 1),
  );
}

export function commitMountingNodeCreateDraftPoint(draft = createMountingNodeCreateDraft(), pointForm = {}) {
  if (!pointForm) {
    return draft;
  }

  return {
    ...draft,
    points: [...(Array.isArray(draft.points) ? draft.points : []), normalizeMountingNodeCreateDraftPoint(pointForm)],
    is_dirty: true,
  };
}

export function addMountingNodeCreateDraftPoint(draft = createMountingNodeCreateDraft(), fitting = {}, overrides = {}) {
  const variantPreset = getMountingNodeCreatePointPreset(draft?.mounting_variant_key);
  const resolvedPanelKey = normalizeText(overrides.panel_key) || normalizeText(overrides.target_panel) || normalizeText(variantPreset.panel_key);

  const nextPoint = createMountingNodeCreateDraftPointFromFitting(
    fitting,
    {
      ...variantPreset,
      ...overrides,
      panel_key: resolvedPanelKey || normalizeText(variantPreset.panel_key),
      target_panel:
        normalizeText(overrides.target_panel) ||
        resolvedPanelKey ||
        normalizeText(variantPreset.target_panel),
    },
    Array.isArray(draft.points) ? draft.points.length : 0,
    Math.max(Array.isArray(draft.points) ? draft.points.length + 1 : 1, 1),
  );

  return {
    ...draft,
    points: [...(Array.isArray(draft.points) ? draft.points : []), nextPoint],
    is_dirty: true,
  };
}

export function updateMountingNodeCreateDraftPoint(draft = createMountingNodeCreateDraft(), clientKey, patch = {}) {
  const normalizedClientKey = normalizeText(clientKey);
  return {
    ...draft,
    points: (Array.isArray(draft.points) ? draft.points : []).map((point) => {
      if (normalizeText(point.client_key) !== normalizedClientKey) {
        return point;
      }

      return normalizeMountingNodeCreateDraftPoint({
        ...point,
        ...patch,
        client_key: point.client_key,
        id: point.id ?? null,
        fitting_id: point.fitting_id,
      });
    }),
    is_dirty: true,
  };
}

export function removeMountingNodeCreateDraftPoint(draft = createMountingNodeCreateDraft(), clientKey) {
  const normalizedClientKey = normalizeText(clientKey);
  return {
    ...draft,
    points: (Array.isArray(draft.points) ? draft.points : []).filter(
      (point) => normalizeText(point.client_key) !== normalizedClientKey,
    ),
    is_dirty: true,
  };
}

export function validateMountingNodeCreateDraft(draft = createMountingNodeCreateDraft()) {
  const errors = [];
  const items = Array.isArray(draft.items) ? draft.items : [];
  const points = Array.isArray(draft.points) ? draft.points : [];
  const duplicateIds = new Set();
  const seenIds = new Set();

  if (!normalizeText(draft.name)) {
    errors.push({
      field: "name",
      message: "Вкажіть назву монтажного вузла.",
    });
  }

  if (!items.length) {
    errors.push({
      field: "items",
      message: "Додайте щонайменше одну фурнітуру.",
    });
  }

  items.forEach((item) => {
    const fittingId = normalizeItemId(item.fitting_id);
    if (seenIds.has(fittingId)) {
      duplicateIds.add(fittingId);
    }
    seenIds.add(fittingId);

    if (!normalizeText(item.role)) {
      errors.push({
        field: "role",
        message: "Для кожного артикула вкажіть роль.",
      });
    }

    if (!Number.isFinite(Number(item.quantity)) || Number(item.quantity) <= 0) {
      errors.push({
        field: "quantity",
        message: "Кількість має бути більшою за 0.",
      });
    }
  });

  if (!normalizeText(draft.mounting_variant_key)) {
    errors.push({
      field: "mounting_variant_key",
      message: "Оберіть варіант кріплення.",
    });
  }

  if (duplicateIds.size) {
    errors.push({
      field: "items",
      message: "Один артикул можна додати лише один раз.",
    });
  }

  points.forEach((point) => {
    if (!normalizeText(point.client_key)) {
      errors.push({
        field: "points",
        message: "Для локальної точки потрібен client_key.",
      });
    }
  });

  return errors;
}

export function isMountingNodeCreateDraftReady(draft = createMountingNodeCreateDraft()) {
  return validateMountingNodeCreateDraft(draft).length === 0;
}
