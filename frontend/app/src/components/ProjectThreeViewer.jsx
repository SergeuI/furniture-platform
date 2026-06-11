import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { Component, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const VISIBILITY_GROUPS = ["carcass", "facades", "drawers", "back", "other"];
const VISUAL_LAYERS = ["holes", "grooves", "quarters"];
const AXIS_INDEX = { x: 0, y: 1, z: 2 };

function safePositiveNumber(value, fallback = 1) {
  const number = Number(value);

  if (!Number.isFinite(number) || number <= 0) {
    return fallback;
  }

  return number;
}

function clampRatio(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return 0;
  }

  return Math.min(Math.max(number, 0), 1);
}

class ProjectThreeViewerErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { errorMessage: "", hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    this.setState({
      errorMessage: error?.message || "Unknown 3D rendering error",
    });
  }

  componentDidUpdate(prevProps) {
    if (
      prevProps.selectedPartCode !== this.props.selectedPartCode ||
      prevProps.items !== this.props.items
    ) {
      if (this.state.hasError) {
        this.setState({ errorMessage: "", hasError: false });
      }
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="project-three-viewer-error">
          <strong>{this.props.t?.production || "Production"}</strong>
          <span>{this.props.t?.productionAssemblyHint || "3D preview is temporarily unavailable."}</span>
          {this.state.errorMessage ? <code>{this.state.errorMessage}</code> : null}
        </div>
      );
    }

    return this.props.children;
  }
}

function SolidViewIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path
        d="M5 8.5 12 5l7 3.5v7L12 19l-7-3.5z"
        fill="none"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path d="M12 5v14M5 8.5l7 3.5 7-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function TransparentViewIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path
        d="M6 7.5 12 4l6 3.5v6.5L12 17l-6-3.5z"
        fill="none"
        opacity="0.95"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M8 10.5 12 8l4 2.5"
        fill="none"
        opacity="0.55"
        stroke="currentColor"
        strokeDasharray="2.4 2.4"
        strokeWidth="1.8"
      />
      <circle cx="16.7" cy="10.2" fill="currentColor" r="1.25" />
    </svg>
  );
}

function AssembledViewIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="5" y="5" width="6" height="6" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="5" width="6" height="6" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <rect x="5" y="13" width="6" height="6" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="13" width="6" height="6" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function ExplodedViewIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="3.5" y="3.5" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <rect x="15" y="3.5" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <rect x="3.5" y="15" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
      <rect x="15" y="15" width="5.5" height="5.5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function getLabel(value, fallback) {
  if (typeof value !== "string") {
    return fallback;
  }

  const normalized = value.trim();
  return normalized ? normalized : fallback;
}

function ModeIconButton({ active, children, onClick, title }) {
  return (
    <button
      aria-label={title}
      className={`project-three-viewer-mode-button${active ? " active" : ""}`}
      onClick={onClick}
      title={title}
      type="button"
    >
      {children}
      <span className="project-three-viewer-button-label">{title}</span>
    </button>
  );
}

function getPanelColor(item, kind, profileType) {
  const category = String(item?.category || "").toLowerCase();
  const material = String(
    item?.material ||
      item?.material_name ||
      item?.sheet_material ||
      item?.material_type ||
      "",
  ).toLowerCase();
  const name = String(item?.part_name || "").toLowerCase();

  if (kind === "facade" || category.includes("facade") || name.includes("facade")) {
    if (material.includes("paint") || material.includes("фарб")) {
      return "#f3efe7";
    }

    if (material.includes("wood") || material.includes("oak") || material.includes("ash") || material.includes("дер")) {
      return "#dec8aa";
    }

    return profileType === "wardrobe" ? "#f0ebe2" : "#efe7db";
  }

  if (kind === "drawer" || category.includes("drawer") || name.includes("drawer")) {
    return material.includes("metal") ? "#cfd7de" : "#dbe5ec";
  }

  if (kind === "back" || category.includes("back") || name.includes("back")) {
    return material.includes("hdf") || material.includes("fiber") ? "#cfd7df" : "#d8e2ec";
  }

  if (kind === "support-rail") {
    return "#b9c5cd";
  }

  if (kind === "divider-vertical" || kind === "shelf") {
    return material.includes("dark") ? "#cfd7db" : "#d8e0e4";
  }

  if (material.includes("hdf")) {
    return "#d5dde4";
  }

  if (material.includes("mdf")) {
    return "#ddd6ce";
  }

  if (material.includes("wood") || material.includes("oak") || material.includes("ash") || material.includes("дер")) {
    return "#d7c7ab";
  }

  return profileType === "kitchen" ? "#e6ecef" : "#e3eaee";
}

function classifyItem(item) {
  const category = String(item?.category || "").toLowerCase();
  const name = String(item?.part_name || "").toLowerCase();

  if (category.includes("back") || name.includes("back")) {
    return "back";
  }

  if (category.includes("facade") || name.includes("facade") || name.includes("front")) {
    return "facade";
  }

  if (category.includes("drawer") || name.includes("drawer")) {
    return "drawer";
  }

  if (
    name.includes("left side") ||
    name.includes("side left") ||
    name.includes("side panel left") ||
    name.includes("бок ліва") ||
    name.includes("боковина ліва")
  ) {
    return "side-left";
  }

  if (
    name.includes("right side") ||
    name.includes("side right") ||
    name.includes("side panel right") ||
    name.includes("бок права") ||
    name.includes("боковина права")
  ) {
    return "side-right";
  }

  if (name.includes("top") || name.includes("roof") || name.includes("upper")) {
    return "top";
  }

  if (name.includes("bottom") || name.includes("base") || name.includes("lower")) {
    return "bottom";
  }

  if (name.includes("shelf") || name.includes("shelves")) {
    return "shelf";
  }

  if (
    name.includes("divider") ||
    name.includes("partition") ||
    name.includes("vertical divider")
  ) {
    return "divider-vertical";
  }

  if (name.includes("rail") || name.includes("stretcher")) {
    return "support-rail";
  }

  return "other";
}

function hasWord(value, terms) {
  const normalized = String(value || "").toLowerCase();
  return terms.some((term) => normalized.includes(term));
}

function expandAssemblyItems(items) {
  return items.flatMap((item) => {
    const quantity = Math.max(Number(item.quantity) || 1, 1);
    const partName = String(item?.part_name || "").toLowerCase();
    const hasTop = hasWord(partName, ["top", "upper", "roof"]);
    const hasBottom = hasWord(partName, ["bottom", "base", "lower"]);
    const hasLeft = hasWord(partName, ["left side", "side left", "side panel left"]);
    const hasRight = hasWord(partName, ["right side", "side right", "side panel right"]);

    return Array.from({ length: quantity }, (_, copyIndex) => {
      let kindHint = null;

      if (hasTop && hasBottom) {
        kindHint = copyIndex % 2 === 0 ? "top" : "bottom";
      } else if (hasLeft && hasRight) {
        kindHint = copyIndex % 2 === 0 ? "side-left" : "side-right";
      }

      return {
        ...item,
        _copyIndex: copyIndex,
        _kindHint: kindHint,
      };
    });
  });
}

function groupByKind(kind) {
  if (kind === "facade") {
    return "facades";
  }

  if (
    [
      "drawer",
      "drawer-visual",
      "drawer-side-left",
      "drawer-side-right",
      "drawer-front-rail",
      "drawer-back-rail",
      "drawer-bottom",
    ].includes(kind)
  ) {
    return "drawers";
  }

  if (kind === "back") {
    return "back";
  }

  if (["side-left", "side-right", "top", "bottom", "shelf", "divider-vertical", "support-rail"].includes(kind)) {
    return "carcass";
  }

  return "other";
}

function normalizeDetailDimensions(part) {
  return {
    height: safePositiveNumber(part?.height, 1),
    thickness: safePositiveNumber(part?.thickness, 18),
    width: safePositiveNumber(part?.width, 1),
  };
}

function sanitizeVector(vector, fallback = [0, 0, 0]) {
  if (!Array.isArray(vector) || vector.length !== 3) {
    return [...fallback];
  }

  return vector.map((value, index) => {
    const numericValue = Number(value);
    const fallbackValue = Number(fallback[index]) || 0;
    return Number.isFinite(numericValue) ? numericValue : fallbackValue;
  });
}

function sanitizeSizeVector(vector, fallback = [0.03, 0.03, 0.03]) {
  if (!Array.isArray(vector) || vector.length !== 3) {
    return [...fallback];
  }

  return vector.map((value, index) => {
    const numericValue = Number(value);
    const fallbackValue = safePositiveNumber(fallback[index], 0.03);
    return Number.isFinite(numericValue) && numericValue > 0
      ? numericValue
      : fallbackValue;
  });
}

function holeMarkerPosition(hole, detailDimensions, mesh) {
  return projectSurfacePoint(
    {
      heightRatio: clampRatio((Number(hole?.y) || 0) / detailDimensions.height),
      normalOffset: 0,
      widthRatio: clampRatio((Number(hole?.x) || 0) / detailDimensions.width),
    },
    mesh,
  );
}

