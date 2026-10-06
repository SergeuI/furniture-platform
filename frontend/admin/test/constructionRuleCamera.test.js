import assert from "node:assert/strict";
import test from "node:test";
import { orbitCameraPosition, zoomCameraPosition } from "../src/constructionRuleCamera.js";

const distance = (a, b) => Math.hypot(...a.map((value, index) => value - b[index]));

test("orbit preserves target and distance", () => {
  const camera = [9, 7, 11];
  const target = [2, 1, -3];
  const result = orbitCameraPosition(camera, target, 0.2, 0);
  assert.notDeepEqual(result, camera);
  assert.equal(Number(distance(result, target).toFixed(8)), Number(distance(camera, target).toFixed(8)));
});

test("orbit changes phi and clamps at both poles", () => {
  const target = [0, 0, 0];
  const up = orbitCameraPosition([0, 0.01, 1], target, 0, -10);
  const down = orbitCameraPosition([0, 0.01, 1], target, 0, 10);
  assert.ok(up[1] > 0);
  assert.ok(down[1] < 0);
});

test("right orbit uses negative theta step", () => {
  const left = orbitCameraPosition([9, 7, 11], [0, 0, 0], 0.2, 0);
  const right = orbitCameraPosition([9, 7, 11], [0, 0, 0], -0.2, 0);
  assert.notDeepEqual(left, right);
});

test("zoom semantics move toward or away from the target within limits", () => {
  const camera = [9, 7, 11];
  const target = [0, 0, 0];
  const before = distance(camera, target);
  const zoomIn = zoomCameraPosition(camera, target, 1 / 1.12, 7, 17);
  const zoomOut = zoomCameraPosition(camera, target, 1.12, 7, 17);
  assert.ok(distance(zoomIn, target) < before);
  assert.ok(distance(zoomOut, target) > before);
  assert.equal(Number(distance(zoomCameraPosition(camera, target, 0.01, 7, 17), target).toFixed(8)), 7);
  assert.equal(Number(distance(zoomCameraPosition(camera, target, 10, 7, 17), target).toFixed(8)), 17);
});
