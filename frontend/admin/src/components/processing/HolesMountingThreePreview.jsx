import { memo, useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { BoxGeometry, CanvasTexture, DoubleSide, EdgesGeometry, Float32BufferAttribute, LinearFilter, MOUSE, Quaternion, Vector3 } from "three";

import {
  buildSurfaceMountThreePreviewHoleVolumes,
  buildSurfaceMountThreePreviewLayout,
  buildSurfaceMountThreePreviewLabelPlacements,
  getSurfaceMountPanelContourStyle,
  normalizeSurfaceMountPreviewThicknessMm,
  SURFACE_MOUNT_PREVIEW_THICKNESS_MM_DEFAULT,
  SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MAX,
  SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MIN,
  shouldRenderSurfaceMountPanelContour,
} from "../../surfaceMountThreePreview.js";
import {
  ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
  ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX,
  ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN,
  buildAngledTwoPlanesThreePreviewHoleVolumes,
  buildAngledTwoPlanesThreePreviewLabelPlacements,
  buildAngledTwoPlanesThreePreviewLayout,
  normalizeAngledTwoPlanesPreviewThicknessMm,
  shouldRenderAngledTwoPlanesThreePreview,
} from "../../angledTwoPlanesThreePreview.js";

  function normalizeHoleWorkspaceMountingVariantKey(key) {
    const allowedVariants = new Set([
      "surface_mount",
      "angled_two_planes",
      "face_to_edge",
      "edge_to_edge",
      "drawer_slides",
    ]);

    return allowedVariants.has(key) ? key : "surface_mount";
  }

  function getHoleWorkspaceThreePreviewLayout(variantKey, surfaceMountPreviewThicknessMm = SURFACE_MOUNT_PREVIEW_THICKNESS_MM_DEFAULT) {
    switch (variantKey) {
      case "angled_two_planes":
        return {
          camera: [4.7, 3.0, 6.2],
          label: "Дві площини під кутом",
          markerPlane: { axis: "z", origin: [-0.92, 0.02, 0], spanU: 1.1, spanV: 1.78 },
          panels: [
            {
              args: [0.24, 2.05, 1.3],
              color: "#d7edf0",
              opacity: 0.44,
              position: [-0.95, 0.04, 0],
              rotation: [0, 0, 0],
            },
            {
              args: [0.24, 1.55, 1.18],
              color: "#e4f2e8",
              opacity: 0.5,
              position: [0.65, -0.28, 0.1],
              rotation: [0, 0, -0.72],
            },
          ],
          subtitle: "Панель A → панель B · angled_two_planes",
        };
      case "face_to_edge":
        return {
          camera: [3.55, 2.35, 4.1],
          label: "Пласть → торець",
          markerPlane: { axis: "z", origin: [0, 0, 0], spanU: 1.22, spanV: 1.72 },
          panels: [
            {
              args: [0.28, 2.18, 1.34],
              color: "#b9ffb9",
              opacity: 0.28,
              position: [-0.14, 0, 0],
              rotation: [0, 0, 0],
            },
            {
              args: [1.96, 0.28, 1.08],
              color: "#b9ffb9",
              opacity: 0.28,
              position: [0.98, -0.14, 0],
              rotation: [0, 0, 0],
            },
          ],
          subtitle: "Пласть панелі → торець панелі · face_to_edge",
        };
      case "edge_to_edge":
        return {
          camera: [4.9, 2.8, 6.1],
          label: "Торець до торця",
          markerPlane: { axis: "z", origin: [-0.82, 0.03, 0], spanU: 1.0, spanV: 1.62 },
          panels: [
            {
              args: [0.26, 1.92, 1.28],
              color: "#dbeaf0",
              opacity: 0.44,
              position: [-0.95, 0.03, 0],
              rotation: [0, 0, 0],
            },
            {
              args: [0.26, 1.92, 1.28],
              color: "#e3f0e3",
              opacity: 0.46,
              position: [0.84, 0.03, 0.02],
              rotation: [0, 0, 0],
            },
          ],
          subtitle: "Торець панелі A → торець панелі B · edge_to_edge",
        };
      case "drawer_slides":
        return {
          camera: [5.1, 2.9, 6.6],
          label: "Напрямні шухляди",
          markerPlane: { axis: "z", origin: [-0.98, 0.02, 0], spanU: 1.16, spanV: 1.8 },
          panels: [
            {
              args: [0.24, 2.15, 1.22],
              color: "#d7e8f0",
              opacity: 0.42,
              position: [-1.2, 0.04, 0],
              rotation: [0, 0, 0],
            },
            {
              args: [0.24, 2.15, 1.22],
              color: "#dfe7ef",
              opacity: 0.42,
              position: [1.2, 0.04, 0],
              rotation: [0, 0, 0],
            },
            {
              args: [2.0, 0.18, 0.26],
              color: "#8ea0ad",
              opacity: 0.92,
              position: [0, -0.03, 0],
              rotation: [0, 0, 0],
            },
          ],
          subtitle: "Боковини та напрямна · drawer_slides",
        };
      case "surface_mount":
      default:
        return buildSurfaceMountThreePreviewLayout(surfaceMountPreviewThicknessMm);
    }
  }

  function normalizeThreePreviewHoleRange(values, fallbackValue) {
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

  function getSafeHolePointLabel(value, fallback) {
    const raw = String(value || "").trim();

    if (!raw) {
      return fallback;
    }

    return /^[A-Za-z0-9 _.\-#]+$/.test(raw) ? raw : fallback;
  }

  function inferFaceToEdgePointLocation(point) {
    const sourcePoint = point?.source && typeof point.source === "object" ? point.source : null;
    const targetPanel = String(point?.target_panel || sourcePoint?.target_panel || "").trim();
    const targetSurface = String(point?.target_surface || sourcePoint?.target_surface || "").trim();
    const targetSide = String(point?.target_side || sourcePoint?.target_side || "").trim();
    const panelKey = String(point?.panelKey || point?.panel_key || point?.panelId || point?.panel_id || "").trim();
    const legacySide = String(point?.side || "").trim().toLowerCase();

    let resolvedTargetPanel = targetPanel;
    let resolvedTargetSurface = targetSurface;
    let resolvedTargetSide = targetSide;
    let needsClarification = false;

    if (!resolvedTargetPanel) {
      if (["edge_near_vertical", "edge_near_vertical_panel", "edge_far_vertical", "top_edge", "bottom_edge"].includes(targetSide)) {
        resolvedTargetPanel = "horizontal_panel";
      } else if (["inner_face", "outer_face", "top_face", "bottom_face", "needs_clarification"].includes(targetSide)) {
        resolvedTargetPanel = "vertical_panel";
      }

      if (!resolvedTargetPanel && ["edge", "left", "right", "top", "bottom"].includes(legacySide)) {
        resolvedTargetPanel = "horizontal_panel";
      } else if (!resolvedTargetPanel && legacySide) {
        resolvedTargetPanel = "vertical_panel";
      }
    }

    if (!resolvedTargetSurface) {
      if (["edge_near_vertical", "edge_near_vertical_panel", "edge_far_vertical", "top_edge", "bottom_edge"].includes(targetSide)) {
        resolvedTargetSurface = "edge";
      } else if (["inner_face", "outer_face", "top_face", "bottom_face", "needs_clarification"].includes(targetSide)) {
        resolvedTargetSurface = "plane";
      }

      if (panelKey === "horizontal_panel") {
        resolvedTargetPanel = "horizontal_panel";
      } else if (panelKey === "vertical_panel") {
        resolvedTargetPanel = "vertical_panel";
      } else if (["edge", "left", "right", "top", "bottom"].includes(legacySide)) {
        resolvedTargetPanel = "horizontal_panel";
      } else if (legacySide) {
        resolvedTargetPanel = "vertical_panel";
      }
    }

    if (!resolvedTargetSurface) {
      if (resolvedTargetPanel === "horizontal_panel" && ["edge", "left", "right"].includes(legacySide)) {
        resolvedTargetSurface = "edge";
      } else if (resolvedTargetPanel === "vertical_panel" && ["front", "back", "face", "inner", "outer"].includes(legacySide)) {
        resolvedTargetSurface = "plane";
      } else if (resolvedTargetPanel) {
        resolvedTargetSurface = resolvedTargetPanel === "horizontal_panel" ? "edge" : "plane";
      }
    }

    if (!resolvedTargetSide) {
      if (resolvedTargetPanel === "horizontal_panel" && resolvedTargetSurface === "edge" && ["edge_near_vertical", "edge_near_vertical_panel", "edge_far_vertical"].includes(targetSide)) {
        resolvedTargetSide = targetSide;
      } else if (resolvedTargetPanel === "vertical_panel" && resolvedTargetSurface === "plane" && ["inner_face", "outer_face"].includes(targetSide)) {
        resolvedTargetSide = targetSide;
      } else if (resolvedTargetPanel === "horizontal_panel" && resolvedTargetSurface === "plane" && ["top_face", "bottom_face"].includes(targetSide)) {
        resolvedTargetSide = targetSide;
      }

      if (resolvedTargetPanel === "vertical_panel" && resolvedTargetSurface === "plane") {
        resolvedTargetSide = legacySide === "back" || legacySide === "outer" ? "outer_face" : "inner_face";
      } else if (resolvedTargetPanel === "horizontal_panel" && resolvedTargetSurface === "edge") {
        if (["edge_near_vertical", "edge_near_vertical_panel", "edge_far_vertical", "edge_far_vertical_panel"].includes(legacySide)) {
          resolvedTargetSide = legacySide;
        } else {
          resolvedTargetSide = "edge_near_vertical";
        }
      } else if (resolvedTargetPanel === "horizontal_panel" && resolvedTargetSurface === "plane") {
        resolvedTargetSide = legacySide === "bottom" ? "bottom_face" : "top_face";
      }
    }

    if (!resolvedTargetPanel || !resolvedTargetSurface || !resolvedTargetSide) {
      needsClarification = true;
    }

    return {
      needsClarification,
      targetPanel: resolvedTargetPanel || "vertical_panel",
      targetSide: resolvedTargetSide || "needs_clarification",
      targetSurface: resolvedTargetSurface || "plane",
    };
  }

  function readHolePreviewNumber(hole, keys, fallback = null) {
    for (const key of keys) {
      const parsed = Number(String(hole?.[key] ?? "").replace(",", "."));

      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }

    return fallback;
  }

  function formatPreviewNumber(value) {
    const parsed = Number(value);

    if (!Number.isFinite(parsed)) {
      return "n/a";
    }

    return parsed.toFixed(3).replace(/\.?0+$/, "");
  }

  function formatPreviewVector(values) {
    if (!Array.isArray(values)) {
      return "n/a";
    }

    return `[${values.map((value) => formatPreviewNumber(value)).join(", ")}]`;
  }

  function buildThreePreviewMarkerPositions(holes, markerPlane) {
    const sourceHoles = Array.isArray(holes) ? holes : [];
    const readHoleNumber = (hole, keys) => {
      for (const key of keys) {
        const parsed = Number(String(hole?.[key] ?? "").replace(",", "."));

        if (Number.isFinite(parsed)) {
          return parsed;
        }
      }

      return null;
    };
    const xRange = normalizeThreePreviewHoleRange(
      sourceHoles.map((hole) => readHoleNumber(hole, ["x", "x_mm"])),
      0,
    );
    const yRange = normalizeThreePreviewHoleRange(
      sourceHoles.map((hole) => readHoleNumber(hole, ["y", "y_mm"])),
      0,
    );

    return sourceHoles.map((hole, index) => {
      const numericX = readHoleNumber(hole, ["x", "x_mm"]);
      const numericY = readHoleNumber(hole, ["y", "y_mm"]);
      const numericDiameter = readHoleNumber(hole, ["diameter", "diameter_mm"]);
      const depthValue = readHoleNumber(hole, ["depth", "depth_mm"]);
      const ratioX = Number.isFinite(numericX)
        ? (numericX - xRange.min) / xRange.span
        : (index % 3) / 2;
      const ratioY = Number.isFinite(numericY)
        ? (numericY - yRange.min) / yRange.span
        : Math.floor(index / 3) / 2;
      const markerRadius = Math.max(0.04, Math.min(0.08, numericDiameter ? numericDiameter / 150 : 0.05));
      const offset = Number.isFinite(depthValue) ? Math.min(depthValue / 1000, 0.06) : 0.02;
      const hasDepth = Number.isFinite(depthValue) && depthValue > 0;

      return {
        id: hole?.id ?? index + 1,
        label: getSafeHolePointLabel(hole?.label, `P${index + 1}`),
        diameter: Number.isFinite(numericDiameter) ? numericDiameter : null,
        depth: hasDepth ? depthValue : null,
        hasDepth,
        markerRadius,
        onSurfacePosition:
          markerPlane.axis === "z"
            ? [
                markerPlane.origin[0] + offset,
                markerPlane.origin[1] + (0.5 - ratioY) * markerPlane.spanV,
                markerPlane.origin[2] + (ratioX - 0.5) * markerPlane.spanU,
              ]
            : [
                markerPlane.origin[0] + (ratioX - 0.5) * markerPlane.spanU,
                markerPlane.origin[1] + (0.5 - ratioY) * markerPlane.spanV,
                markerPlane.origin[2] + offset,
              ],
        operation: String(hole?.operation || "").trim() || "drill",
        side: String(hole?.side || "").trim() || "front",
      };
    });
  }

  function getHoleWorkspaceHoleDirection(side) {
    switch (String(side || "").trim()) {
      case "back":
        return { axis: "x", sign: -1 };
      case "face":
        return { axis: "x", sign: 1 };
      case "inner":
        return { axis: "x", sign: -1 };
      case "outer":
        return { axis: "x", sign: 1 };
      case "left":
      case "edge":
        return { axis: "z", sign: -1 };
      case "right":
        return { axis: "z", sign: 1 };
      case "top":
        return { axis: "y", sign: 1 };
      case "bottom":
        return { axis: "y", sign: -1 };
      case "front":
      default:
        return { axis: "x", sign: 1 };
    }
  }

  function getHoleWorkspaceHoleRotation(axis) {
    switch (axis) {
      case "y":
        return [0, 0, 0];
      case "z":
        return [Math.PI / 2, 0, 0];
      case "x":
      default:
        return [0, 0, Math.PI / 2];
    }
  }

  function markerPlaneThickness(panels, axis) {
    const panel = Array.isArray(panels) ? panels[0] : null;

    if (!panel || !Array.isArray(panel.args)) {
      return 0.28;
    }

    return Math.max(0.24, Number(panel.args[0]) || 0.28);
  }

function getFaceToEdgeHolePlacement(layout, hole, index) {
  const sourceHole = hole?.source && typeof hole.source === "object" ? hole.source : hole;
  const location = inferFaceToEdgePointLocation(sourceHole);
  const panelA = Array.isArray(layout?.panels) ? layout.panels[0] || null : null;
  const panelB = Array.isArray(layout?.panels) ? layout.panels[1] || null : null;

  if (!panelA || !panelB) {
    return null;
  }

  const panelAThickness = Number(panelA?.args?.[0]) || 0.28;
  const panelAHeight = Number(panelA?.args?.[1]) || 2.18;
  const panelBWidth = Number(panelB?.args?.[0]) || 1.96;
  const panelBThickness = Number(panelB?.args?.[1]) || 0.28;
  const originX = (Number(panelA?.position?.[0]) || 0) + panelAThickness / 2;
  const originY = Number(panelB?.position?.[1]) || 0;
  const originZ = ((Number(panelA?.position?.[2]) || 0) + (Number(panelB?.position?.[2]) || 0)) / 2;
  const mmToScene = 0.01;
  const diameterValue = readHolePreviewNumber(sourceHole, ["diameter", "diameter_mm"], 8);
  const depthValue = readHolePreviewNumber(sourceHole, ["depth", "depth_mm"], null);
  const xOffset = readHolePreviewNumber(sourceHole, ["x", "x_mm"], 0) * mmToScene;
  const yOffset = readHolePreviewNumber(sourceHole, ["y", "y_mm"], 0) * mmToScene;
  const zOffset = readHolePreviewNumber(sourceHole, ["z", "z_mm"], 0) * mmToScene;
  const isHorizontalEdge = location.targetPanel === "horizontal_panel" && location.targetSurface === "edge";
  const isHorizontalPlane = location.targetPanel === "horizontal_panel" && location.targetSurface === "plane";
  const isVerticalEdge = location.targetPanel === "vertical_panel" && location.targetSurface === "edge";
  const holeRadius = Math.max(0.028, Math.min(0.08, Number.isFinite(diameterValue) ? diameterValue * 0.005 : 0.04));
  const holeLength = isHorizontalEdge
    ? Math.max(0.18, Math.min(0.74, Number.isFinite(depthValue) ? Math.abs(depthValue) * mmToScene : 0.32))
    : Math.max(0.18, Math.min(0.62, Number.isFinite(depthValue) ? Math.abs(depthValue) * mmToScene : panelAThickness));
  const sourcePanelKey = String(sourceHole?.panelKey || sourceHole?.panel_key || sourceHole?.panelId || sourceHole?.panel_id || "").trim();
  const sourceSurface = String(sourceHole?.surface || sourceHole?.target_surface || sourceHole?.targetSurface || "").trim();
  const sourceSide = String(sourceHole?.side || "").trim();
  const depthScene = Number.isFinite(depthValue) ? Math.abs(depthValue) * mmToScene : holeLength;
  const placementFunctionName = "getFaceToEdgeHolePlacement";
  const renderPath = "holeVolumes.map -> marker.isFaceToEdge ? group -> <cylinderGeometry/> : <mesh><cylinderGeometry/></mesh>";

  if (isHorizontalEdge) {
    const edgeX =
      location.targetSide === "edge_far_vertical"
        ? (Number(panelB?.position?.[0]) || 0) + panelBWidth / 2
        : (Number(panelB?.position?.[0]) || 0) - panelBWidth / 2;
    const directionSign = location.targetSide === "edge_far_vertical" ? -1 : 1;
    const previewInset = 0.002;
    const startPosition = [edgeX + xOffset, originY + yOffset, originZ + zOffset];
    const directionVector = [directionSign, 0, 0];
    const endPosition = [edgeX + directionSign * depthScene + xOffset, originY + yOffset, originZ + zOffset];

    return {
      id: sourceHole?.id ?? hole?.id ?? index,
      label: String(sourceHole?.label ?? hole?.label ?? `P${index + 1}`),
      axis: "x",
      centerPosition: [
        edgeX + directionSign * (holeLength * 0.5 + previewInset) + xOffset,
        originY + yOffset,
        originZ + zOffset,
      ],
      holeLength,
      holeRadius,
      isFaceToEdge: true,
      isThrough: !Number.isFinite(depthValue) || depthValue <= 0,
      location,
      orderIndex: index,
      placementFunctionName,
      renderPath,
      sourcePanelKey,
      sourceSide,
      sourceSurface,
      debugDepth: depthValue,
      debugDirectionVector: directionVector,
      debugEndPosition: endPosition,
      debugStartPosition: startPosition,
      rotation: [0, 0, -Math.PI / 2],
      targetPanel: location.targetPanel,
      targetSide: location.targetSide,
      targetSurface: location.targetSurface,
    };
  }

  if (isHorizontalPlane) {
    const isBottomFace = location.targetSide === "bottom_face";
    const startY = isBottomFace
      ? (Number(panelB?.position?.[1]) || 0) - panelBThickness / 2
      : (Number(panelB?.position?.[1]) || 0) + panelBThickness / 2;
    const directionSign = isBottomFace ? 1 : -1;
    const startPosition = [originX + xOffset, startY + yOffset, originZ + zOffset];
    const directionVector = [0, directionSign, 0];
    const endPosition = [originX + xOffset, startY + directionSign * depthScene + yOffset, originZ + zOffset];

    return {
      id: sourceHole?.id ?? hole?.id ?? index,
      label: String(sourceHole?.label ?? hole?.label ?? `P${index + 1}`),
      axis: "y",
      centerPosition: [originX + xOffset, startY + directionSign * holeLength * 0.5 + yOffset, originZ + zOffset],
      holeLength,
      holeRadius,
      isFaceToEdge: true,
      isThrough: !Number.isFinite(depthValue) || depthValue <= 0,
      location,
      orderIndex: index,
      placementFunctionName,
      renderPath,
      sourcePanelKey,
      sourceSide,
      sourceSurface,
      debugDepth: depthValue,
      debugDirectionVector: directionVector,
      debugEndPosition: endPosition,
      debugStartPosition: startPosition,
      rotation: [0, 0, 0],
      targetPanel: location.targetPanel,
      targetSide: location.targetSide,
      targetSurface: location.targetSurface,
    };
  }

  if (isVerticalEdge) {
    const isTopEdge = location.targetSide === "top_edge";
    const startY = isTopEdge
      ? (Number(panelA?.position?.[1]) || 0) + panelAHeight / 2
      : (Number(panelA?.position?.[1]) || 0) - panelAHeight / 2;
    const directionSign = isTopEdge ? -1 : 1;
    const startPosition = [originX + xOffset, startY + yOffset, originZ + zOffset];
    const directionVector = [0, directionSign, 0];
    const endPosition = [originX + xOffset, startY + directionSign * depthScene + yOffset, originZ + zOffset];

    return {
      id: sourceHole?.id ?? hole?.id ?? index,
      label: String(sourceHole?.label ?? hole?.label ?? `P${index + 1}`),
      axis: "y",
      centerPosition: [originX + xOffset, startY + directionSign * holeLength * 0.5 + yOffset, originZ + zOffset],
      holeLength,
      holeRadius,
      isFaceToEdge: true,
      isThrough: !Number.isFinite(depthValue) || depthValue <= 0,
      location,
      orderIndex: index,
      placementFunctionName,
      renderPath,
      sourcePanelKey,
      sourceSide,
      sourceSurface,
      debugDepth: depthValue,
      debugDirectionVector: directionVector,
      debugEndPosition: endPosition,
      debugStartPosition: startPosition,
      rotation: [0, 0, 0],
      targetPanel: location.targetPanel,
      targetSide: location.targetSide,
      targetSurface: location.targetSurface,
    };
  }

  const isOuterFace = location.targetSide === "outer_face";
  const startX = isOuterFace
    ? (Number(panelA?.position?.[0]) || 0) - panelAThickness / 2
    : originX;
  const directionSign = isOuterFace ? 1 : -1;
  const startPosition = [startX + xOffset, originY + yOffset, originZ + zOffset];
  const directionVector = [directionSign, 0, 0];
  const endPosition = [startX + directionSign * depthScene + xOffset, originY + yOffset, originZ + zOffset];

  return {
    id: sourceHole?.id ?? hole?.id ?? index,
    label: String(sourceHole?.label ?? hole?.label ?? `P${index + 1}`),
    axis: "x",
    centerPosition: [startX + directionSign * holeLength * 0.5 + xOffset, originY + yOffset, originZ + zOffset],
    holeLength,
    holeRadius,
    isFaceToEdge: true,
    isThrough: !Number.isFinite(depthValue) || depthValue <= 0,
    location,
    orderIndex: index,
    placementFunctionName,
    renderPath,
    sourcePanelKey,
    sourceSide,
    sourceSurface,
    debugDepth: depthValue,
    debugDirectionVector: directionVector,
    debugEndPosition: endPosition,
    debugStartPosition: startPosition,
    rotation: [0, 0, Math.PI / 2],
    targetPanel: location.targetPanel,
    targetSide: location.targetSide,
    targetSurface: location.targetSurface,
  };
}

function SurfaceMountPanelContour({ args }) {
  const contourStyle = useMemo(() => getSurfaceMountPanelContourStyle(), []);
  const contourGeometry = useMemo(
    () => new EdgesGeometry(new BoxGeometry(...args)),
    [args],
  );

  useEffect(() => () => {
    contourGeometry.dispose();
  }, [contourGeometry]);

  return (
    <lineSegments geometry={contourGeometry} renderOrder={3}>
      <lineBasicMaterial
        color={contourStyle.color}
        depthTest={false}
        depthWrite={false}
        transparent
        opacity={contourStyle.opacity}
      />
    </lineSegments>
  );
}

function buildSurfaceMountHoleQuaternion(inwardNormal) {
  const direction = new Vector3(
    Number(inwardNormal?.[0]) || 0,
    Number(inwardNormal?.[1]) || 0,
    Number(inwardNormal?.[2]) || 0,
  );

  if (direction.lengthSq() === 0) {
    return null;
  }

  return new Quaternion().setFromUnitVectors(new Vector3(0, 1, 0), direction.normalize());
}

export default function HolesMountingThreePreview({
  holes,
  mountingVariantKey,
  hoveredHoleId,
  selectedHoleId,
  onHoverHole,
  onLeaveHole,
  onSelectHole,
  renderSchematicPreview,
}) {
        const [surfaceMountPreviewThicknessMm, setSurfaceMountPreviewThicknessMm] = useState(
          SURFACE_MOUNT_PREVIEW_THICKNESS_MM_DEFAULT,
        );
        const [angledTwoPlanesVerticalPreviewThicknessMm, setAngledTwoPlanesVerticalPreviewThicknessMm] = useState(
          ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
        );
        const [angledTwoPlanesHorizontalPreviewThicknessMm, setAngledTwoPlanesHorizontalPreviewThicknessMm] = useState(
          ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_DEFAULT,
        );
        const normalizedSurfaceMountPreviewThicknessMm = normalizeSurfaceMountPreviewThicknessMm(
          surfaceMountPreviewThicknessMm,
        );
        const normalizedAngledTwoPlanesVerticalPreviewThicknessMm = normalizeAngledTwoPlanesPreviewThicknessMm(
          angledTwoPlanesVerticalPreviewThicknessMm,
        );
        const normalizedAngledTwoPlanesHorizontalPreviewThicknessMm = normalizeAngledTwoPlanesPreviewThicknessMm(
          angledTwoPlanesHorizontalPreviewThicknessMm,
        );
        const normalizedVariantKey = normalizeHoleWorkspaceMountingVariantKey(mountingVariantKey);
        const isSurfaceMountPreview = normalizedVariantKey === "surface_mount";
        const isAngledTwoPlanesPreview = normalizedVariantKey === "angled_two_planes";
        const isFaceToEdgePreview = normalizedVariantKey === "face_to_edge" || isSurfaceMountPreview;
        const isCompactThreePreview = isFaceToEdgePreview || isAngledTwoPlanesPreview;
        const baseLayout = useMemo(
          () => getHoleWorkspaceThreePreviewLayout(mountingVariantKey, normalizedSurfaceMountPreviewThicknessMm),
          [mountingVariantKey, normalizedSurfaceMountPreviewThicknessMm],
        );
        const markerPositions = useMemo(
          () => buildThreePreviewMarkerPositions(holes, baseLayout.markerPlane),
          [holes, baseLayout.markerPlane],
        );
        const holeVolumes = useMemo(
          () => {
            const isFaceToEdge = normalizedVariantKey === "face_to_edge";
            const isSurfaceMountPreview = normalizedVariantKey === "surface_mount";
            const isAngledTwoPlanesPreview = normalizedVariantKey === "angled_two_planes";

            if (isFaceToEdge) {
              const sortedHoles = [...(Array.isArray(holes) ? holes : [])].sort((left, right) => {
                const leftOrder = Number(left?.order_index ?? left?.orderIndex ?? 0);
                const rightOrder = Number(right?.order_index ?? right?.orderIndex ?? 0);
                if (leftOrder !== rightOrder) {
                  return leftOrder - rightOrder;
                }

                return Number(left?.id ?? 0) - Number(right?.id ?? 0);
              });

              return sortedHoles
                .map((hole, index) => getFaceToEdgeHolePlacement(baseLayout, hole, index))
                .filter(Boolean);
            }

            if (isSurfaceMountPreview) {
              return buildSurfaceMountThreePreviewHoleVolumes(holes, baseLayout);
            }

            if (isAngledTwoPlanesPreview) {
              return buildAngledTwoPlanesThreePreviewHoleVolumes(
                holes,
                normalizedAngledTwoPlanesVerticalPreviewThicknessMm,
                normalizedAngledTwoPlanesHorizontalPreviewThicknessMm,
              );
            }

            return markerPositions.map((marker) => {
              const sideDirection = getHoleWorkspaceHoleDirection(marker.side);
              const holeRadius = Math.max(0.045, Math.min(0.1, (marker.diameter || 0) / 110 || 0.052));
              const panelThickness = markerPlaneThickness(baseLayout.panels, sideDirection.axis);
              const holeLength = marker.hasDepth
                ? Math.max(0.18, Math.min(0.62, (marker.depth || 0) / 120 || 0.22))
                : Math.max(0.42, panelThickness);
              const visibleLength = holeLength;
              const surfaceMountQuaternion = marker.isSurfaceMount
                ? buildSurfaceMountHoleQuaternion(marker.inwardNormal)
                : null;
              const centerPosition = [
                marker.onSurfacePosition[0] +
                  (sideDirection.axis === "x" ? sideDirection.sign * visibleLength * 0.5 : 0),
                marker.onSurfacePosition[1] +
                  (sideDirection.axis === "y" ? sideDirection.sign * visibleLength * 0.5 : 0),
                marker.onSurfacePosition[2] +
                  (sideDirection.axis === "z" ? sideDirection.sign * visibleLength * 0.5 : 0),
              ];

              return {
                ...marker,
                centerPosition,
                holeLength: visibleLength,
                holeRadius,
                quaternion: surfaceMountQuaternion || undefined,
                rotation: getHoleWorkspaceHoleRotation(sideDirection.axis),
                isThrough: !marker.hasDepth,
                sideDirection,
                isFaceToEdge: false,
              };
            });
          },
          [
            baseLayout.panels,
            holes,
            markerPositions,
            normalizedAngledTwoPlanesHorizontalPreviewThicknessMm,
            normalizedAngledTwoPlanesVerticalPreviewThicknessMm,
            normalizedVariantKey,
          ],
        );
        const layout = useMemo(
          () => {
            if (isSurfaceMountPreview) {
              return buildSurfaceMountThreePreviewLayout(normalizedSurfaceMountPreviewThicknessMm, holeVolumes);
            }

            if (isAngledTwoPlanesPreview) {
              return buildAngledTwoPlanesThreePreviewLayout(
                normalizedAngledTwoPlanesVerticalPreviewThicknessMm,
                normalizedAngledTwoPlanesHorizontalPreviewThicknessMm,
                holes,
              );
            }

            return baseLayout;
          },
          [
            baseLayout,
            holeVolumes,
            holes,
            isAngledTwoPlanesPreview,
            isSurfaceMountPreview,
            normalizedAngledTwoPlanesHorizontalPreviewThicknessMm,
            normalizedAngledTwoPlanesVerticalPreviewThicknessMm,
            normalizedSurfaceMountPreviewThicknessMm,
          ],
        );
        const previewPanels = isAngledTwoPlanesPreview
          ? [layout.verticalPanel, layout.horizontalPanel].filter(Boolean)
          : layout.panels;
        const previewOrigin = layout.sceneOrigin || layout.markerPlane.origin;
        const shouldRenderSurfaceMountContour =
          shouldRenderSurfaceMountPanelContour(mountingVariantKey) || isAngledTwoPlanesPreview;
        const axisLabelTextures = useMemo(() => {
          const createAxisLabelTexture = (label, color) => {
            const canvas = document.createElement("canvas");
            canvas.width = 128;
            canvas.height = 128;
            const context = canvas.getContext("2d");

            if (!context) {
              return null;
            }

            context.clearRect(0, 0, canvas.width, canvas.height);
            context.fillStyle = color;
            context.font = "700 76px Arial, sans-serif";
            context.textAlign = "center";
            context.textBaseline = "middle";
            context.fillText(label, 64, 68);

            const texture = new CanvasTexture(canvas);
            texture.minFilter = LinearFilter;
            texture.magFilter = LinearFilter;
            texture.needsUpdate = true;
            return texture;
          };

          return {
            x: createAxisLabelTexture("X", "#e200b6"),
            y: createAxisLabelTexture("Y", "#0f766e"),
            z: createAxisLabelTexture("Z", "#2563eb"),
          };
        }, []);
        const holeIdTextures = useMemo(() => {
          const createHoleIdTexture = (label) => {
            const canvas = document.createElement("canvas");
            canvas.width = 128;
            canvas.height = 128;
            const context = canvas.getContext("2d");

            if (!context) {
              return null;
            }

            context.clearRect(0, 0, canvas.width, canvas.height);
            context.fillStyle = "rgba(255, 255, 255, 0.86)";
            context.beginPath();
            context.arc(64, 64, 24, 0, Math.PI * 2);
            context.fill();
            context.strokeStyle = "rgba(15, 23, 42, 0.28)";
            context.lineWidth = 4;
            context.stroke();
            context.fillStyle = "#0f172a";
            context.font = "700 56px Arial, sans-serif";
            context.textAlign = "center";
            context.textBaseline = "middle";
            context.fillText(label, 64, 68);

            const texture = new CanvasTexture(canvas);
            texture.minFilter = LinearFilter;
            texture.magFilter = LinearFilter;
            texture.needsUpdate = true;
            return texture;
          };

          return Object.fromEntries(
            (Array.isArray(holeVolumes) ? holeVolumes : [])
              .filter((hole) => hole?.id !== undefined && hole?.id !== null)
            .map((hole) => [hole.id, createHoleIdTexture(String(hole.id))]),
          );
        }, [holeVolumes]);
        const faceToEdgeHoleIdTextures = useMemo(() => {
          if (!isFaceToEdgePreview) {
            return {};
          }

          const drawRoundedRect = (context, x, y, width, height, radius) => {
            const cornerRadius = Math.max(0, Math.min(radius, width * 0.5, height * 0.5));

            context.beginPath();
            context.moveTo(x + cornerRadius, y);
            context.lineTo(x + width - cornerRadius, y);
            context.arcTo(x + width, y, x + width, y + cornerRadius, cornerRadius);
            context.lineTo(x + width, y + height - cornerRadius);
            context.arcTo(x + width, y + height, x + width - cornerRadius, y + height, cornerRadius);
            context.lineTo(x + cornerRadius, y + height);
            context.arcTo(x, y + height, x, y + height - cornerRadius, cornerRadius);
            context.lineTo(x, y + cornerRadius);
            context.arcTo(x, y, x + cornerRadius, y, cornerRadius);
            context.closePath();
          };

          const createHoleIdTexture = (label, state = "default") => {
            const canvas = document.createElement("canvas");
            canvas.width = 160;
            canvas.height = 96;
            const context = canvas.getContext("2d");

            if (!context) {
              return null;
            }

            const isSelected = state === "selected";
            const isHovered = state === "hover";
            const bgColor = isSelected ? "rgba(219, 234, 254, 0.96)" : isHovered ? "rgba(240, 253, 250, 0.96)" : "rgba(255, 255, 255, 0.9)";
            const strokeColor = isSelected ? "rgba(37, 99, 235, 0.7)" : isHovered ? "rgba(13, 148, 136, 0.55)" : "rgba(15, 23, 42, 0.24)";
            const textColor = isSelected ? "#1d4ed8" : isHovered ? "#0f766e" : "#0f172a";
            const shadowColor = isSelected ? "rgba(37, 99, 235, 0.2)" : isHovered ? "rgba(15, 118, 110, 0.18)" : "rgba(15, 23, 42, 0.12)";

            context.clearRect(0, 0, canvas.width, canvas.height);
            context.save();
            context.shadowColor = shadowColor;
            context.shadowBlur = isSelected ? 12 : isHovered ? 10 : 8;
            context.shadowOffsetY = 2;
            drawRoundedRect(context, 22, 21, 116, 54, 27);
            context.fillStyle = bgColor;
            context.fill();
            context.shadowBlur = 0;
            context.lineWidth = isSelected ? 3.5 : isHovered ? 3 : 2.5;
            context.strokeStyle = strokeColor;
            context.stroke();
            context.restore();
            context.fillStyle = textColor;
            context.font = isSelected ? "800 46px Arial, sans-serif" : isHovered ? "800 44px Arial, sans-serif" : "700 42px Arial, sans-serif";
            context.textAlign = "center";
            context.textBaseline = "middle";
            context.fillText(label, 80, 48);

            const texture = new CanvasTexture(canvas);
            texture.minFilter = LinearFilter;
            texture.magFilter = LinearFilter;
            texture.needsUpdate = true;
            return texture;
          };

          return Object.fromEntries(
            (Array.isArray(holeVolumes) ? holeVolumes : [])
              .filter((hole) => hole?.id !== undefined && hole?.id !== null)
              .map((hole) => {
                const isSelected = String(selectedHoleId) === String(hole.id);
                const isHovered = String(hoveredHoleId) === String(hole.id);
                const state = isSelected ? "selected" : isHovered ? "hover" : "default";
                return [hole.id, createHoleIdTexture(String(hole.id), state)];
              }),
          );
        }, [holeVolumes, hoveredHoleId, isFaceToEdgePreview, selectedHoleId]);
        const faceToEdgeLabelPlacements = useMemo(() => {
          if (!isFaceToEdgePreview) {
            return {};
          }

          return Object.fromEntries(
            (Array.isArray(holeVolumes) ? holeVolumes : [])
              .filter((marker) => marker?.isFaceToEdge)
              .map((marker) => {
                const sideSign = Number(marker?.orderIndex ?? 0) % 2 === 0 ? -1 : 1;
                const lift = Number(marker?.holeRadius || 0) * 3.1 + 0.08;
                const spread = Number(marker?.holeRadius || 0) * 0.95 + 0.06;
                const labelPosition = [0, lift, sideSign * spread];
                const lineEnd = [0, lift * 0.84, sideSign * spread * 0.84];

                return [String(marker?.id), { labelPosition, lineEnd }];
              }),
          );
        }, [holeVolumes, isFaceToEdgePreview]);
        const surfaceMountLabelPlacements = useMemo(() => {
          if (isSurfaceMountPreview) {
            return buildSurfaceMountThreePreviewLabelPlacements(holeVolumes);
          }

          if (isAngledTwoPlanesPreview) {
            return buildAngledTwoPlanesThreePreviewLabelPlacements(holeVolumes);
          }

          return {};
        }, [holeVolumes, isAngledTwoPlanesPreview, isSurfaceMountPreview]);
        const surfaceMountPreviewThicknessMmOptions = [16, 18, 19];
        const axisLabelPresentation = isCompactThreePreview
          ? {
              opacity: 0.96,
              positions: {
                x: [0.36, -0.02, 0],
                y: [0.03, 0.38, 0],
                z: [0.0, -0.04, 0.52],
              },
              scale: 0.13,
            }
          : {
              opacity: 1,
              positions: {
                x: [1.95, 0, 0],
                y: [0, 1.95, 0],
                z: [0, 0, 1.95],
              },
              scale: 0.42,
            };

        const faceToEdgeOrigin = useMemo(() => {
          if (!isFaceToEdgePreview) {
            return null;
          }

          const panelA = Array.isArray(layout.panels) ? layout.panels[0] || null : null;

          if (!panelA) {
            return null;
          }

          const panelAThickness = Number(panelA?.args?.[0]) || 0.28;
          return [
            isSurfaceMountPreview ? 0 : (Number(panelA?.position?.[0]) || 0) + panelAThickness / 2,
            Number(panelA?.position?.[1]) || 0,
            Number(panelA?.position?.[2]) || 0,
          ];
        }, [isFaceToEdgePreview, isSurfaceMountPreview, layout.panels]);

        useEffect(
          () => () => {
            Object.values(axisLabelTextures).forEach((texture) => texture?.dispose?.());
          },
          [axisLabelTextures],
        );
        useEffect(
          () => () => {
            Object.values(holeIdTextures).forEach((texture) => texture?.dispose?.());
          },
          [holeIdTextures],
        );
        useEffect(
          () => () => {
            Object.values(faceToEdgeHoleIdTextures).forEach((texture) => texture?.dispose?.());
          },
          [faceToEdgeHoleIdTextures],
        );

    return (
      <div className="holes-three-preview">
        {isSurfaceMountPreview ? (
          <div
            style={{
              alignItems: "center",
              display: "flex",
              flexWrap: "wrap",
              gap: "0.5rem",
              justifyContent: "space-between",
              marginBottom: "0.5rem",
            }}
          >
            <strong style={{ fontSize: "0.85rem" }}>Товщина панелі для перегляду, мм</strong>
            <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
              {surfaceMountPreviewThicknessMmOptions.map((value) => (
                <button
                  key={value}
                  className={`ghost-button compact-button${normalizedSurfaceMountPreviewThicknessMm === value ? " is-active" : ""}`}
                  onClick={() => setSurfaceMountPreviewThicknessMm(value)}
                  type="button"
                >
                  {value}
                </button>
              ))}
              <input
                aria-label="Товщина панелі для перегляду, мм"
                max={SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MAX}
                min={SURFACE_MOUNT_PREVIEW_THICKNESS_MM_MIN}
                onChange={(event) => setSurfaceMountPreviewThicknessMm(event.target.value)}
                step="1"
                style={{ width: "6rem" }}
                type="number"
                value={normalizedSurfaceMountPreviewThicknessMm}
              />
            </div>
          </div>
        ) : isAngledTwoPlanesPreview ? (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
              gap: "0.5rem",
              marginBottom: "0.5rem",
            }}
          >
            <div
              style={{
                display: "grid",
                gap: "0.35rem",
                minWidth: 0,
              }}
            >
              <strong style={{ fontSize: "0.85rem" }}>Товщина вертикальної панелі, мм</strong>
              <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                {[16, 18, 19].map((value) => (
                  <button
                    key={`angled-vertical-${value}`}
                    className={`ghost-button compact-button${normalizedAngledTwoPlanesVerticalPreviewThicknessMm === value ? " is-active" : ""}`}
                    onClick={() => setAngledTwoPlanesVerticalPreviewThicknessMm(value)}
                    type="button"
                  >
                    {value}
                  </button>
                ))}
                <input
                  aria-label="Товщина вертикальної панелі, мм"
                  max={ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX}
                  min={ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN}
                  onChange={(event) => setAngledTwoPlanesVerticalPreviewThicknessMm(event.target.value)}
                  step="1"
                  style={{ width: "6rem" }}
                  type="number"
                  value={normalizedAngledTwoPlanesVerticalPreviewThicknessMm}
                />
              </div>
            </div>
            <div
              style={{
                display: "grid",
                gap: "0.35rem",
                minWidth: 0,
              }}
            >
              <strong style={{ fontSize: "0.85rem" }}>Товщина горизонтальної панелі, мм</strong>
              <div style={{ alignItems: "center", display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                {[16, 18, 19].map((value) => (
                  <button
                    key={`angled-horizontal-${value}`}
                    className={`ghost-button compact-button${normalizedAngledTwoPlanesHorizontalPreviewThicknessMm === value ? " is-active" : ""}`}
                    onClick={() => setAngledTwoPlanesHorizontalPreviewThicknessMm(value)}
                    type="button"
                  >
                    {value}
                  </button>
                ))}
                <input
                  aria-label="Товщина горизонтальної панелі, мм"
                  max={ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MAX}
                  min={ANGLED_TWO_PLANES_PREVIEW_THICKNESS_MM_MIN}
                  onChange={(event) => setAngledTwoPlanesHorizontalPreviewThicknessMm(event.target.value)}
                  step="1"
                  style={{ width: "6rem" }}
                  type="number"
                  value={normalizedAngledTwoPlanesHorizontalPreviewThicknessMm}
                />
              </div>
            </div>
          </div>
        ) : null}
        <Canvas
          camera={{ fov: 32, position: layout.camera }}
          className="holes-three-preview-canvas"
          dpr={[1, 1.5]}
          onContextMenu={(event) => event.preventDefault()}
          shadows
        >
          <color attach="background" args={["#f7fbfc"]} />
          <fog attach="fog" args={["#f7fbfc", 8, 18]} />
          <ambientLight intensity={1.05} />
          <directionalLight castShadow position={[5.2, 7.2, 8]} intensity={1.45} />
          <directionalLight position={[-4, 2.8, 3]} intensity={0.55} />
          <axesHelper args={isCompactThreePreview ? [0.42] : [1.8]} position={faceToEdgeOrigin || previewOrigin} />
          {isCompactThreePreview ? null : (
            <gridHelper args={[3.1, 10, "#d2dde5", "#e7eef3"]} position={[0, -1.02, 0]} />
          )}
          <group>
            {previewPanels.map((panel, index) => (
              <group
                key={`${mountingVariantKey}-panel-${index}`}
                position={panel.position}
                rotation={panel.rotation}
              >
                <mesh castShadow receiveShadow renderOrder={1}>
                  <boxGeometry args={panel.args} />
                  {isFaceToEdgePreview || isAngledTwoPlanesPreview ? (
                    <meshBasicMaterial
                      color={panel.color}
                      depthWrite={false}
                      opacity={panel.opacity}
                      side={DoubleSide}
                      transparent
                    />
                  ) : (
                    <meshPhysicalMaterial
                      color={panel.color}
                      depthWrite={!isFaceToEdgePreview && !isAngledTwoPlanesPreview}
                      emissive="#c9f3df"
                      emissiveIntensity={0.08}
                      metalness={0.02}
                      opacity={panel.opacity}
                      roughness={0.45}
                      side={DoubleSide}
                      transparent
                      transmission={0.34}
                    />
                  )}
                </mesh>
                {shouldRenderSurfaceMountContour ? <SurfaceMountPanelContour args={panel.args} /> : null}
              </group>
            ))}

            {previewPanels[1] && normalizedVariantKey !== "face_to_edge" && normalizedVariantKey !== "angled_two_planes" ? (
              <mesh
                position={[
                  (previewPanels[0].position[0] + previewPanels[1].position[0]) / 2,
                  (previewPanels[0].position[1] + previewPanels[1].position[1]) / 2,
                  (previewPanels[0].position[2] + previewPanels[1].position[2]) / 2,
                ]}
                rotation={[0, 0, 0]}
              >
                <cylinderGeometry args={[0.04, 0.04, 2.2, 20]} />
                <meshStandardMaterial color="#0f766e" emissive="#1db3a5" emissiveIntensity={0.22} />
              </mesh>
            ) : null}

            {holeVolumes.length ? (
              holeVolumes.map((marker, index) =>
                marker.isFaceToEdge ? (
                  (() => {
                    const isSelected = String(selectedHoleId) === String(marker.id);
                    const isHovered = String(hoveredHoleId) === String(marker.id);
                    const isActive = isSelected || isHovered;
                    const holeColor = isSelected ? "#334155" : isHovered ? "#475569" : "#6b7280";
                    const holeEmissive = isSelected ? "#f8fafc" : isHovered ? "#dbeafe" : "#cfd8e3";
                    const holeOpacity = isSelected ? 0.92 : isHovered ? 0.78 : 0.58;
                    const holeEmissiveIntensity = isSelected ? 0.42 : isHovered ? 0.22 : 0.08;
                    const labelScale = isSelected ? 0.22 : isHovered ? 0.2 : 0.18;
                    const lineColor = isSelected ? "#3b82f6" : isHovered ? "#0f766e" : "#94a3b8";
                    const lineOpacity = isSelected ? 0.92 : isHovered ? 0.88 : 0.72;
                    return (
                  <group
                    key={`face-to-edge-${index}-${String(marker.id ?? marker.point?.client_key ?? "fallback")}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelectHole?.(marker.id);
                    }}
                    onPointerOut={(event) => {
                      event.stopPropagation();
                      onLeaveHole?.();
                    }}
                    onPointerOver={(event) => {
                      event.stopPropagation();
                      onHoverHole?.(marker.id);
                    }}
                    position={marker.centerPosition}
                    renderOrder={2}
                    quaternion={marker.quaternion}
                    rotation={marker.quaternion ? undefined : marker.rotation}
                  >
                    <mesh castShadow renderOrder={2}>
                      <cylinderGeometry args={[marker.holeRadius * (isSelected ? 0.96 : isHovered ? 0.94 : 0.92), marker.holeRadius * (isSelected ? 0.96 : isHovered ? 0.94 : 0.92), marker.holeLength, 24, 1, false]} />
                      <meshStandardMaterial
                        color={holeColor}
                        emissive={holeEmissive}
                        emissiveIntensity={holeEmissiveIntensity}
                        opacity={isSelected ? 0.88 : holeOpacity}
                        transparent
                        depthWrite={false}
                        roughness={isActive ? 0.28 : 0.36}
                        metalness={isActive ? 0.2 : 0.18}
                      />
                    </mesh>
                    {faceToEdgeHoleIdTextures[marker.id] ? (
                      <>
                        <line renderOrder={isActive ? 4 : 3}>
                          <bufferGeometry>
                            <bufferAttribute
                              attach="attributes-position"
                              args={[
                                new Float32Array([
                                  0,
                                  0,
                                  0,
                                  faceToEdgeLabelPlacements[String(marker.id)]?.lineEnd?.[0] ?? 0,
                                  faceToEdgeLabelPlacements[String(marker.id)]?.lineEnd?.[1] ?? marker.holeRadius * 2.4,
                                  faceToEdgeLabelPlacements[String(marker.id)]?.lineEnd?.[2] ?? 0,
                                ]),
                                3,
                              ]}
                            />
                          </bufferGeometry>
                          <lineBasicMaterial color={lineColor} depthTest={false} opacity={lineOpacity} transparent />
                        </line>
                        <sprite
                          position={faceToEdgeLabelPlacements[String(marker.id)]?.labelPosition || [0, marker.holeRadius * 3.1, 0.08]}
                          renderOrder={isActive ? 5 : 4}
                          scale={[labelScale, labelScale, labelScale]}
                        >
                          <spriteMaterial
                            attach="material"
                            depthTest={false}
                            depthWrite={false}
                            map={faceToEdgeHoleIdTextures[marker.id] || undefined}
                            transparent
                          />
                        </sprite>
                      </>
                    ) : null}
                  </group>
                    );
                  })()
                ) : (
                  (() => {
                    const markerPanelKey = String(marker.panelKey || marker.panel_key || marker.target_panel || "").trim();
                    const isHorizontalPanelMarker = markerPanelKey === "horizontal_panel";
                    const shouldAnchorAtSurface = isHorizontalPanelMarker || marker.isAngledTwoPlanes;

                    return (
                      <group
                        key={`marker-${index}-${String(marker.id ?? marker.point?.client_key ?? "fallback")}`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onSelectHole?.(marker.id);
                        }}
                        onPointerOut={(event) => {
                          event.stopPropagation();
                          onLeaveHole?.();
                        }}
                        onPointerOver={(event) => {
                          event.stopPropagation();
                          onHoverHole?.(marker.id);
                        }}
                        position={shouldAnchorAtSurface || marker.isSurfaceMount ? marker.surfacePoint : marker.centerPosition}
                        quaternion={shouldAnchorAtSurface || marker.isSurfaceMount ? marker.quaternion : undefined}
                        userData={{
                          holeId: marker.point?.id ?? marker.id,
                          inwardDirection: marker.inwardNormal,
                          panelKey: markerPanelKey,
                          surfacePoint: marker.surfacePoint,
                        }}
                      >
                        <mesh
                          castShadow
                          position={shouldAnchorAtSurface || marker.isSurfaceMount ? [0, marker.holeLength / 2, 0] : [0, 0, 0]}
                          renderOrder={4}
                          userData={{
                            holeId: marker.point?.id ?? marker.id,
                            panelKey: markerPanelKey,
                          }}
                        >
                          <cylinderGeometry args={[marker.holeRadius, marker.holeRadius, marker.holeLength, 24, 1, false]} />
                          <meshStandardMaterial
                            color={String(selectedHoleId) === String(marker.id) ? "#16a34a" : String(hoveredHoleId) === String(marker.id) ? "#0f766e" : "#6f2bd6"}
                            emissive={String(selectedHoleId) === String(marker.id) ? "#8df0ae" : String(hoveredHoleId) === String(marker.id) ? "#43d0bf" : "#b28fff"}
                            emissiveIntensity={String(selectedHoleId) === String(marker.id) ? 0.42 : 0.22}
                            opacity={0.92}
                            depthWrite={false}
                            transparent
                            roughness={0.22}
                          />
                          {holeIdTextures[marker.id] && (shouldAnchorAtSurface || marker.isSurfaceMount) ? (
                            <>
                              <line renderOrder={3}>
                                <bufferGeometry>
                                  <bufferAttribute
                                    attach="attributes-position"
                                    args={[
                                      new Float32Array([
                                        0,
                                        0,
                                        0,
                                        surfaceMountLabelPlacements[String(marker.id)]?.lineEnd?.[0] ?? 0,
                                        surfaceMountLabelPlacements[String(marker.id)]?.lineEnd?.[1] ?? marker.holeRadius * 2.1 + 0.06,
                                        surfaceMountLabelPlacements[String(marker.id)]?.lineEnd?.[2] ?? Math.max(marker.holeRadius * 1.4 + 0.07, 0.11),
                                      ]),
                                      3,
                                    ]}
                                  />
                                </bufferGeometry>
                                <lineBasicMaterial color="#94a3b8" depthTest={false} opacity={0.82} transparent />
                              </line>
                              <sprite
                                position={
                                  surfaceMountLabelPlacements[String(marker.id)]?.labelPosition || [
                                    0,
                                    marker.holeRadius * 2.1 + 0.06,
                                    Math.max(marker.holeRadius * 1.4 + 0.07, 0.11),
                                  ]
                                }
                                scale={[0.16, 0.16, 0.16]}
                              >
                                <spriteMaterial
                                  attach="material"
                                  depthTest={false}
                                  depthWrite={false}
                                  map={holeIdTextures[marker.id] || undefined}
                                  transparent
                                />
                              </sprite>
                            </>
                          ) : holeIdTextures[marker.id] ? (
                            <sprite
                              position={[0, marker.holeRadius * 1.9, 0]}
                              scale={[0.16, 0.16, 0.16]}
                            >
                              <spriteMaterial
                                attach="material"
                                depthTest={false}
                                depthWrite={false}
                                map={holeIdTextures[marker.id] || undefined}
                                transparent
                              />
                            </sprite>
                          ) : null}
                        </mesh>
                      </group>
                    );
                  })()
                ),
              )
            ) : (
              <mesh position={layout.markerPlane.origin}>
                <sphereGeometry args={[0.06, 20, 20]} />
                <meshStandardMaterial color="#94a3b8" emissive="#cbd5e1" emissiveIntensity={0.12} />
              </mesh>
            )}
            {isFaceToEdgePreview ? (
              <group position={faceToEdgeOrigin || layout.markerPlane.origin}>
                <sprite position={axisLabelPresentation.positions.x} scale={[axisLabelPresentation.scale, axisLabelPresentation.scale, axisLabelPresentation.scale]}>
                  <spriteMaterial attach="material" depthTest={false} depthWrite={false} map={axisLabelTextures.x || undefined} opacity={axisLabelPresentation.opacity} transparent />
                </sprite>
                <sprite position={axisLabelPresentation.positions.y} scale={[axisLabelPresentation.scale, axisLabelPresentation.scale, axisLabelPresentation.scale]}>
                  <spriteMaterial attach="material" depthTest={false} depthWrite={false} map={axisLabelTextures.y || undefined} opacity={axisLabelPresentation.opacity} transparent />
                </sprite>
                <sprite position={axisLabelPresentation.positions.z} scale={[axisLabelPresentation.scale, axisLabelPresentation.scale, axisLabelPresentation.scale]}>
                  <spriteMaterial attach="material" depthTest={false} depthWrite={false} map={axisLabelTextures.z || undefined} opacity={axisLabelPresentation.opacity} transparent />
                </sprite>
              </group>
            ) : (
              <group position={layout.markerPlane.origin}>
                <sprite position={axisLabelPresentation.positions.x} scale={[axisLabelPresentation.scale, axisLabelPresentation.scale, axisLabelPresentation.scale]}>
                  <spriteMaterial attach="material" depthTest={false} depthWrite={false} map={axisLabelTextures.x || undefined} opacity={axisLabelPresentation.opacity} transparent />
                </sprite>
                <sprite position={axisLabelPresentation.positions.y} scale={[axisLabelPresentation.scale, axisLabelPresentation.scale, axisLabelPresentation.scale]}>
                  <spriteMaterial attach="material" depthTest={false} depthWrite={false} map={axisLabelTextures.y || undefined} opacity={axisLabelPresentation.opacity} transparent />
                </sprite>
                <sprite position={axisLabelPresentation.positions.z} scale={[axisLabelPresentation.scale, axisLabelPresentation.scale, axisLabelPresentation.scale]}>
                  <spriteMaterial attach="material" depthTest={false} depthWrite={false} map={axisLabelTextures.z || undefined} opacity={axisLabelPresentation.opacity} transparent />
                </sprite>
              </group>
            )}
          </group>
          <OrbitControls
            enableDamping
            enablePan
            enableRotate
            enableZoom
            maxDistance={11}
            minDistance={4.2}
            maxPolarAngle={Math.PI}
            minPolarAngle={0}
            mouseButtons={{ LEFT: MOUSE.ROTATE, MIDDLE: MOUSE.DOLLY, RIGHT: MOUSE.PAN }}
            target={faceToEdgeOrigin || previewOrigin}
          />
        </Canvas>
        <div className="holes-three-preview-overlay">
          {!markerPositions.length && !isCompactThreePreview ? (
            <div className="holes-three-preview-empty">Отвори ще не додані</div>
          ) : null}
        </div>
      </div>
  );
}
  function renderHoleWorkspaceFittingInfo(fitting, bundleItems = []) {
    const selectedBundleItems = Array.isArray(bundleItems) ? bundleItems : [];

    if (!fitting && !selectedBundleItems.length) {
      return (
        <section className="hole-template-fitting-info is-empty">
          <div className="hole-template-fitting-info-head">
            <strong>{t.holeWorkspaceFittingInfoTitle}</strong>
          </div>
          <div className="empty-state compact-empty-state">
            <span>{t.holeTemplateSelectFitting}</span>
          </div>
        </section>
      );
    }

    return (
      <section className="hole-template-fitting-info">
        <div className="hole-template-fitting-info-head">
          <strong>{t.holeWorkspaceFittingInfoTitle}</strong>
          {selectedBundleItems.length ? (
            <span className="service-tree-badge subtle">
              {selectedBundleItems.length} {t.holeBundleSelectedItemsCount}
            </span>
          ) : null}
        </div>
        {fitting ? (
          (() => {
            const fittingName = String(fitting.name || fitting.code || fitting.article || "").trim();
            const fittingArticle = String(fitting.article || "").trim();
            const fittingImageUrl = String(fitting.image_url || "").trim();
            const fittingTitle = fittingName || t.holeTemplateFitting;
            const fittingSubtitle = [fittingArticle, fitting.code].filter(Boolean).join(" В· ");

            return (
              <div className={`hole-template-fitting-info-body${fittingImageUrl ? "" : " no-image"}`}>
                {fittingImageUrl ? (
                  <img
                    alt={t.holeWorkspaceFittingInfoImageAlt || t.holeTemplateFittingInfoImageAlt}
                    className="hole-template-fitting-info-image"
                    src={fittingImageUrl}
                  />
                ) : (
                  <div className="hole-template-fitting-info-placeholder">{t.holeWorkspaceNoImage}</div>
                )}

                <div className="hole-template-fitting-info-copy">
                  <strong className="hole-template-fitting-info-title">{fittingTitle}</strong>
                  {fittingSubtitle ? <div className="hole-template-fitting-info-subtitle">{fittingSubtitle}</div> : null}
                </div>
              </div>
            );
          })()
        ) : null}
        {selectedBundleItems.length ? (
          <div className="hole-bundle-selected-list">
            <div className="hole-bundle-selected-list-head">
              <strong>{t.holeBundleSelectedItemsTitle}</strong>
              <span className="service-tree-badge subtle">
                {selectedBundleItems.length} {t.holeBundleSelectedItemsCount}
              </span>
            </div>
            <div className="hole-bundle-selected-items">
              {selectedBundleItems.map((item) => {
                const itemKey = getFittingBundleItemKey(item);
                const itemName = getFittingBundleItemName(item);
                const itemArticle = getFittingBundleItemArticle(item);
                const itemImageUrl = getFittingBundleItemImageUrl(item);
                const itemCategoryLabel = getFittingBundleCategoryLabel(item);
                const itemId = String(item?.id || "");
                const isActiveItem = Boolean(holeSelectedFittingId) && itemId === String(holeSelectedFittingId);

                return (
                  <article
                    aria-label={itemName}
                    className={`hole-bundle-selected-item${itemId ? " is-clickable" : ""}${isActiveItem ? " is-active" : ""}`}
                    key={itemKey || itemName}
                    onClick={
                      itemId
                        ? () => {
                            if (String(holeSelectedFittingId) !== itemId) {
                              void handleHoleFittingChange(itemId);
                            }
                          }
                        : undefined
                    }
                    onKeyDown={
                      itemId
                        ? (event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              if (String(holeSelectedFittingId) !== itemId) {
                                void handleHoleFittingChange(itemId);
                              }
                            }
                          }
                        : undefined
                    }
                    role={itemId ? "button" : undefined}
                    tabIndex={itemId ? 0 : undefined}
                  >
                    <div className="hole-bundle-selected-item-media">
                      {itemImageUrl ? (
                        <img alt={t.holeBundleItemImageAlt} src={itemImageUrl} />
                      ) : (
                        <div className="hole-bundle-selected-item-placeholder">{t.holeWorkspaceNoImage}</div>
                      )}
                    </div>
                    <div className="hole-bundle-selected-item-copy">
                      <strong>{itemName}</strong>
                      {isActiveItem ? (
                        <span className="hole-bundle-selected-item-active-badge">Активна для присадки</span>
                      ) : null}
                      {itemArticle ? (
                        <span>
                          {t.holeBundleItemArticle}: {itemArticle}
                        </span>
                      ) : null}
                      {itemCategoryLabel ? (
                        <span>
                          {t.holeBundleItemCategory}: {itemCategoryLabel}
                        </span>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>
          </div>
        ) : null}
      </section>
    );
  }

  function renderHoleWorkspaceMountingVariantDropdown() {
    const selectedVariant = selectedHoleMountingVariant || holeMountingVariantOptions[0] || null;
    const selectedVariantIcon = selectedVariant?.icon || null;

    return (
      <section className="holes-mounting-variant-dropdown">
        <div className="holes-mounting-variant-dropdown-head">
          <div>
            <strong>{t.holeWorkspaceConnectionVariantTitle}</strong>
            <p>Оберіть варіант кріплення для активного шаблону.</p>
          </div>
          {holeWorkspaceHasUnsavedVariantChanges ? (
            <span className="service-tree-badge subtle holes-mounting-variant-dirty">
              Є незбережені зміни
            </span>
          ) : null}
        </div>
        <div className={`holes-mounting-variant-dropdown-shell${holeMountingVariantDropdownOpen ? " is-open" : ""}`}>
                  <button
                    aria-expanded={holeMountingVariantDropdownOpen}
                    className="holes-mounting-variant-toggle"
                    disabled={!activeHoleFittingId}
                    onClick={() => setHoleMountingVariantDropdownOpen((current) => !current)}
                    type="button"
                  >
            <span className="holes-mounting-variant-toggle-mark">
              {selectedVariantIcon ? <img alt="" src={selectedVariantIcon} /> : <span>⋯</span>}
            </span>
            <span className="holes-mounting-variant-toggle-copy">
              <strong>{selectedVariant?.label || normalizedSelectedHoleMountingVariantKey}</strong>
              <span>{selectedVariant?.description || t.holeWorkspaceSelected}</span>
            </span>
            <ChevronRight className="holes-mounting-variant-toggle-arrow" size={16} />
          </button>
          {holeMountingVariantDropdownOpen ? (
            <div className="holes-mounting-variant-menu" role="listbox">
              {holeMountingVariantOptions.map((variant) => {
                const isActive = normalizedSelectedHoleMountingVariantKey === variant.key;

                return (
                  <button
                    aria-pressed={isActive}
                    className={`holes-mounting-variant-option${isActive ? " active" : ""}`}
                    key={variant.key}
                    onClick={() => {
                      handleHoleMountingVariantChange(variant.key);
                      setHoleMountingVariantDropdownOpen(false);
                    }}
                    type="button"
                  >
                    <span className="holes-mounting-variant-option-mark">
                      <img alt="" src={variant.icon} />
                    </span>
                    <span className="holes-mounting-variant-option-copy">
                      <strong>{variant.label}</strong>
                      <span>{variant.description}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
      </section>
    );
  }