function projectSurfacePoint(point, mesh) {
  if (!mesh?.surfaceAxes) {
    return sanitizeVector(mesh?.position || [0, 0, 0]);
  }

  const position = sanitizeVector(mesh.position);
  const [dimX, dimY, dimZ] = sanitizeSizeVector(mesh.dimensions, [1, 1, 1]);
  const dimensionByAxis = { x: dimX, y: dimY, z: dimZ };
  const widthAxis = mesh.surfaceAxes.width;
  const heightAxis = mesh.surfaceAxes.height;
  const normalAxis = mesh.surfaceAxes.normal;

  if (
    AXIS_INDEX[widthAxis] == null ||
    AXIS_INDEX[heightAxis] == null ||
    AXIS_INDEX[normalAxis] == null
  ) {
    return position;
  }

  position[AXIS_INDEX[widthAxis]] +=
    -dimensionByAxis[widthAxis] / 2 + point.widthRatio * dimensionByAxis[widthAxis];
  position[AXIS_INDEX[heightAxis]] +=
    -dimensionByAxis[heightAxis] / 2 + point.heightRatio * dimensionByAxis[heightAxis];
  position[AXIS_INDEX[normalAxis]] += Number.isFinite(Number(point.normalOffset))
    ? Number(point.normalOffset)
    : 0;

  return sanitizeVector(position);
}

function grooveOverlay(groove, detailDimensions, mesh) {
  if (!mesh?.surfaceAxes) {
    return null;
  }

  const widthAxisSize = safePositiveNumber(
    mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.width]],
    0.08,
  );
  const heightAxisSize = safePositiveNumber(
    mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.height]],
    0.03,
  );
  const widthRatio = clampRatio((Number(groove?.x) || 0) / detailDimensions.width);
  const heightRatio = clampRatio((Number(groove?.y) || 0) / detailDimensions.height);
  const grooveWidth = Math.max(
    ((Number(groove?.length) || 0) / detailDimensions.width) * widthAxisSize,
    0.08,
  );
  const grooveHeight = Math.max(
    ((Number(groove?.width) || 0) / detailDimensions.height) * heightAxisSize,
    0.03,
  );

  const size = sanitizeSizeVector(
    mesh.surfaceAxes.normal === "x"
      ? [0.03, grooveHeight, grooveWidth]
      : mesh.surfaceAxes.normal === "y"
        ? [grooveWidth, 0.03, grooveHeight]
        : [grooveWidth, grooveHeight, 0.03],
  );

  return {
    key: `groove-${groove?.number ?? groove?.x ?? groove?.y ?? "item"}`,
    position: projectSurfacePoint(
      {
        heightRatio,
        normalOffset: 0.004,
        widthRatio: clampRatio(widthRatio + grooveWidth / widthAxisSize / 2),
      },
      mesh,
    ),
    size,
  };
}

function quarterOverlay(quarter, detailDimensions, mesh) {
  if (!mesh?.surfaceAxes) {
    return null;
  }

  const widthAxisSize = safePositiveNumber(
    mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.width]],
    0.08,
  );
  const heightAxisSize = safePositiveNumber(
    mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.height]],
    0.04,
  );
  const normalAxisSize = safePositiveNumber(
    mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.normal]],
    0.05,
  );
  const widthRatio = clampRatio((Number(quarter?.x) || 0) / detailDimensions.width);
  const heightRatio = clampRatio((Number(quarter?.y) || 0) / detailDimensions.height);
  const quarterWidth = Math.max(
    ((Number(quarter?.length) || 0) / detailDimensions.width) * widthAxisSize,
    0.08,
  );
  const quarterHeight = Math.max(
    ((Number(quarter?.width) || 0) / detailDimensions.height) * heightAxisSize,
    0.04,
  );
  const quarterDepth = Math.max(
    ((Number(quarter?.depth) || 0) / detailDimensions.thickness) * Math.max(normalAxisSize, 0.05),
    0.03,
  );

  const size = sanitizeSizeVector(
    mesh.surfaceAxes.normal === "x"
      ? [quarterDepth, quarterHeight, quarterWidth]
      : mesh.surfaceAxes.normal === "y"
        ? [quarterWidth, quarterDepth, quarterHeight]
        : [quarterWidth, quarterHeight, quarterDepth],
  );

  return {
    key: `quarter-${quarter?.number ?? quarter?.x ?? quarter?.y ?? "item"}`,
    position: projectSurfacePoint(
      {
        heightRatio: clampRatio(heightRatio + quarterHeight / heightAxisSize / 2),
        normalOffset: -quarterDepth / 3,
        widthRatio: clampRatio(widthRatio + quarterWidth / widthAxisSize / 2),
      },
      mesh,
    ),
    size,
  };
}

function normalizeProjectType(value) {
  const type = String(value || "").trim().toLowerCase();

  if (!type) {
    return "dresser";
  }

  if (type.includes("wardrobe") || type.includes("closet") || type.includes("шаф")) {
    return "wardrobe";
  }

  if (
    type.includes("kitchen") ||
    type.includes("кух")
  ) {
    return "kitchen";
  }

  if (
    type.includes("cabinet") ||
    type.includes("pedestal") ||
    type.includes("nightstand") ||
    type.includes("тумб") ||
    type.includes("пенал")
  ) {
    return "cabinet";
  }

  if (type.includes("dresser") || type.includes("комод")) {
    return "dresser";
  }

  return "dresser";
}

function getHorizontalSlotCenter(totalSpan, columns, columnIndex, insetRatio = 0.04) {
  const safeColumns = Math.max(columns, 1);
  const inset = totalSpan * insetRatio;
  const usableSpan = Math.max(totalSpan - inset * 2, totalSpan * 0.42);
  const slotSize = usableSpan / safeColumns;

  return -usableSpan / 2 + slotSize * (columnIndex + 0.5);
}

function getVerticalSlotCenter(totalSpan, rows, rowIndex, topInsetRatio = 0.08, bottomInsetRatio = 0.08) {
  const safeRows = Math.max(rows, 1);
  const topInset = totalSpan * topInsetRatio;
  const bottomInset = totalSpan * bottomInsetRatio;
  const usableSpan = Math.max(totalSpan - topInset - bottomInset, totalSpan * 0.34);
  const slotSize = usableSpan / safeRows;

  return totalSpan / 2 - topInset - slotSize * (rowIndex + 0.5);
}

function getDividerSlotCenter(totalSpan, columns, dividerIndex, insetRatio = 0.04) {
  const safeColumns = Math.max(columns, 1);
  const inset = totalSpan * insetRatio;
  const usableSpan = Math.max(totalSpan - inset * 2, totalSpan * 0.42);
  const slotSize = usableSpan / safeColumns;

  return -usableSpan / 2 + slotSize * (dividerIndex + 1);
}

function ratioToCenteredX(totalSpan, ratio) {
  return -totalSpan / 2 + totalSpan * clampRatio(ratio);
}

function ratioToCenteredY(totalSpan, ratio) {
  return totalSpan / 2 - totalSpan * clampRatio(ratio);
}

function getSlotSpan(totalSpan, ratio, fallback) {
  const numericRatio = Number(ratio);

  if (!Number.isFinite(numericRatio) || numericRatio <= 0) {
    return fallback;
  }

  return Math.max(totalSpan * numericRatio, fallback * 0.4);
}

function resolveVisualSpan(actualSpan, visualSpan, profileType, axis) {
  const safeActual = safePositiveNumber(actualSpan, visualSpan);
  const safeVisual = safePositiveNumber(visualSpan, safeActual);

  if (profileType === "dresser" && (axis === "width" || axis === "height")) {
    return safeVisual;
  }

  return Math.min(safeVisual, safeActual);
}

function buildAssemblyPlacementIndex(cuttingAssembly) {
  const placements = Array.isArray(cuttingAssembly?.placements) ? cuttingAssembly.placements : [];

  return placements.reduce((index, placement) => {
    const exportCode = String(placement?.export_code || "").trim();
    const copyIndex = Number(placement?.copy_index);

    if (!exportCode || !Number.isInteger(copyIndex)) {
      return index;
    }

    index.set(`${exportCode}:${copyIndex}`, placement);
    return index;
  }, new Map());
}

