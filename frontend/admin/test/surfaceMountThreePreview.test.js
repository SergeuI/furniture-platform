import assert from "node:assert/strict";
import test from "node:test";
import { Vector3 } from "three";

import {
  SURFACE_MOUNT_THREE_PREVIEW_VARIANT_KEY,
  buildSurfaceMountThreePreviewHoleVolumes,
  buildSurfaceMountThreePreviewLayout,
  buildSurfaceMountPreviewPanelDimensions,
  buildSurfaceMountThreePreviewLabelPlacements,
  getSurfaceMountPanelContourStyle,
  getSurfaceMountPointFormPreset,
  shouldRenderSurfaceMountPanelContour,
  shouldShowSurfaceMountPointTargetFields,
} from "../src/surfaceMountThreePreview.js";

test("surface mount preview helper stays dedicated to the surface_mount variant", () => {
  assert.equal(SURFACE_MOUNT_THREE_PREVIEW_VARIANT_KEY, "surface_mount");
});

test("surface mount preview uses the face_to_edge base panel only", () => {
  const layout = buildSurfaceMountThreePreviewLayout();

  assert.equal(layout.camera[0], 3.55);
  assert.equal(layout.camera[1], 2.35);
  assert.equal(layout.camera[2], 4.1);
  assert.equal(layout.panels.length, 1);
  assert.deepEqual(layout.panels[0], {
    args: [0.18, 2.18, 1.34],
    color: "#b9ffb9",
    opacity: 0.28,
    position: [-0.09, 0, 0],
    rotation: [0, 0, 0],
  });
});

test("surface mount preview expands panel height for a point at Y = 100 mm", () => {
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 20,
        label: "P20",
        x_mm: 0,
        y_mm: 100,
        z_mm: 0,
        diameter_mm: 12,
        side: "inner_face",
      },
    ],
    buildSurfaceMountThreePreviewLayout(),
  );
  const layout = buildSurfaceMountThreePreviewLayout(18, volumes);
  const dimensions = buildSurfaceMountPreviewPanelDimensions(volumes);

  assert.equal(Number(dimensions.maxAbsY.toFixed(3)), 1);
  assert.equal(Number(dimensions.maxAbsZ.toFixed(3)), 0);
  assert.equal(Number(dimensions.visualMarginScene.toFixed(3)), 0.3);
  assert.equal(Number(layout.panels[0].args[1].toFixed(3)), 2.72);
  assert.equal(Number(layout.panels[0].args[2].toFixed(3)), 1.34);
});

test("surface mount preview expands panel height symmetrically for a point at Y = -100 mm", () => {
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 21,
        label: "P21",
        x_mm: 0,
        y_mm: -100,
        z_mm: 0,
        diameter_mm: 12,
        side: "inner_face",
      },
    ],
    buildSurfaceMountThreePreviewLayout(),
  );
  const layout = buildSurfaceMountThreePreviewLayout(18, volumes);

  assert.equal(Number(layout.panels[0].args[1].toFixed(3)), 2.72);
  assert.equal(Number(layout.panels[0].args[2].toFixed(3)), 1.34);
});

test("surface mount preview expands panel width for a point at Z = 100 mm", () => {
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 22,
        label: "P22",
        x_mm: 0,
        y_mm: 0,
        z_mm: 100,
        diameter_mm: 12,
        side: "inner_face",
      },
    ],
    buildSurfaceMountThreePreviewLayout(),
  );
  const layout = buildSurfaceMountThreePreviewLayout(18, volumes);

  assert.equal(Number(layout.panels[0].args[1].toFixed(3)), 2.18);
  assert.equal(Number(layout.panels[0].args[2].toFixed(3)), 2.72);
});

test("surface mount preview caps the visual panel size for extreme coordinates", () => {
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 23,
        label: "P23",
        x_mm: 0,
        y_mm: 100000,
        z_mm: 100000,
        diameter_mm: 12,
        side: "inner_face",
      },
    ],
    buildSurfaceMountThreePreviewLayout(),
  );
  const layout = buildSurfaceMountThreePreviewLayout(18, volumes);

  assert.equal(Number(layout.panels[0].args[1].toFixed(3)), 12);
  assert.equal(Number(layout.panels[0].args[2].toFixed(3)), 12);
});

