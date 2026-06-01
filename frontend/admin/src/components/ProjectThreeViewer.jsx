import { Canvas, useThree } from "@react-three/fiber";
import { Edges, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

const VISIBILITY_GROUPS = ["carcass", "facades", "drawers", "back", "other"];
const VISUAL_LAYERS = ["holes", "grooves", "quarters"];
const AXIS_INDEX = { x: 0, y: 1, z: 2 };

function getPanelColor(item) {
  const category = String(item?.category || "").toLowerCase();
  const name = String(item?.part_name || "").toLowerCase();

  if (category.includes("facade") || name.includes("facade")) {
    return "#efe7db";
  }

  if (category.includes("drawer") || name.includes("drawer")) {
    return "#eaf1f6";
  }

  if (category.includes("back") || name.includes("back")) {
    return "#eef2ff";
  }

  return "#f7f9fb";
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

  return "other";
}

function groupByKind(kind) {
  if (kind === "facade") {
    return "facades";
  }

  if (kind === "drawer") {
    return "drawers";
  }

  if (kind === "back") {
    return "back";
  }

  if (["side-left", "side-right", "top", "bottom", "shelf"].includes(kind)) {
    return "carcass";
  }

  return "other";
}

function normalizeDetailDimensions(part) {
  return {
    height: Math.max(Number(part?.height) || 1, 1),
    thickness: Math.max(Number(part?.thickness) || 18, 1),
    width: Math.max(Number(part?.width) || 1, 1),
  };
}

function holeMarkerPosition(hole, detailDimensions, mesh) {
  return projectSurfacePoint(
    {
      heightRatio: Math.min(Math.max((Number(hole?.y) || 0) / detailDimensions.height, 0), 1),
      normalOffset: 0,
      widthRatio: Math.min(Math.max((Number(hole?.x) || 0) / detailDimensions.width, 0), 1),
    },
    mesh,
  );
}

function projectSurfacePoint(point, mesh) {
  if (!mesh?.surfaceAxes) {
    return mesh?.position || [0, 0, 0];
  }

  const position = [...mesh.position];
  const [dimX, dimY, dimZ] = mesh.dimensions;
  const dimensionByAxis = { x: dimX, y: dimY, z: dimZ };

  position[AXIS_INDEX[mesh.surfaceAxes.width]] +=
    -dimensionByAxis[mesh.surfaceAxes.width] / 2 + point.widthRatio * dimensionByAxis[mesh.surfaceAxes.width];
  position[AXIS_INDEX[mesh.surfaceAxes.height]] +=
    -dimensionByAxis[mesh.surfaceAxes.height] / 2 + point.heightRatio * dimensionByAxis[mesh.surfaceAxes.height];
  position[AXIS_INDEX[mesh.surfaceAxes.normal]] += point.normalOffset || 0;

  return position;
}

function grooveOverlay(groove, detailDimensions, mesh) {
  const widthRatio = Math.min(Math.max((Number(groove?.x) || 0) / detailDimensions.width, 0), 1);
  const heightRatio = Math.min(Math.max((Number(groove?.y) || 0) / detailDimensions.height, 0), 1);
  const grooveWidth = Math.max(((Number(groove?.length) || 0) / detailDimensions.width) * mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.width]], 0.08);
  const grooveHeight = Math.max(((Number(groove?.width) || 0) / detailDimensions.height) * mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.height]], 0.03);

  return {
    key: `groove-${groove.number}`,
    position: projectSurfacePoint(
      {
        heightRatio,
        normalOffset: 0.004,
        widthRatio: Math.min(widthRatio + grooveWidth / mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.width]] / 2, 1),
      },
      mesh,
    ),
    size: mesh.surfaceAxes.normal === "x"
      ? [0.03, grooveHeight, grooveWidth]
      : mesh.surfaceAxes.normal === "y"
        ? [grooveWidth, 0.03, grooveHeight]
        : [grooveWidth, grooveHeight, 0.03],
  };
}

