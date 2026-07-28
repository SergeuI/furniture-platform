import assert from "node:assert/strict";
import test from "node:test";

import {
  buildHolePointFormFromPoint,
  buildHolePointPayload,
  createHolePointFormDefaults,
  mergeHolePointSaveResponse,
} from "../src/holePointForm.js";

const messages = {
  holePointDiameterRequired: "diameter required",
  holePointDepth: "depth required",
  holePointX: "x required",
  holePointY: "y required",
  holePointZ: "z required",
  holePointDiameter: "diameter invalid",
};

function buildHelpers() {
  return {
    getAngledTwoPlanesPointFormPreset: (panelKey = "vertical_panel") => ({
      panel_key: panelKey === "horizontal_panel" ? "horizontal_panel" : "vertical_panel",
      target_panel: panelKey === "horizontal_panel" ? "horizontal_panel" : "vertical_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "inner_face",
    }),
    inferFaceToEdgePointLocation: () => ({
      targetPanel: "vertical_panel",
      targetSurface: "edge",
      targetSide: "edge_near_vertical",
    }),
  };
}

test("angled two planes payload keeps the selected horizontal panel and inner-face contract", () => {
  const payload = buildHolePointPayload(
    {
      panel_key: "horizontal_panel",
      target_panel: "horizontal_panel",
      target_surface: "edge",
      target_side: "edge_near_vertical",
      side: "edge_near_vertical",
      x_mm: "80",
      y_mm: "0",
      z_mm: "0",
      diameter_mm: "5",
      depth_mm: "13",
      is_through: false,
      notes: "",
    },
    {
      variantKey: "angled_two_planes",
      ...buildHelpers(),
      messages,
    },
  );

  assert.equal(payload.panel_key, undefined);
  assert.equal(payload.target_panel, "horizontal_panel");
  assert.equal(payload.target_surface, "plane");
  assert.equal(payload.target_side, "inner_face");
  assert.equal(payload.side, "inner_face");
  assert.equal(payload.depth_mm, 13);
});

test("new hole point form starts as a blind hole with depth visible", () => {
  const defaults = createHolePointFormDefaults();

  assert.equal(defaults.is_through, false);
  assert.equal(defaults.depth_mm, "");
});

test("saved hole point with null depth restores as through hole in edit form", () => {
  const form = buildHolePointFormFromPoint({
    id: 103,
    template_id: 7467,
    target_panel: "horizontal_panel",
    target_surface: "plane",
    target_side: "inner_face",
    x_mm: 100,
    y_mm: 0,
    z_mm: 100,
    diameter_mm: 7,
    depth_mm: null,
    side: "inner_face",
  });

  assert.equal(form.is_through, true);
  assert.equal(form.depth_mm, "");
  assert.equal(form.target_panel, "horizontal_panel");
});

test("saved hole point with depth restores as blind hole in edit form", () => {
  const form = buildHolePointFormFromPoint({
    id: 104,
    template_id: 7467,
    target_panel: "horizontal_panel",
    target_surface: "plane",
    target_side: "inner_face",
    x_mm: 50,
    y_mm: 0,
    z_mm: 0,
    diameter_mm: 5,
    depth_mm: 13,
    side: "inner_face",
  });

  assert.equal(form.is_through, false);
  assert.equal(form.depth_mm, 13);
  assert.equal(form.target_panel, "horizontal_panel");
});

test("angled two planes through-hole keeps empty depth and does not need numeric validation", () => {
  const payload = buildHolePointPayload(
    {
      panel_key: "horizontal_panel",
      target_panel: "horizontal_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "inner_face",
      x_mm: "100",
      y_mm: "0",
      z_mm: "100",
      diameter_mm: "7",
      depth_mm: "",
      is_through: true,
      notes: "through",
    },
    {
      variantKey: "angled_two_planes",
      ...buildHelpers(),
      messages,
    },
  );

  assert.equal(payload.is_through, true);
  assert.equal(payload.depth_mm, null);
  assert.equal(payload.target_panel, "horizontal_panel");
  assert.equal(payload.target_surface, "plane");
  assert.equal(payload.target_side, "inner_face");
  assert.equal(payload.side, "inner_face");
});