test("surface mount point preset starts from the centered panel coordinate system", () => {
  assert.deepEqual(getSurfaceMountPointFormPreset(), {
    panel_key: "vertical_panel",
    target_panel: "vertical_panel",
    target_surface: "plane",
    target_side: "inner_face",
    side: "front",
    x_mm: "0",
    y_mm: "0",
    z_mm: "0",
  });
});

test("surface mount hides the target panel, surface and side form fields", () => {
  assert.equal(shouldShowSurfaceMountPointTargetFields("surface_mount"), false);
  assert.equal(shouldShowSurfaceMountPointTargetFields("face_to_edge"), true);
});

test("surface mount renders the panel contour only for surface_mount", () => {
  assert.equal(shouldRenderSurfaceMountPanelContour("surface_mount"), true);
  assert.equal(shouldRenderSurfaceMountPanelContour("face_to_edge"), false);
  assert.deepEqual(getSurfaceMountPanelContourStyle(), {
    color: "#8da48d",
    opacity: 0.38,
  });
});

test("surface mount preview returns no holes for an empty point list", () => {
  const layout = buildSurfaceMountThreePreviewLayout();

  assert.deepEqual(buildSurfaceMountThreePreviewHoleVolumes([], layout), []);
  assert.deepEqual(buildSurfaceMountThreePreviewHoleVolumes(null, layout), []);
});

test("surface mount preview ignores invalid input safely and keeps no service objects", () => {
  const layout = buildSurfaceMountThreePreviewLayout();
  const volumes = buildSurfaceMountThreePreviewHoleVolumes([null, {}], layout);

  assert.equal(volumes.length, 2);
  assert.equal(volumes[0].id, 1);
  assert.equal(volumes[1].id, 2);
  assert.equal(volumes[0].isSurfaceMount, true);
  assert.equal(volumes[1].isSurfaceMount, true);
  assert.equal(layout.panels.length, 1);
  assert.equal(layout.panels[0].args[0], 0.18);
});

