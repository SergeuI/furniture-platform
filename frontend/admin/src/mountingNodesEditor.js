import { normalizeMountingNodeCategoryCode } from "./mountingNodeCategories.js";

function normalizeText(value) {
  return String(value || "").trim();
}

function normalizeOptionalText(value) {
  const text = normalizeText(value);
  return text || null;
}

function normalizeBoolean(value, fallback = false) {
  if (typeof value === "boolean") {
    return value;
  }

  if (value === null || value === undefined) {
    return fallback;
  }

  const normalized = String(value).trim().toLowerCase();

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

function normalizeInteger(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeNodeItem(item) {
  return {
    fitting_id: normalizeInteger(item?.fitting_id),
    quantity: Math.max(1, normalizeInteger(item?.quantity, 1)),
    role: normalizeOptionalText(item?.role),
    is_required: normalizeBoolean(item?.is_required, true),
    affects_processing: normalizeBoolean(item?.affects_processing, true),
    order_index: normalizeInteger(item?.order_index),
  };
}

function normalizePoint(point, templateId) {
  const normalizedTemplateId = normalizeInteger(point?.template_id, templateId);
  const normalizedPoint = {
    template_id: normalizedTemplateId || templateId,
    label: normalizeOptionalText(point?.label),
    x_mm: point?.x_mm === "" || point?.x_mm === undefined ? null : point?.x_mm,
    y_mm: point?.y_mm === "" || point?.y_mm === undefined ? null : point?.y_mm,
    z_mm: point?.z_mm === "" || point?.z_mm === undefined ? null : point?.z_mm,
    target_panel: normalizeOptionalText(point?.target_panel),
    target_surface: normalizeOptionalText(point?.target_surface),
    target_side: normalizeOptionalText(point?.target_side),
    diameter_mm: point?.diameter_mm === "" || point?.diameter_mm === undefined ? null : point?.diameter_mm,
    service_drilling_rule_id:
      point?.service_drilling_rule_id === "" || point?.service_drilling_rule_id === undefined
        ? null
        : point?.service_drilling_rule_id,
    depth_mm: point?.depth_mm === "" || point?.depth_mm === undefined ? null : point?.depth_mm,
    side: normalizeOptionalText(point?.side),
    operation: normalizeOptionalText(point?.operation),
    order_index: normalizeInteger(point?.order_index),
    quantity: Math.max(1, normalizeInteger(point?.quantity, 1)),
    mirrored: normalizeBoolean(point?.mirrored, false),
    notes: normalizeOptionalText(point?.notes),
  };

  if (point?.id !== undefined && point?.id !== null && String(point.id).trim() !== "") {
    const normalizedId = normalizeInteger(point.id);
    if (normalizedId > 0) {
      normalizedPoint.id = normalizedId;
    }
  }

  if (!normalizedPoint.template_id) {
    normalizedPoint.template_id = templateId;
  }

  return normalizedPoint;
}

function resolveMountingNodeTemplateSource(template) {
  if (!template || typeof template !== "object") {
    return null;
  }

  if (template.template && typeof template.template === "object") {
    return template.template;
  }

  return template;
}

function isCurrentMountingNodeVersion(version) {
  if (!version || typeof version !== "object") {
    return false;
  }

  return Boolean(
    version.is_current ||
      version.current ||
      version.isCurrent ||
      version.is_active ||
      version.isActive ||
      version.is_active_version,
  );
}

export function resolveActiveMountingNodeVersion(nodeDetail) {
  const versions = Array.isArray(nodeDetail?.versions)
    ? nodeDetail.versions.filter((version) => version && typeof version === "object")
    : [];

  if (!versions.length) {
    return null;
  }

  const explicitCurrentVersion = versions.find(isCurrentMountingNodeVersion);
  if (explicitCurrentVersion) {
    return explicitCurrentVersion;
  }

  const versionsWithNumbers = versions
    .map((version) => ({
      version,
      versionNumber: Number(version?.version_number),
    }))
    .filter(({ versionNumber }) => Number.isFinite(versionNumber));

  if (!versionsWithNumbers.length) {
    return versions[0];
  }

  return versionsWithNumbers.reduce((best, current) =>
    current.versionNumber > best.versionNumber ? current : best,
  ).version;
}

function getMountingNodeSnapshotTemplatePointCount(templateLink) {
  const templateSource =
    templateLink?.template && typeof templateLink.template === "object"
      ? templateLink.template
      : templateLink?.fitting_hole_template && typeof templateLink.fitting_hole_template === "object"
        ? templateLink.fitting_hole_template
        : templateLink && typeof templateLink === "object"
          ? templateLink
          : null;

  if (!templateSource) {
    return 0;
  }

  const templatePoints = Array.isArray(templateSource.points)
    ? templateSource.points
    : Array.isArray(templateLink?.points)
      ? templateLink.points
      : [];

  return templatePoints.length;
}

export function getMountingNodeSnapshotPointCount(snapshot) {
  const templates = Array.isArray(snapshot?.templates) ? snapshot.templates : [];

  return templates.reduce((total, templateLink) => total + getMountingNodeSnapshotTemplatePointCount(templateLink), 0);
}

function resolveMountingNodeTemplateLink(nodeDetail) {
  const templates = Array.isArray(nodeDetail?.templates)
    ? nodeDetail.templates.filter((template) => template && typeof template === "object")
    : [];
  const primaryTemplateLink = templates.find((template) => template?.is_default) || templates[0] || null;
  const linkedTemplate =
    primaryTemplateLink?.template && typeof primaryTemplateLink.template === "object"
      ? primaryTemplateLink.template
      : primaryTemplateLink?.fitting_hole_template && typeof primaryTemplateLink.fitting_hole_template === "object"
        ? primaryTemplateLink.fitting_hole_template
        : null;

  return {
    actualTemplate: linkedTemplate || primaryTemplateLink || null,
    primaryTemplateLink,
    templates,
  };
}

function resolveMountingNodeTemplateId(template, fallbackTemplateId = "") {
  if (!template || typeof template !== "object") {
    return normalizeText(fallbackTemplateId);
  }

  if (template.template && typeof template.template === "object") {
    return normalizeText(template.template.id || template.template.template_id || fallbackTemplateId);
  }

  return normalizeText(template.template_id || template.id || fallbackTemplateId);
}

function cloneMountingNodeEditorTemplate(template) {
  if (!template || typeof template !== "object") {
    return null;
  }

  const templateClone = {
    ...template,
  };

  if (templateClone.template && typeof templateClone.template === "object") {
    templateClone.template = {
      ...templateClone.template,
      points: Array.isArray(templateClone.template.points)
        ? templateClone.template.points.map((point) => ({ ...point }))
        : [],
    };
  }

  if (templateClone.fitting_hole_template && typeof templateClone.fitting_hole_template === "object") {
    templateClone.fitting_hole_template = {
      ...templateClone.fitting_hole_template,
      points: Array.isArray(templateClone.fitting_hole_template.points)
        ? templateClone.fitting_hole_template.points.map((point) => ({ ...point }))
        : [],
    };
  }

  if (Array.isArray(templateClone.points)) {
    templateClone.points = templateClone.points.map((point) => ({ ...point }));
  }

  return templateClone;
}

function resolveMountingNodeEditorSnapshot(nodeDetail) {
  const versions = Array.isArray(nodeDetail?.versions) ? nodeDetail.versions : [];
  const activeVersion = resolveActiveMountingNodeVersion(nodeDetail);
  const snapshot = activeVersion?.snapshot && typeof activeVersion.snapshot === "object" ? activeVersion.snapshot : null;

  if (!snapshot) {
    return nodeDetail;
  }

  const snapshotTemplates = Array.isArray(snapshot.templates) ? snapshot.templates : [];
  const liveTemplates = Array.isArray(nodeDetail?.templates) ? nodeDetail.templates : [];
  const snapshotItems = Array.isArray(snapshot.items) ? snapshot.items : [];
  const liveItems = Array.isArray(nodeDetail?.items) ? nodeDetail.items : [];

  return {
    ...nodeDetail,
    ...snapshot,
    id: snapshot.id ?? nodeDetail.id,
    node_id: snapshot.node_id ?? nodeDetail.node_id ?? nodeDetail.id,
    code: snapshot.code ?? nodeDetail.code,
    name: snapshot.name ?? nodeDetail.name,
    description: snapshot.description ?? nodeDetail.description,
    items: snapshotItems.length
      ? snapshotItems.map((item) => ({ ...item }))
      : liveItems.map((item) => ({ ...item })),
    templates: snapshotTemplates.length
      ? snapshotTemplates.map((template) => cloneMountingNodeEditorTemplate(template)).filter(Boolean)
      : liveTemplates.map((template) => cloneMountingNodeEditorTemplate(template)).filter(Boolean),
    versions,
  };
}

export function resolveMountingNodeEditorContext(nodeDetail, fallbackNodeId = "") {
  const snapshotNodeDetail = resolveMountingNodeEditorSnapshot(
    nodeDetail && typeof nodeDetail === "object" ? nodeDetail : null,
  );

  if (!snapshotNodeDetail || typeof snapshotNodeDetail !== "object") {
    return null;
  }

  const { actualTemplate, primaryTemplateLink } = resolveMountingNodeTemplateLink(snapshotNodeDetail);
  const primaryItem = Array.isArray(snapshotNodeDetail.items) ? snapshotNodeDetail.items[0] || null : null;
  const mountingNodeId = normalizeText(snapshotNodeDetail.id || snapshotNodeDetail.node_id || fallbackNodeId);

  if (!mountingNodeId) {
    return null;
  }

  const hasTemplateLinkShape = Boolean(
    primaryTemplateLink &&
      (Object.prototype.hasOwnProperty.call(primaryTemplateLink, "template_id") ||
        Object.prototype.hasOwnProperty.call(primaryTemplateLink, "template") ||
        Object.prototype.hasOwnProperty.call(primaryTemplateLink, "fitting_hole_template")),
  );
  const templateId = normalizeText(
    actualTemplate?.template_id ||
      (actualTemplate && actualTemplate !== primaryTemplateLink ? actualTemplate.id : "") ||
      primaryTemplateLink?.template_id ||
      (!hasTemplateLinkShape ? primaryTemplateLink?.id : "") ||
      snapshotNodeDetail.template_id,
  );
  const fittingId = normalizeText(
    actualTemplate?.fitting_id ||
      primaryTemplateLink?.fitting_id ||
      primaryItem?.fitting_id ||
      snapshotNodeDetail.fitting_id,
  );
  const mountingVariantKey = normalizeText(
    actualTemplate?.mounting_variant_key ||
      primaryTemplateLink?.mounting_variant_key ||
      snapshotNodeDetail.mounting_variant_key ||
      "surface_mount",
  );
  const points = Array.isArray(actualTemplate?.points)
    ? actualTemplate.points
    : Array.isArray(primaryTemplateLink?.points)
      ? primaryTemplateLink.points
      : [];

  return {
    fittingId,
    mountingNodeId,
    mountingVariantKey,
    nodeDetail: snapshotNodeDetail,
    nodeName: normalizeText(snapshotNodeDetail.name),
    points,
    templateId,
  };
}

export function hydrateMountingNodeEditorState(nodeDetail, fallbackNodeId = "") {
  const context = resolveMountingNodeEditorContext(
    nodeDetail && typeof nodeDetail === "object" ? nodeDetail : null,
    fallbackNodeId,
  );

  if (!context) {
    return null;
  }

  const templateItems = Array.isArray(context.nodeDetail?.templates)
    ? context.nodeDetail.templates.map((template) => cloneMountingNodeEditorTemplate(template)).filter(Boolean)
    : [];
  const selectedTemplateLink =
    templateItems.find((template) => String(template?.template_id || template?.template?.id || template?.fitting_hole_template?.id || "") === String(context.templateId || "")) ||
    templateItems.find((template) => Boolean(template?.is_default)) ||
    templateItems[0] ||
    null;

  return {
    activeVersion: resolveActiveMountingNodeVersion(context.nodeDetail),
    context,
    points: Array.isArray(context.points) ? context.points.map((point) => ({ ...point })) : [],
    selectedTemplateLink,
    templateItems,
  };
}

function buildTemplatePayload({
  link = {},
  template = null,
  points = [],
  isCurrentTemplate = false,
  currentTemplateId = "",
}) {
  const linkedTemplate = link?.template && typeof link.template === "object" ? link.template : null;
  const resolvedTemplate = template && typeof template === "object" ? template : linkedTemplate;
  const templateId = normalizeInteger(
    resolvedTemplate?.id || link?.template_id || currentTemplateId,
  );
  const fittingId = normalizeInteger(
    resolvedTemplate?.fitting_id || link?.fitting_id || link?.template?.fitting_id,
  );

  if (!templateId) {
    return null;
  }

  const basePayload = {
    template_id: templateId,
    is_default: normalizeBoolean(link?.is_default ?? resolvedTemplate?.is_default, false),
    order_index: normalizeInteger(link?.order_index ?? resolvedTemplate?.bundle_order_index),
  };

  if (!isCurrentTemplate) {
    return basePayload;
  }

  return {
    ...basePayload,
    template: {
      template_id: templateId,
      fitting_id: fittingId,
      name: normalizeOptionalText(resolvedTemplate?.name),
      bundle_key: normalizeOptionalText(resolvedTemplate?.bundle_key),
      bundle_name: normalizeOptionalText(resolvedTemplate?.bundle_name),
      bundle_order_index: normalizeInteger(
        resolvedTemplate?.bundle_order_index ?? link?.bundle_order_index,
      ),
      template_type: normalizeOptionalText(resolvedTemplate?.template_type) || "manual",
      side: normalizeOptionalText(resolvedTemplate?.side),
      coordinate_system: normalizeOptionalText(resolvedTemplate?.coordinate_system) || "2d",
      mounting_variant_key: normalizeOptionalText(
        resolvedTemplate?.mounting_variant_key || link?.mounting_variant_key,
      ),
      is_default: normalizeBoolean(resolvedTemplate?.is_default ?? link?.is_default, false),
      notes: normalizeOptionalText(resolvedTemplate?.notes),
      is_active: normalizeBoolean(resolvedTemplate?.is_active ?? link?.is_active, true),
      points: points.map((point) => normalizePoint(point, templateId)),
    },
  };
}

export function canSaveMountingNodeEditor({
  context = null,
  pointsLoaded = false,
  selectedTemplate = null,
  saving = false,
} = {}) {
  const mountingNodeId = normalizeText(context?.mountingNodeId);
  const nodeDetail = context?.nodeDetail && typeof context.nodeDetail === "object" ? context.nodeDetail : null;
  const templateId = resolveMountingNodeTemplateId(selectedTemplate, context?.templateId);

  return Boolean(
    mountingNodeId &&
      nodeDetail &&
      templateId &&
      pointsLoaded &&
      !saving &&
      Array.isArray(nodeDetail.items) &&
      Array.isArray(nodeDetail.templates),
  );
}

export function canAddMountingNodeEditorPoint({
  isMountingNodeEditorMode = false,
  loading = false,
  holePointSubmitting = false,
  activeHoleFittingId = "",
  selectedHoleMountingVariantKey = "",
  mountingNodeEditorDraft = null,
} = {}) {
  if (!isMountingNodeEditorMode) {
    return Boolean(!loading && !holePointSubmitting && activeHoleFittingId && selectedHoleMountingVariantKey);
  }

  const draftItems = Array.isArray(mountingNodeEditorDraft?.items) ? mountingNodeEditorDraft.items : [];
  const draftVariantKey = normalizeText(
    mountingNodeEditorDraft?.mounting_variant_key || selectedHoleMountingVariantKey,
  );

  return Boolean(!holePointSubmitting && draftItems.length > 0 && draftVariantKey);
}

export function getMountingNodeEditorItemFittingId(item = {}) {
  return normalizeText(item?.fitting_id || item?.fittingId || item?.id || "");
}

export function getMountingNodeEditorItemImageUrl(item = {}, fallbackItem = null) {
  const fallbackSource = fallbackItem && typeof fallbackItem === "object" ? fallbackItem : null;
  return normalizeText(
    item?.image_url ||
      item?.image ||
      item?.thumbnail_url ||
      item?.thumbnail ||
      item?.image_data ||
      fallbackSource?.image_url ||
      fallbackSource?.image ||
      fallbackSource?.thumbnail_url ||
      fallbackSource?.thumbnail ||
      fallbackSource?.image_data ||
      "",
  );
}

export function getMountingNodeEditorPointDisplayId(point = {}) {
  const normalizedId = Number(point?.id);
  return Number.isFinite(normalizedId) && normalizedId > 0 ? String(normalizedId) : "—";
}

export function getMountingNodeEditorPointDisplayLabel(point = {}, index = 0) {
  const explicitLabel = normalizeText(point?.label);
  if (explicitLabel) {
    return explicitLabel;
  }

  const resolvedOrder = Number(point?.order_index);
  if (Number.isFinite(resolvedOrder) && resolvedOrder >= 0) {
    return `P${resolvedOrder + 1}`;
  }

  return `P${Number(index) + 1}`;
}

export function buildMountingNodeEditorSavePayload({
  context = null,
  points = [],
  pointsLoaded = false,
  selectedTemplate = null,
} = {}) {
  if (!pointsLoaded) {
    throw new Error("Template points are not loaded");
  }

  const mountingNodeId = normalizeText(context?.mountingNodeId);
  const nodeDetail = context?.nodeDetail && typeof context.nodeDetail === "object" ? context.nodeDetail : null;
  const selectedTemplateSource = resolveMountingNodeTemplateSource(selectedTemplate);
  const templateId = resolveMountingNodeTemplateId(selectedTemplate, context?.templateId);

  if (!mountingNodeId) {
    throw new Error("Mounting node ID is required");
  }

  if (!nodeDetail) {
    throw new Error("Mounting node details are required");
  }

  if (!templateId) {
    throw new Error("Template ID is required");
  }

  const items = Array.isArray(nodeDetail.items) ? nodeDetail.items.map(normalizeNodeItem) : [];
  const templates = Array.isArray(nodeDetail.templates) ? nodeDetail.templates : [];
  const currentTemplateIndex = templates.findIndex((link) => {
    const linkTemplateId = resolveMountingNodeTemplateId(link);
    return linkTemplateId === templateId;
  });
  const currentTemplateLink = currentTemplateIndex >= 0 ? templates[currentTemplateIndex] : null;
  const currentTemplatePayload = buildTemplatePayload({
    link: currentTemplateLink || {
      template_id: templateId,
      is_default: normalizeBoolean(selectedTemplate?.is_default, false),
      order_index: 0,
    },
    template: selectedTemplateSource,
    points,
    isCurrentTemplate: true,
    currentTemplateId: templateId,
  });

  const nextTemplates = templates.map((link) => {
    const linkTemplateId = resolveMountingNodeTemplateId(link);
    if (linkTemplateId === templateId) {
      return currentTemplatePayload;
    }

    return buildTemplatePayload({
      link,
      isCurrentTemplate: false,
      currentTemplateId: templateId,
    });
  }).filter(Boolean);

  if (currentTemplateIndex < 0 && currentTemplatePayload) {
    nextTemplates.push(currentTemplatePayload);
  }

  return {
    category_code: normalizeMountingNodeCategoryCode(nodeDetail.category_code) || undefined,
    code: normalizeOptionalText(nodeDetail.code) || undefined,
    name: normalizeText(nodeDetail.name),
    description: normalizeOptionalText(nodeDetail.description),
    is_active: normalizeBoolean(nodeDetail.is_active, true),
    items,
    templates: nextTemplates,
  };
}
