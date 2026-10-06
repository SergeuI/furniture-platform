const MM_TO_SCENE = 0.01;

function readConstructionNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function resolveMountingNodeInstanceFrame({ constructionGeometry = {}, joint = "left", schemePositionMm = 0, node = {}, holePoints = [] }) {
  const width = readConstructionNumber(constructionGeometry.width, 6);
  const height = readConstructionNumber(constructionGeometry.height, 7.2);
  const depth = readConstructionNumber(constructionGeometry.depth, 5);
  const thickness = readConstructionNumber(constructionGeometry.thickness, 0.18);
  const bottomY = readConstructionNumber(constructionGeometry.bottomY, -height / 2 + thickness / 2);
  const bottomWidth = readConstructionNumber(constructionGeometry.bottomWidth, width);
  const sideSign = String(joint).toLowerCase() === "right" ? 1 : -1;
  const sideX = (width - thickness) / 2;
  const z = -depth / 2 + (readConstructionNumber(schemePositionMm) / (depth * 100)) * depth;
  const panel = String(node.visual_anchor_panel || "vertical_panel").trim() || "vertical_panel";
  const surface = String(node.visual_anchor_surface || "outer_face").trim() || "outer_face";
  const surfaceOffset = surface === "outer_face" ? thickness / 2 : -thickness / 2;
  const position = panel === "vertical_panel"
    ? [sideSign * (sideX + surfaceOffset), bottomY, z]
    : [sideSign * (bottomWidth / 2), bottomY, z];
  const pointList = Array.isArray(holePoints) ? holePoints : [];
  const p1 = pointList.find((point) => String(point?.label || point?.name || "").toUpperCase() === "P1") || null;
  const p2 = pointList.find((point) => String(point?.label || point?.name || "").toUpperCase() === "P2") || null;
  const isBottomToSide = p1?.target_panel === "horizontal_panel"
    && p1?.target_surface === "plane"
    && p1?.target_side === "bottom_face"
    && p2?.target_panel === "vertical_panel"
    && p2?.target_surface === "edge"
    && p2?.target_side === "bottom_edge";
  const direction = isBottomToSide ? [0, 1, 0] : [-sideSign, 0, 0];

  return {
    position,
    direction,
    joint: String(joint).toLowerCase() === "right" ? "right" : "left",
    schemePositionMm: readConstructionNumber(schemePositionMm),
    panel,
    surface,
    p1Target: p1 ? { panel: p1.target_panel || p1.panel_key || "vertical_panel", surface: p1.target_surface || p1.surface || "plane" } : null,
    p2Target: p2 ? { panel: p2.target_panel || p2.panel_key || "horizontal_panel", surface: p2.target_surface || p2.surface || "edge" } : null,
    p1Position: panel === "vertical_panel" ? [...position] : null,
    p2Position: [sideSign * (bottomWidth / 2), bottomY, z],
  };
}

