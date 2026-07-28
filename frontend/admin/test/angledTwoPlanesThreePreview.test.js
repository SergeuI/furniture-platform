import assert from "node:assert/strict";
import test from "node:test";
import { Vector3 } from "three";

import {
  ANGLED_TWO_PLANES_THREE_PREVIEW_VARIANT_KEY,
  ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
  ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX,
  ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN,
  buildAngledTwoPlanesPreviewPanelDimensions,
  buildAngledTwoPlanesThreePreviewHoleVolumes,
  buildAngledTwoPlanesThreePreviewLabelPlacements,
  buildAngledTwoPlanesThreePreviewLayout,
  getAngledTwoPlanesPointFormPreset,
  normalizeAngledTwoPlanesPreviewThicknessMm,
  shouldRenderAngledTwoPlanesThreePreview,
} from "../src/angledTwoPlanesThreePreview.js";

test("angled two planes preview helper stays dedicated to the angled_two_planes variant", () => {
  assert.equal(ANGLED_TWO_PLANES_THREE_PREVIEW_VARIANT_KEY, "angled_two_planes");
});

test("angled two planes preview render gate is enabled only for the angled_two_planes variant", () => {
  assert.equal(shouldRenderAngledTwoPlanesThreePreview("angled_two_planes"), true);
  assert.equal(shouldRenderAngledTwoPlanesThreePreview("surface_mount"), false);
  assert.equal(shouldRenderAngledTwoPlanesThreePreview("face_to_edge"), false);
});

test("angled two planes preview point form preset always writes the inner plane", () => {
  assert.deepEqual(getAngledTwoPlanesPointFormPreset(), {
    panel_key: "vertical_panel",
    target_panel: "vertical_panel",
    target_surface: "plane",
    target_side: "inner_face",
    side: "inner_face",
  });

  assert.deepEqual(getAngledTwoPlanesPointFormPreset("horizontal_panel"), {
    panel_key: "horizontal_panel",
    target_panel: "horizontal_panel",
    target_surface: "plane",
    target_side: "inner_face",
    side: "inner_face",
  });
});

test("angled two planes preview clamps thickness values to the local 4 to 60 mm range", () => {
  assert.equal(normalizeAngledTwoPlanesPreviewThicknessMm("not-a-number"), ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT);
  assert.equal(normalizeAngledTwoPlanesPreviewThicknessMm(3), ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN);
  assert.equal(normalizeAngledTwoPlanesPreviewThicknessMm(61), ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX);
  assert.equal(normalizeAngledTwoPlanesPreviewThicknessMm(18.4), 18);
});

test("angled two planes preview keeps two L-shaped panels visible at the origin even without points", () => {
  const layout = buildAngledTwoPlanesThreePreviewLayout();

  assert.equal(layout.panels.length, 2);
  assert.deepEqual(layout.markerPlane.origin, [0, 0, 0]);
  assert.equal(Number(layout.panels[0].args[0].toFixed(3)), 0.18);
  assert.equal(Number(layout.panels[1].args[1].toFixed(3)), 0.18);
  assert.equal(layout.panels[0].color, "#b9ffb9");
  assert.equal(layout.panels[1].color, "#b9ffb9");
  assert.equal(layout.panels[0].opacity, 0.28);
  assert.equal(layout.panels[1].opacity, 0.28);
  assert.equal(layout.panels[0].rotation[2], 0);
  assert.equal(layout.panels[1].rotation[2], 0);
  assert.equal(layout.panels[0].position[0] < 0, true);
  assert.equal(layout.panels[1].position[1] < 0, true);
  assert.equal(layout.camera.length, 3);
});