function resolveAssemblyProfile({
  assemblyLayout,
  dividerCount,
  drawerItemsCount,
  facadeItemsCount,
  projectType,
  requestedSections,
}) {
  if (assemblyLayout && typeof assemblyLayout === "object" && Object.keys(assemblyLayout).length > 0) {
    return {
      columns: Math.max(Number(assemblyLayout.columns) || 1, 1),
      drawerBottomInset: Number(assemblyLayout.drawer_bottom_inset ?? 0.08),
      drawerColumns: Math.max(Number(assemblyLayout.drawer_columns) || 1, 1),
      drawerDepthRatio: Number(assemblyLayout.drawer_depth_ratio ?? 0.78),
      drawerFillDirection: String(assemblyLayout.drawer_fill_direction || "top-down"),
      drawerGap: Number(assemblyLayout.drawer_gap ?? 0.1),
      drawerRows: Math.max(Number(assemblyLayout.drawer_rows) || 1, 1),
      drawerSetback: Number(assemblyLayout.drawer_setback ?? 0.09),
      drawerSlots: Array.isArray(assemblyLayout.drawer_slots) ? assemblyLayout.drawer_slots : [],
      drawerTopInset: Number(assemblyLayout.drawer_top_inset ?? 0.38),
      dividerSlots: Array.isArray(assemblyLayout.divider_slots) ? assemblyLayout.divider_slots : [],
      facadeBottomInset: Number(assemblyLayout.facade_bottom_inset ?? 0.06),
      facadeColumns: Math.max(Number(assemblyLayout.facade_columns) || 1, 1),
      facadeFillDirection: String(assemblyLayout.facade_fill_direction || "top-down"),
      facadeFrontOffset: Number(assemblyLayout.facade_front_offset ?? 0.02),
      facadeGap: Number(assemblyLayout.facade_gap ?? 0.085),
      facadeRows: Math.max(Number(assemblyLayout.facade_rows) || 1, 1),
      facadeSlots: Array.isArray(assemblyLayout.facade_slots) ? assemblyLayout.facade_slots : [],
      facadeTopInset: Number(assemblyLayout.facade_top_inset ?? 0.06),
      otherBottomInset: Number(assemblyLayout.other_bottom_inset ?? 0.18),
      otherTopInset: Number(assemblyLayout.other_top_inset ?? 0.16),
      shelfSlots: Array.isArray(assemblyLayout.shelf_slots) ? assemblyLayout.shelf_slots : [],
      shelfBottomInset: Number(assemblyLayout.shelf_bottom_inset ?? 0.24),
      shelfTopInset: Number(assemblyLayout.shelf_top_inset ?? 0.18),
      supportRailFrontInset: Number(assemblyLayout.support_rail_front_inset ?? 0.05),
      supportRailSlots: Array.isArray(assemblyLayout.support_rail_slots) ? assemblyLayout.support_rail_slots : [],
      supportRailTopInset: Number(assemblyLayout.support_rail_top_inset ?? 0.13),
      type: normalizeProjectType(assemblyLayout.project_type || projectType),
      verticalInsetRatio: Number(assemblyLayout.vertical_inset_ratio ?? 0.05),
    };
  }

  const normalizedType = normalizeProjectType(projectType);
  const naturalColumns = Math.max(dividerCount + 1, requestedSections, 1);

  if (normalizedType === "wardrobe") {
    const columns = Math.max(2, Math.min(4, naturalColumns));
    return {
      columns,
      drawerBottomInset: 0.08,
      drawerColumns: Math.max(1, Math.min(columns, drawerItemsCount > 0 ? 2 : 1)),
      drawerDepthRatio: 0.68,
      drawerFillDirection: "bottom-up",
      drawerGap: 0.11,
      drawerRows: Math.max(1, Math.min(drawerItemsCount || 1, 2)),
      drawerSetback: 0.1,
      drawerSlots: [],
      drawerTopInset: 0.56,
      dividerSlots: [],
      facadeBottomInset: 0.06,
      facadeColumns: Math.max(2, Math.min(columns, Math.max(facadeItemsCount, columns))),
      facadeFillDirection: "top-down",
      facadeFrontOffset: 0.01,
      facadeGap: 0.08,
      facadeRows: Math.max(1, drawerItemsCount ? 2 : 1),
      facadeSlots: [],
      facadeTopInset: 0.05,
      otherBottomInset: 0.16,
      otherTopInset: 0.16,
      shelfSlots: [],
      shelfBottomInset: 0.18,
      shelfTopInset: 0.16,
      supportRailFrontInset: 0.05,
      supportRailSlots: [],
      supportRailTopInset: 0.12,
      type: normalizedType,
      verticalInsetRatio: 0.05,
    };
  }

  if (normalizedType === "kitchen") {
    const columns = Math.max(2, Math.min(5, naturalColumns));
    return {
      columns,
      drawerBottomInset: 0.1,
      drawerColumns: Math.max(1, Math.min(columns, Math.max(requestedSections, 2))),
      drawerDepthRatio: 0.62,
      drawerFillDirection: "top-down",
      drawerGap: 0.09,
      drawerRows: Math.max(1, Math.min(drawerItemsCount || 1, 2)),
      drawerSetback: 0.08,
      drawerSlots: [],
      drawerTopInset: 0.46,
      dividerSlots: [],
      facadeBottomInset: 0.08,
      facadeColumns: Math.max(2, Math.min(columns, Math.max(requestedSections, 2))),
      facadeFillDirection: "top-down",
      facadeFrontOffset: 0.03,
      facadeGap: 0.07,
      facadeRows: Math.max(1, drawerItemsCount ? 2 : 1),
      facadeSlots: [],
      facadeTopInset: 0.08,
      otherBottomInset: 0.18,
      otherTopInset: 0.18,
      shelfSlots: [],
      shelfBottomInset: 0.22,
      shelfTopInset: 0.22,
      supportRailFrontInset: 0.04,
      supportRailSlots: [],
      supportRailTopInset: 0.14,
      type: normalizedType,
      verticalInsetRatio: 0.05,
    };
  }

  if (normalizedType === "cabinet") {
    const columns = Math.max(1, Math.min(2, naturalColumns));
    return {
      columns,
      drawerBottomInset: 0.1,
      drawerColumns: Math.max(1, Math.min(columns, drawerItemsCount || 1)),
      drawerDepthRatio: 0.74,
      drawerFillDirection: "bottom-up",
      drawerGap: 0.1,
      drawerRows: Math.max(1, drawerItemsCount || 1),
      drawerSetback: 0.09,
      drawerSlots: [],
      drawerTopInset: 0.48,
      dividerSlots: [],
      facadeBottomInset: 0.08,
      facadeColumns: Math.max(1, Math.min(columns, Math.max(facadeItemsCount, columns))),
      facadeFillDirection: "top-down",
      facadeFrontOffset: 0.015,
      facadeGap: 0.08,
      facadeRows: Math.max(1, drawerItemsCount ? 2 : 1),
      facadeSlots: [],
      facadeTopInset: 0.08,
      otherBottomInset: 0.2,
      otherTopInset: 0.18,
      shelfSlots: [],
      shelfBottomInset: 0.24,
      shelfTopInset: 0.2,
      supportRailFrontInset: 0.05,
      supportRailSlots: [],
      supportRailTopInset: 0.14,
      type: normalizedType,
      verticalInsetRatio: 0.06,
    };
  }

  const columns = Math.max(1, Math.min(3, naturalColumns));
  return {
    columns,
    backPanelInset: 0,
    backPanelThicknessRatio: 1,
    drawerBottomInset: 0.1,
    drawerColumns: Math.max(1, Math.min(columns, Math.max(requestedSections, 1))),
    drawerDepthRatio: 0.88,
    drawerFillDirection: "top-down",
    drawerFrontClearance: 0.045,
    drawerGap: 0.04,
    drawerRows: Math.max(1, drawerItemsCount || 1),
    drawerSetback: 0.03,
    drawerSlots: [],
    drawerTopInset: 0.1,
    dividerSlots: [],
    facadeBottomInset: 0.06,
    facadeColumns: Math.max(1, Math.min(columns, Math.max(facadeItemsCount, columns))),
    facadeFillDirection: "top-down",
    facadeFrontOffset: 0.012,
    facadeGap: 0.03,
    facadeRows: Math.max(1, facadeItemsCount || drawerItemsCount || 1),
    facadeSlots: [],
    facadeTopInset: 0.06,
    otherBottomInset: 0.18,
    otherTopInset: 0.16,
    shelfSlots: [],
    shelfBottomInset: 0.24,
    shelfTopInset: 0.18,
    supportRailFrontInset: 0.05,
    supportRailSlots: [],
    supportRailTopInset: 0.13,
    type: "dresser",
    verticalInsetRatio: 0.05,
  };
}

function resolveGridSlot(kind, index, columns, rows, profile) {
  const safeColumns = Math.max(columns, 1);
  const safeRows = Math.max(rows, 1);
  const baseColumn = index % safeColumns;
  const baseRow = Math.floor(index / safeColumns);

  if (kind === "drawer" && profile?.drawerFillDirection === "bottom-up") {
    return {
      column: baseColumn,
      row: Math.max(safeRows - 1 - baseRow, 0),
    };
  }

  if (
    kind === "facade" &&
    profile?.type === "wardrobe" &&
    profile?.facadeFillDirection === "top-down" &&
    safeColumns >= 2 &&
    safeRows > 1
  ) {
    const wardrobeColumn = index % Math.min(safeColumns, 2);
    const wardrobeRow = Math.floor(index / Math.min(safeColumns, 2));
    return {
      column: wardrobeColumn,
      row: Math.min(wardrobeRow, safeRows - 1),
    };
  }

  return {
    column: baseColumn,
    row: Math.min(baseRow, safeRows - 1),
  };
}

