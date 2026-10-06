import test from "node:test";
import assert from "node:assert/strict";
import { Matrix4, Vector3 } from "three";
import { getMountingPointSnapCandidates, localPointToWorldPoint, snapMountingPoint, worldPointToLocalPoint } from "../src/fitting3DTransform.js";
import { buildFitting3DCoordinateSavePayload, resolveEffectiveMountingPoint } from "../src/fitting3DCoordinates.js";

test("fitting mounting point world/local transform round-trips", () => {
  const matrix = new Matrix4().makeRotationY(Math.PI / 4);
  matrix.setPosition(3, -2, 5);
  const local = [1.25, -0.5, 2.75];
  const world = localPointToWorldPoint(local, matrix);
  const restored = worldPointToLocalPoint(new Vector3(...world), matrix);
  assert.deepEqual(restored.map((value) => Number(value.toFixed(8))), local.map((value) => Number(value.toFixed(8))));
});

const bbox = { x: [-2, 2], y: [-1, 3], z: [-4, 4] };

test("mounting snap candidates include center and bbox face centers", () => {
  const points = getMountingPointSnapCandidates(bbox).map(({ point }) => point);
  assert.deepEqual(points, [[0, 1, 0], [-2, 1, 0], [2, 1, 0], [0, -1, 0], [0, 3, 0], [0, 1, -4], [0, 1, 4]]);
});

test("mounting point snaps inside threshold and remains exact outside it", () => {
  assert.deepEqual(snapMountingPoint([0.03, 1, 0], bbox, 0.1), { point: [0, 1, 0], label: "Прив'язка: центр", snapped: true });
  assert.deepEqual(snapMountingPoint([0.5, 1, 0], bbox, 0.1), { point: [0.5, 1, 0], label: "Прив'язка: довільна точка", snapped: false });
});

test("mounting point null resolves to local origin", () => {
  assert.deepEqual(resolveEffectiveMountingPoint({ mounting_point_x: null, mounting_point_y: null, mounting_point_z: null }), [0, 0, 0]);
});

test("configured custom and explicit zero mounting points are preserved", () => {
  assert.deepEqual(resolveEffectiveMountingPoint({ mounting_point_x: 1, mounting_point_y: -2, mounting_point_z: 3 }), [1, -2, 3]);
  assert.deepEqual(resolveEffectiveMountingPoint({ mounting_point_x: 0, mounting_point_y: 0, mounting_point_z: 0 }), [0, 0, 0]);
});

test("default mounting point stores null while effective point stays origin", () => {
  const result = buildFitting3DCoordinateSavePayload({ mounting_point_x: "", mounting_point_y: "", mounting_point_z: "", axis_forward: "X", axis_up: "Y" }, { mountingPointOverride: false });
  assert.equal(result.ok, true);
  assert.equal(result.payload.mounting_point_x, null);
  assert.deepEqual(resolveEffectiveMountingPoint(result.payload), [0, 0, 0]);
});
