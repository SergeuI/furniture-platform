export function createHolePointFormDefaults() {
  return {
    template_id: "",
    panel_key: "",
    target_panel: "",
    target_surface: "",
    target_side: "",
    label: "",
    x_mm: "",
    y_mm: "",
    z_mm: "",
    diameter_mm: "",
    depth_mm: "",
    side: "front",
    operation: "drill",
    order_index: "0",
    quantity: "1",
    mirrored: false,
    is_through: false,
    notes: "",
  };
}

export function buildHolePointFormFromPoint(point) {
  const targetPanel = String(point?.target_panel || "").trim();
  const panelKey = String(point?.panelKey || point?.panel_key || point?.panelId || point?.panel_id || "").trim();
  const targetSurface = String(point?.target_surface || "").trim();
  const targetSide = String(point?.target_side || "").trim();
  const resolvedPanelKey = targetPanel || panelKey || "vertical_panel";
  const resolvedTargetPanel = targetPanel || resolvedPanelKey;
  const resolvedIsThrough =
    point?.is_through === true ||
    point?.depth_mm === null ||
    point?.depth_mm === undefined;

  return {
    template_id: String(point?.template_id ?? ""),
    panel_key: resolvedPanelKey,
    target_panel: resolvedTargetPanel,
    target_surface: targetSurface,
    target_side: targetSide,
    label: String(point?.label ?? ""),
    x_mm: point?.x_mm ?? "",
    y_mm: point?.y_mm ?? "",
    z_mm: point?.z_mm ?? "",
    diameter_mm: point?.diameter_mm ?? "",
    depth_mm: point?.depth_mm ?? "",
    side: String(point?.side || targetSide || "front"),
    operation: String(point?.operation ?? "drill"),
    order_index: point?.order_index ?? 0,
    quantity: point?.quantity ?? 1,
    mirrored: Boolean(point?.mirrored),
    is_through: resolvedIsThrough,
    notes: String(point?.notes ?? ""),
  };
}

function parseMaybeNumber(text, fieldName) {
  const value = String(text || "").trim();

  if (!value) {
    return undefined;
  }

  const numericValue = Number(value.replace(",", "."));

  if (!Number.isFinite(numericValue)) {
    throw new Error(fieldName);
  }

  return numericValue;
}

export function buildHolePointPayload(form, options = {}) {
  const {
    variantKey = "",
    inferFaceToEdgePointLocation = null,
    getAngledTwoPlanesPointFormPreset = null,
    messages = {},
  } = options;

  const diameterText = String(form?.diameter_mm || "").trim();

  if (!diameterText) {
    throw new Error(messages.holePointDiameterRequired || "diameter");
  }

  const targetPanel = String(form?.target_panel || form?.panel_key || "").trim();
  const panelKey = String(form?.panel_key || targetPanel || "").trim();
  const isThrough = Boolean(form?.is_through);
  const depthText = String(form?.depth_mm || "").trim();
  const depthValue = isThrough ? null : parseMaybeNumber(depthText, messages.holePointDepth || "depth");
  const targetSurface = String(form?.target_surface || "").trim();
  const targetSide = String(form?.target_side || "").trim();
  const normalizedVariantKey = String(variantKey || "").trim();
  const isAngledTwoPlanesVariant = normalizedVariantKey === "angled_two_planes";
  const forcedAngledPreset =
    isAngledTwoPlanesVariant && typeof getAngledTwoPlanesPointFormPreset === "function"
      ? getAngledTwoPlanesPointFormPreset(String(targetPanel || panelKey || "vertical_panel").trim() || "vertical_panel")
      : null;
  const inferredLocation =
    !isAngledTwoPlanesVariant && typeof inferFaceToEdgePointLocation === "function"
      ? inferFaceToEdgePointLocation({
          panel_key: targetPanel || panelKey,
          side: form?.side,
          target_panel: targetPanel,
          target_surface: targetSurface,
          target_side: targetSide,
        })
      : {};
  const resolvedTargetPanel = isAngledTwoPlanesVariant
    ? forcedAngledPreset?.target_panel || targetPanel || panelKey || "vertical_panel"
    : forcedAngledPreset?.target_panel || targetPanel || panelKey || inferredLocation.targetPanel;
  const resolvedTargetSurface = isAngledTwoPlanesVariant
    ? "plane"
    : forcedAngledPreset?.target_surface || targetSurface || inferredLocation.targetSurface;
  const resolvedTargetSide = isAngledTwoPlanesVariant
    ? "inner_face"
    : forcedAngledPreset?.target_side || targetSide || inferredLocation.targetSide;
  const resolvedSide = isAngledTwoPlanesVariant
    ? "inner_face"
    : String(form?.side || "").trim() || resolvedTargetSide || "front";

  if (!isThrough && !Number.isFinite(depthValue)) {
    throw new Error(messages.holePointDepth || "depth");
  }

  const payload = {
    label: String(form?.label || "").trim() || undefined,
    x_mm: parseMaybeNumber(form?.x_mm, messages.holePointX || "x"),
    y_mm: parseMaybeNumber(form?.y_mm, messages.holePointY || "y"),
    z_mm: parseMaybeNumber(form?.z_mm, messages.holePointZ || "z"),
    diameter_mm: parseMaybeNumber(diameterText, messages.holePointDiameter || "diameter"),
    depth_mm: depthValue,
    is_through: isThrough,
    target_panel: resolvedTargetPanel || undefined,
    target_surface: resolvedTargetSurface || undefined,
    target_side: resolvedTargetSide || undefined,
    side: resolvedSide,
    notes: String(form?.notes || "").trim() || null,
  };

  if (normalizedVariantKey !== "angled_two_planes") {
    payload.panel_key = panelKey || undefined;
  }

  if (!Number.isFinite(payload.x_mm)) {
    payload.x_mm = undefined;
  }

  if (!Number.isFinite(payload.y_mm)) {
    payload.y_mm = undefined;
  }

  if (!Number.isFinite(payload.z_mm)) {
    payload.z_mm = undefined;
  }

  return payload;
}

export function mergeHolePointSaveResponse({
  payload,
  responsePoint,
  existingPoint,
} = {}) {
  if (!responsePoint) {
    return null;
  }

  const resolvedTargetPanel = String(
    payload?.target_panel || responsePoint?.target_panel || existingPoint?.target_panel || "",
  ).trim();
  const resolvedTargetSurface = String(
    payload?.target_surface || responsePoint?.target_surface || existingPoint?.target_surface || "",
  ).trim();
  const resolvedTargetSide = String(
    payload?.target_side || responsePoint?.target_side || existingPoint?.target_side || "",
  ).trim();
  const resolvedSide = String(payload?.side || responsePoint?.side || existingPoint?.side || "").trim();
  const resolvedPanelKey = String(
    payload?.panel_key || responsePoint?.panel_key || existingPoint?.panel_key || resolvedTargetPanel || "",
  ).trim();

  return {
    ...responsePoint,
    ...payload,
    panel_key: resolvedPanelKey || undefined,
    target_panel: resolvedTargetPanel || undefined,
    target_surface: resolvedTargetSurface || undefined,
    target_side: resolvedTargetSide || undefined,
    side: resolvedSide || undefined,
  };
}