test("angled two planes preview exposes separate vertical and horizontal panel models", () => {
  const layout = buildAngledTwoPlanesThreePreviewLayout(18, 18, [
    {
      id: 1,
      panel_key: "vertical_panel",
      x_mm: 0,
      y_mm: 20,
      z_mm: 0,
      diameter_mm: 12,
    },
    {
      id: 2,
      panel_key: "horizontal_panel",
      x_mm: 80,
      y_mm: 0,
      z_mm: 0,
      diameter_mm: 12,
    },
  ]);

  assert.equal(layout.verticalPanel.key, "vertical_panel");
  assert.equal(layout.horizontalPanel.key, "horizontal_panel");
  assert.deepEqual(layout.verticalPanel.workingPlane, {
    axis: "yz",
    inwardNormal: [-1, 0, 0],
    origin: [0, 0, 0],
    uAxis: "y",
    vAxis: "z",
  });
  assert.deepEqual(layout.horizontalPanel.workingPlane, {
    axis: "xz",
    inwardNormal: [0, -1, 0],
    origin: [0, 0, 0],
    uAxis: "x",
    vAxis: "z",
  });
  assert.equal(layout.verticalPanel.color, "#b9ffb9");
  assert.equal(layout.horizontalPanel.color, "#b9ffb9");
  assert.equal(layout.verticalPanel.opacity, 0.28);
  assert.equal(layout.horizontalPanel.opacity, 0.28);
  assert.equal(layout.panels[0].color, "#b9ffb9");
  assert.equal(layout.panels[1].color, "#b9ffb9");
  assert.equal(layout.panels[0].opacity, 0.28);
  assert.equal(layout.panels[1].opacity, 0.28);
  assert.deepEqual(
    layout.verticalPanel.pointToWorld({ y_mm: 20, z_mm: 0 }).map((value) => Number(value.toFixed(3))),
    [0, 0.2, 0],
  );
  assert.deepEqual(
    layout.horizontalPanel.pointToWorld({ x_mm: 80, z_mm: 0 }).map((value) => Number(value.toFixed(3))),
    [0.8, 0, 0],
  );
  assert.equal(Number(layout.verticalPanel.autoFitBounds.height.toFixed(3)), 0.75);
  assert.equal(Number(layout.horizontalPanel.autoFitBounds.width.toFixed(3)), 1.16);
});

test("angled two planes preview auto-fits the vertical panel independently from the horizontal panel", () => {
  const layout = buildAngledTwoPlanesThreePreviewLayout(18, 18, [
    {
      id: 1,
      panel_key: "vertical_panel",
      x_mm: 0,
      y_mm: 280,
      z_mm: 0,
      diameter_mm: 12,
    },
  ]);
  const dimensions = buildAngledTwoPlanesPreviewPanelDimensions([
    {
      id: 1,
      panel_key: "vertical_panel",
      x_mm: 0,
      y_mm: 280,
      z_mm: 0,
      diameter_mm: 12,
    },
  ]);

  assert.equal(Number(layout.panels[0].args[1].toFixed(3)) > 2.05, true);
  assert.equal(Number(layout.panels[1].args[0].toFixed(3)), 2.05);
  assert.equal(Number(dimensions.verticalHeight.toFixed(3)) > 2.05, true);
  assert.equal(Number(dimensions.horizontalWidth.toFixed(3)), 2.05);
});

test("angled two planes preview auto-fits the horizontal panel independently from the vertical panel", () => {
  const layout = buildAngledTwoPlanesThreePreviewLayout(18, 18, [
    {
      id: 2,
      panel_key: "horizontal_panel",
      x_mm: 280,
      y_mm: 0,
      z_mm: 0,
      diameter_mm: 12,
    },
  ]);
  const dimensions = buildAngledTwoPlanesPreviewPanelDimensions([
    {
      id: 2,
      panel_key: "horizontal_panel",
      x_mm: 280,
      y_mm: 0,
      z_mm: 0,
      diameter_mm: 12,
    },
  ]);

  assert.equal(Number(layout.panels[1].args[0].toFixed(3)) > 2.05, true);
  assert.equal(Number(layout.panels[0].args[1].toFixed(3)), 2.05);
  assert.equal(Number(dimensions.horizontalWidth.toFixed(3)) > 2.05, true);
  assert.equal(Number(dimensions.verticalHeight.toFixed(3)), 2.05);
});

test("angled two planes preview skips holes with no resolved panel key instead of falling back", () => {
  const volumes = buildAngledTwoPlanesThreePreviewHoleVolumes([
    {
      id: 91,
      x_mm: 80,
      y_mm: 0,
      z_mm: 0,
      diameter_mm: 5,
      depth_mm: 13,
    },
  ]);

  assert.deepEqual(volumes, []);
});

