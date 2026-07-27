import { Quaternion, Vector3 } from "three";

export const SURFACE_MOUNT_THREE_PREVIEW_VARIANT_KEY = "surface_mount";
export const SURFACE_MOUNT_PREVIEW_THICKNESS_MM_DEFAULT = 18;
export const SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MIN = 4;
export const SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MAX = 60;
export const SURFACE_MOUNT_PREVIEW_VISUAL_MARGIN_MM = 30;
export const SURFACE_MOUNT_PREVIEW_MAX_PANEL_HALF_SIZE_SCENE = 6;

const SURFACE_MOUNT_MM_TO_SCENE = 0.01;

export function normalizeSurfaceMountPreviewThicknessMm(value) {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return SURFACE_MOUNT_PREVIEW_THICKNESS_MM_DEFAULT;
  }

  return Math.max(
    SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MIN,
    Math.min(SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MAX, Math.round(parsed)),
  );
}

export function buildSurfaceMountPreviewPanelDimensions(holeVolumes = []) {
  const sourceHoles = Array.isArray(holeVolumes) ? holeVolumes : [];
  const basePanelHalfHeight = 2.18 / 2;
  const basePanelHalfWidth = 1.34 / 2;
  const visualMarginScene = SURFACE_MOUNT_PREVIEW_VISUAL_MARGIN_MM * SURFACE_MOUNT_MM_TO_SCENE;
  const maxAbsY = sourceHoles.reduce((maxValue, hole) => {
    const holeCenterY = Math.abs(Number(hole?.surfacePoint?.[1] ?? hole?.centerPosition?.[1] ?? 0));
    return Math.max(maxValue, holeCenterY);
  }, 0);
  const maxAbsZ = sourceHoles.reduce((maxValue, hole) => {
    const holeCenterZ = Math.abs(Number(hole?.surfacePoint?.[2] ?? hole?.centerPosition?.[2] ?? 0));
    return Math.max(maxValue, holeCenterZ);
  }, 0);
  const maxHoleRadius = sourceHoles.reduce((maxValue, hole) => Math.max(maxValue, Number(hole?.holeRadius) || 0), 0);

  return {
    maxAbsY,
    maxAbsZ,
    panelHalfHeight: Math.max(
      basePanelHalfHeight,
      Math.min(
        SURFACE_MOUNT_PREVIEW_MAX_PANEL_HALF_SIZE_SCENE,
        maxAbsY + maxHoleRadius + visualMarginScene,
      ),
    ),
    panelHalfWidth: Math.max(
      basePanelHalfWidth,
      Math.min(
        SURFACE_MOUNT_PREVIEW_MAX_PANEL_HALF_SIZE_SCENE,
        maxAbsZ + maxHoleRadius + visualMarginScene,
      ),
    ),
    visualMarginScene,
  };
}

export function buildSurfaceMountThreePreviewLayout(
  panelThicknessMm = SURFACE_MOUNT_PREVIEW_THICKNESS_MM_DEFAULT,
  holeVolumes = [],
) {
  const panelThickness = normalizeSurfaceMountPreviewThicknessMm(panelThicknessMm) * SURFACE_MOUNT_MM_TO_SCENE;
  const panelDimensions = buildSurfaceMountPreviewPanelDimensions(holeVolumes);
  return {
    camera: [3.55, 2.35, 4.1],
    label: "Накладне кріплення",
    markerPlane: { axis: "z", origin: [0, 0, 0], spanU: 1.22, spanV: 1.72 },
    panels: [
      {
        args: [panelThickness, panelDimensions.panelHalfHeight * 2, panelDimensions.panelHalfWidth * 2],
        color: "#b9ffb9",
        opacity: 0.28,
        position: [-panelThickness / 2, 0, 0],
        rotation: [0, 0, 0],
      },
    ],
    subtitle: "Панель → накладний елемент · surface_mount",
  };
}

export function getSurfaceMountPointFormPreset() {
  return {
    panel_key: "vertical_panel",
    target_panel: "vertical_panel",
    target_surface: "plane",
    target_side: "inner_face",
    side: "front",
    x_mm: "0",
    y_mm: "0",
    z_mm: "0",
  };
}

export function shouldShowSurfaceMountPointTargetFields(variantKey) {
  return String(variantKey || "").trim() !== "surface_mount";
}

export function shouldRenderSurfaceMountPanelContour(variantKey) {
  return String(variantKey || "").trim() === "surface_mount";
}

export function getSurfaceMountPanelContourStyle() {
  return {
    color: "#8da48d",
    opacity: 0.38,
  };
}

export function buildSurfaceMountThreePreviewLabelPlacements(holeVolumes) {
  const sourceHoles = Array.isArray(holeVolumes) ? holeVolumes : [];

  return Object.fromEntries(
    sourceHoles
      .filter((hole) => hole?.id !== undefined && hole?.id !== null)
      .map((hole, index) => {
        const holeRadius = Number(hole?.holeRadius || 0.05);
        const holeIndex = Number(hole?.id ?? index + 1);
        const sideSign = holeIndex % 2 === 0 ? 1 : -1;
        const lift = holeRadius * 2.1 + 0.06;
        const spread = Math.max(holeRadius * 1.4 + 0.07, 0.11);

        return [
          hole.id,
          {
            labelPosition: [0, lift, sideSign * spread],
            lineEnd: [0, lift * 0.78, sideSign * spread * 0.78],
            sideSign,
          },
        ];
      }),
  );
}