function buildAssembly(items, exploded, visibility, projectMeta) {
  const placementIndex = buildAssemblyPlacementIndex(projectMeta?.cuttingAssembly);
  const normalizedItems = expandAssemblyItems(items).map((item, index) => {
    const placement = placementIndex.get(`${item.export_code}:${item._copyIndex}`) || null;

    return {
      ...item,
      _index: index,
      _kind: placement?.kind || item._kindHint || classifyItem(item),
      _placement: placement,
      _depth: safePositiveNumber(item.depth || item.height, 420),
      _height: safePositiveNumber(item.height, 1),
      _thickness: safePositiveNumber(
        item.thickness ?? (String(item.material || "").toLowerCase().includes("hdf") ? 4 : 18),
        18,
      ),
      _width: safePositiveNumber(item.width, 1),
    };
  });

  const sides = normalizedItems.filter((item) => item._kind === "side-left" || item._kind === "side-right");
  const genericBoards = normalizedItems.filter((item) => item._kind === "other");

  if (sides.length < 2) {
    const candidates = [...genericBoards].sort((a, b) => b._height - a._height);
    if (candidates[0] && !sides.includes(candidates[0])) {
      candidates[0]._kind = "side-left";
      sides.push(candidates[0]);
    }
    if (candidates[1] && !sides.includes(candidates[1])) {
      candidates[1]._kind = "side-right";
      sides.push(candidates[1]);
    }
  }

  const cabinetWidth = Math.max(...normalizedItems.map((item) => item._width), 600);
  const cabinetHeight = Math.max(...normalizedItems.map((item) => item._height), 720);
  const cabinetDepth = Math.max(...normalizedItems.map((item) => item._depth), 420);
  const largest = Math.max(cabinetWidth, cabinetHeight, cabinetDepth);
  const scale = 3.4 / largest;
  const widthUnits = cabinetWidth * scale;
  const heightUnits = cabinetHeight * scale;
  const depthUnits = cabinetDepth * scale;
  const gap = exploded ? 0.48 : 0.08;
  const spread = exploded ? 0.42 : 0;
  const sideThickness =
    (sides[0]?._thickness || normalizedItems.find((item) => item._kind === "side-left" || item._kind === "side-right")?._thickness || 18) * scale;
  const horizontalBoardThickness =
    (normalizedItems.find((item) => item._kind === "top" || item._kind === "bottom")?._thickness || 18) * scale;
  const innerWidth = Math.max(widthUnits - sideThickness * 2, widthUnits * 0.58);
  const innerHeight = Math.max(heightUnits - horizontalBoardThickness * 2, heightUnits * 0.58);
  const innerDepth = Math.max(depthUnits - sideThickness * 0.85, depthUnits * 0.68);
  const dividerCount = normalizedItems.filter((item) => item._kind === "divider-vertical").length;
  const facadeItemsCount = normalizedItems.filter((item) => item._kind === "facade").length;
  const drawerItemsCount = normalizedItems.filter((item) => item._kind === "drawer").length;
  const shelfCount = normalizedItems.filter((item) => item._kind === "shelf").length;
  const supportRailCount = normalizedItems.filter((item) => item._kind === "support-rail").length;
  const requestedSections = Math.max(Number(projectMeta?.sections) || 1, 1);
  const assemblyProfile = resolveAssemblyProfile({
    assemblyLayout: projectMeta?.assemblyLayout,
    dividerCount,
    drawerItemsCount,
    facadeItemsCount,
    projectType: projectMeta?.projectType,
    requestedSections,
  });
  const assemblyColumns = Math.max(assemblyProfile.columns, 1);
  const facadeColumns = Math.max(1, Math.min(assemblyColumns, assemblyProfile.facadeColumns || assemblyColumns));
  const drawerColumns = Math.max(1, Math.min(assemblyColumns, assemblyProfile.drawerColumns || assemblyColumns));
  const facadeRows = Math.max(
    assemblyProfile.facadeRows || 1,
    Math.ceil(Math.max(facadeItemsCount, 1) / facadeColumns),
  );
  const drawerRows = Math.max(
    assemblyProfile.drawerRows || 1,
    Math.ceil(Math.max(drawerItemsCount, 1) / drawerColumns),
  );
  const facadeStepX = innerWidth / facadeColumns;
  const facadeStepY = innerHeight / facadeRows;
  const drawerStepX = innerWidth / drawerColumns;
  const drawerStepY = innerHeight / drawerRows;
  const verticalDividerSlots = Math.max(0, assemblyColumns - 1);
  const baseDrawerWidth = Math.min(
    Math.max(drawerStepX - assemblyProfile.drawerGap, drawerStepX * 0.78),
    drawerStepX * 0.92,
  );
  const baseDrawerHeight = Math.min(
    Math.max(drawerStepY - assemblyProfile.drawerGap, drawerStepY * 0.76),
    drawerStepY * 0.82,
  );
  const baseDrawerDepth = Math.min(innerDepth * assemblyProfile.drawerDepthRatio, depthUnits * 0.92);

  let facadeOffset = 0;
  let drawerOffset = 0;
  let shelfLevel = 0;
  let dividerOffset = 0;
  let supportRailOffset = 0;
  let otherColumn = 0;

  const meshes = normalizedItems
    .filter((item) => visibility[groupByKind(item._kind)] !== false)
    .map((item, index) => {
      const thickness = item._thickness * scale;
      const width = item._width * scale;
      const depth = item._depth * scale;
      const height = item._height * scale;
      const color = getPanelColor(item, item._kind, assemblyProfile.type);
      let dimensions = [width, height, thickness];
      let position = [0, 0, 0];
      let surfaceAxes = {
        height: "y",
        normal: "z",
        width: "x",
      };
      const facadeSlot = resolveGridSlot(
        "facade",
        facadeOffset,
        facadeColumns,
        facadeRows,
        assemblyProfile,
      );
      const drawerSlot = resolveGridSlot(
        "drawer",
        drawerOffset,
        drawerColumns,
        drawerRows,
        assemblyProfile,
      );
      const plannedFacadeSlot =
        assemblyProfile.facadeSlots.length > 0
          ? assemblyProfile.facadeSlots[
              ((Number.isInteger(item._placement?.slot_index) ? item._placement.slot_index : facadeOffset) %
                assemblyProfile.facadeSlots.length +
                assemblyProfile.facadeSlots.length) %
                assemblyProfile.facadeSlots.length
            ]
          : null;
      const plannedDrawerSlot =
        assemblyProfile.drawerSlots.length > 0
          ? assemblyProfile.drawerSlots[
              ((Number.isInteger(item._placement?.slot_index) ? item._placement.slot_index : drawerOffset) %
                assemblyProfile.drawerSlots.length +
                assemblyProfile.drawerSlots.length) %
                assemblyProfile.drawerSlots.length
            ]
          : null;
      const mappedFacadeSlotIndex = Number.isInteger(item._placement?.slot_index)
        ? item._placement.slot_index
        : facadeOffset;
      const mappedDrawerSlotIndex = Number.isInteger(item._placement?.slot_index)
        ? item._placement.slot_index
        : drawerOffset;
      const mappedDividerSlotIndex = Number.isInteger(item._placement?.slot_index)
        ? item._placement.slot_index
        : dividerOffset;
      const mappedShelfSlotIndex = Number.isInteger(item._placement?.slot_index)
        ? item._placement.slot_index
        : shelfLevel;
      const mappedSupportRailSlotIndex = Number.isInteger(item._placement?.slot_index)
        ? item._placement.slot_index
        : supportRailOffset;
      const resolvedDrawerSlot = resolveGridSlot(
        "drawer",
        mappedDrawerSlotIndex,
        drawerColumns,
        drawerRows,
        assemblyProfile,
      );
      const drawerCenterX =
        plannedDrawerSlot?.x_ratio != null
          ? ratioToCenteredX(innerWidth, plannedDrawerSlot.x_ratio)
          : getHorizontalSlotCenter(innerWidth, drawerColumns, resolvedDrawerSlot.column);
      const drawerCenterY =
        plannedDrawerSlot?.y_ratio != null
          ? ratioToCenteredY(innerHeight, plannedDrawerSlot.y_ratio)
          : getVerticalSlotCenter(
              innerHeight,
              drawerRows,
              resolvedDrawerSlot.row,
              assemblyProfile.drawerTopInset,
              assemblyProfile.drawerBottomInset,
            );
      const drawerCenterZ = exploded
        ? depthUnits / 2 + baseDrawerDepth / 2 + 0.74
        : depthUnits / 2 - baseDrawerDepth / 2 - assemblyProfile.drawerSetback;
      const facadeSlotWidth = getSlotSpan(
        innerWidth,
        plannedFacadeSlot?.width_ratio,
        facadeStepX,
      );
      const facadeSlotHeight = getSlotSpan(
        innerHeight,
        plannedFacadeSlot?.height_ratio,
        facadeStepY,
      );
      const drawerSlotWidth = getSlotSpan(
        innerWidth,
        plannedDrawerSlot?.width_ratio,
        drawerStepX,
      );
      const drawerSlotHeight = getSlotSpan(
        innerHeight,
        plannedDrawerSlot?.height_ratio,
        drawerStepY,
      );
      const localDrawerWidth = Math.min(
        Math.max(drawerSlotWidth - assemblyProfile.drawerGap, drawerSlotWidth * 0.78),
        drawerSlotWidth * 0.94,
      );
      const localDrawerHeight = Math.min(
        Math.max(drawerSlotHeight - assemblyProfile.drawerGap, drawerSlotHeight * 0.74),
        drawerSlotHeight * 0.84,
      );
      const localDrawerDepth = Math.min(baseDrawerDepth, depthUnits * 0.92);
      const preferVisualSlotSizing = assemblyProfile.type === "dresser";
      const facadeVisualWidth = Math.max(
        facadeSlotWidth - assemblyProfile.facadeGap,
        facadeSlotWidth * 0.82,
      );
      const facadeVisualHeight = Math.max(
        facadeSlotHeight - assemblyProfile.facadeGap,
        facadeSlotHeight * 0.82,
      );
      const drawerRailVisualWidth = Math.max(localDrawerWidth - thickness * 1.2, localDrawerWidth * 0.84);
      const drawerBottomVisualWidth = Math.max(localDrawerWidth - thickness * 0.8, localDrawerWidth * 0.86);
      const drawerBottomVisualDepth = Math.max(
        localDrawerDepth - thickness * 0.8,
        localDrawerDepth * 0.88,
      );

      switch (item._kind) {
        case "side-left":
          dimensions = [thickness, heightUnits, depthUnits];
          position = [-widthUnits / 2 + thickness / 2 - spread, 0, 0];
          surfaceAxes = {
            height: "y",
            normal: "x",
            width: "z",
          };
          break;
        case "side-right":
          dimensions = [thickness, heightUnits, depthUnits];
          position = [widthUnits / 2 - thickness / 2 + spread, 0, 0];
          surfaceAxes = {
            height: "y",
            normal: "x",
            width: "z",
          };
          break;
        case "top":
          dimensions = [widthUnits - 2 * thickness, thickness, depthUnits];
          position = [0, heightUnits / 2 - thickness / 2 + spread, 0];
          surfaceAxes = {
            height: "z",
            normal: "y",
            width: "x",
          };
          break;
        case "bottom":
          dimensions = [widthUnits - 2 * thickness, thickness, depthUnits];
          position = [0, -heightUnits / 2 + thickness / 2 - spread, 0];
          surfaceAxes = {
            height: "z",
            normal: "y",
            width: "x",
          };
          break;
        case "back":
          dimensions = [
            widthUnits - sideThickness * 2,
            heightUnits - horizontalBoardThickness * 2,
            Math.max(thickness * (assemblyProfile.backPanelThicknessRatio || 0.5), thickness * 0.45),
          ];
          position = [
            0,
            0,
            -depthUnits / 2 + dimensions[2] / 2 + (assemblyProfile.backPanelInset || 0) - (exploded ? spread : 0),
          ];
          surfaceAxes = {
            height: "y",
            normal: "z",
            width: "x",
          };
          break;
        case "shelf":
          dimensions = [Math.min(innerWidth, width), thickness, Math.min(innerDepth, depth)];
          const plannedShelfSlot =
            assemblyProfile.shelfSlots.length > 0
              ? assemblyProfile.shelfSlots[
                  ((mappedShelfSlotIndex % assemblyProfile.shelfSlots.length) + assemblyProfile.shelfSlots.length) %
                    assemblyProfile.shelfSlots.length
                ]
              : null;
          position = [
            0,
            plannedShelfSlot?.y_ratio != null
              ? ratioToCenteredY(innerHeight, plannedShelfSlot.y_ratio)
              : getVerticalSlotCenter(
                  innerHeight,
                  Math.max(shelfCount + 1, 2),
                  Math.min(shelfLevel + 1, shelfCount),
                  assemblyProfile.shelfTopInset,
                  assemblyProfile.shelfBottomInset,
                ),
            exploded ? (shelfLevel % 2 === 0 ? -spread * 0.24 : spread * 0.24) : 0,
          ];
          shelfLevel += 1;
          surfaceAxes = {
            height: "z",
            normal: "y",
            width: "x",
          };
          break;
        case "divider-vertical": {
          const slotIndex = verticalDividerSlots > 0 ? mappedDividerSlotIndex % verticalDividerSlots : 0;
          const plannedDividerSlot =
            assemblyProfile.dividerSlots.length > 0
              ? assemblyProfile.dividerSlots[slotIndex % assemblyProfile.dividerSlots.length]
              : null;
          const xOffset =
            plannedDividerSlot?.x_ratio != null
              ? ratioToCenteredX(innerWidth, plannedDividerSlot.x_ratio)
              : verticalDividerSlots > 0
              ? getDividerSlotCenter(innerWidth, assemblyColumns, slotIndex, assemblyProfile.verticalInsetRatio)
              : 0;
          dimensions = [thickness, innerHeight, Math.min(innerDepth, depth)];
          position = [xOffset, 0, exploded ? (slotIndex % 2 === 0 ? -spread * 0.22 : spread * 0.22) : 0];
          dividerOffset += 1;
          surfaceAxes = {
            height: "y",
            normal: "x",
            width: "z",
          };
          break;
        }
        case "support-rail":
          dimensions = [Math.min(innerWidth, width), Math.max(thickness, 0.04), Math.min(depthUnits * 0.12, depth * 0.2)];
          const plannedRailSlot =
            assemblyProfile.supportRailSlots.length > 0
              ? assemblyProfile.supportRailSlots[
                  ((mappedSupportRailSlotIndex % assemblyProfile.supportRailSlots.length) +
                    assemblyProfile.supportRailSlots.length) %
                    assemblyProfile.supportRailSlots.length
                ]
              : null;
          position = [
            0,
            plannedRailSlot?.y_ratio != null
              ? ratioToCenteredY(innerHeight, plannedRailSlot.y_ratio)
              : getVerticalSlotCenter(
                  innerHeight,
                  Math.max(supportRailCount, 1),
                  supportRailOffset,
                  assemblyProfile.supportRailTopInset,
                  0.72,
                ),
            depthUnits / 2 - dimensions[2] / 2 - assemblyProfile.supportRailFrontInset,
          ];
          supportRailOffset += 1;
          surfaceAxes = {
            height: "z",
            normal: "y",
            width: "x",
          };
          break;
        case "facade":
          dimensions = [
            resolveVisualSpan(width, facadeVisualWidth, assemblyProfile.type, "width"),
            resolveVisualSpan(height, facadeVisualHeight, assemblyProfile.type, "height"),
            thickness,
          ];
          position = [
            plannedFacadeSlot?.x_ratio != null
              ? ratioToCenteredX(innerWidth, plannedFacadeSlot.x_ratio)
              : getHorizontalSlotCenter(
                  innerWidth,
                  facadeColumns,
                  resolveGridSlot("facade", mappedFacadeSlotIndex, facadeColumns, facadeRows, assemblyProfile).column,
                ),
            plannedFacadeSlot?.y_ratio != null
              ? ratioToCenteredY(innerHeight, plannedFacadeSlot.y_ratio)
              : getVerticalSlotCenter(
                  innerHeight,
                  facadeRows,
                  resolveGridSlot("facade", mappedFacadeSlotIndex, facadeColumns, facadeRows, assemblyProfile).row,
                  assemblyProfile.facadeTopInset,
                  assemblyProfile.facadeBottomInset,
                ),
            depthUnits / 2 + thickness / 2 + gap + assemblyProfile.facadeFrontOffset,
          ];
          facadeOffset += 1;
          surfaceAxes = {
            height: "y",
            normal: "z",
            width: "x",
          };
          break;
        case "drawer":
          dimensions = [
            resolveVisualSpan(width, localDrawerWidth, assemblyProfile.type, "width"),
            resolveVisualSpan(height, localDrawerHeight, assemblyProfile.type, "height"),
            preferVisualSlotSizing ? localDrawerDepth : Math.min(localDrawerDepth, depth),
          ];
          position = [drawerCenterX, drawerCenterY, drawerCenterZ];
          drawerOffset += 1;
          surfaceAxes = {
            height: "y",
            normal: "z",
            width: "x",
          };
          break;
        case "drawer-side-left":
        case "drawer-side-right":
          dimensions = [
            Math.max(thickness, 0.04),
            resolveVisualSpan(height, localDrawerHeight, assemblyProfile.type, "height"),
            preferVisualSlotSizing ? localDrawerDepth : Math.min(localDrawerDepth, width),
          ];
          position = [
            drawerCenterX + (item._kind === "drawer-side-left" ? -1 : 1) * (localDrawerWidth / 2 - dimensions[0] / 2),
            drawerCenterY,
            drawerCenterZ,
          ];
          surfaceAxes = {
            height: "y",
            normal: "x",
            width: "z",
          };
          break;
        case "drawer-front-rail":
        case "drawer-back-rail":
          dimensions = [
            resolveVisualSpan(width, drawerRailVisualWidth, assemblyProfile.type, "width"),
            resolveVisualSpan(height, localDrawerHeight, assemblyProfile.type, "height"),
            Math.max(thickness, 0.04),
          ];
          position = [
            drawerCenterX,
            drawerCenterY,
            drawerCenterZ +
              (item._kind === "drawer-front-rail" ? 1 : -1) * (localDrawerDepth / 2 - dimensions[2] / 2),
          ];
          surfaceAxes = {
            height: "y",
            normal: "z",
            width: "x",
          };
          break;
        case "drawer-bottom":
          dimensions = [
            resolveVisualSpan(width, drawerBottomVisualWidth, assemblyProfile.type, "width"),
            Math.max(Math.min(thickness, 0.08), 0.03),
            preferVisualSlotSizing ? drawerBottomVisualDepth : Math.min(drawerBottomVisualDepth, height),
          ];
          position = [
            drawerCenterX,
            drawerCenterY - localDrawerHeight / 2 + dimensions[1] / 2,
            drawerCenterZ,
          ];
          surfaceAxes = {
            height: "z",
            normal: "y",
            width: "x",
          };
          break;
        default:
          dimensions =
            height > width
              ? [Math.max(thickness, 0.04), Math.min(innerHeight, height), Math.min(innerDepth, depth)]
              : [Math.min(innerWidth * 0.92, width), Math.max(thickness, 0.04), Math.min(innerDepth, height)];
          position = [
            height > width
              ? getHorizontalSlotCenter(innerWidth, Math.max(assemblyColumns, 1), otherColumn % Math.max(assemblyColumns, 1))
              : 0,
            height > width
              ? getVerticalSlotCenter(
                  innerHeight,
                  Math.max(Math.ceil(Math.max(genericBoards.length, 1) / Math.max(assemblyColumns, 1)), 1),
                  Math.floor(otherColumn / Math.max(assemblyColumns, 1)),
                  assemblyProfile.otherTopInset,
                  assemblyProfile.otherBottomInset,
                )
              : getVerticalSlotCenter(
                  innerHeight,
                  Math.max(Math.ceil(Math.max(genericBoards.length, 1) / Math.max(assemblyColumns, 1)), 1),
                  Math.floor(otherColumn / Math.max(assemblyColumns, 1)),
                  assemblyProfile.otherTopInset,
                  assemblyProfile.otherBottomInset,
                ),
            height > width ? 0 : exploded ? spread * 0.16 : 0,
          ];
          otherColumn += 1;
          surfaceAxes = {
            height: height > width ? "y" : "z",
            normal: height > width ? "x" : "y",
            width: height > width ? "z" : "x",
          };
          break;
      }

      return {
        color,
        dimensions,
        item,
        key: `${item.export_code}-${index}`,
        position,
        surfaceAxes,
      };
    });

  const drawerVisualMeshes =
    visibility.drawers === false
      ? []
      : (assemblyProfile.drawerSlots || []).map((slot, slotIndex) => {
          const representativeItem =
            normalizedItems.find(
              (item) =>
                item._placement?.slot_type === "drawer" &&
                Number(item._placement?.slot_index) === slotIndex,
            ) ||
            normalizedItems.find((item) => item._kind === "facade" && Number(item._placement?.slot_index) === slotIndex) ||
            normalizedItems.find((item) => item._kind.startsWith("drawer")) ||
            normalizedItems[0];

          const drawerSlotWidth = getSlotSpan(innerWidth, slot?.width_ratio, drawerStepX);
          const drawerSlotHeight = getSlotSpan(innerHeight, slot?.height_ratio, drawerStepY);
          const drawerVisualWidth = Math.max(
            drawerSlotWidth - assemblyProfile.drawerGap,
            drawerSlotWidth * (assemblyProfile.type === "dresser" ? 0.92 : 0.84),
          );
          const drawerVisualHeight = Math.max(
            drawerSlotHeight - assemblyProfile.drawerGap,
            drawerSlotHeight * (assemblyProfile.type === "dresser" ? 0.9 : 0.8),
          );
          const drawerVisualDepth = Math.max(
            baseDrawerDepth * (assemblyProfile.type === "dresser" ? 0.96 : 0.9),
            innerDepth * 0.42,
          );
          const drawerCenterX =
            slot?.x_ratio != null
              ? ratioToCenteredX(innerWidth, slot.x_ratio)
              : getHorizontalSlotCenter(innerWidth, drawerColumns, slotIndex % drawerColumns);
          const drawerCenterY =
            slot?.y_ratio != null
              ? ratioToCenteredY(innerHeight, slot.y_ratio)
              : getVerticalSlotCenter(
                  innerHeight,
                  Math.max(drawerRows, 1),
                  slotIndex,
                  assemblyProfile.drawerTopInset,
                  assemblyProfile.drawerBottomInset,
                );
      const drawerCenterZ =
        depthUnits / 2 -
        drawerVisualDepth / 2 -
        Math.max(assemblyProfile.drawerSetback, assemblyProfile.drawerFrontClearance || 0.045);

          return {
            color: getPanelColor(representativeItem, "drawer", assemblyProfile.type),
            dimensions: [drawerVisualWidth, drawerVisualHeight, drawerVisualDepth],
            item: {
              ...representativeItem,
              export_code: representativeItem?.export_code || `drawer-visual-${slotIndex}`,
              _kind: "drawer-visual",
            },
            key: `drawer-visual-${slotIndex}`,
            position: [drawerCenterX, drawerCenterY, drawerCenterZ],
            surfaceAxes: {
              height: "y",
              normal: "z",
              width: "x",
            },
          };
        });

  return { meshes, drawerVisualMeshes };
}