test("angled two planes preview auto-fits a vertical point 58 hole without forcing the old base minimum", () => {
  const hole = {
    id: 58,
    panel_key: "vertical_panel",
    x_mm: 0,
    y_mm: 20,
    z_mm: 80,
    diameter_mm: 5,
    is_through: true,
  };
  const dimensions = buildAngledTwoPlanesPreviewPanelDimensions([hole]);
  const volumes = buildAngledTwoPlanesThreePreviewHoleVolumes([hole], 18, 18);
  const layout = buildAngledTwoPlanesThreePreviewLayout(18, 18, [hole]);
  const volume = volumes[0];

  assert.equal(volume.panelKey, "vertical_panel");
  assert.deepEqual(volume.surfacePoint.map((value) => Number(value.toFixed(3))), [0, 0.2, 0.8]);
  assert.equal(Number(volume.holeRadius.toFixed(3)), 0.045);
  assert.equal(Number(dimensions.maxRadiusScene.toFixed(3)), 0.025);
  assert.equal(Number(dimensions.visualMarginScene.toFixed(3)), 0.3);
  assert.equal(Number(dimensions.verticalHeight.toFixed(3)), 0.75);
  assert.equal(Number(layout.panels[0].args[1].toFixed(3)), 0.75);
  assert.equal(Number(layout.markerPlane.spanU.toFixed(3)), 2.05);
  assert.equal(Number(layout.markerPlane.spanV.toFixed(3)), 1.8);
  assert.deepEqual(layout.panels[0].position.map((value) => Number(value.toFixed(3))), [-0.09, 0.375, 0]);
  assert.deepEqual(layout.panels[1].position.map((value) => Number(value.toFixed(3))), [1.025, -0.09, 0]);
  assert.equal(Number(layout.panels[0].args[2].toFixed(3)), 1.34);
  assert.equal(Number(layout.panels[1].args[0].toFixed(3)), 2.05);
  assert.equal(Number(layout.panels[1].args[2].toFixed(3)), 1.34);
});

test("angled two planes preview auto-fits the horizontal point 91 hole to the actual span", () => {
  const hole = {
    id: 91,
    panel_key: "horizontal_panel",
    x_mm: 90,
    y_mm: 0,
    z_mm: -200,
    diameter_mm: 5,
    depth_mm: 13,
  };
  const dimensions = buildAngledTwoPlanesPreviewPanelDimensions([hole]);
  const layout = buildAngledTwoPlanesThreePreviewLayout(18, 18, [hole]);

  assert.equal(Number(dimensions.horizontalWidth.toFixed(3)), 1.225);
  assert.equal(Number(dimensions.panelDepth.toFixed(3)), 2.325);
  assert.equal(Number(layout.horizontalPanel.args[0].toFixed(3)), 1.225);
  assert.equal(Number(layout.horizontalPanel.args[2].toFixed(3)), 2.325);
  assert.deepEqual(layout.horizontalPanel.position.map((value) => Number(value.toFixed(3))), [0.613, -0.09, 0]);
});

test("angled two planes preview maps the vertical panel hole to the inside corner and sends it inward", () => {
  const layout = buildAngledTwoPlanesThreePreviewLayout(18, 18);
  const volumes = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 7,
        label: "P7",
        panel_key: "vertical_panel",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 14,
        depth_mm: 10,
      },
    ],
    18,
    18,
  );

  const volume = volumes[0];
  const worldStart = new Vector3(...volume.surfacePoint).applyQuaternion(volume.quaternion);
  const worldEnd = new Vector3(0, volume.holeLength, 0).applyQuaternion(volume.quaternion).add(new Vector3(...volume.surfacePoint));

  assert.equal(volume.panelKey, "vertical_panel");
  assert.equal(volume.isAngledTwoPlanes, true);
  assert.equal(volume.isSurfaceMount, false);
  assert.deepEqual(volume.surfacePoint.map((value) => Number(value.toFixed(3))), [0, 0, 0]);
  assert.deepEqual(worldStart.toArray().map((value) => Number(value.toFixed(3))), [0, 0, 0]);
  assert.equal(Number(volume.holeLength.toFixed(3)), 0.1);
  assert.equal(Number(worldEnd.x.toFixed(3)) < 0, true);
  assert.equal(Number(volume.inwardNormal[0].toFixed(3)), -1);
  assert.equal(Number(volume.inwardNormal[1].toFixed(3)), 0);
  assert.equal(Number(volume.inwardNormal[2].toFixed(3)), 0);
  assert.equal(Number(volume.centerPosition[0].toFixed(3)) < 0, true);
});