test("surface mount preview creates one hole from one real point and preserves point data", () => {
  const layout = buildSurfaceMountThreePreviewLayout();
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 7,
        label: "P7",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 14,
        depth_mm: 18,
        side: "inner_face",
      },
    ],
    layout,
  );

  assert.equal(volumes.length, 1);
  assert.equal(volumes[0].id, 7);
  assert.equal(volumes[0].point.id, 7);
  assert.equal(volumes[0].point.diameter_mm, 14);
  assert.equal(volumes[0].point.depth_mm, 18);
  assert.equal(volumes[0].diameter_mm, 14);
  assert.equal(volumes[0].depth_mm, 18);
  assert.deepEqual(volumes[0].surfacePoint.map((value) => Number(value.toFixed(3))), [0, 0, 0]);
  assert.deepEqual(volumes[0].onSurfacePosition.map((value) => Number(value.toFixed(3))), [0, 0, 0]);
  assert.deepEqual(volumes[0].endPoint.map((value) => Number(value.toFixed(3))), [-0.18, 0, 0]);
  assert.equal(Number(volumes[0].centerPosition[0].toFixed(3)), -0.09);
  assert.equal(Number(volumes[0].centerPosition[1].toFixed(3)), 0);
  assert.equal(Number(volumes[0].centerPosition[2].toFixed(3)), 0);
  assert.equal(Number(volumes[0].holeCenter[0].toFixed(3)), -0.09);
  assert.equal(Number(volumes[0].inwardNormal[0].toFixed(3)), -1);
  assert.equal(Number(volumes[0].inwardNormal[1].toFixed(3)), 0);
  assert.equal(Number(volumes[0].inwardNormal[2].toFixed(3)), 0);
  assert.equal(volumes[0].isSurfaceMount, true);
  assert.equal(volumes[0].isFaceToEdge, false);
  assert.deepEqual(volumes[0].rotation, [0, 0, Math.PI / 2]);
  assert.ok(volumes[0].quaternion);
  assert.equal(volumes[0].holeRadius > 0, true);
  assert.equal(volumes[0].sideDirection.axis, "x");
  assert.equal(volumes[0].sideDirection.sign, -1);

  const direction = new Vector3(
    volumes[0].inwardNormal[0],
    volumes[0].inwardNormal[1],
    volumes[0].inwardNormal[2],
  ).normalize();
  const quaternion = volumes[0].quaternion;
  const halfLength = (volumes[0].holeLength || 0) / 2;
  const groupPosition = new Vector3(...volumes[0].surfacePoint);
  const meshLocalStart = new Vector3(0, 0, 0);
  const meshLocalEnd = new Vector3(0, volumes[0].holeLength, 0);
  const worldStart = meshLocalStart.applyQuaternion(quaternion).add(groupPosition);
  const worldEnd = meshLocalEnd.applyQuaternion(quaternion).add(groupPosition);
  const worldMeshCenter = new Vector3(0, halfLength, 0).applyQuaternion(quaternion).add(groupPosition);
  const normalizeZero = (value) => (Object.is(value, -0) ? 0 : value);

  assert.deepEqual(groupPosition.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [0, 0, 0]);
  assert.deepEqual(worldStart.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [0, 0, 0]);
  assert.deepEqual(worldEnd.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [-0.18, 0, 0]);
  assert.deepEqual(worldMeshCenter.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [-0.09, 0, 0]);
  assert.equal(worldStart.x <= 0.0005, true);
  assert.equal(worldEnd.x < 0, true);
  assert.deepEqual(
    new Vector3(0, 1, 0).applyQuaternion(quaternion).toArray().map((value) => normalizeZero(Number(value.toFixed(3)))),
    direction.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))),
  );
});

test("surface mount quaternion turns local Y inward for the inner_face side", () => {
  const layout = buildSurfaceMountThreePreviewLayout();
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 9,
        label: "P9",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 12,
        depth_mm: 13,
        side: "inner_face",
      },
    ],
    layout,
  );

  const quaternion = volumes[0].quaternion;
  const holeLength = volumes[0].holeLength;
  const groupPosition = new Vector3(...volumes[0].surfacePoint);
  const transformedLocalY = new Vector3(0, 1, 0).applyQuaternion(quaternion);
  const worldStart = new Vector3(0, 0, 0).applyQuaternion(quaternion).add(groupPosition);
  const worldCenter = new Vector3(0, holeLength * 0.5, 0).applyQuaternion(quaternion).add(groupPosition);
  const worldEnd = new Vector3(0, holeLength, 0).applyQuaternion(quaternion).add(groupPosition);
  const normalizeZero = (value) => (Object.is(value, -0) ? 0 : value);

  assert.deepEqual(
    transformedLocalY.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))),
    [-1, 0, 0],
  );
  assert.deepEqual(worldStart.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [0, 0, 0]);
  assert.equal(Number(holeLength.toFixed(3)), 0.13);
  assert.equal(Number(worldCenter.x.toFixed(3)), -0.065);
  assert.equal(Number(worldEnd.x.toFixed(3)), -0.13);
  assert.equal(worldCenter.x < 0, true);
  assert.equal(worldEnd.x < 0, true);
  assert.equal(worldStart.x > 0, false);
});

