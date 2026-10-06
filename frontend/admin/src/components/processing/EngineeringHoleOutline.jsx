import { Line } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { useState } from "react";
import { buildHoleRingPoints, getHoleSilhouetteRadial } from "../../holeOutlineGeometry.js";

export default function EngineeringHoleOutline({ marker, color = "#16a34a", opacity = 1 }) {
  const { camera } = useThree();
  const [silhouette, setSilhouette] = useState([1, 0, 0]);
  const direction = marker.directionVector || marker.direction || [0, 1, 0];
  const start = marker.debugStartPosition || marker.startPosition || marker.start;
  const end = marker.debugEndPosition || marker.endPosition || marker.end;
  useFrame(() => {
    const center = marker.centerPosition || marker.center || start;
    const next = getHoleSilhouetteRadial(direction, center, camera.position);
    if (next.some((value, index) => Math.abs(value - silhouette[index]) > 0.0001)) setSilhouette(next);
  });
  const radius = marker.holeRadius ?? marker.radius ?? 0.04;
  const ringPoints = [buildHoleRingPoints(start, radius, direction), buildHoleRingPoints(end, radius, direction)];
  const firstSilhouette = start.map((value, index) => value + silhouette[index] * radius);
  const secondSilhouette = start.map((value, index) => value - silhouette[index] * radius);
  const firstEnd = end.map((value, index) => value + silhouette[index] * radius);
  const secondEnd = end.map((value, index) => value - silhouette[index] * radius);
  return <>
    {ringPoints.map((points, index) => <Line key={`engineering-hole-ring-${index}`} points={points} color={color} lineWidth={3} opacity={1} depthTest renderOrder={6} />)}
    <Line points={[firstSilhouette, firstEnd]} color={color} lineWidth={3} opacity={opacity} depthTest={false} renderOrder={6} />
    <Line points={[secondSilhouette, secondEnd]} color={color} lineWidth={3} opacity={opacity} depthTest={false} renderOrder={6} />
  </>;
}
