import { Spherical, Vector3 } from "three";

export function orbitCameraPosition(cameraPosition, target, thetaDelta = 0, phiDelta = 0, epsilon = 0.01) {
  const targetVector = new Vector3(...target);
  const spherical = new Spherical().setFromVector3(new Vector3(...cameraPosition).sub(targetVector));
  spherical.theta += thetaDelta;
  spherical.phi = Math.max(epsilon, Math.min(Math.PI - epsilon, spherical.phi + phiDelta));
  return new Vector3().setFromSpherical(spherical).add(targetVector).toArray();
}

export function zoomCameraPosition(cameraPosition, target, factor, minDistance = 7, maxDistance = 17) {
  const targetVector = new Vector3(...target);
  const offset = new Vector3(...cameraPosition).sub(targetVector);
  const distance = Math.max(minDistance, Math.min(maxDistance, offset.length() * factor));
  return offset.normalize().multiplyScalar(distance).add(targetVector).toArray();
}