function quarterOverlay(quarter, detailDimensions, mesh) {
  const widthRatio = Math.min(Math.max((Number(quarter?.x) || 0) / detailDimensions.width, 0), 1);
  const heightRatio = Math.min(Math.max((Number(quarter?.y) || 0) / detailDimensions.height, 0), 1);
  const quarterWidth = Math.max(((Number(quarter?.length) || 0) / detailDimensions.width) * mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.width]], 0.08);
  const quarterHeight = Math.max(((Number(quarter?.width) || 0) / detailDimensions.height) * mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.height]], 0.04);
  const quarterDepth = Math.max(((Number(quarter?.depth) || 0) / detailDimensions.thickness) * Math.max(mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.normal]], 0.05), 0.03);

  return {
    key: `quarter-${quarter.number}`,
    position: projectSurfacePoint(
      {
        heightRatio: Math.min(heightRatio + quarterHeight / mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.height]] / 2, 1),
        normalOffset: -quarterDepth / 3,
        widthRatio: Math.min(widthRatio + quarterWidth / mesh.dimensions[AXIS_INDEX[mesh.surfaceAxes.width]] / 2, 1),
      },
      mesh,
    ),
    size: mesh.surfaceAxes.normal === "x"
      ? [quarterDepth, quarterHeight, quarterWidth]
      : mesh.surfaceAxes.normal === "y"
        ? [quarterWidth, quarterDepth, quarterHeight]
        : [quarterWidth, quarterHeight, quarterDepth],
  };
}