test("surface mount blind hole uses the raw depth value without a 0.18 floor", () => {
  const layout = buildSurfaceMountThreePreviewLayout(18);
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 11,
        label: "P11",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 12,
        depth_mm: 10,
        side: "inner_face",
      },
    ],
    layout,
  );

  const quaternion = volumes[0].quaternion;
  const groupPosition = new Vector3(...volumes[0].surfacePoint);
  const start = new Vector3(0, 0, 0).applyQuaternion(quaternion).add(groupPosition);
  const center = new Vector3(0, volumes[0].holeLength / 2, 0).applyQuaternion(quaternion).add(groupPosition);
  const end = new Vector3(0, volumes[0].holeLength, 0).applyQuaternion(quaternion).add(groupPosition);
  const normalizeZero = (value) => (Object.is(value, -0) ? 0 : value);

  assert.equal(Number(volumes[0].holeLength.toFixed(3)), 0.1);
  assert.deepEqual(start.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [0, 0, 0]);
  assert.equal(Number(center.x.toFixed(3)), -0.05);
  assert.equal(Number(end.x.toFixed(3)), -0.1);
  assert.equal(center.x < 0, true);
  assert.equal(end.x < 0, true);
});

test("surface mount keeps 3 mm diameter and 3 mm depth as exact cylinder geometry", () => {
  const layout = buildSurfaceMountThreePreviewLayout(18);
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 13,
        label: "P13",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 3,
        depth_mm: 3,
        side: "inner_face",
      },
    ],
    layout,
  );

  const quaternion = volumes[0].quaternion;
  const groupPosition = new Vector3(...volumes[0].surfacePoint);
  const start = new Vector3(0, 0, 0).applyQuaternion(quaternion).add(groupPosition);
  const center = new Vector3(0, volumes[0].holeLength / 2, 0).applyQuaternion(quaternion).add(groupPosition);
  const end = new Vector3(0, volumes[0].holeLength, 0).applyQuaternion(quaternion).add(groupPosition);
  const normalizeZero = (value) => (Object.is(value, -0) ? 0 : value);

  assert.equal(Number(volumes[0].holeRadius.toFixed(3)), 0.015);
  assert.equal(Number(volumes[0].holeLength.toFixed(3)), 0.03);
  assert.equal(Number(volumes[0].centerPosition[0].toFixed(3)), -0.015);
  assert.deepEqual(start.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [0, 0, 0]);
  assert.deepEqual(center.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [-0.015, 0, 0]);
  assert.deepEqual(end.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [-0.03, 0, 0]);
});

test("surface mount preview keeps the same mm to scene scale for 18 mm and 34 mm panels", () => {
  for (const thicknessMm of [18, 34]) {
    const layout = buildSurfaceMountThreePreviewLayout(thicknessMm);
    const volumes = buildSurfaceMountThreePreviewHoleVolumes(
      [
        {
          id: thicknessMm,
          label: `P${thicknessMm}`,
          x_mm: 0,
          y_mm: 0,
          z_mm: 0,
          diameter_mm: 12,
          depth_mm: 10,
          side: "inner_face",
        },
      ],
      layout,
    );

    assert.equal(Number(layout.panels[0].args[0].toFixed(3)), Number((thicknessMm * 0.01).toFixed(3)));
    assert.equal(Number(volumes[0].holeLength.toFixed(3)), 0.1);
    assert.equal(Number((volumes[0].holeLength / layout.panels[0].args[0]).toFixed(3)), Number((10 / thicknessMm).toFixed(3)));
  }
});

test("surface mount through hole uses the preview panel thickness", () => {
  for (const thicknessMm of [16, 18, 19]) {
    const layout = buildSurfaceMountThreePreviewLayout(thicknessMm);
    const volumes = buildSurfaceMountThreePreviewHoleVolumes(
      [
        {
          id: 10,
          label: "P10",
          x_mm: 0,
          y_mm: 0,
          z_mm: 0,
          diameter_mm: 12,
          side: "inner_face",
        },
      ],
      layout,
    );

    const quaternion = volumes[0].quaternion;
    const groupPosition = new Vector3(...volumes[0].surfacePoint);
    const start = new Vector3(0, 0, 0).applyQuaternion(quaternion).add(groupPosition);
    const center = new Vector3(0, volumes[0].holeLength / 2, 0).applyQuaternion(quaternion).add(groupPosition);
    const end = new Vector3(0, volumes[0].holeLength, 0).applyQuaternion(quaternion).add(groupPosition);
    const normalizeZero = (value) => (Object.is(value, -0) ? 0 : value);

    assert.equal(Number(layout.panels[0].args[0].toFixed(3)), Number((thicknessMm * 0.01).toFixed(3)));
    assert.equal(Number(volumes[0].holeLength.toFixed(3)), Number((thicknessMm * 0.01).toFixed(3)));
    assert.deepEqual(start.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [0, 0, 0]);
    assert.equal(Number(center.x.toFixed(3)), Number((-(thicknessMm * 0.01) / 2).toFixed(3)));
    assert.equal(Number(end.x.toFixed(3)), Number((-(thicknessMm * 0.01)).toFixed(3)));
    assert.equal(center.x < 0, true);
    assert.equal(end.x < 0, true);
  }
});

