import { Matrix4, Vector3 } from "three";

export function worldPointToLocalPoint(worldPoint, worldMatrix) {
  const point = worldPoint instanceof Vector3 ? worldPoint.clone() : new Vector3(...worldPoint);
  return point.applyMatrix4(new Matrix4().copy(worldMatrix).invert()).toArray();
}

export function localPointToWorldPoint(localPoint, worldMatrix) {
  return new Vector3(...localPoint).applyMatrix4(worldMatrix).toArray();
}

export function getMountingPointSnapCandidates(bbox) {
  const axes = ["x", "y", "z"];
  if (!axes.every((axis) => Number.isFinite(Number(bbox?.[axis]?.[0])) && Number.isFinite(Number(bbox?.[axis]?.[1])))) return [];
  const center = axes.map((axis) => (Number(bbox[axis][0]) + Number(bbox[axis][1])) / 2);
  return [
    { point: center, label: "центр" },
    ...axes.flatMap((axis, index) => ["min", "max"].map((side) => {
      const point = [...center];
      point[index] = Number(bbox[axis][side === "min" ? 0 : 1]);
      return { point, label: `${axis.toUpperCase()} ${side}` };
    })),
  ];
}

export function snapMountingPoint(point, bbox, threshold) {
  const candidates = getMountingPointSnapCandidates(bbox);
  if (!candidates.length) return { point: [...point], label: "довільна точка", snapped: false };
  let nearest = null;
  let nearestDistance = Infinity;
  candidates.forEach((candidate) => {
    const distance = Math.hypot(...candidate.point.map((value, index) => Number(point[index]) - value));
    if (distance < nearestDistance) {
      nearest = candidate;
      nearestDistance = distance;
    }
  });
  return nearestDistance <= threshold
    ? { point: [...nearest.point], label: `Прив'язка: ${nearest.label}`, snapped: true }
    : { point: [...point], label: "Прив'язка: довільна точка", snapped: false };
}
