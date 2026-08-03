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
    normalizedPoint.id = normalizeInteger(point.id);
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

export function resolveMountingNodeEditorContext(nodeDetail, fallbackNodeId = "") {
  if (!nodeDetail || typeof nodeDetail !== "object") {
    return null;
  }

  const { actualTemplate, primaryTemplateLink } = resolveMountingNodeTemplateLink(nodeDetail);
  const primaryItem = Array.isArray(nodeDetail.items) ? nodeDetail.items[0] || null : null;
  const mountingNodeId = normalizeText(nodeDetail.id || nodeDetail.node_id || fallbackNodeId);

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
      nodeDetail.template_id,
  );
  const fittingId = normalizeText(
    actualTemplate?.fitting_id || primaryTemplateLink?.fitting_id || primaryItem?.fitting_id || nodeDetail.fitting_id,
  );
  const mountingVariantKey = normalizeText(
    actualTemplate?.mounting_variant_key ||
      primaryTemplateLink?.mounting_variant_key ||
      nodeDetail.mounting_variant_key ||
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
    nodeDetail,
    nodeName: normalizeText(nodeDetail.name),
    points,
    templateId,
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
    code: normalizeOptionalText(nodeDetail.code) || undefined,
    name: normalizeText(nodeDetail.name),
    description: normalizeOptionalText(nodeDetail.description),
    is_active: normalizeBoolean(nodeDetail.is_active, true),
    items,
    templates: nextTemplates,
  };
}