test("surface mount preview keeps the 13 mm hole fully inside the panel and flush on the surface", () => {
  const layout = buildSurfaceMountThreePreviewLayout();
  const volumes = buildSurfaceMountThreePreviewHoleVolumes(
    [
      {
        id: 8,
        label: "P8",
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        diameter_mm: 12,
        depth_mm: 13,
        side: "inner_face",
      },
    ],
    layout,
  );

  const halfLength = (volumes[0].holeLength || 0) / 2;
  const direction = new Vector3(
    volumes[0].inwardNormal[0],
    volumes[0].inwardNormal[1],
    volumes[0].inwardNormal[2],
  ).normalize();
  const quaternion = volumes[0].quaternion;
  const groupPosition = new Vector3(...volumes[0].surfacePoint);
  const frontEnd = new Vector3(0, 0, 0).applyQuaternion(quaternion).add(groupPosition);
  const backEnd = new Vector3(0, volumes[0].holeLength, 0).applyQuaternion(quaternion).add(groupPosition);
  const holeCenter = new Vector3(0, halfLength, 0).applyQuaternion(quaternion).add(groupPosition);
  const panelCenter = new Vector3(-layout.panels[0].args[0] / 2, 0, 0);
  const normalizeZero = (value) => (Object.is(value, -0) ? 0 : value);

  assert.ok(quaternion);
  assert.deepEqual(groupPosition.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))), [0, 0, 0]);
  assert.equal(normalizeZero(Number(frontEnd.x.toFixed(3))), 0);
  assert.equal(Number(backEnd.x.toFixed(3)), -0.13);
  assert.equal(Number(holeCenter.x.toFixed(3)), -0.065);
  assert.equal(frontEnd.x <= 0.0005, true);
  assert.equal(backEnd.x < 0, true);
  assert.equal(holeCenter.x < 0, true);
  assert.equal(holeCenter.x > panelCenter.x, true);
  assert.equal(backEnd.x >= -layout.panels[0].args[0] - 0.001, true);
  assert.deepEqual(
    new Vector3(0, 1, 0).applyQuaternion(quaternion).toArray().map((value) => normalizeZero(Number(value.toFixed(3)))),
    direction.toArray().map((value) => normalizeZero(Number(value.toFixed(3)))),
  );
});

test("surface mount hole id sprite uses a small side offset", () => {
  const placements = buildSurfaceMountThreePreviewLabelPlacements([
    { id: 47, holeRadius: 0.045 },
    { id: 48, holeRadius: 0.045 },
  ]);

  assert.deepEqual(placements[47].labelPosition.map((value) => Number(value.toFixed(3))), [0, 0.154, -0.133]);
  assert.deepEqual(placements[47].lineEnd.map((value) => Number(value.toFixed(3))), [0, 0.121, -0.104]);
  assert.deepEqual(placements[48].labelPosition.map((value) => Number(value.toFixed(3))), [0, 0.154, 0.133]);
  assert.deepEqual(placements[48].lineEnd.map((value) => Number(value.toFixed(3))), [0, 0.121, 0.104]);
});

test("face_to_edge special geometry stays untouched by the surface mount helper", () => {
  const layout = buildSurfaceMountThreePreviewLayout();

  assert.deepEqual(layout.panels[0].rotation, [0, 0, 0]);
  assert.equal(layout.panels.length, 1);
});