function readHoleNumber(hole, keys) {
  for (const key of keys) {
    const rawValue = hole?.[key];

    if (rawValue === null || rawValue === undefined || String(rawValue).trim() === "") {
      continue;
    }

    const parsed = Number(String(rawValue).replace(",", "."));

    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return null;
}

function normalizeHoleRange(values, fallbackValue) {
  const numericValues = values.filter((value) => Number.isFinite(value));

  if (!numericValues.length) {
    return { max: fallbackValue, min: fallbackValue, span: 0 };
  }

  const min = Math.min(...numericValues);
  const max = Math.max(...numericValues);

  return {
    max,
    min,
    span: Math.max(max - min, 1),
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getSurfaceMountHoleDirection(side) {
  switch (String(side || "").trim()) {
    case "front":
      return { axis: "x", sign: -1 };
    case "back":
      return { axis: "x", sign: -1 };
    case "inner_face":
      return { axis: "x", sign: -1 };
    case "outer_face":
      return { axis: "x", sign: 1 };
    case "face":
      return { axis: "x", sign: 1 };
    case "inner":
      return { axis: "x", sign: -1 };
    case "outer":
      return { axis: "x", sign: 1 };
    case "left":
    case "edge":
      return { axis: "y", sign: -1 };
    case "right":
      return { axis: "y", sign: 1 };
    case "top":
      return { axis: "z", sign: 1 };
    case "bottom":
      return { axis: "z", sign: -1 };
    default:
      return { axis: "x", sign: 1 };
  }
}

function getSurfaceMountHoleRotation(axis) {
  switch (axis) {
    case "x":
      return [0, 0, Math.PI / 2];
    case "y":
      return [0, 0, 0];
    case "z":
    default:
      return [Math.PI / 2, 0, 0];
  }
}

function getSurfaceMountHoleQuaternion(inwardNormal) {
  const direction = new Vector3(
    Number(inwardNormal?.[0]) || 0,
    Number(inwardNormal?.[1]) || 0,
    Number(inwardNormal?.[2]) || 0,
  );

  if (direction.lengthSq() === 0) {
    direction.set(-1, 0, 0);
  }

  return new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), direction.normalize());
}

export function buildSurfaceMountThreePreviewHoleVolumes(holes, layout = {}) {
  const sourceHoles = Array.isArray(holes) ? holes : [];
  const basePanel = Array.isArray(layout?.panels) ? layout.panels[0] || null : null;
  const basePanelThickness = clamp(
    Number(basePanel?.args?.[0]) || 0.26,
    SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MIN * SURFACE_MOUNT_MM_TO_SCENE,
    SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MAX * SURFACE_MOUNT_MM_TO_SCENE,
  );

  return sourceHoles.map((hole, index) => {
    const numericX = readHoleNumber(hole, ["x_mm", "x"]);
    const numericY = readHoleNumber(hole, ["y_mm", "y"]);
    const numericZ = readHoleNumber(hole, ["z_mm", "z"]);
    const numericDiameter = readHoleNumber(hole, ["diameter", "diameter_mm"]);
    const depthValue = readHoleNumber(hole, ["depth", "depth_mm"]);
    const hasDepth = Number.isFinite(depthValue) && depthValue > 0;
    const sideDirection = getSurfaceMountHoleDirection(hole?.side);
    const holeRadius = clamp(
      Number.isFinite(numericDiameter) ? numericDiameter / 110 : 0.052,
      0.045,
      0.1,
    );
    const holeLength = hasDepth
      ? Math.abs(depthValue || 0) * SURFACE_MOUNT_MM_TO_SCENE
      : basePanelThickness;
    const scenePosition = [
      Number.isFinite(numericX) ? numericX * SURFACE_MOUNT_MM_TO_SCENE : 0,
      Number.isFinite(numericY) ? numericY * SURFACE_MOUNT_MM_TO_SCENE : 0,
      Number.isFinite(numericZ) ? numericZ * SURFACE_MOUNT_MM_TO_SCENE : 0,
    ];
    const surfacePoint = scenePosition;
    const directionOffset = holeLength * 0.5;
    const inwardNormal = [
      sideDirection.axis === "x" ? sideDirection.sign : 0,
      sideDirection.axis === "y" ? sideDirection.sign : 0,
      sideDirection.axis === "z" ? sideDirection.sign : 0,
    ];
    const endPoint = [
      surfacePoint[0] + inwardNormal[0] * holeLength,
      surfacePoint[1] + inwardNormal[1] * holeLength,
      surfacePoint[2] + inwardNormal[2] * holeLength,
    ];
    const centerPosition = [
      surfacePoint[0] + inwardNormal[0] * directionOffset,
      surfacePoint[1] + inwardNormal[1] * directionOffset,
      surfacePoint[2] + inwardNormal[2] * directionOffset,
    ];

    return {
      id: hole?.id ?? index + 1,
      point: hole || null,
      label: String(hole?.label || `P${index + 1}`),
      diameter: Number.isFinite(numericDiameter) ? numericDiameter : null,
      diameter_mm: Number.isFinite(numericDiameter) ? numericDiameter : null,
      depth: Number.isFinite(depthValue) ? depthValue : null,
      depth_mm: Number.isFinite(depthValue) ? depthValue : null,
      hasDepth,
      holeLength,
      holeRadius,
      centerPosition,
      surfacePoint,
      onSurfacePosition: surfacePoint,
      endPoint,
      holeCenter: centerPosition,
      inwardNormal,
      quaternion: getSurfaceMountHoleQuaternion(inwardNormal),
      operation: String(hole?.operation || "").trim() || "drill",
      rotation: getSurfaceMountHoleRotation(sideDirection.axis),
      side: String(hole?.side || "").trim() || "front",
      sideDirection,
      isThrough: !hasDepth,
      isFaceToEdge: false,
      isSurfaceMount: true,
    };
  });
}
