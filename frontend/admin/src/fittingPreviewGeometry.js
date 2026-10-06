import { canonicalAxisToVector, resolveEffectiveMountingPoint } from "./fitting3DCoordinates.js";

const negate = (vector) => vector.map((value) => {
  const negated = -Number(value || 0);
  return Object.is(negated, -0) ? 0 : negated;
});

export const VERTICAL_FITTING_SURFACES = ["inner_face", "outer_face", "left_edge", "right_edge", "top_edge", "bottom_edge"];
export const HORIZONTAL_FITTING_SURFACES = ["top_face", "bottom_face", "left_edge", "right_edge", "front_edge", "back_edge"];
export const VERTICAL_FITTING_FACE_SURFACES = ["inner_face", "outer_face"];
export const HORIZONTAL_FITTING_FACE_SURFACES = ["top_face", "bottom_face"];

export function fittingSurfaceOptionsForPanel(panel) {
  if (panel === "horizontal_panel") return HORIZONTAL_FITTING_FACE_SURFACES;
  if (panel === "vertical_panel") return VERTICAL_FITTING_FACE_SURFACES;
  return [];
}

export function normalizeFittingSurfaceForPanel(panel, surface) {
  const options = fittingSurfaceOptionsForPanel(panel);
  return options.includes(surface) ? surface : options[0];
}

export function normalizeFittingAnchorSurface(panel, surface) {
  const value = String(surface || "").trim();
  if (value === "edge") return panel === "horizontal_panel" ? "top_face" : "inner_face";
  if (value === "plane") return panel === "horizontal_panel" ? "top_face" : "inner_face";
  return value;
}

function panelBounds(panelGeometry) {
  const position = panelGeometry?.position || [0, 0, 0];
  const args = panelGeometry?.args || [];
  const half = (value) => (Number(value) || 0) / 2;
  return {
    x: [Number(position[0]) - half(args[0]), Number(position[0]) + half(args[0])],
    y: [Number(position[1]) - half(args[1]), Number(position[1]) + half(args[1])],
    z: [Number(position[2]) - half(args[2]), Number(position[2]) + half(args[2])],
  };
}

export function resolveFittingAnchor({ panelGeometry, anchorPanel, anchorSurface, referencePoint } = {}) {
  const bounds = panelBounds(panelGeometry);
  const panel = anchorPanel === "horizontal_panel" ? "horizontal_panel" : "vertical_panel";
  const surface = normalizeFittingAnchorSurface(panel, anchorSurface);
  const center = (range) => (range[0] + range[1]) / 2;
  const reference = Array.isArray(referencePoint) ? referencePoint : [];
  const valueOrCenter = (value, fallback) => Number.isFinite(Number(value)) ? Number(value) : fallback;
  const point = Array.isArray(referencePoint)
    ? [valueOrCenter(reference[0], center(bounds.x)), valueOrCenter(reference[1], center(bounds.y)), valueOrCenter(reference[2], center(bounds.z))]
    : [center(bounds.x), center(bounds.y), center(bounds.z)];
  let normal = [0, 0, 0];
  const set = (axis, value, direction) => { point[axis] = value; normal[axis] = direction; };
  if (panel === "vertical_panel") {
    if (surface === "outer_face") set(0, bounds.x[0], -1);
    else if (surface === "inner_face") set(0, bounds.x[1], 1);
    else if (surface === "left_edge") set(2, bounds.z[0], -1);
    else if (surface === "right_edge") set(2, bounds.z[1], 1);
    else if (surface === "top_edge") set(1, bounds.y[1], 1);
    else if (surface === "bottom_edge") set(1, bounds.y[0], -1);
  } else {
    if (surface === "top_face") { point[0] = bounds.x[0]; set(1, bounds.y[1], 1); }
    else if (surface === "bottom_face") { point[0] = bounds.x[0]; set(1, bounds.y[0], -1); }
    else if (surface === "left_edge") set(0, bounds.x[0], -1);
    else if (surface === "right_edge") set(0, bounds.x[1], 1);
    else if (surface === "front_edge") set(2, bounds.z[1], 1);
    else if (surface === "back_edge") set(2, bounds.z[0], -1);
  }
  return { point, normal, panel, surface };
}

export function resolveFaceToEdgeFittingFrame(holeVolumes) {
  const p1 = (Array.isArray(holeVolumes) ? holeVolumes : []).find((hole) => String(hole?.label || "").toUpperCase() === "P1");
  const p2 = (Array.isArray(holeVolumes) ? holeVolumes : []).find((hole) => String(hole?.label || "").toUpperCase() === "P2");
  if (!p1 || !p2 || !Array.isArray(p1.debugEndPosition) || !Array.isArray(p1.debugDirectionVector)) return null;
  return { entryPoint: [...p1.debugEndPosition], forward: negate(p1.debugDirectionVector), p1, p2 };
}

export function resolveFittingLocalFrame(asset, engineeringFrame) {
  return {
    mountingPoint: resolveEffectiveMountingPoint(asset),
    localForward: canonicalAxisToVector(asset?.axis_forward) || [1, 0, 0],
    localUp: canonicalAxisToVector(asset?.axis_up),
    engineeringForward: engineeringFrame?.forward || [1, 0, 0],
    entryPoint: engineeringFrame?.entryPoint || [0, 0, 0],
  };
}

export function resolveSelectedFittingAnchor(layout, panelKey, surface, engineeringFrame) {
  const panels = Array.isArray(layout?.panels) ? layout.panels : [];
  const panel = panelKey === "horizontal_panel" ? panels[1] : panels[0];
  if (!panel) return null;
  const resolved = resolveFittingAnchor({ panelGeometry: panel, anchorPanel: panelKey, anchorSurface: surface, referencePoint: engineeringFrame?.entryPoint });
  return { anchorPoint: resolved.point, anchorNormal: resolved.normal, anchorPanel: resolved.panel, anchorSurface: resolved.surface };
}