function AssemblyCameraController({ controlsRef, focusRequestToken, groupRef, resetToken, selectedMesh }) {
  const { camera } = useThree();
  const desiredPositionRef = useRef(new THREE.Vector3(1.45, 0.35, 7.1));
  const desiredTargetRef = useRef(new THREE.Vector3(0, 0, 0));
  const isAnimatingRef = useRef(false);
  const defaultPositionRef = useRef(new THREE.Vector3(1.45, 0.35, 7.1));

  useEffect(() => {
    if (!controlsRef.current) {
      return;
    }

    camera.up.set(0, 1, 0);

    if (!selectedMesh || !groupRef.current) {
      return;
    }

    const worldTarget = groupRef.current.localToWorld(new THREE.Vector3(...selectedMesh.position));
    const largestDimension = Math.max(...selectedMesh.dimensions);
    const fitDistance =
      (largestDimension / 2) / Math.tan(THREE.MathUtils.degToRad((camera.fov || 30) / 2));
    const fallbackDistance = Math.max(fitDistance * 2.1, largestDimension * 2.4, 2.3);
    const currentDirection = camera.position.clone().sub(controlsRef.current.target);
    const normalizedDirection =
      currentDirection.lengthSq() > 0.0001
        ? currentDirection.normalize()
        : new THREE.Vector3(1.15, 0.82, 1.55).normalize();
    const preservedDistance = camera.position.distanceTo(controlsRef.current.target);
    const nextDistance =
      preservedDistance > 0.1
        ? THREE.MathUtils.clamp(preservedDistance, Math.max(largestDimension * 1.35, 1.6), 11.2)
        : fallbackDistance;
    const nextCameraPosition = worldTarget
      .clone()
      .add(normalizedDirection.multiplyScalar(Math.max(nextDistance, fallbackDistance * 0.82)));

    desiredTargetRef.current.copy(worldTarget);
    desiredPositionRef.current.copy(nextCameraPosition);
    isAnimatingRef.current = true;
  }, [camera, controlsRef, focusRequestToken, groupRef, selectedMesh]);

  useEffect(() => {
    if (!controlsRef.current) {
      return;
    }

    camera.up.set(0, 1, 0);
    desiredTargetRef.current.copy(new THREE.Vector3(0, 0, 0));
    desiredPositionRef.current.copy(defaultPositionRef.current);
    isAnimatingRef.current = true;
  }, [camera, controlsRef, resetToken]);

  useFrame((_, delta) => {
    if (!controlsRef.current || !isAnimatingRef.current) {
      return;
    }

    const controls = controlsRef.current;
    const smoothing = 1 - Math.exp(-delta * 7.5);

    camera.position.lerp(desiredPositionRef.current, smoothing);
    controls.target.lerp(desiredTargetRef.current, smoothing);
    camera.lookAt(controls.target);
    controls.update();

    if (
      camera.position.distanceToSquared(desiredPositionRef.current) < 0.0004 &&
      controls.target.distanceToSquared(desiredTargetRef.current) < 0.0004
    ) {
      camera.position.copy(desiredPositionRef.current);
      controls.target.copy(desiredTargetRef.current);
      camera.lookAt(controls.target);
      controls.update();
      isAnimatingRef.current = false;
    }
  });

  return null;
}