test("angled two planes preview keeps a 13 mm depth readable in world space for both panels", () => {
  const verticalVolume = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 9,
        label: "P9",
        panel_key: "vertical_panel",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 14,
        depth_mm: 13,
      },
    ],
    18,
    18,
  )[0];
  const horizontalVolume = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 10,
        label: "P10",
        panel_key: "horizontal_panel",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 14,
        depth_mm: 13,
      },
    ],
    18,
    18,
  )[0];

  const verticalWorldStart = new Vector3(...verticalVolume.surfacePoint).applyQuaternion(verticalVolume.quaternion);
  const verticalWorldEnd = new Vector3(0, verticalVolume.holeLength, 0).applyQuaternion(verticalVolume.quaternion).add(new Vector3(...verticalVolume.surfacePoint));
  const horizontalWorldStart = new Vector3(...horizontalVolume.surfacePoint).applyQuaternion(horizontalVolume.quaternion);
  const horizontalWorldEnd = new Vector3(0, horizontalVolume.holeLength, 0).applyQuaternion(horizontalVolume.quaternion).add(new Vector3(...horizontalVolume.surfacePoint));

  assert.deepEqual(verticalWorldStart.toArray().map((value) => Number(value.toFixed(3))), [0, 0, 0]);
  assert.deepEqual(verticalWorldEnd.toArray().map((value) => Number(value.toFixed(3))), [-0.13, 0, 0]);
  assert.deepEqual(horizontalWorldStart.toArray().map((value) => Number(value.toFixed(3))), [0, 0, 0]);
  assert.deepEqual(horizontalWorldEnd.toArray().map((value) => Number(value.toFixed(3))), [0, -0.13, 0]);
});

test("angled two planes preview keeps point 76 on the horizontal surface and sends it inward", () => {
  const volume = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 76,
        label: "P76",
        panel_key: "horizontal_panel",
        x_mm: 80,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 5,
        depth_mm: 13,
        side: "inner_face",
        target_panel: "horizontal_panel",
        target_surface: "plane",
        target_side: "inner_face",
      },
    ],
    18,
    18,
  )[0];

  const groupPosition = new Vector3(...volume.surfacePoint);
  const worldStart = groupPosition.clone();
  const worldEnd = new Vector3(0, volume.holeLength, 0).applyQuaternion(volume.quaternion).add(groupPosition);

  assert.equal(volume.panelKey, "horizontal_panel");
  assert.deepEqual(volume.surfacePoint.map((value) => Number(value.toFixed(3))), [0.8, 0, 0]);
  assert.deepEqual(volume.panelCenter.map((value) => Number(value.toFixed(3))), [0.8, -0.09, 0]);
  assert.deepEqual(volume.inwardNormal.map((value) => Number(value.toFixed(3))), [0, -1, 0]);
  assert.equal(Number(volume.holeLength.toFixed(3)), 0.13);
  assert.deepEqual(worldStart.toArray().map((value) => Number(value.toFixed(3))), [0.8, 0, 0]);
  assert.deepEqual(worldEnd.toArray().map((value) => Number(value.toFixed(3))), [0.8, -0.13, 0]);
});

test("angled two planes preview places a horizontal through-hole fully inside 18 mm thickness", () => {
  const volume = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 103,
        label: "P103",
        panel_key: "horizontal_panel",
        x_mm: 100,
        y_mm: 0,
        z_mm: 100,
        diameter_mm: 7,
        depth_mm: null,
        target_panel: "horizontal_panel",
        target_surface: "plane",
        target_side: "inner_face",
        side: "inner_face",
      },
    ],
    18,
    18,
  )[0];

  assert.equal(volume.panelKey, "horizontal_panel");
  assert.deepEqual(volume.surfacePoint.map((value) => Number(value.toFixed(3))), [1, 0, 1]);
  assert.deepEqual(volume.centerPosition.map((value) => Number(value.toFixed(3))), [1, -0.09, 1]);
  assert.deepEqual(volume.endPoint.map((value) => Number(value.toFixed(3))), [1, -0.18, 1]);
  assert.deepEqual(volume.panelCenter.map((value) => Number(value.toFixed(3))), [1, -0.09, 1]);
  assert.deepEqual(volume.onSurfacePosition.map((value) => Number(value.toFixed(3))), [1, 0, 1]);
  assert.equal(Number(volume.holeLength.toFixed(3)), 0.18);
  assert.equal(Number(volume.inwardNormal[0].toFixed(3)), 0);
  assert.equal(Number(volume.inwardNormal[1].toFixed(3)), -1);
  assert.equal(Number(volume.inwardNormal[2].toFixed(3)), 0);
});