test("explicit form selection wins over preset and existing state when building angled payloads", () => {
  const payload = buildHolePointPayload(
    {
      panel_key: "horizontal_panel",
      target_panel: "horizontal_panel",
      target_surface: "edge",
      target_side: "edge_near_vertical",
      side: "edge_near_vertical",
      x_mm: "50",
      y_mm: "0",
      z_mm: "0",
      diameter_mm: "5",
      depth_mm: "13",
      is_through: false,
      notes: "",
    },
    {
      variantKey: "angled_two_planes",
      ...buildHelpers(),
      messages,
    },
  );

  const merged = mergeHolePointSaveResponse({
    payload,
    responsePoint: {
      id: 72,
      template_id: 7467,
      target_panel: "vertical_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "edge_near_vertical",
    },
    existingPoint: {
      target_panel: "vertical_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "edge_near_vertical",
    },
  });

  assert.equal(merged.target_panel, "horizontal_panel");
  assert.equal(merged.panel_key, "horizontal_panel");
  assert.equal(merged.target_surface, "plane");
  assert.equal(merged.target_side, "inner_face");
  assert.equal(merged.side, "inner_face");
});

test("response without target_panel keeps the selected horizontal panel in merged state", () => {
  const payload = buildHolePointPayload(
    {
      panel_key: "horizontal_panel",
      target_panel: "horizontal_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "inner_face",
      x_mm: "90",
      y_mm: "0",
      z_mm: "-200",
      diameter_mm: "5",
      depth_mm: "13",
      is_through: false,
      notes: "",
    },
    {
      variantKey: "angled_two_planes",
      ...buildHelpers(),
      messages,
    },
  );

  const merged = mergeHolePointSaveResponse({
    payload,
    responsePoint: {
      id: 91,
      template_id: 7467,
      target_surface: "plane",
      target_side: "inner_face",
      side: "edge_near_vertical",
    },
    existingPoint: {
      target_panel: "vertical_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "edge_near_vertical",
    },
  });

  assert.equal(merged.target_panel, "horizontal_panel");
  assert.equal(merged.panel_key, "horizontal_panel");
  assert.equal(merged.target_surface, "plane");
  assert.equal(merged.target_side, "inner_face");
  assert.equal(merged.side, "inner_face");
});

test("vertical and surface-mount payloads keep their own panel keys", () => {
  const verticalPayload = buildHolePointPayload(
    {
      panel_key: "vertical_panel",
      target_panel: "vertical_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "inner_face",
      x_mm: "0",
      y_mm: "20",
      z_mm: "0",
      diameter_mm: "12",
      depth_mm: "13",
      is_through: false,
      notes: "",
    },
    {
      variantKey: "angled_two_planes",
      ...buildHelpers(),
      messages,
    },
  );

  const surfaceMountPayload = buildHolePointPayload(
    {
      panel_key: "vertical_panel",
      target_panel: "vertical_panel",
      target_surface: "plane",
      target_side: "inner_face",
      side: "inner_face",
      x_mm: "0",
      y_mm: "0",
      z_mm: "0",
      diameter_mm: "6",
      depth_mm: "10",
      is_through: false,
      notes: "",
    },
    {
      variantKey: "surface_mount",
      ...buildHelpers(),
      messages,
    },
  );

  assert.equal(verticalPayload.target_panel, "vertical_panel");
  assert.equal(verticalPayload.target_surface, "plane");
  assert.equal(verticalPayload.target_side, "inner_face");
  assert.equal(verticalPayload.side, "inner_face");
  assert.equal(verticalPayload.panel_key, undefined);

  assert.equal(surfaceMountPayload.target_panel, "vertical_panel");
  assert.equal(surfaceMountPayload.target_surface, "plane");
  assert.equal(surfaceMountPayload.target_side, "inner_face");
  assert.equal(surfaceMountPayload.side, "inner_face");
  assert.equal(surfaceMountPayload.panel_key, "vertical_panel");
});
