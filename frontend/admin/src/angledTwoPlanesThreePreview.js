import { Quaternion, Vector3 } from "three";

export const ANGLED_TWO_PLANES_THREE_PREVIEW_VARIANT_KEY = "angled_two_planes";
export const ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT = 18;
export const ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN = 4;
export const ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX = 60;
export const ANGLED_TWO_PLANES_PREVIEW_VISUAL_MARGIN_MM = 30;
export const ANGLED_TWO_PLANES_PREVIEW_MAX_PANEL_HALF_SIZE_SCENE = 6;
export const ANGLED_TWO_PLANES_PREVIEW_PANEL_PADDING_MM = 50;
export const ANGLED_TWO_PLANES_PREVIEW_BASE_PANEL_SPAN_SCENE = 2.05;
export const ANGLED_TWO_PLANES_PREVIEW_BASE_PANEL_DEPTH_SCENE = 1.34;

const ANGLED_TWO_PLANES_MM_TO_SCENE = 0.01;

export function normalizeAngledTwoPlanesPreviewThicknessMm(value) {
  const parsed = Number(value);

  if (!Number.isFinite(parsed)) {
    return ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT;
  }

  return Math.max(
    ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN,
    Math.min(ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX, Math.round(parsed)),
  );
}

export function shouldRenderAngledTwoPlanesThreePreview(variantKey) {
  return String(variantKey || "").trim() === "angled_two_planes";
}

export function getAngledTwoPlanesPointFormPreset(panelKey = "vertical_panel") {
  const resolvedPanelKey = String(panelKey || "").trim() === "horizontal_panel"
    ? "horizontal_panel"
    : "vertical_panel";

  return {
    panel_key: resolvedPanelKey,
    target_panel: resolvedPanelKey,
    target_surface: "plane",
    target_side: "inner_face",
    side: "inner_face",
  };
}