function buildAssembly(items, exploded, visibility, selectedPartCode, focusSelected) {
  const normalizedItems = items.map((item, index) => ({
    ...item,
    _index: index,
    _kind: classifyItem(item),
    _width: Math.max(Number(item.width) || 1, 1),
    _height: Math.max(Number(item.height) || 1, 1),
    _thickness: Math.max(Number(item.thickness) || 18, 1),
  }));

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
  const cabinetDepth = Math.max(...normalizedItems.map((item) => item._height), 420);
  const largest = Math.max(cabinetWidth, cabinetHeight, cabinetDepth);
  const scale = 3.4 / largest;
  const widthUnits = cabinetWidth * scale;
  const heightUnits = cabinetHeight * scale;
  const depthUnits = cabinetDepth * scale;
  const gap = exploded ? 0.48 : 0.08;
  const spread = exploded ? 0.42 : 0;

  let facadeOffset = 0;
  let drawerOffset = 0;
  let shelfLevel = 0;
  let otherColumn = 0;

  const meshes = normalizedItems
    .filter((item) => visibility[groupByKind(item._kind)] !== false)
    .filter((item) => !focusSelected || !selectedPartCode || item.export_code === selectedPartCode)
    .map((item, index) => {
      const thickness = item._thickness * scale;
      const width = item._width * scale;
      const height = item._height * scale;
      const color = getPanelColor(item);
      let dimensions = [width, height, thickness];
      let position = [0, 0, 0];
      let surfaceAxes = {
        height: "y",
        normal: "z",
        width: "x",
      };

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
          dimensions = [widthUnits - 2 * thickness, heightUnits - 2 * thickness, thickness * 0.5];
          position = [0, 0, -depthUnits / 2 - thickness * 0.25 - spread];
          surfaceAxes = {
            height: "y",
            normal: "z",
            width: "x",
          };
          break;
        case "shelf":
          dimensions = [Math.min(widthUnits - 2 * thickness, width), thickness, Math.min(depthUnits, height)];
          position = [0, -heightUnits / 2 + 0.34 + shelfLevel * 0.42, exploded ? (shelfLevel % 2 === 0 ? -spread * 0.35 : spread * 0.35) : 0];
          shelfLevel += 1;
          surfaceAxes = {
            height: "z",
            normal: "y",
            width: "x",
          };
          break;
        case "facade":
          dimensions = [Math.min(widthUnits * 0.48, width), Math.min(heightUnits * 0.38, height), thickness];
          position = [
            facadeOffset % 2 === 0 ? -widthUnits * 0.24 - spread * 0.2 : widthUnits * 0.24 + spread * 0.2,
            heightUnits / 2 - 0.46 - Math.floor(facadeOffset / 2) * 0.52,
            depthUnits / 2 + thickness / 2 + gap,
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
            Math.min(widthUnits * 0.42, width),
            Math.min(heightUnits * 0.18, height),
            Math.min(depthUnits * 0.75, height),
          ];
          position = [
            drawerOffset % 2 === 0 ? -widthUnits * 0.22 - spread * 0.16 : widthUnits * 0.22 + spread * 0.16,
            -0.18 - Math.floor(drawerOffset / 2) * 0.34,
            depthUnits / 2 + dimensions[2] / 2 + (exploded ? 0.82 : 0.3),
          ];
          drawerOffset += 1;
          surfaceAxes = {
            height: "y",
            normal: "z",
            width: "x",
          };
          break;
        default:
          dimensions = [width, Math.max(thickness, 0.04), height];
          position = [
            widthUnits / 2 + 0.42 + (otherColumn % 2) * 0.34 + spread * 0.25,
            heightUnits / 2 - 0.34 - Math.floor(otherColumn / 2) * 0.26,
            0,
          ];
          otherColumn += 1;
          surfaceAxes = {
            height: "z",
            normal: "y",
            width: "x",
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

  return { meshes };
}

function AssemblyCameraController({ controlsRef, focusSelected, groupRef, selectedMesh }) {
  const { camera } = useThree();

  useEffect(() => {
    if (!controlsRef.current) {
      return;
    }

    const controls = controlsRef.current;
    const defaultTarget = new THREE.Vector3(0, 0, 0);
    const defaultPosition = new THREE.Vector3(0, 0, 7.8);

    if (!focusSelected || !selectedMesh || !groupRef.current) {
      controls.target.copy(defaultTarget);
      camera.position.copy(defaultPosition);
      camera.lookAt(defaultTarget);
      controls.update();
      return;
    }

    const worldTarget = groupRef.current.localToWorld(new THREE.Vector3(...selectedMesh.position));
    const direction = camera.position.clone().sub(controls.target);

    if (direction.lengthSq() < 0.001) {
      direction.set(1.6, 1.1, 2.8);
    }

    direction.normalize();

    const radius = Math.max(...selectedMesh.dimensions) * 2.2;
    const nextCameraPosition = worldTarget.clone().add(direction.multiplyScalar(Math.max(radius, 1.4)));

    controls.target.copy(worldTarget);
    camera.position.copy(nextCameraPosition);
    camera.lookAt(worldTarget);
    controls.update();
  }, [camera, controlsRef, focusSelected, groupRef, selectedMesh]);

  return null;
}

function ProjectAssemblyModel({
  controlsRef,
  displayMode,
  exploded,
  focusSelected,
  items,
  onHoverPart,
  onSelectPart,
  selectedPartDetail,
  selectedPartCode,
  visibility,
  visualLayers,
}) {
  const groupRef = useRef(null);
  const assembly = useMemo(
    () => buildAssembly(items, exploded, visibility, selectedPartCode, focusSelected),
    [exploded, focusSelected, items, selectedPartCode, visibility],
  );
  const selectedMesh = useMemo(
    () => assembly.meshes.find((mesh) => mesh.item.export_code === selectedPartCode) || null,
    [assembly.meshes, selectedPartCode],
  );
  const holeMarkers = useMemo(() => {
    if (
      displayMode !== "transparent" ||
      !visualLayers.holes ||
      !selectedMesh ||
      !selectedPartDetail?.part ||
      selectedPartDetail.part.export_code !== selectedPartCode ||
      !selectedPartDetail.holes?.length
    ) {
      return [];
    }

    const detailDimensions = normalizeDetailDimensions(selectedPartDetail.part);

    return selectedPartDetail.holes.map((hole) => ({
      key: `hole-${selectedPartCode}-${hole.number}`,
      markerRadius: Math.max((Number(hole.diameter) || 5) * 0.008, 0.03),
      position: holeMarkerPosition(hole, detailDimensions, selectedMesh),
    }));
  }, [displayMode, selectedMesh, selectedPartCode, selectedPartDetail, visualLayers.holes]);
  const grooveMeshes = useMemo(() => {
    if (
      displayMode !== "transparent" ||
      !visualLayers.grooves ||
      !selectedMesh ||
      !selectedPartDetail?.part ||
      selectedPartDetail.part.export_code !== selectedPartCode ||
      !selectedPartDetail.grooves?.length
    ) {
      return [];
    }

    const detailDimensions = normalizeDetailDimensions(selectedPartDetail.part);

    return selectedPartDetail.grooves.map((groove) => grooveOverlay(groove, detailDimensions, selectedMesh));
  }, [displayMode, selectedMesh, selectedPartCode, selectedPartDetail, visualLayers.grooves]);
  const quarterMeshes = useMemo(() => {
    if (
      displayMode !== "transparent" ||
      !visualLayers.quarters ||
      !selectedMesh ||
      !selectedPartDetail?.part ||
      selectedPartDetail.part.export_code !== selectedPartCode ||
      !selectedPartDetail.quarters?.length
    ) {
      return [];
    }

    const detailDimensions = normalizeDetailDimensions(selectedPartDetail.part);

    return selectedPartDetail.quarters.map((quarter) => quarterOverlay(quarter, detailDimensions, selectedMesh));
  }, [displayMode, selectedMesh, selectedPartCode, selectedPartDetail, visualLayers.quarters]);

  return (
    <>
      <AssemblyCameraController
        controlsRef={controlsRef}
        focusSelected={focusSelected}
        groupRef={groupRef}
        selectedMesh={selectedMesh}
      />
      <group ref={groupRef} rotation={[-0.4, 0.72, 0]}>
      {assembly.meshes.map((mesh) => (
        <mesh
          key={mesh.key}
          onClick={(event) => {
            event.stopPropagation();
            onSelectPart?.(mesh.item.export_code);
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
          scale={selectedPartCode === mesh.item.export_code ? [1.03, 1.03, 1.03] : [1, 1, 1]}
        >
          <boxGeometry args={mesh.dimensions} />
          <meshStandardMaterial
            color={mesh.color}
            emissive={selectedPartCode === mesh.item.export_code ? "#9df0b1" : "#000000"}
            emissiveIntensity={selectedPartCode === mesh.item.export_code ? 0.34 : 0}
            metalness={0.08}
            opacity={
              selectedPartCode && selectedPartCode !== mesh.item.export_code && !focusSelected
                ? displayMode === "transparent"
                  ? 0.12
                  : 0.24
                : displayMode === "transparent"
                  ? selectedPartCode === mesh.item.export_code
                    ? 0.72
                    : 0.46
                  : 1
            }
            roughness={0.72}
            transparent={
              displayMode === "transparent" ||
              Boolean(
                selectedPartCode && selectedPartCode !== mesh.item.export_code && !focusSelected,
              )
            }
          />
          <Edges
            color={
              selectedPartCode === mesh.item.export_code
                ? "#117a29"
                : selectedPartCode && !focusSelected
                  ? "#90a2af"
                  : "#22313e"
            }
            lineWidth={1}
          />
        </mesh>
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
  items,
  onClearSelection,
  onOpenPart,
  onSelectPart,
  selectedPartDetail,
  selectedPartCode,
  t,
}) {
  const controlsRef = useRef(null);
  const [displayMode, setDisplayMode] = useState("solid");
  const [exploded, setExploded] = useState(false);
  const [focusSelected, setFocusSelected] = useState(false);
  const [hoveredPartCode, setHoveredPartCode] = useState(null);
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
  const hoveredItem = hoveredPartCode
    ? items.find((item) => item.export_code === hoveredPartCode) || null
    : null;

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

    setFocusSelected((current) => !current);
  }

  function handleClearSelection() {
    setFocusSelected(false);
    onClearSelection?.();
  }

  function toggleLayer(layer) {
    setVisualLayers((current) => ({
      ...current,
      [layer]: !current[layer],
    }));
  }

  const groupLabels = {
    back: t.assemblyGroupBack,
    carcass: t.assemblyGroupCarcass,
    drawers: t.assemblyGroupDrawers,
    facades: t.assemblyGroupFacades,
    other: t.assemblyGroupOther,
  };

  return (
    <section className="project-three-viewer">
      <div className="project-three-viewer-toolbar">
        <div className="project-three-viewer-toggle">
          <button
            className={displayMode === "solid" ? "active" : ""}
            onClick={() => setDisplayMode("solid")}
            type="button"
          >
            {t.assemblyModeSolid || "Solid"}
          </button>
          <button
            className={displayMode === "transparent" ? "active" : ""}
            onClick={() => setDisplayMode("transparent")}
            type="button"
          >
            {t.assemblyModeTransparent || "Transparent + holes"}
          </button>
        </div>
        <div className="project-three-viewer-toggle">
          <button
            className={!exploded ? "active" : ""}
            onClick={() => setExploded(false)}
            type="button"
          >
            {t.assemblyAssembled}
          </button>
          <button
            className={exploded ? "active" : ""}
            onClick={() => setExploded(true)}
            type="button"
          >
            {t.assemblyExploded}
          </button>
        </div>
        <div className="project-three-viewer-filters">
          <button onClick={showAll} type="button">
            {t.assemblyShowAll}
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
                {layer}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {selectedPartCode ? (
        <div className="project-three-viewer-actions">
          <button
            className={focusSelected ? "active" : ""}
            onClick={handleFocusSelected}
            type="button"
          >
            {focusSelected
              ? (t.assemblyShowFull || "Show full assembly")
              : (t.assemblyFocusSelected || "Focus selected")}
          </button>
          <button onClick={() => onOpenPart?.(selectedPartCode)} type="button">
            {t.assemblyOpenWorkspace || "Open detail workspace"}
          </button>
          <button onClick={handleClearSelection} type="button">
            {t.assemblyClearSelection || "Clear selection"}
          </button>
        </div>
      ) : null}
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
        <Canvas camera={{ fov: 30, position: [0, 0, 7.8] }} shadows>
          <color attach="background" args={["#f7fbfc"]} />
          <ambientLight intensity={0.96} />
          <directionalLight castShadow intensity={1.24} position={[6, 7, 6]} />
          <directionalLight intensity={0.3} position={[-4, -3, 4]} />
          <ProjectAssemblyModel
            controlsRef={controlsRef}
            displayMode={displayMode}
            exploded={exploded}
            focusSelected={focusSelected}
            items={items}
            onHoverPart={setHoveredPartCode}
            onSelectPart={onSelectPart}
            selectedPartDetail={selectedPartDetail}
            selectedPartCode={selectedPartCode}
            visibility={visibility}
            visualLayers={visualLayers}
          />
          <OrbitControls
            ref={controlsRef}
            enablePan={false}
            maxDistance={12}
            minDistance={3}
            target={[0, 0, 0]}
          />
        </Canvas>
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
        {displayMode === "transparent" && selectedPartDetail?.part?.export_code === selectedPartCode ? (
          <span className="project-three-viewer-badge">
            {selectedPartDetail.holes?.length || 0} {t.holes || "holes"}
          </span>
        ) : null}
        {displayMode === "transparent" && selectedPartDetail?.part?.export_code === selectedPartCode ? (
          <span className="project-three-viewer-badge">
            {selectedPartDetail.grooves?.length || 0} grooves
          </span>
        ) : null}
        {displayMode === "transparent" && selectedPartDetail?.part?.export_code === selectedPartCode ? (
          <span className="project-three-viewer-badge">
            {selectedPartDetail.quarters?.length || 0} quarters
          </span>
        ) : null}
      </div>
      <p className="project-three-viewer-hint">{t.productionAssemblyHint}</p>
    </section>
  );
}
