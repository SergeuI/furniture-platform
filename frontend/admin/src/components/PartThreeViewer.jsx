import { Canvas } from "@react-three/fiber";
import { Edges, Line, OrbitControls } from "@react-three/drei";
import { useMemo } from "react";

function getEdgeColor(value) {
  if (!value || value === "not_set") {
    return "#dbe3e8";
  }

  const normalized = String(value).toLowerCase();

  if (normalized.includes("2.0") || normalized.includes("2,0")) {
    return "#7a0b80";
  }

  if (normalized.includes("1.0") || normalized.includes("1,0")) {
    return "#b7dce8";
  }

  if (normalized.includes("0.8") || normalized.includes("0,8")) {
    return "#ff7300";
  }

  if (normalized.includes("0.4") || normalized.includes("0,4")) {
    return "#078000";
  }

  return "#0b1cff";
}

function getPartBaseColor(part) {
  const category = String(part?.category || "").toLowerCase();
  const name = String(part?.part_name || "").toLowerCase();

  if (category.includes("facade") || name.includes("facade")) {
    return "#f4efe7";
  }

  if (category.includes("back") || name.includes("back")) {
    return "#eef2ff";
  }

  if (category.includes("bottom") || name.includes("bottom")) {
    return "#f7f8fb";
  }

  return "#f8fafb";
}

function normalizePartDimensions(part) {
  const width = Math.max(Number(part?.width) || 1, 1);
  const height = Math.max(Number(part?.height) || 1, 1);
  const thickness = Math.max(Number(part?.thickness) || 18, 1);
  const largest = Math.max(width, height, thickness);
  const scale = 2.6 / largest;

  return {
    width,
    widthUnits: width * scale,
    height,
    heightUnits: height * scale,
    thickness,
    thicknessUnits: thickness * scale,
  };
}

function holePosition(hole, dimensions) {
  return [
    -dimensions.widthUnits / 2 + (hole.x / dimensions.width) * dimensions.widthUnits,
    -dimensions.heightUnits / 2 + (hole.y / dimensions.height) * dimensions.heightUnits,
    dimensions.thicknessUnits / 2 + 0.01,
  ];
}

function groovePosition(groove, dimensions) {
  const grooveHeight = Math.max((groove.width / dimensions.height) * dimensions.heightUnits, 0.02);
  const grooveLength = Math.max((groove.length / dimensions.width) * dimensions.widthUnits, 0.04);

  return {
    grooveHeight,
    grooveLength,
    position: [
      -dimensions.widthUnits / 2 + (groove.x / dimensions.width) * dimensions.widthUnits + grooveLength / 2,
      -dimensions.heightUnits / 2 + (groove.y / dimensions.height) * dimensions.heightUnits,
      dimensions.thicknessUnits / 2 + 0.012,
    ],
  };
}

function quarterPosition(quarter, dimensions) {
  const quarterHeight = Math.max((quarter.width / dimensions.height) * dimensions.heightUnits, 0.03);
  const quarterLength = Math.max((quarter.length / dimensions.width) * dimensions.widthUnits, 0.05);
  const quarterDepth = Math.max((quarter.depth / dimensions.thickness) * dimensions.thicknessUnits, 0.02);

  return {
    size: [quarterLength, quarterHeight, quarterDepth],
    position: [
      -dimensions.widthUnits / 2 + (quarter.x / dimensions.width) * dimensions.widthUnits + quarterLength / 2,
      -dimensions.heightUnits / 2 + (quarter.y / dimensions.height) * dimensions.heightUnits + quarterHeight / 2,
      dimensions.thicknessUnits / 2 - quarterDepth / 2,
    ],
  };
}

function EdgeBand({
  color,
  dimensions,
  selected,
  side,
  onSelectEdge,
}) {
  const bandSize = Math.max(Math.min(dimensions.widthUnits, dimensions.heightUnits) * 0.05, 0.035);
  const argsBySide = {
    top: [dimensions.widthUnits, bandSize, dimensions.thicknessUnits + 0.018],
    bottom: [dimensions.widthUnits, bandSize, dimensions.thicknessUnits + 0.018],
    left: [bandSize, dimensions.heightUnits, dimensions.thicknessUnits + 0.018],
    right: [bandSize, dimensions.heightUnits, dimensions.thicknessUnits + 0.018],
  };
  const positionBySide = {
    top: [0, dimensions.heightUnits / 2 + bandSize / 2, 0],
    bottom: [0, -dimensions.heightUnits / 2 - bandSize / 2, 0],
    left: [-dimensions.widthUnits / 2 - bandSize / 2, 0, 0],
    right: [dimensions.widthUnits / 2 + bandSize / 2, 0, 0],
  };

  return (
    <mesh
      onClick={(event) => {
        event.stopPropagation();
        onSelectEdge?.(side);
      }}
      position={positionBySide[side]}
      scale={selected ? [1.02, 1.02, 1.04] : [1, 1, 1]}
    >
      <boxGeometry args={argsBySide[side]} />
      <meshStandardMaterial
        color={color}
        emissive={selected ? "#9df0b1" : "#000000"}
        emissiveIntensity={selected ? 0.35 : 0}
        metalness={0.12}
        roughness={0.55}
        transparent
        opacity={color === "#dbe3e8" ? 0.42 : 1}
      />
    </mesh>
  );
}

