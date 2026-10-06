import assert from "node:assert/strict";
import test from "node:test";
import { buildHoleRingPoints, getHoleSilhouetteRadial } from "../src/holeOutlineGeometry.js";

test("camera-aware silhouette is perpendicular, symmetric, and changes with camera", () => {
  const direction = [1, 0, 0];
  const center = [0, 0, 0];
  const first = getHoleSilhouetteRadial(direction, center, [2, 3, 4]);
  const second = getHoleSilhouetteRadial(direction, center, [2, -3, -4]);
  assert.equal(Number(first[0].toFixed(8)), 0);
  assert.equal(Number(second[0].toFixed(8)), 0);
  assert.notDeepEqual(first.map((value) => Number(value.toFixed(5))), second.map((value) => Number(value.toFixed(5))));
  assert.equal(Number(first.reduce((sum, value, index) => sum + value * direction[index], 0).toFixed(8)), 0);
  assert.equal(Number(Math.hypot(...first).toFixed(8)), 1);
  const start = [0, -0.09, 0];
  const end = [0.34, -0.09, 0];
  const lineStart = start.map((value, index) => value + first[index] * 0.028);
  const lineEnd = end.map((value, index) => value + first[index] * 0.028);
  assert.deepEqual(lineEnd.map((value, index) => Number((value - lineStart[index]).toFixed(8))), [0.34, 0, 0]);
  assert.deepEqual(second.map((value, index) => Number((value + first[index]).toFixed(8))), [0, 0, 0]);
});

test("collinear camera uses a stable perpendicular fallback", () => {
  const result = getHoleSilhouetteRadial([-1, 0, 0], [0, 0, 0], [5, 0, 0]);
  assert.equal(Number(result[0].toFixed(8)), 0);
  assert.equal(Number(Math.hypot(...result).toFixed(8)), 1);
});

test("rings are closed, perpendicular to the hole axis, and preserve radius", () => {
  for (const direction of [[-1, 0, 0], [1, 0, 0]]) {
    const center = [0.34, -0.09, 0.2];
    const radius = 0.028;
    const ring = buildHoleRingPoints(center, radius, direction);
    assert.equal(ring.length, 33);
    assert.deepEqual(ring[0].map((value) => Number(value.toFixed(8))), ring.at(-1).map((value) => Number(value.toFixed(8))));
    ring.forEach((point) => {
      const delta = point.map((value, index) => value - center[index]);
      assert.ok(Math.abs(delta.reduce((sum, value, index) => sum + value * direction[index], 0)) < 1e-8);
      assert.ok(Math.abs(Math.hypot(...delta) - radius) < 1e-8);
    });
  }
});