function AssemblyPanelMesh({
  displayMode,
  focusSelected,
  isHovered,
  isSelected,
  mesh,
  onHoverPart,
  onOpenPart,
  onSelectPart,
  selectedPartCode,
}) {
  const isDimmed = Boolean(selectedPartCode && !isSelected);
  const baseColor = new THREE.Color(mesh.color);
  const resolvedColor =
    displayMode === "transparent"
      ? baseColor.clone().lerp(new THREE.Color("#5f7f92"), 0.18).getStyle()
      : baseColor.getStyle();

  return (
    <mesh
      castShadow
      key={mesh.key}
      onClick={(event) => {
        event.stopPropagation();
        onSelectPart?.(mesh.item.export_code);
      }}
      onDoubleClick={(event) => {
        event.stopPropagation();
        onSelectPart?.(mesh.item.export_code);
        onOpenPart?.(mesh.item.export_code);
      }}
      onPointerOut={(event) => {
        event.stopPropagation();
        onHoverPart?.(null);
      }}
      onPointerOver={(event) => {
        event.stopPropagation();
        onHoverPart?.(mesh.item.export_code);
      }}
      position={mesh.position}
      receiveShadow
    >
      <boxGeometry args={mesh.dimensions} />
      <meshStandardMaterial
        color={resolvedColor}
        depthWrite={displayMode !== "transparent"}
        emissive={isSelected ? "#9df0b1" : isHovered ? "#b9e8ff" : "#000000"}
        emissiveIntensity={isSelected ? 0.26 : isHovered ? 0.12 : 0}
        metalness={0.04}
        opacity={
          isDimmed
            ? focusSelected
              ? displayMode === "transparent"
                ? 0.22
                : 0.34
              : displayMode === "transparent"
                ? 0.14
                : 0.24
            : displayMode === "transparent"
              ? isSelected
                ? 0.9
                : 0.78
              : 1
        }
        roughness={0.82}
        side={THREE.DoubleSide}
        transparent={
          displayMode === "transparent" || isDimmed
        }
      />
    </mesh>
  );
}

