import { Canvas } from "@react-three/fiber";
import { Edges, OrbitControls } from "@react-three/drei";
import { useMemo } from "react";

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

  if (name.includes("left side") || name.includes("side left") || name.includes("side panel left") || name.includes("бок ліва") || name.includes("боковина ліва")) {
    return "side-left";
  }

  if (name.includes("right side") || name.includes("side right") || name.includes("side panel right") || name.includes("бок права") || name.includes("боковина права")) {
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

function buildAssembly(items) {
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
  const gap = 0.08;

  let facadeOffset = 0;
  let drawerOffset = 0;
  let shelfLevel = 0;
  let otherColumn = 0;

  const meshes = normalizedItems.map((item, index) => {
    const thickness = item._thickness * scale;
    const width = item._width * scale;
    const height = item._height * scale;
    const color = getPanelColor(item);
    let dimensions = [width, height, thickness];
    let position = [0, 0, 0];

    switch (item._kind) {
      case "side-left":
        dimensions = [thickness, heightUnits, depthUnits];
        position = [-widthUnits / 2 + thickness / 2, 0, 0];
        break;
      case "side-right":
        dimensions = [thickness, heightUnits, depthUnits];
        position = [widthUnits / 2 - thickness / 2, 0, 0];
        break;
      case "top":
        dimensions = [widthUnits - 2 * thickness, thickness, depthUnits];
        position = [0, heightUnits / 2 - thickness / 2, 0];
        break;
      case "bottom":
        dimensions = [widthUnits - 2 * thickness, thickness, depthUnits];
        position = [0, -heightUnits / 2 + thickness / 2, 0];
        break;
      case "back":
        dimensions = [widthUnits - 2 * thickness, heightUnits - 2 * thickness, thickness * 0.5];
        position = [0, 0, -depthUnits / 2 - thickness * 0.25];
        break;
      case "shelf":
        dimensions = [Math.min(widthUnits - 2 * thickness, width), thickness, Math.min(depthUnits, height)];
        position = [0, -heightUnits / 2 + 0.34 + shelfLevel * 0.42, 0];
        shelfLevel += 1;
        break;
      case "facade":
        dimensions = [Math.min(widthUnits * 0.48, width), Math.min(heightUnits * 0.38, height), thickness];
        position = [
          facadeOffset % 2 === 0 ? -widthUnits * 0.24 : widthUnits * 0.24,
          heightUnits / 2 - 0.46 - Math.floor(facadeOffset / 2) * 0.52,
          depthUnits / 2 + thickness / 2 + gap,
        ];
        facadeOffset += 1;
        break;
      case "drawer":
        dimensions = [Math.min(widthUnits * 0.42, width), Math.min(heightUnits * 0.18, height), Math.min(depthUnits * 0.75, height)];
        position = [
          drawerOffset % 2 === 0 ? -widthUnits * 0.22 : widthUnits * 0.22,
          -0.18 - Math.floor(drawerOffset / 2) * 0.34,
          depthUnits / 2 + dimensions[2] / 2 + 0.3,
        ];
        drawerOffset += 1;
        break;
      default:
        dimensions = [width, Math.max(thickness, 0.04), height];
        position = [
          widthUnits / 2 + 0.42 + (otherColumn % 2) * 0.34,
          heightUnits / 2 - 0.34 - Math.floor(otherColumn / 2) * 0.26,
          0,
        ];
        otherColumn += 1;
        break;
    }

    return {
      color,
      dimensions,
      item,
      key: `${item.export_code}-${index}`,
      position,
      selected: false,
    };
  });

  return {
    bounds: {
      depthUnits,
      heightUnits,
      widthUnits,
    },
    meshes,
  };
}

function ProjectAssemblyModel({ items, onSelectPart, selectedPartCode }) {
  const assembly = useMemo(() => buildAssembly(items), [items]);

  return (
    <group rotation={[-0.4, 0.72, 0]}>
      {assembly.meshes.map((mesh) => (
        <mesh
          key={mesh.key}
          onClick={(event) => {
            event.stopPropagation();
            onSelectPart?.(mesh.item.export_code);
          }}
          position={mesh.position}
          scale={selectedPartCode === mesh.item.export_code ? [1.02, 1.02, 1.02] : [1, 1, 1]}
        >
          <boxGeometry args={mesh.dimensions} />
          <meshStandardMaterial
            color={mesh.color}
            emissive={selectedPartCode === mesh.item.export_code ? "#9df0b1" : "#000000"}
            emissiveIntensity={selectedPartCode === mesh.item.export_code ? 0.3 : 0}
            metalness={0.08}
            roughness={0.72}
          />
          <Edges color={selectedPartCode === mesh.item.export_code ? "#117a29" : "#22313e"} lineWidth={1} />
        </mesh>
      ))}
    </group>
  );
}

export default function ProjectThreeViewer({
  items,
  onSelectPart,
  selectedPartCode,
  t,
}) {
  if (!items?.length) {
    return null;
  }

  return (
    <section className="project-three-viewer">
      <div className="project-three-viewer-canvas">
        <Canvas camera={{ fov: 30, position: [0, 0, 7.8] }} shadows>
          <color attach="background" args={["#f7fbfc"]} />
          <ambientLight intensity={0.96} />
          <directionalLight castShadow intensity={1.24} position={[6, 7, 6]} />
          <directionalLight intensity={0.3} position={[-4, -3, 4]} />
          <ProjectAssemblyModel
            items={items}
            onSelectPart={onSelectPart}
            selectedPartCode={selectedPartCode}
          />
          <OrbitControls enablePan={false} maxDistance={12} minDistance={3} target={[0, 0, 0]} />
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
      </div>
      <p className="project-three-viewer-hint">
        {t.productionAssemblyHint}
      </p>
    </section>
  );
}