function readNumber(hole, keys) {
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

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getAngledTwoPlanesPointRadiusScene(hole) {
  const diameterMm = readNumber(hole, ["diameter_mm", "diameter"]);

  if (!Number.isFinite(diameterMm)) {
    return 0;
  }

  return Math.abs(diameterMm) * ANGLED_TWO_PLANES_MM_TO_SCENE * 0.5;
}

function buildAngledTwoPlanesAxisBounds(sourceHoles, panelKey, valueGetter, baseSpanScene, defaultCenterScene = 0) {
  const paddingScene = ANGLED_TWO_PLANES_PREVIEW_PANEL_PADDING_MM * ANGLED_TWO_PLANES_MM_TO_SCENE;
  const values = sourceHoles
    .filter((hole) => panelKey === null || resolveAngledTwoPlanesPanelKey(hole) === panelKey)
    .map((hole) => {
      const value = valueGetter(hole);

      if (!Number.isFinite(value)) {
        return null;
      }

      const radiusScene = getAngledTwoPlanesPointRadiusScene(hole);
      return {
        max: value + radiusScene,
        min: value - radiusScene,
      };
    })
    .filter(Boolean);

  if (!values.length) {
    return {
      center: defaultCenterScene,
      max: defaultCenterScene + baseSpanScene / 2,
      min: defaultCenterScene - baseSpanScene / 2,
      span: baseSpanScene,
    };
  }

  const min = Math.min(...values.map((entry) => entry.min));
  const max = Math.max(...values.map((entry) => entry.max));
  let paddedMin;
  let paddedMax;

  if (min >= 0) {
    paddedMin = 0;
    paddedMax = Math.max(baseSpanScene, max + paddingScene);
  } else if (max <= 0) {
    paddedMin = Math.min(-baseSpanScene, min - paddingScene);
    paddedMax = 0;
  } else {
    paddedMin = min - paddingScene;
    paddedMax = max + paddingScene;
  }

  const span = paddedMax - paddedMin;

  return {
    center: (paddedMin + paddedMax) / 2,
    max: paddedMax,
    min: paddedMin,
    span,
  };
}

function buildAngledTwoPlanesCenteredDepthBounds(sourceHoles, baseSpanScene) {
  const paddingScene = ANGLED_TWO_PLANES_PREVIEW_PANEL_PADDING_MM * ANGLED_TWO_PLANES_MM_TO_SCENE;
  const values = sourceHoles
    .map((hole) => {
      const zMm = readNumber(hole, ["z_mm", "z"]);

      if (!Number.isFinite(zMm)) {
        return null;
      }

      const radiusScene = getAngledTwoPlanesPointRadiusScene(hole);
      return Math.abs(zMm * ANGLED_TWO_PLANES_MM_TO_SCENE) + radiusScene;
    })
    .filter((value) => Number.isFinite(value));

  if (!values.length) {
    return {
      center: 0,
      max: baseSpanScene / 2,
      min: -baseSpanScene / 2,
      span: baseSpanScene,
    };
  }

  const maxExtent = Math.max(...values) + paddingScene;
  const extent = Math.max(baseSpanScene / 2, maxExtent);

  return {
    center: 0,
    max: extent,
    min: -extent,
    span: extent * 2,
  };
}

function resolveAngledTwoPlanesPanelKey(hole) {
  const explicitKey = String(
    hole?.panelKey ||
      hole?.panel_key ||
      hole?.panelId ||
      hole?.panel_id ||
      hole?.target_panel ||
      hole?.targetPanel ||
      "",
  )
    .trim()
    .toLowerCase();

  if (["horizontal_panel", "horizontal", "panel_b", "b"].includes(explicitKey)) {
    return "horizontal_panel";
  }

  if (["vertical_panel", "vertical", "panel_a", "a"].includes(explicitKey)) {
    return "vertical_panel";
  }

  return null;
}

function getAngledTwoPlanesHoleQuaternion(inwardNormal) {
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

function buildAngledTwoPlanesPanelModel(panelKey, panelDimensions, verticalPanelThickness, horizontalPanelThickness) {
  const isHorizontalPanel = panelKey === "horizontal_panel";
  const thickness = isHorizontalPanel ? horizontalPanelThickness : verticalPanelThickness;
  const inwardNormal = isHorizontalPanel ? [0, -1, 0] : [-1, 0, 0];
  const position = isHorizontalPanel
    ? [panelDimensions.horizontalCenter, -thickness / 2, panelDimensions.panelCenter]
    : [-thickness / 2, panelDimensions.verticalCenter, panelDimensions.panelCenter];
  const autoFitBounds = isHorizontalPanel
    ? {
        center: panelDimensions.horizontalCenter,
        max: panelDimensions.horizontalMax,
        min: panelDimensions.horizontalMin,
        width: panelDimensions.horizontalWidth,
      }
    : {
        center: panelDimensions.verticalCenter,
        height: panelDimensions.verticalHeight,
        max: panelDimensions.verticalMax,
        min: panelDimensions.verticalMin,
      };

  return {
    key: panelKey,
    args: isHorizontalPanel
      ? [panelDimensions.horizontalWidth, thickness, panelDimensions.panelDepth]
      : [thickness, panelDimensions.verticalHeight, panelDimensions.panelDepth],
    autoFitBounds,
    inwardNormal,
    label: isHorizontalPanel ? "Горизонтальна панель" : "Вертикальна панель",
    pointToWorld(point = {}) {
      const numericX = readNumber(point, ["x_mm", "x"]);
      const numericY = readNumber(point, ["y_mm", "y"]);
      const numericZ = readNumber(point, ["z_mm", "z"]);

      return isHorizontalPanel
        ? [
            Number.isFinite(numericX) ? numericX * ANGLED_TWO_PLANES_MM_TO_SCENE : 0,
            0,
            Number.isFinite(numericZ) ? numericZ * ANGLED_TWO_PLANES_MM_TO_SCENE : 0,
          ]
        : [
            0,
            Number.isFinite(numericY) ? numericY * ANGLED_TWO_PLANES_MM_TO_SCENE : 0,
            Number.isFinite(numericZ) ? numericZ * ANGLED_TWO_PLANES_MM_TO_SCENE : 0,
          ];
    },
    position,
    rotation: [0, 0, 0],
    workingPlane: isHorizontalPanel
      ? {
          axis: "xz",
          inwardNormal,
          origin: [0, 0, 0],
          uAxis: "x",
          vAxis: "z",
        }
      : {
          axis: "yz",
          inwardNormal,
          origin: [0, 0, 0],
          uAxis: "y",
          vAxis: "z",
        },
  };
}

function buildAngledTwoPlanesPanelModels(panelDimensions, verticalPanelThickness, horizontalPanelThickness) {
  const verticalPanel = buildAngledTwoPlanesPanelModel(
    "vertical_panel",
    panelDimensions,
    verticalPanelThickness,
    horizontalPanelThickness,
  );
  const horizontalPanel = buildAngledTwoPlanesPanelModel(
    "horizontal_panel",
    panelDimensions,
    verticalPanelThickness,
    horizontalPanelThickness,
  );

  return { horizontalPanel, verticalPanel };
}

export function buildAngledTwoPlanesPreviewPanelDimensions(holes = []) {
  const sourceHoles = Array.isArray(holes) ? holes : [];
  const visualMarginScene = ANGLED_TWO_PLANES_PREVIEW_VISUAL_MARGIN_MM * ANGLED_TWO_PLANES_MM_TO_SCENE;
  const maxRadiusScene = sourceHoles.reduce((maxValue, hole) => {
    const diameterMm = readNumber(hole, ["diameter_mm", "diameter"]);
    const radiusScene = Number.isFinite(diameterMm) ? Math.abs(diameterMm) * 0.005 : 0;
    return Math.max(maxValue, radiusScene);
  }, 0);
  const verticalBounds = buildAngledTwoPlanesAxisBounds(
    sourceHoles,
    "vertical_panel",
    (hole) => {
      const yMm = readNumber(hole, ["y_mm", "y"]);
      return Number.isFinite(yMm) ? yMm * ANGLED_TWO_PLANES_MM_TO_SCENE : null;
    },
    ANGLED_TWO_PLANES_PREVIEW_BASE_PANEL_SPAN_SCENE,
    ANGLED_TWO_PLANES_PREVIEW_BASE_PANEL_SPAN_SCENE / 2,
  );
  const horizontalBounds = buildAngledTwoPlanesAxisBounds(
    sourceHoles,
    "horizontal_panel",
    (hole) => {
      const xMm = readNumber(hole, ["x_mm", "x"]);
      return Number.isFinite(xMm) ? xMm * ANGLED_TWO_PLANES_MM_TO_SCENE : null;
    },
    ANGLED_TWO_PLANES_PREVIEW_BASE_PANEL_SPAN_SCENE,
    ANGLED_TWO_PLANES_PREVIEW_BASE_PANEL_SPAN_SCENE / 2,
  );
  const depthBounds = buildAngledTwoPlanesCenteredDepthBounds(
    sourceHoles,
    ANGLED_TWO_PLANES_PREVIEW_BASE_PANEL_DEPTH_SCENE,
  );

  return {
    horizontalCenter: horizontalBounds.center,
    horizontalMax: horizontalBounds.max,
    horizontalMin: horizontalBounds.min,
    horizontalWidth: horizontalBounds.span,
    maxRadiusScene,
    panelCenter: depthBounds.center,
    panelDepth: depthBounds.span,
    panelDepthMax: depthBounds.max,
    panelDepthMin: depthBounds.min,
    verticalCenter: verticalBounds.center,
    verticalHeight: verticalBounds.span,
    verticalMax: verticalBounds.max,
    verticalMin: verticalBounds.min,
    visualMarginScene,
  };
}

export function buildAngledTwoPlanesThreePreviewLayout(
  verticalPanelThicknessMm = ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
  horizontalPanelThicknessMm = ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
  holes = [],
) {
  const sourceHoles = Array.isArray(holes) ? holes : [];
  const verticalPanelThickness = normalizeAngledTwoPlanesPreviewThicknessMm(verticalPanelThicknessMm) * ANGLED_TWO_PLANES_MM_TO_SCENE;
  const horizontalPanelThickness = normalizeAngledTwoPlanesPreviewThicknessMm(horizontalPanelThicknessMm) * ANGLED_TWO_PLANES_MM_TO_SCENE;
  const panelDimensions = buildAngledTwoPlanesPreviewPanelDimensions(holes);
  const { verticalPanel, horizontalPanel } = buildAngledTwoPlanesPanelModels(
    panelDimensions,
    verticalPanelThickness,
    horizontalPanelThickness,
  );
  const longestSpan = Math.max(
    panelDimensions.verticalHeight,
    panelDimensions.horizontalWidth,
    panelDimensions.panelDepth,
  );
  const cameraDistance = clamp(4.4 + longestSpan * 0.55, 4.8, 8.2);
  const panelStyle = {
    color: "#b9ffb9",
    opacity: 0.28,
  };
  const sceneOrigin = [0, 0, 0];
  const styledVerticalPanel = {
    ...verticalPanel,
    ...panelStyle,
  };
  const styledHorizontalPanel = {
    ...horizontalPanel,
    ...panelStyle,
  };

  return {
    camera: [cameraDistance, cameraDistance * 0.66, cameraDistance * 1.16],
    horizontalPanel: styledHorizontalPanel,
    label: "Дві площини під кутом",
    markerPlane: { axis: "z", origin: sceneOrigin, spanU: panelDimensions.horizontalWidth, spanV: panelDimensions.verticalHeight },
    panels: [
      styledVerticalPanel,
      styledHorizontalPanel,
    ],
    sceneOrigin,
    subtitle: "Панель A → Панель B · angled_two_planes",
    verticalPanel: styledVerticalPanel,
  };
}

export function buildAngledTwoPlanesThreePreviewLabelPlacements(holeVolumes) {
  const sourceHoles = Array.isArray(holeVolumes) ? holeVolumes : [];

  return Object.fromEntries(
    sourceHoles
      .filter((hole) => hole?.id !== undefined && hole?.id !== null)
      .map((hole, index) => {
        const panelKey = String(hole?.panelKey || "").trim();

        if (!panelKey) {
          return null;
        }

        const holeRadius = Number(hole?.holeRadius || 0.05);
        const holeIndex = Number(hole?.id ?? index + 1);
        const sideSign = holeIndex % 2 === 0 ? 1 : -1;
        const lift = holeRadius * 2.4 + 0.07;
        const spread = Math.max(holeRadius * 1.5 + 0.08, 0.12);

        if (panelKey === "horizontal_panel") {
          return [
            hole.id,
            {
              labelPosition: [sideSign * spread, -lift, 0],
              lineEnd: [sideSign * spread * 0.8, -lift * 0.78, 0],
              sideSign,
            },
          ];
        }

        return [
          hole.id,
          {
            labelPosition: [0, lift, sideSign * spread],
            lineEnd: [0, lift * 0.78, sideSign * spread * 0.78],
            sideSign,
          },
        ];
      })
      .filter(Boolean),
  );
}

export function buildAngledTwoPlanesThreePreviewHoleVolumes(
  holes,
  verticalPanelThicknessMm = ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
  horizontalPanelThicknessMm = ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
) {
  const sourceHoles = Array.isArray(holes) ? holes : [];
  const panelDimensions = buildAngledTwoPlanesPreviewPanelDimensions(sourceHoles);
  const verticalPanelThickness = clamp(
    normalizeAngledTwoPlanesPreviewThicknessMm(verticalPanelThicknessMm) * ANGLED_TWO_PLANES_MM_TO_SCENE,
    ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN * ANGLED_TWO_PLANES_MM_TO_SCENE,
    ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX * ANGLED_TWO_PLANES_MM_TO_SCENE,
  );
  const horizontalPanelThickness = clamp(
    normalizeAngledTwoPlanesPreviewThicknessMm(horizontalPanelThicknessMm) * ANGLED_TWO_PLANES_MM_TO_SCENE,
    ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN * ANGLED_TWO_PLANES_MM_TO_SCENE,
    ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX * ANGLED_TWO_PLANES_MM_TO_SCENE,
  );
  const { verticalPanel, horizontalPanel } = buildAngledTwoPlanesPanelModels(
    panelDimensions,
    verticalPanelThickness,
    horizontalPanelThickness,
  );

  return sourceHoles
    .map((hole, index) => {
      const panelKey = resolveAngledTwoPlanesPanelKey(hole);
      const panel = panelKey === "horizontal_panel"
        ? horizontalPanel
        : panelKey === "vertical_panel"
          ? verticalPanel
          : null;

      if (!panel) {
        if (import.meta.env?.DEV) {
          console.warn("Skipping angled_two_planes hole with unresolved panel key", {
            holeId: hole?.id ?? index + 1,
            panelKey: hole?.panelKey || hole?.panel_key || hole?.target_panel || "",
          });
        }
        return null;
      }

      const numericDiameter = readNumber(hole, ["diameter_mm", "diameter"]);
      const depthValue = readNumber(hole, ["depth_mm", "depth"]);
      const hasDepth = Number.isFinite(depthValue) && depthValue > 0;
      const holeRadius = clamp(
        Number.isFinite(numericDiameter) ? numericDiameter * 0.005 : 0.052,
        0.045,
        0.1,
      );
      const holeLength = hasDepth
        ? Math.abs(depthValue) * ANGLED_TWO_PLANES_MM_TO_SCENE
        : panelKey === "horizontal_panel"
          ? horizontalPanelThickness
          : verticalPanelThickness;
      const surfacePoint = panel.pointToWorld(hole);
      const inwardNormal = panel.inwardNormal;
      const panelThickness = panelKey === "horizontal_panel" ? horizontalPanelThickness : verticalPanelThickness;
      const panelCenter = [
        surfacePoint[0] + inwardNormal[0] * (panelThickness / 2),
        surfacePoint[1] + inwardNormal[1] * (panelThickness / 2),
        surfacePoint[2] + inwardNormal[2] * (panelThickness / 2),
      ];
      const inwardNormalVector = new Vector3(...inwardNormal);
      const directionOffset = holeLength * 0.5;
      const endPoint = [
        surfacePoint[0] + inwardNormalVector.x * holeLength,
        surfacePoint[1] + inwardNormalVector.y * holeLength,
        surfacePoint[2] + inwardNormalVector.z * holeLength,
      ];
      const centerPosition = [
        surfacePoint[0] + inwardNormalVector.x * directionOffset,
        surfacePoint[1] + inwardNormalVector.y * directionOffset,
        surfacePoint[2] + inwardNormalVector.z * directionOffset,
      ];

      return {
        axis: panelKey === "horizontal_panel" ? "y" : "x",
        centerPosition,
        depth: Number.isFinite(depthValue) ? depthValue : null,
        depth_mm: Number.isFinite(depthValue) ? depthValue : null,
        diameter: Number.isFinite(numericDiameter) ? numericDiameter : null,
        diameter_mm: Number.isFinite(numericDiameter) ? numericDiameter : null,
        directionVector: inwardNormal,
        endPoint,
        hasDepth,
        holeCenter: centerPosition,
        holeLength,
        holeRadius,
        id: hole?.id ?? index + 1,
        inwardNormal,
        isAngledTwoPlanes: true,
        isFaceToEdge: false,
        isSurfaceMount: false,
        isThrough: !hasDepth,
        label: String(hole?.label || `P${index + 1}`),
        onSurfacePosition: surfacePoint,
        operation: String(hole?.operation || "").trim() || "drill",
        panelCenter,
        panelKey,
        panelLabel: panel.label,
        panelModel: panel,
        point: hole || null,
        pointToWorld: panel.pointToWorld,
        quaternion: getAngledTwoPlanesHoleQuaternion(inwardNormal),
        rotation: panelKey === "horizontal_panel" ? [0, 0, 0] : [0, 0, Math.PI / 2],
        side: String(hole?.side || "").trim() || "front",
        sideDirection: panelKey === "horizontal_panel"
          ? { axis: "y", sign: -1 }
          : { axis: "x", sign: -1 },
        sourcePanelKey: String(hole?.panelKey || hole?.panel_key || hole?.panelId || hole?.panel_id || "").trim(),
        surfacePoint,
        targetPanel: panelKey,
        targetSide: "inner_face",
        targetSurface: "plane",
      };
    })
    .filter(Boolean);
}