function ProjectAssemblyModel({
  controlsRef,
  displayMode,
  exploded,
  focusSelected,
  focusRequestToken,
  hoveredPartCode,
  items,
  onHoverPart,
  onOpenPart,
  onSelectPart,
  resetToken,
  selectedPartDetail,
  selectedPartCode,
  projectMeta,
  visibility,
  visualLayers,
}) {
  const groupRef = useRef(null);
  const assembly = useMemo(
    () => buildAssembly(items, exploded, visibility, projectMeta),
    [exploded, items, projectMeta, visibility],
  );
  const selectedMesh = useMemo(
    () => assembly.meshes.find((mesh) => mesh.item.export_code === selectedPartCode) || null,
    [assembly.meshes, selectedPartCode],
  );
  const canRenderOverlays =
    displayMode === "transparent" &&
    selectedMesh &&
    selectedPartCode &&
    selectedPartDetail?.part &&
    selectedPartDetail.part.export_code === selectedPartCode &&
    selectedMesh.surfaceAxes &&
    Array.isArray(selectedMesh.position) &&
    Array.isArray(selectedMesh.dimensions);
  const holeMarkers = useMemo(() => {
    if (
      !canRenderOverlays ||
      !visualLayers.holes ||
      !selectedPartDetail.holes?.length
    ) {
      return [];
    }

    const detailDimensions = normalizeDetailDimensions(selectedPartDetail.part);
    try {
      return selectedPartDetail.holes.map((hole) => ({
        key: `hole-${selectedPartCode}-${hole?.number ?? hole?.x ?? hole?.y ?? "item"}`,
        markerRadius: Math.max((Number(hole?.diameter) || 5) * 0.008, 0.03),
        position: holeMarkerPosition(hole, detailDimensions, selectedMesh),
      }));
    } catch {
      return [];
    }
  }, [canRenderOverlays, selectedMesh, selectedPartCode, selectedPartDetail, visualLayers.holes]);
  const grooveMeshes = useMemo(() => {
    if (
      !canRenderOverlays ||
      !visualLayers.grooves ||
      !selectedPartDetail.grooves?.length
    ) {
      return [];
    }

    const detailDimensions = normalizeDetailDimensions(selectedPartDetail.part);
    try {
      return selectedPartDetail.grooves
        .map((groove) => grooveOverlay(groove, detailDimensions, selectedMesh))
        .filter(Boolean);
    } catch {
      return [];
    }
  }, [canRenderOverlays, selectedMesh, selectedPartCode, selectedPartDetail, visualLayers.grooves]);
  const quarterMeshes = useMemo(() => {
    if (
      !canRenderOverlays ||
      !visualLayers.quarters ||
      !selectedPartDetail.quarters?.length
    ) {
      return [];
    }

    const detailDimensions = normalizeDetailDimensions(selectedPartDetail.part);
    try {
      return selectedPartDetail.quarters
        .map((quarter) => quarterOverlay(quarter, detailDimensions, selectedMesh))
        .filter(Boolean);
    } catch {
      return [];
    }
  }, [canRenderOverlays, selectedMesh, selectedPartCode, selectedPartDetail, visualLayers.quarters]);
  const visibleMeshes = useMemo(() => {
    if (displayMode === "transparent") {
      return assembly.meshes;
    }

    const internalDrawerKinds = new Set([
      "drawer-visual",
      "drawer-side-left",
      "drawer-side-right",
      "drawer-front-rail",
      "drawer-back-rail",
      "drawer-bottom",
    ]);

    return assembly.meshes.filter((mesh) => {
      if (mesh.item._kind === "drawer-visual") {
        return false;
      }

      if (!internalDrawerKinds.has(mesh.item._kind)) {
        return true;
      }

      return mesh.item.export_code === selectedPartCode || mesh.item.export_code === hoveredPartCode;
    });
  }, [assembly.meshes, displayMode, hoveredPartCode, selectedPartCode]);
  const visibleDrawerVisualMeshes = useMemo(() => {
    if (displayMode === "transparent") {
      return [];
    }

    return assembly.drawerVisualMeshes || [];
  }, [assembly.drawerVisualMeshes, displayMode]);

  return (
    <>
      <AssemblyCameraController
        controlsRef={controlsRef}
        focusRequestToken={focusRequestToken}
        groupRef={groupRef}
        resetToken={resetToken}
        selectedMesh={selectedMesh}
      />
      <group ref={groupRef} rotation={[0, 0.48, 0]}>
        {visibleMeshes.map((mesh) => (
          <AssemblyPanelMesh
            displayMode={displayMode}
            focusSelected={focusSelected}
            isHovered={hoveredPartCode === mesh.item.export_code}
            isSelected={selectedPartCode === mesh.item.export_code}
            key={mesh.key}
            mesh={mesh}
            onHoverPart={onHoverPart}
            onOpenPart={onOpenPart}
            onSelectPart={onSelectPart}
            selectedPartCode={selectedPartCode}
          />
        ))}
        {visibleDrawerVisualMeshes.map((mesh) => (
          <AssemblyPanelMesh
            displayMode={displayMode}
            focusSelected={focusSelected}
            isHovered={hoveredPartCode === mesh.item.export_code}
            isSelected={selectedPartCode === mesh.item.export_code}
            key={mesh.key}
            mesh={mesh}
            onHoverPart={onHoverPart}
            onOpenPart={onOpenPart}
            onSelectPart={onSelectPart}
            selectedPartCode={selectedPartCode}
          />
        ))}
      {holeMarkers.map((marker) => (
        <mesh key={marker.key} position={marker.position}>
          <cylinderGeometry args={[marker.markerRadius, marker.markerRadius, 0.032, 20]} />
          <meshStandardMaterial color="#ff33c4" emissive="#ff8de0" emissiveIntensity={0.3} />
        </mesh>
      ))}
      {grooveMeshes.map((groove) => (
        <mesh key={groove.key} position={groove.position}>
          <boxGeometry args={groove.size} />
          <meshStandardMaterial color="#ff6a6a" transparent opacity={0.82} />
        </mesh>
      ))}
      {quarterMeshes.map((quarter) => (
        <mesh key={quarter.key} position={quarter.position}>
          <boxGeometry args={quarter.size} />
          <meshStandardMaterial color="#f3b300" transparent opacity={0.68} />
        </mesh>
      ))}
      </group>
    </>
  );
}