function readNumber(value, fallback = null) {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(String(value).replace(",", "."));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function resolvedOffset(point, key) {
  const value = point?.[key] ?? point?.[`${key}_mm`];
  return {
    value: readNumber(value, 0),
    usedFallback: value === null || value === undefined || value === "",
  };
}

export function resolveFaceToEdgeHolePlacement({ panelA, panelB, point = {}, index = 0, location, joint = null, constructionGeometry = null }) {
  const panelAThickness = Number(panelA?.args?.[0]) || 0.28;
  const panelAHeight = Number(panelA?.args?.[1]) || 2.18;
  const panelBWidth = Number(panelB?.args?.[0]) || 1.96;
  const panelBThickness = Number(panelB?.args?.[1]) || 0.28;
  const originX = (Number(panelA?.position?.[0]) || 0) + panelAThickness / 2;
  const originY = Number(panelB?.position?.[1]) || 0;
  const originZ = ((Number(panelA?.position?.[2]) || 0) + (Number(panelB?.position?.[2]) || 0)) / 2;
  const diameter = readNumber(point.diameter ?? point.diameter_mm, 8);
  const depth = readNumber(point.depth ?? point.depth_mm, null);
  const x = resolvedOffset(point, "x");
  const y = resolvedOffset(point, "y");
  const z = resolvedOffset(point, "z");
  const xOffset = x.value * MM_TO_SCENE;
  const yOffset = y.value * MM_TO_SCENE;
  const zOffset = z.value * MM_TO_SCENE;
  const hasDepth = Number.isFinite(depth) && depth > 0;
  const isHorizontalEdge = location.targetPanel === "horizontal_panel" && location.targetSurface === "edge";
  const isHorizontalPlane = location.targetPanel === "horizontal_panel" && location.targetSurface === "plane";
  const isVerticalEdge = location.targetPanel === "vertical_panel" && location.targetSurface === "edge";
  const isBottomToSide = location.targetSide === "bottom_face" || location.targetSide === "bottom_edge";
  const sideSign = String(joint || location.joint || "").toLowerCase() === "right" ? 1 : -1;
  const holeRadius = Math.max(0.028, Math.min(0.08, Number.isFinite(diameter) ? diameter * 0.005 : 0.04));
  const throughHoleLength = isHorizontalEdge || isHorizontalPlane ? panelBThickness : panelAThickness;
  const holeLength = hasDepth ? Math.abs(depth) * MM_TO_SCENE : throughHoleLength;
  const depthScene = hasDepth ? Math.abs(depth) * MM_TO_SCENE : holeLength;
  const fallback = { usedFallbackOffsets: x.usedFallback || y.usedFallback || z.usedFallback };
  const base = {
    id: point.id ?? index,
    label: String(point.label ?? `P${index + 1}`),
    holeLength,
    holeRadius,
    isFaceToEdge: true,
    isThrough: !hasDepth,
    location,
    orderIndex: index,
    placementFunctionName: "resolveFaceToEdgeHolePlacement",
    renderPath: "resolver result -> Three.js cylinder",
    sourcePanelKey: String(point.panelKey || point.panel_key || point.panelId || point.panel_id || "").trim(),
    sourceSide: String(point.side || "").trim(),
    sourceSurface: String(point.surface || point.target_surface || point.targetSurface || "").trim(),
    debugDepth: depth,
    ...fallback,
    targetPanel: location.targetPanel,
    targetSide: location.targetSide,
    targetSurface: location.targetSurface,
  };

  if (isHorizontalEdge) {
    const jointRelativeEdge = Boolean(joint || location.joint) && location.targetSide === "edge_near_vertical";
    const edgeX = jointRelativeEdge
      ? (Number(panelB?.position?.[0]) || 0) + sideSign * panelBWidth / 2
      : location.targetSide === "edge_far_vertical"
      ? (Number(panelB?.position?.[0]) || 0) + panelBWidth / 2
      : (Number(panelB?.position?.[0]) || 0) - panelBWidth / 2;
    const directionSign = jointRelativeEdge ? -sideSign : location.targetSide === "edge_far_vertical" ? -1 : 1;
    const startPosition = [edgeX + xOffset, originY + yOffset, originZ + zOffset];
    return { ...base, axis: "x", centerPosition: [edgeX + directionSign * holeLength * 0.5 + xOffset, originY + yOffset, originZ + zOffset], directionVector: [directionSign, 0, 0], debugDirectionVector: [directionSign, 0, 0], debugStartPosition: startPosition, debugEndPosition: [edgeX + directionSign * depthScene + xOffset, originY + yOffset, originZ + zOffset], rotation: [0, 0, -Math.PI / 2] };
  }

  if (isHorizontalPlane) {
    const isBottomFace = location.targetSide === "bottom_face";
    // bottom_to_side starts on the horizontal board's top surface and points upward.
    // Other face-to-edge semantics retain their existing face direction.
    const startY = isBottomToSide && constructionGeometry
      ? (Number(constructionGeometry.bottomY) || 0) - panelBThickness / 2
      : (Number(panelB?.position?.[1]) || 0) + panelBThickness / 2;
    const directionSign = isBottomFace ? 1 : -1;
    const axisX = isBottomToSide && constructionGeometry ? sideSign * (Number(constructionGeometry.sideX) || 0) : originX;
    return { ...base, axis: "y", centerPosition: [axisX + xOffset, startY + directionSign * holeLength * 0.5 + yOffset, originZ + zOffset], directionVector: [0, directionSign, 0], debugDirectionVector: [0, directionSign, 0], debugStartPosition: [axisX + xOffset, startY + yOffset, originZ + zOffset], debugEndPosition: [axisX + xOffset, startY + directionSign * depthScene + yOffset, originZ + zOffset], rotation: [0, 0, 0] };
  }

  if (isVerticalEdge) {
    const edgePosition = location.targetSide === "top_edge"
      ? "top"
      : location.targetSide === "bottom_edge"
        ? "bottom"
        : "legacy-bottom";
    const isTopEdge = edgePosition === "top";
    const startY = isBottomToSide && constructionGeometry
      ? (Number(constructionGeometry.bottomY) || 0) + panelBThickness / 2
      : isTopEdge ? (Number(panelA?.position?.[1]) || 0) + panelAHeight / 2 : (Number(panelA?.position?.[1]) || 0) - panelAHeight / 2;
    const directionSign = isTopEdge ? -1 : 1;
    const axisX = isBottomToSide && constructionGeometry ? sideSign * (Number(constructionGeometry.sideX) || 0) : originX;
    return { ...base, axis: "y", centerPosition: [axisX + xOffset, startY + directionSign * holeLength * 0.5 + yOffset, originZ + zOffset], directionVector: [0, directionSign, 0], debugDirectionVector: [0, directionSign, 0], debugStartPosition: [axisX + xOffset, startY + yOffset, originZ + zOffset], debugEndPosition: [axisX + xOffset, startY + directionSign * depthScene + yOffset, originZ + zOffset], rotation: [0, 0, 0] };
  }

  const isOuterFace = location.targetSide === "outer_face";
  const startX = isOuterFace ? (Number(panelA?.position?.[0]) || 0) - panelAThickness / 2 : originX;
  const directionSign = isOuterFace ? 1 : -1;
  return { ...base, axis: "x", centerPosition: [startX + directionSign * holeLength * 0.5 + xOffset, originY + yOffset, originZ + zOffset], directionVector: [directionSign, 0, 0], debugDirectionVector: [directionSign, 0, 0], debugStartPosition: [startX + xOffset, originY + yOffset, originZ + zOffset], debugEndPosition: [startX + directionSign * depthScene + xOffset, originY + yOffset, originZ + zOffset], rotation: [0, 0, 0] };
}
