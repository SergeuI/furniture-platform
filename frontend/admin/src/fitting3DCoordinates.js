export const CANONICAL_AXES = ["X", "-X", "Y", "-Y", "Z", "-Z"];
const AXIS_VECTORS = { X: [1, 0, 0], "-X": [-1, 0, 0], Y: [0, 1, 0], "-Y": [0, -1, 0], Z: [0, 0, 1], "-Z": [0, 0, -1] };
export function canonicalAxisToVector(axis) { return AXIS_VECTORS[axis] ? [...AXIS_VECTORS[axis]] : null; }
export function areCanonicalAxesPerpendicular(forward, up) { const a = canonicalAxisToVector(forward); const b = canonicalAxisToVector(up); return Boolean(a && b && a[0] * b[0] + a[1] * b[1] + a[2] * b[2] === 0); }
export function mountingPointPreset(bbox, preset) {
  const mid = (a, b) => (Number(a) + Number(b)) / 2;
  const x = bbox?.x || [], y = bbox?.y || [], z = bbox?.z || [];
  if (![...x, ...y, ...z].every(Number.isFinite)) return null;
  const c = [mid(x[0], x[1]), mid(y[0], y[1]), mid(z[0], z[1])];
  return ({ center: c, xMin: [x[0], c[1], c[2]], xMax: [x[1], c[1], c[2]], yMin: [c[0], y[0], c[2]], yMax: [c[0], y[1], c[2]], zMin: [c[0], c[1], z[0]], zMax: [c[0], c[1], z[1]] })[preset] || null;
}
export function resolveEffectiveMountingPoint(asset) {
  const point = [asset?.mounting_point_x, asset?.mounting_point_y, asset?.mounting_point_z];
  return point.every((value) => value !== null && value !== undefined && Number.isFinite(Number(value))) ? point.map(Number) : [0, 0, 0];
}
export function buildFitting3DCoordinateSavePayload(coordinates, { mountingPointOverride = true } = {}) {
  const point = [coordinates.mounting_point_x, coordinates.mounting_point_y, coordinates.mounting_point_z];
  if (!mountingPointOverride && !coordinates.axis_forward && !coordinates.axis_up) return { ok: true, payload: { mounting_point_x: null, mounting_point_y: null, mounting_point_z: null, axis_forward: null, axis_up: null, mounting_coordinate_system_configured: false } };
  if ((mountingPointOverride && !point.every((value) => Number.isFinite(Number(value)))) || !CANONICAL_AXES.includes(coordinates.axis_forward) || !CANONICAL_AXES.includes(coordinates.axis_up)) return { ok: false, error: "Виберіть напрям монтажу й вісь вгору; точка може залишатися нулем моделі." };
  if (!areCanonicalAxesPerpendicular(coordinates.axis_forward, coordinates.axis_up)) return { ok: false, error: "Напрям монтажу та вісь вгору не можуть бути паралельними." };
  return { ok: true, payload: { mounting_point_x: mountingPointOverride ? Number(point[0]) : null, mounting_point_y: mountingPointOverride ? Number(point[1]) : null, mounting_point_z: mountingPointOverride ? Number(point[2]) : null, axis_forward: coordinates.axis_forward, axis_up: coordinates.axis_up, mounting_coordinate_system_configured: true } };
}