export default function ProjectThreeViewer({
  hoveredPartCode: hoveredPartCodeProp,
  items,
  onClearSelection,
  onHoverPartChange,
  onOpenPart,
  onSelectPart,
  projectMeta,
  selectedPartDetail,
  selectedPartCode,
  t,
}) {
  const controlsRef = useRef(null);
  const [displayMode, setDisplayMode] = useState("solid");
  const [exploded, setExploded] = useState(false);
  const [focusSelected, setFocusSelected] = useState(false);
  const [focusRequestToken, setFocusRequestToken] = useState(0);
  const [hoveredPartCode, setHoveredPartCode] = useState(null);
  const [resetToken, setResetToken] = useState(0);
  const [visibility, setVisibility] = useState({
    back: true,
    carcass: true,
    drawers: true,
    facades: true,
    other: true,
  });
  const [visualLayers, setVisualLayers] = useState({
    holes: true,
    grooves: true,
    quarters: true,
  });

  if (!items?.length) {
    return null;
  }

  const selectedItem = selectedPartCode
    ? items.find((item) => item.export_code === selectedPartCode) || null
    : null;
  const canRenderOverlays =
    displayMode === "transparent" &&
    Boolean(selectedPartCode) &&
    Boolean(selectedPartDetail?.part) &&
    selectedPartDetail.part.export_code === selectedPartCode;
  const labels = {
    assemblyAssembled: getLabel(t?.assemblyAssembled, "Assembled"),
    assemblyClearSelection: getLabel(t?.assemblyClearSelection, "Clear selection"),
    assemblyExploded: getLabel(t?.assemblyExploded, "Exploded"),
    assemblyFocusSelected: getLabel(t?.assemblyFocusSelected, "Focus selected"),
    assemblyGroupBack: getLabel(t?.assemblyGroupBack, "Back panel"),
    assemblyGroupCarcass: getLabel(t?.assemblyGroupCarcass, "Carcass"),
    assemblyGroupDrawers: getLabel(t?.assemblyGroupDrawers, "Drawers"),
    assemblyGroupFacades: getLabel(t?.assemblyGroupFacades, "Facades"),
    assemblyGroupOther: getLabel(t?.assemblyGroupOther, "Other panels"),
    assemblyLayerGrooves: getLabel(t?.assemblyLayerGrooves, "Grooves"),
    assemblyLayerHoles: getLabel(t?.assemblyLayerHoles, "Holes"),
    assemblyLayerQuarters: getLabel(t?.assemblyLayerQuarters, "Quarters"),
    assemblyModeSolid: getLabel(t?.assemblyModeSolid, "Solid"),
    assemblyModeTransparent: getLabel(t?.assemblyModeTransparent, "Transparent + holes"),
    assemblyOpenWorkspace: getLabel(t?.assemblyOpenWorkspace, "Open detail workspace"),
    assemblyResetCamera: getLabel(t?.assemblyResetCamera, "Reset camera"),
    assemblyShowAll: getLabel(t?.assemblyShowAll, "Show all"),
    assemblyShowFull: getLabel(t?.assemblyShowFull, "Show full assembly"),
    preview3dInteractiveHint: getLabel(t?.preview3dInteractiveHint, "LMB rotate, RMB move, wheel zoom."),
  };
  const effectiveHoveredPartCode = hoveredPartCodeProp ?? hoveredPartCode;
  const hoveredItem = effectiveHoveredPartCode
    ? items.find((item) => item.export_code === effectiveHoveredPartCode) || null
    : null;

  function handleHoverPart(partCode) {
    setHoveredPartCode(partCode);
    onHoverPartChange?.(partCode);
  }

  function toggleGroup(group) {
    setVisibility((current) => ({
      ...current,
      [group]: !current[group],
    }));
  }

  function showAll() {
    setVisibility({
      back: true,
      carcass: true,
      drawers: true,
      facades: true,
      other: true,
    });
  }

  function handleFocusSelected() {
    if (!selectedPartCode) {
      return;
    }

    if (focusSelected) {
      setFocusSelected(false);
      return;
    }

    setFocusSelected(true);
    setFocusRequestToken((current) => current + 1);
  }

  function handleClearSelection() {
    setFocusSelected(false);
    onClearSelection?.();
  }

  function handleResetCamera() {
    setFocusSelected(false);
    setResetToken((current) => current + 1);
  }

  function toggleLayer(layer) {
    setVisualLayers((current) => ({
      ...current,
      [layer]: !current[layer],
    }));
  }

  const groupLabels = {
    back: labels.assemblyGroupBack,
    carcass: labels.assemblyGroupCarcass,
    drawers: labels.assemblyGroupDrawers,
    facades: labels.assemblyGroupFacades,
    other: labels.assemblyGroupOther,
  };

  return (
    <section className="project-three-viewer">
      <div className="project-three-viewer-toolbar">
        <div className="project-three-viewer-mode-groups">
          <div className="project-three-viewer-segment" role="tablist" aria-label={labels.assemblyModeSolid}>
            <ModeIconButton
              active={displayMode === "solid"}
              onClick={() => setDisplayMode("solid")}
              title={labels.assemblyModeSolid}
            >
              <SolidViewIcon />
            </ModeIconButton>
            <ModeIconButton
              active={displayMode === "transparent"}
              onClick={() => setDisplayMode("transparent")}
              title={labels.assemblyModeTransparent}
            >
              <TransparentViewIcon />
            </ModeIconButton>
          </div>

          <div className="project-three-viewer-segment" role="tablist" aria-label={labels.assemblyAssembled}>
            <ModeIconButton
              active={!exploded}
              onClick={() => setExploded(false)}
              title={labels.assemblyAssembled}
            >
              <AssembledViewIcon />
            </ModeIconButton>
            <ModeIconButton
              active={exploded}
              onClick={() => setExploded(true)}
              title={labels.assemblyExploded}
            >
              <ExplodedViewIcon />
            </ModeIconButton>
          </div>
        </div>
        <div className="project-three-viewer-filters">
          <button onClick={showAll} type="button">
            {labels.assemblyShowAll}
          </button>
          {VISIBILITY_GROUPS.map((group) => (
            <button
              className={visibility[group] ? "active" : ""}
              key={group}
              onClick={() => toggleGroup(group)}
              type="button"
            >
              {groupLabels[group]}
            </button>
          ))}
        </div>
        {displayMode === "transparent" && selectedPartCode && selectedPartDetail?.part?.export_code === selectedPartCode ? (
          <div className="project-three-viewer-toggle">
            {VISUAL_LAYERS.map((layer) => (
              <button
                className={visualLayers[layer] ? "active" : ""}
                key={layer}
                onClick={() => toggleLayer(layer)}
                type="button"
              >
                {layer === "holes"
                  ? labels.assemblyLayerHoles
                  : layer === "grooves"
                    ? labels.assemblyLayerGrooves
                    : labels.assemblyLayerQuarters}
              </button>
            ))}
          </div>
        ) : null}
        {selectedPartCode ? (
          <div className="project-three-viewer-actions">
          <button
            className={focusSelected ? "active" : ""}
            onClick={handleFocusSelected}
            type="button"
          >
            {focusSelected
              ? labels.assemblyShowFull
              : labels.assemblyFocusSelected}
          </button>
          <button onClick={() => onOpenPart?.(selectedPartCode)} type="button">
            {labels.assemblyOpenWorkspace}
          </button>
          <button onClick={handleResetCamera} type="button">
            {labels.assemblyResetCamera}
          </button>
          <button onClick={handleClearSelection} type="button">
            {labels.assemblyClearSelection}
          </button>
          </div>
        ) : null}
      </div>
      <div className="project-three-viewer-canvas">
        {hoveredItem ? (
          <div className="project-three-viewer-tooltip">
            <strong>{hoveredItem.export_code}</strong>
            <span>{hoveredItem.part_name}</span>
            <span>
              {hoveredItem.width} x {hoveredItem.height} x {hoveredItem.thickness || 18}
            </span>
          </div>
        ) : null}
        <ProjectThreeViewerErrorBoundary
          items={items}
          selectedPartCode={selectedPartCode}
          t={t}
        >
          <Canvas camera={{ fov: 26, position: [1.45, 0.35, 7.1] }} shadows>
            <color attach="background" args={[displayMode === "transparent" ? "#d6e3eb" : "#eef4f7"]} />
            <ambientLight intensity={0.74} />
            <directionalLight castShadow intensity={1.18} position={[5.2, 7.8, 5.4]} shadow-mapSize-width={2048} shadow-mapSize-height={2048} />
            <directionalLight intensity={0.3} position={[-4, 2.2, -3.5]} />
            <hemisphereLight groundColor="#d6e0e7" intensity={0.42} skyColor="#ffffff" />
            {displayMode === "transparent" ? (
              <gridHelper args={[8, 12, "#b4c6d3", "#cfdce5"]} position={[0, -2.05, 0]} />
            ) : null}
            <mesh position={[0, -2.04, 0]} receiveShadow rotation={[-Math.PI / 2, 0, 0]}>
              <planeGeometry args={[10, 10]} />
              <shadowMaterial opacity={0.14} transparent />
            </mesh>
            <ProjectAssemblyModel
              controlsRef={controlsRef}
              displayMode={displayMode}
              exploded={exploded}
              focusSelected={focusSelected}
              focusRequestToken={focusRequestToken}
              hoveredPartCode={effectiveHoveredPartCode}
              items={items}
              onHoverPart={handleHoverPart}
              onOpenPart={onOpenPart}
              onSelectPart={onSelectPart}
              projectMeta={projectMeta}
              resetToken={resetToken}
              selectedPartDetail={selectedPartDetail}
              selectedPartCode={selectedPartCode}
              visibility={visibility}
              visualLayers={visualLayers}
            />
            <OrbitControls
              ref={controlsRef}
              enableDamping
              dampingFactor={0.08}
              enablePan
              maxDistance={12}
              maxPolarAngle={Math.PI * 0.88}
              mouseButtons={{
                LEFT: THREE.MOUSE.ROTATE,
                MIDDLE: THREE.MOUSE.DOLLY,
                RIGHT: THREE.MOUSE.PAN,
              }}
              minDistance={3}
              minPolarAngle={Math.PI * 0.12}
              screenSpacePanning
              target={[0, 0, 0]}
            />
          </Canvas>
        </ProjectThreeViewerErrorBoundary>
      </div>
      <div className="project-three-viewer-meta">
        <span className="project-three-viewer-badge">
          {items.length} {t.details}
        </span>
        {selectedPartCode ? (
          <span className="project-three-viewer-badge active">
            {t.cuttingExportCode}: {selectedPartCode}
          </span>
        ) : null}
        {selectedItem?.part_name ? (
          <span className="project-three-viewer-badge">
            {selectedItem.part_name}
          </span>
        ) : null}
        {canRenderOverlays ? (
          <span className="project-three-viewer-badge">
            {selectedPartDetail.holes?.length || 0} {t.holes || "holes"}
          </span>
        ) : null}
        {canRenderOverlays ? (
          <span className="project-three-viewer-badge">
            {selectedPartDetail.grooves?.length || 0} grooves
          </span>
        ) : null}
        {canRenderOverlays ? (
          <span className="project-three-viewer-badge">
            {selectedPartDetail.quarters?.length || 0} quarters
          </span>
        ) : null}
      </div>
      {canRenderOverlays ? (
        <div className="project-three-viewer-legend">
          <span className="project-three-viewer-legend-item">
            <span className="project-three-viewer-legend-swatch holes" />
            {labels.assemblyLayerHoles}
          </span>
          <span className="project-three-viewer-legend-item">
            <span className="project-three-viewer-legend-swatch grooves" />
            {labels.assemblyLayerGrooves}
          </span>
          <span className="project-three-viewer-legend-item">
            <span className="project-three-viewer-legend-swatch quarters" />
            {labels.assemblyLayerQuarters}
          </span>
        </div>
      ) : null}
      <p className="project-three-viewer-hint">
        {labels.preview3dInteractiveHint}
      </p>
    </section>
  );
}
