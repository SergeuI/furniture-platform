import { Vector3 } from "three";

export function getHoleSilhouetteRadial(direction, center, cameraPosition, fallback = [0, 1, 0]) {
  const d = new Vector3(...direction).normalize();
  const view = new Vector3(...cameraPosition).sub(new Vector3(...center)).normalize();
  const perpendicular = view.sub(d.clone().multiplyScalar(view.dot(d)));
  if (perpendicular.lengthSq() < 1e-10) {
    const fallbackVector = new Vector3(...fallback);
    perpendicular.copy(fallbackVector.sub(d.clone().multiplyScalar(fallbackVector.dot(d))));
  }
  perpendicular.normalize();
  return new Vector3().crossVectors(d, perpendicular).normalize().toArray();
}

export function buildHoleRingPoints(center, radius, direction, segments = 32) {
  const d = new Vector3(...direction).normalize();
  const reference = Math.abs(d.y) < 0.9 ? new Vector3(0, 1, 0) : new Vector3(1, 0, 0);
  const u = new Vector3().crossVectors(d, reference).normalize();
  const v = new Vector3().crossVectors(d, u).normalize();
  return Array.from({ length: segments + 1 }, (_, index) => {
    const angle = (index / segments) * Math.PI * 2;
    return new Vector3(...center)
      .addScaledVector(u, Math.cos(angle) * radius)
      .addScaledVector(v, Math.sin(angle) * radius)
      .toArray();
  });
}