test("angled two planes preview places the horizontal panel point 64 at the surface corner and sends it inward", () => {
  const volume = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 64,
        label: "P64",
        panel_key: "horizontal_panel",
        x_mm: 20,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 12,
        depth_mm: 13,
      },
    ],
    18,
    18,
  )[0];

  const groupPosition = new Vector3(...volume.surfacePoint);
  const worldStart = groupPosition.clone();
  const worldEnd = new Vector3(0, volume.holeLength, 0).applyQuaternion(volume.quaternion).add(groupPosition);

  assert.equal(volume.panelKey, "horizontal_panel");
  assert.deepEqual(volume.surfacePoint.map((value) => Number(value.toFixed(3))), [0.2, 0, 0]);
  assert.deepEqual(volume.panelCenter.map((value) => Number(value.toFixed(3))), [0.2, -0.09, 0]);
  assert.deepEqual(volume.inwardNormal.map((value) => Number(value.toFixed(3))), [0, -1, 0]);
  assert.equal(Number(volume.holeLength.toFixed(3)), 0.13);
  assert.deepEqual(worldStart.toArray().map((value) => Number(value.toFixed(3))), [0.2, 0, 0]);
  assert.deepEqual(worldEnd.toArray().map((value) => Number(value.toFixed(3))), [0.2, -0.13, 0]);
});

test("angled two planes preview maps the horizontal panel hole to the inside corner and sends it downward", () => {
  const volumes = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 8,
        label: "P8",
        panel_key: "horizontal_panel",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 12,
      },
    ],
    19,
    16,
  );

  const volume = volumes[0];

  assert.equal(volume.panelKey, "horizontal_panel");
  assert.deepEqual(volume.surfacePoint.map((value) => Number(value.toFixed(3))), [0, 0, 0]);
  assert.equal(Number(volume.holeLength.toFixed(3)), 0.16);
  assert.equal(Number(volume.inwardNormal[0].toFixed(3)), 0);
  assert.equal(Number(volume.inwardNormal[1].toFixed(3)), -1);
  assert.equal(Number(volume.inwardNormal[2].toFixed(3)), 0);
  assert.equal(Number(volume.centerPosition[1].toFixed(3)) < 0, true);
});

test("angled two planes preview keeps an explicit horizontal panel key even when target_panel is stale", () => {
  const volumes = buildAngledTwoPlanesThreePreviewHoleVolumes(
    [
      {
        id: 13,
        label: "P13",
        panel_key: "horizontal_panel",
        target_panel: "vertical_panel",
        target_side: "inner_face",
        side: "inner_face",
        x_mm: 20,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 12,
      },
    ],
    18,
    18,
  );

  const volume = volumes[0];

  assert.equal(volume.panelKey, "horizontal_panel");
  assert.deepEqual(volume.surfacePoint.map((value) => Number(value.toFixed(3))), [0.2, 0, 0]);
  assert.equal(Number(volume.inwardNormal[0].toFixed(3)), 0);
  assert.equal(Number(volume.inwardNormal[1].toFixed(3)), -1);
  assert.equal(Number(volume.inwardNormal[2].toFixed(3)), 0);
});

test("angled two planes preview keeps label callouts off the cylinder body", () => {
  const placements = buildAngledTwoPlanesThreePreviewLabelPlacements([
    { id: 11, panelKey: "vertical_panel", holeRadius: 0.045 },
    { id: 12, panelKey: "horizontal_panel", holeRadius: 0.045 },
  ]);

  assert.equal(placements[11].labelPosition[1] > 0, true);
  assert.equal(placements[11].labelPosition[2] !== 0, true);
  assert.equal(placements[12].labelPosition[0] !== 0, true);
  assert.equal(placements[12].labelPosition[1] < 0, true);
});
