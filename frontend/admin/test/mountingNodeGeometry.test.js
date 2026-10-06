import assert from "node:assert/strict";
import test from "node:test";
import { resolveFaceToEdgeHolePlacement } from "../src/mountingNodeGeometry.js";

test("face_to_edge through P1 spans the complete vertical panel thickness", () => {
  for (const thicknessMm of [16, 18, 19]) {
    const thickness = thicknessMm / 100;
    const placement = resolveFaceToEdgeHolePlacement({
      panelA: { args: [thickness, 2, 1], position: [-thickness / 2, 0, 0] },
      panelB: { args: [1.6, thickness, 1], position: [0.8, -thickness / 2, 0] },
      point: { label: "P1", diameter_mm: 7, depth_mm: null, x_mm: 0, y_mm: 0, z_mm: 0 },
      location: { targetPanel: "vertical_panel", targetSurface: "plane", targetSide: "inner_face" },
    });
    assert.equal(Number(placement.holeLength.toFixed(6)), Number(thickness.toFixed(6)));
    assert.deepEqual(placement.debugStartPosition.map((value) => Number(value.toFixed(6))), [0, -thickness / 2, 0].map((value) => Number(value.toFixed(6))));
    assert.deepEqual(placement.centerPosition.map((value) => Number(value.toFixed(6))), [-thickness / 2, -thickness / 2, 0].map((value) => Number(value.toFixed(6))));
    assert.deepEqual(placement.debugEndPosition.map((value) => Number(value.toFixed(6))), [-thickness, -thickness / 2, 0].map((value) => Number(value.toFixed(6))));
  }
});

test("face_to_edge P1 and P2 share the horizontal-panel centerline origin", () => {
  for (const verticalMm of [16, 18, 19]) {
    for (const horizontalMm of [16, 18, 19]) {
      const vertical = verticalMm / 100;
      const horizontal = horizontalMm / 100;
      const panelA = { args: [vertical, 2, 1], position: [-vertical / 2, 0, 0] };
      const panelB = { args: [1.6, horizontal, 1], position: [0.8, -horizontal / 2, 0] };
      const p1 = resolveFaceToEdgeHolePlacement({ panelA, panelB, point: { label: "P1", diameter_mm: 7, depth_mm: null }, location: { targetPanel: "vertical_panel", targetSurface: "plane", targetSide: "inner_face" } });
      const p2 = resolveFaceToEdgeHolePlacement({ panelA, panelB, point: { label: "P2", diameter_mm: 4.5, depth_mm: 34 }, location: { targetPanel: "horizontal_panel", targetSurface: "edge", targetSide: "edge_near_vertical" } });
      assert.equal(Number(p1.holeLength.toFixed(6)), Number(vertical.toFixed(6)));
      assert.equal(Number(p2.holeLength.toFixed(6)), 0.34);
      assert.deepEqual(p1.debugStartPosition, p2.debugStartPosition);
      assert.equal(Number(p1.debugStartPosition[1].toFixed(6)), Number((-horizontal / 2).toFixed(6)));
      assert.equal(Number(p2.debugStartPosition[1].toFixed(6)), Number((-horizontal / 2).toFixed(6)));
      assert.equal(Number(p2.centerPosition[1].toFixed(6)), Number((-horizontal / 2).toFixed(6)));
      assert.equal(Number(p2.debugEndPosition[1].toFixed(6)), Number((-horizontal / 2).toFixed(6)));
    }
  }
});

test("bottom_to_side uses panel bounds and preserves P1/P2 continuity", () => {
  for (const thicknessMm of [16, 18, 19, 60]) {
    const thickness = thicknessMm / 100;
    const geometry = { width: 6, height: 7.2, depth: 5, thickness, sideX: (6 - thickness) / 2, bottomWidth: 6, bottomY: -3.6 - thickness / 2 };
    for (const joint of ["left", "right"]) {
      const sign = joint === "right" ? 1 : -1;
      const panelA = { args: [thickness, 7.2, 5], position: [sign * geometry.sideX, 0, 0] };
      const panelB = { args: [6, thickness, 5], position: [0, geometry.bottomY, 0] };
      const p1 = resolveFaceToEdgeHolePlacement({ panelA, panelB, point: { label: "P1", diameter_mm: 7 }, location: { targetPanel: "horizontal_panel", targetSurface: "plane", targetSide: "bottom_face" }, joint, constructionGeometry: geometry });
      const p2 = resolveFaceToEdgeHolePlacement({ panelA, panelB, point: { label: "P2", diameter_mm: 4.5, depth_mm: 34 }, location: { targetPanel: "vertical_panel", targetSurface: "edge", targetSide: "bottom_edge" }, joint, constructionGeometry: geometry });
      assert.deepEqual(p1.debugStartPosition, [sign * geometry.sideX, geometry.bottomY - thickness / 2, 0]);
      assert.deepEqual(p1.debugEndPosition.map((value) => Number(value.toFixed(6))), p2.debugStartPosition.map((value) => Number(value.toFixed(6))));
      assert.deepEqual(p1.directionVector, [0, 1, 0]);
      assert.deepEqual(p2.directionVector, [0, 1, 0]);
    }
  }
});

test("face_to_edge edge_near_vertical mirrors relative to the joint", () => {
  const panelA = { args: [0.18, 7.2, 5], position: [-2.91, 0, 0] };
  const panelB = { args: [6, 0.18, 5], position: [0, -3.51, 0] };
  const point = { label: "P2", diameter_mm: 4.5, depth_mm: 34 };
  const left = resolveFaceToEdgeHolePlacement({ panelA, panelB, point, joint: "left", location: { targetPanel: "horizontal_panel", targetSurface: "edge", targetSide: "edge_near_vertical" } });
  const right = resolveFaceToEdgeHolePlacement({ panelA: { ...panelA, position: [2.91, 0, 0] }, panelB, point, joint: "right", location: { targetPanel: "horizontal_panel", targetSurface: "edge", targetSide: "edge_near_vertical" } });
  assert.deepEqual(left.debugStartPosition.map((value) => Number(value.toFixed(6))), [-3, -3.51, 0]);
  assert.deepEqual(right.debugStartPosition.map((value) => Number(value.toFixed(6))), [3, -3.51, 0]);
  assert.deepEqual(left.directionVector, [1, 0, 0]);
  assert.deepEqual(right.directionVector, [-1, 0, 0]);
});