function PartBoardModel({ detail, onSelectEdge, rotation, selectedEdgeSide }) {
  const dimensions = useMemo(() => normalizePartDimensions(detail.part), [detail.part]);
  const baseColor = useMemo(() => getPartBaseColor(detail.part), [detail.part]);
  const edgeColors = useMemo(
    () => ({
      top: getEdgeColor(detail.part.edge_top),
      bottom: getEdgeColor(detail.part.edge_bottom),
      left: getEdgeColor(detail.part.edge_left),
      right: getEdgeColor(detail.part.edge_right),
    }),
    [detail.part],
  );
  const grainLines = useMemo(() => {
    const length = dimensions.widthUnits * 0.18;
    const centerY = dimensions.heightUnits * 0.02;
    const spacing = 0.085;

    return [-spacing, 0, spacing].map((offset) => [
      [-length / 2, centerY + offset, dimensions.thicknessUnits / 2 + 0.014],
      [length / 2, centerY + offset, dimensions.thicknessUnits / 2 + 0.014],
    ]);
  }, [dimensions]);

  return (
    <group rotation={[-0.46, (rotation * Math.PI) / 180, 0.04]}>
      <mesh castShadow receiveShadow>
        <boxGeometry args={[dimensions.widthUnits, dimensions.heightUnits, dimensions.thicknessUnits]} />
        <meshStandardMaterial color={baseColor} metalness={0.08} roughness={0.76} />
        <Edges color="#23313e" lineWidth={1} />
      </mesh>

      {["top", "bottom", "left", "right"].map((side) => (
        <EdgeBand
          color={edgeColors[side]}
          dimensions={dimensions}
          key={side}
          onSelectEdge={onSelectEdge}
          selected={selectedEdgeSide === side}
          side={side}
        />
      ))}

      {detail.holes.map((hole) => {
        const markerRadius = Math.max((hole.diameter / dimensions.width) * dimensions.widthUnits * 0.5, 0.018);

        return (
          <mesh key={`hole-${hole.number}`} position={holePosition(hole, dimensions)}>
            <cylinderGeometry args={[markerRadius, markerRadius, 0.028, 24]} />
            <meshStandardMaterial color="#ff33c4" emissive="#ff8de0" emissiveIntensity={0.25} />
          </mesh>
        );
      })}

      {detail.grooves.map((groove) => {
        const grooveMesh = groovePosition(groove, dimensions);

        return (
          <mesh key={`groove-${groove.number}`} position={grooveMesh.position}>
            <boxGeometry args={[grooveMesh.grooveLength, grooveMesh.grooveHeight, 0.02]} />
            <meshStandardMaterial color="#ff6a6a" transparent opacity={0.8} />
          </mesh>
        );
      })}

      {detail.quarters.map((quarter) => {
        const quarterMesh = quarterPosition(quarter, dimensions);

        return (
          <mesh key={`quarter-${quarter.number}`} position={quarterMesh.position}>
            <boxGeometry args={quarterMesh.size} />
            <meshStandardMaterial color="#f3b300" transparent opacity={0.65} />
          </mesh>
        );
      })}

      {grainLines.map((points, index) => (
        <Line color="#8d97a3" key={`grain-${index}`} lineWidth={1.2} points={points} />
      ))}
    </group>
  );
}

export default function PartThreeViewer({
  detail,
  onSelectEdge,
  rotation,
  selectedEdgeSide,
  t,
}) {
  if (!detail?.part) {
    return null;
  }

  const part = detail.part;

  return (
    <div className="part-three-viewer">
      <div className="part-three-viewer-canvas">
        <Canvas camera={{ fov: 28, position: [0, 0, 4.8] }} shadows>
          <color attach="background" args={["#f6fafc"]} />
          <ambientLight intensity={0.95} />
          <directionalLight castShadow intensity={1.35} position={[5, 7, 6]} />
          <directionalLight intensity={0.38} position={[-4, -3, 4]} />
          <PartBoardModel
            detail={detail}
            onSelectEdge={onSelectEdge}
            rotation={rotation}
            selectedEdgeSide={selectedEdgeSide}
          />
          <OrbitControls
            enablePan={false}
            maxDistance={8}
            minDistance={2.2}
            target={[0, 0, 0]}
          />
        </Canvas>
      </div>
      <div className="part-three-viewer-meta">
        <span className="part-three-viewer-badge">
          {part.width} x {part.height} x {part.thickness} mm
        </span>
        <span className="part-three-viewer-badge subtle">
          {part.category}
        </span>
        {selectedEdgeSide ? (
          <span className="part-three-viewer-badge active">
            {t.edgeSelectedSide}: {selectedEdgeSide}
          </span>
        ) : null}
      </div>
      <p className="part-three-viewer-hint">
        {t.preview3dInteractiveHint}
      </p>
    </div>
  );
}
