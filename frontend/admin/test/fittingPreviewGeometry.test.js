import assert from "node:assert/strict";
import test from "node:test";
import { resolveFaceToEdgeHolePlacement } from "../src/mountingNodeGeometry.js";
import { HORIZONTAL_FITTING_FACE_SURFACES, VERTICAL_FITTING_FACE_SURFACES, fittingSurfaceOptionsForPanel, normalizeFittingSurfaceForPanel, resolveFaceToEdgeFittingFrame, resolveFittingAnchor, resolveFittingLocalFrame, resolveSelectedFittingAnchor } from "../src/fittingPreviewGeometry.js";

const makeFrame = (horizontalMm) => {
  const vertical = 0.18;
  const horizontal = horizontalMm / 100;
  const panelA = { args: [vertical, 2, 1], position: [-vertical / 2, 0, 0] };
  const panelB = { args: [1.6, horizontal, 1], position: [0.8, -horizontal / 2, 0] };
  const p1 = resolveFaceToEdgeHolePlacement({ panelA, panelB, point: { label: "P1", diameter_mm: 7 }, location: { targetPanel: "vertical_panel", targetSurface: "plane", targetSide: "inner_face" } });
  const p2 = resolveFaceToEdgeHolePlacement({ panelA, panelB, point: { label: "P2", diameter_mm: 4.5, depth_mm: 34 }, location: { targetPanel: "horizontal_panel", targetSurface: "edge", targetSide: "edge_near_vertical" } });
  return resolveFaceToEdgeFittingFrame([p1, p2]);
};

test("face_to_edge fitting follows the resolved engineering frame", () => {
  const yValues = [16, 18, 19, 60].map((thickness) => makeFrame(thickness).entryPoint[1]);
  assert.deepEqual(yValues, [-0.08, -0.09, -0.095, -0.3]);
  for (const thickness of [16, 18, 19, 60]) {
    const frame = makeFrame(thickness);
    assert.deepEqual(frame.forward, [1, 0, 0]);
    assert.deepEqual(frame.entryPoint, frame.p1.debugEndPosition);
    assert.equal(frame.p2.debugStartPosition[1], frame.entryPoint[1]);
  }
});

test("zero visual correction preserves the engineering entry point", () => {
  const frame = makeFrame(18);
  const local = resolveFittingLocalFrame({ mounting_point_x: null, mounting_point_y: null, mounting_point_z: null }, frame);
  assert.deepEqual(local.mountingPoint, [0, 0, 0]);
  assert.deepEqual(local.entryPoint, frame.entryPoint);
});

test("selected vertical anchors switch between the two physical faces", () => {
  for (const thicknessMm of [16, 18, 19]) {
    const thickness = thicknessMm / 100;
    const layout = { panels: [{ args: [thickness, 2, 1], position: [-thickness / 2, 0, 0] }, { args: [1.6, thickness, 1], position: [0.8, -thickness / 2, 0] }] };
    const frame = makeFrame(thicknessMm);
    const outer = resolveSelectedFittingAnchor(layout, "vertical_panel", "outer_face", frame);
    const inner = resolveSelectedFittingAnchor(layout, "vertical_panel", "inner_face", frame);
    assert.equal(Math.abs(inner.anchorPoint[0] - outer.anchorPoint[0]), thickness);
    assert.deepEqual(outer.anchorNormal, [-1, 0, 0]);
    assert.deepEqual(inner.anchorNormal, [1, 0, 0]);
    assert.deepEqual(outer.anchorPoint.slice(1), frame.entryPoint.slice(1));
  }
});

test("selected horizontal anchors use horizontal panel geometry", () => {
  const layout = { panels: [{ args: [0.18, 2, 1], position: [-0.09, 0, 0] }, { args: [1.6, 0.18, 1], position: [0.8, -0.09, 0] }] };
  const frame = makeFrame(18);
  const edge = resolveSelectedFittingAnchor(layout, "horizontal_panel", "edge", frame);
  assert.equal(edge.anchorPoint[1], 0);
  assert.equal(edge.anchorPoint[0], 0);
  assert.equal(edge.anchorPanel, "horizontal_panel");
});

test("canonical anchor surfaces use real panel bounds and normals", () => {
  assert.deepEqual(fittingSurfaceOptionsForPanel("vertical_panel"), ["inner_face", "outer_face"]);
  assert.deepEqual(fittingSurfaceOptionsForPanel("horizontal_panel"), ["top_face", "bottom_face"]);
  assert.deepEqual(VERTICAL_FITTING_FACE_SURFACES, ["inner_face", "outer_face"]);
  assert.deepEqual(HORIZONTAL_FITTING_FACE_SURFACES, ["top_face", "bottom_face"]);
  for (const thicknessMm of [16, 18, 19]) {
    const thickness = thicknessMm / 100;
    const vertical = { args: [thickness, 2, 1], position: [-thickness / 2, 0, 0] };
    const horizontal = { args: [1.6, thickness, 1.2], position: [0.8, -thickness / 2, 0] };
    const outer = resolveFittingAnchor({ panelGeometry: vertical, anchorPanel: "vertical_panel", anchorSurface: "outer_face" });
    const inner = resolveFittingAnchor({ panelGeometry: vertical, anchorPanel: "vertical_panel", anchorSurface: "inner_face" });
    const top = resolveFittingAnchor({ panelGeometry: horizontal, anchorPanel: "horizontal_panel", anchorSurface: "top_face" });
    const bottom = resolveFittingAnchor({ panelGeometry: horizontal, anchorPanel: "horizontal_panel", anchorSurface: "bottom_face" });
    assert.equal(Math.abs(inner.point[0] - outer.point[0]), thickness);
    assert.equal(Math.abs(top.point[1] - bottom.point[1]), thickness);
    assert.equal(top.point[0], 0);
    assert.equal(bottom.point[0], 0);
    assert.deepEqual(outer.normal, [-1, 0, 0]);
    assert.deepEqual(inner.normal, [1, 0, 0]);
    assert.deepEqual(top.normal, [0, 1, 0]);
    assert.deepEqual(bottom.normal, [0, -1, 0]);
  }
});

test("panel-specific surface fallback keeps only valid face options", () => {
  assert.equal(normalizeFittingSurfaceForPanel("vertical_panel", "outer_face"), "outer_face");
  assert.equal(normalizeFittingSurfaceForPanel("vertical_panel", "left_edge"), "inner_face");
  assert.equal(normalizeFittingSurfaceForPanel("vertical_panel", "edge"), "inner_face");
  assert.equal(normalizeFittingSurfaceForPanel("horizontal_panel", "bottom_face"), "bottom_face");
  assert.equal(normalizeFittingSurfaceForPanel("horizontal_panel", "right_edge"), "top_face");
  assert.equal(normalizeFittingSurfaceForPanel("horizontal_panel", "plane"), "top_face");
});
