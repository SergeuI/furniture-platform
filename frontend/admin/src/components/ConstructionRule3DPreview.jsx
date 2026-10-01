import { Canvas } from "@react-three/fiber";
import { ContactShadows, OrbitControls, PerspectiveCamera } from "@react-three/drei";
import { CanvasTexture, LinearFilter, RepeatWrapping, SRGBColorSpace, TextureLoader } from "three";
import { Fragment, useEffect, useMemo, useState } from "react";
import { useThree } from "@react-three/fiber";

// Local board material assets. Do not replace these with remote URLs.
const WOOD_TEXTURE_ASSETS = {
  face: "/textures/wood_face.jpg",
  edge: "/textures/wood_edge.png",
};
const FACE_REPEAT = [1.6, 1.2];
const EDGE_REPEAT = [1, 1];
const BOARD_TEXTURE_SCALE = 3.6;
const BOARD_EDGE_TEXTURE_SCALE = 0.24;

const SCENE = {
  width: 6,
  height: 7.2,
  depth: 5,
  thickness: 0.18,
};

function createWoodTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext("2d");
  context.fillStyle = "#d1ad82";
  context.fillRect(0, 0, canvas.width, canvas.height);
  for (let index = 0; index < 40; index += 1) {
    const y = index * 6 + (index % 3);
    context.strokeStyle = index % 7 === 0 ? "rgba(108, 69, 38, 0.13)" : "rgba(255, 239, 210, 0.14)";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(0, y);
    context.bezierCurveTo(76, y - 1, 168, y + 2, 256, y);
    context.stroke();
  }
  const texture = new CanvasTexture(canvas);
  texture.wrapS = RepeatWrapping;
  texture.wrapT = RepeatWrapping;
  texture.repeat.set(1.4, 1.2);
  texture.needsUpdate = true;
  return texture;
}

function createChipboardTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  context.fillStyle = "#ead3ad";
  context.fillRect(0, 0, canvas.width, canvas.height);
  for (let index = 0; index < 180; index += 1) {
    const x = (index * 47) % canvas.width;
    const y = (index * 83) % canvas.height;
    context.fillStyle = index % 3 === 0 ? "rgba(123, 81, 44, 0.2)" : "rgba(255, 247, 226, 0.34)";
    context.fillRect(x, y, index % 4 === 0 ? 2 : 1, 1);
  }
  return new CanvasTexture(canvas);
}

function configureTexture(texture, renderer, repeat) {
  texture.colorSpace = SRGBColorSpace;
  texture.wrapS = RepeatWrapping;
  texture.wrapT = RepeatWrapping;
  texture.repeat.set(...repeat);
  texture.minFilter = LinearFilter;
  texture.magFilter = LinearFilter;
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  texture.needsUpdate = true;
  return texture;
}

function useOptionalTexture(assetUrl, fallbackTexture, renderer, repeat) {
  const [texture, setTexture] = useState(fallbackTexture);

  useEffect(() => {
    if (!assetUrl) return undefined;
    const loader = new TextureLoader();
    let disposed = false;
    loader.load(assetUrl, (loadedTexture) => {
      if (!disposed) setTexture(configureTexture(loadedTexture, renderer, repeat));
    });
    return () => {
      disposed = true;
    };
  }, [assetUrl, renderer, repeat]);

  return texture;
}

function Panel({ position, size, woodTexture, chipboardTexture, isSidePanel, showFasteners }) {
  // BoxGeometry groups: +X, -X, +Y, -Y, +Z, -Z.
  // Side local dimensions are [thickness, height, depth], so +/-X are the two large faces.
  // Bottom local dimensions are [width, thickness, depth], so +/-Y are the two large faces.
  const faceGroups = isSidePanel ? [0, 1] : [2, 3];
  return (
    <mesh position={position} castShadow receiveShadow>
      <boxGeometry args={size} />
      {[0, 1, 2, 3, 4, 5].map((groupIndex) => (
        <meshStandardMaterial
          attach={`material-${groupIndex}`}
          key={groupIndex}
          map={faceGroups.includes(groupIndex) ? woodTexture : chipboardTexture}
          color="#ffffff"
          roughness={faceGroups.includes(groupIndex) ? 0.76 : 0.82}
          metalness={0}
          transparent={showFasteners}
          opacity={showFasteners ? 0.22 : 1}
          depthWrite={!showFasteners}
          depthTest={!showFasteners}
        />
      ))}
    </mesh>
  );
}

function ConfirmatFastener3D({ position, rotation = [0, 0, 0], length = 0.5, diameter = 0.07, visible = true }) {
  return (
    <group position={position} rotation={rotation} visible={visible} renderOrder={10}>
      <mesh castShadow>
        <cylinderGeometry args={[diameter / 2, diameter / 2, length, 16]} />
        <meshStandardMaterial color="#343b3e" metalness={0.72} roughness={0.3} depthTest={false} />
      </mesh>
      <mesh position={[0, -length / 2 - diameter * 0.7, 0]} castShadow>
        <cylinderGeometry args={[diameter * 1.35, diameter * 1.35, diameter * 0.35, 16]} />
        <meshStandardMaterial color="#202729" metalness={0.8} roughness={0.26} depthTest={false} />
      </mesh>
    </group>
  );
}

function ConstructionRuleModel({ selectedVariant, offsetMm, showFasteners, depthMm, edgeOffsetMm }) {
  const { gl } = useThree();
  const { width, height, thickness } = SCENE;
  const depth = Math.min(8, Math.max(2, Number(depthMm) || 500) / 100);
  const edgeOffset = Math.min(depth / 2 - 0.1, Math.max(0, Number(edgeOffsetMm) || 0) / 100);
  const sideX = (width - thickness) / 2;
  const bottomIsBetween = selectedVariant === "offset" || selectedVariant === "between";
  const bottomWidth = bottomIsBetween ? width - thickness * 2 : width;
  const offsetScene = Math.min(300, Math.max(0, Number(offsetMm) || 0)) * 0.006;
  const bottomY = selectedVariant === "on-top"
    ? -height / 2 - thickness / 2
    : -height / 2 + (selectedVariant === "offset" ? offsetScene : 0) + thickness / 2;
  const fallbackFaceTexture = useMemo(() => configureTexture(createWoodTexture(), gl, FACE_REPEAT), [gl]);
  const fallbackEdgeTexture = useMemo(() => configureTexture(createChipboardTexture(), gl, [1, 1]), [gl]);
  const loadedFaceTexture = useOptionalTexture(WOOD_TEXTURE_ASSETS.face, fallbackFaceTexture, gl, FACE_REPEAT);
  const loadedEdgeTexture = useOptionalTexture(WOOD_TEXTURE_ASSETS.edge, fallbackEdgeTexture, gl, EDGE_REPEAT);
  const faceTextures = useMemo(() => {
    const side = loadedFaceTexture.clone();
    configureTexture(side, gl, [depth / BOARD_TEXTURE_SCALE, height / BOARD_TEXTURE_SCALE]);
    const bottom = loadedFaceTexture.clone();
    configureTexture(bottom, gl, [depth / BOARD_TEXTURE_SCALE, bottomWidth / BOARD_TEXTURE_SCALE]);
    bottom.center.set(0.5, 0.5);
    bottom.rotation = Math.PI / 2;
    bottom.needsUpdate = true;
    return { side, bottom };
  }, [bottomWidth, depth, gl, height, loadedFaceTexture]);
  const edgeTextures = useMemo(() => {
    const side = loadedEdgeTexture.clone();
    configureTexture(side, gl, [1, Math.max(1, height / BOARD_EDGE_TEXTURE_SCALE)]);
    const bottom = loadedEdgeTexture.clone();
    configureTexture(bottom, gl, [1, Math.max(1, bottomWidth / BOARD_EDGE_TEXTURE_SCALE)]);
    return { side, bottom };
  }, [bottomWidth, gl, height, loadedEdgeTexture]);

  return (
    <group>
      <Panel isSidePanel showFasteners={showFasteners} position={[-sideX, 0, 0]} size={[thickness, height, depth]} chipboardTexture={edgeTextures.side} woodTexture={faceTextures.side} />
      <Panel isSidePanel showFasteners={showFasteners} position={[sideX, 0, 0]} size={[thickness, height, depth]} chipboardTexture={edgeTextures.side} woodTexture={faceTextures.side} />
      <Panel showFasteners={showFasteners} position={[0, bottomY, 0]} size={[bottomWidth, thickness, depth]} chipboardTexture={edgeTextures.bottom} woodTexture={faceTextures.bottom} />
      {showFasteners ? [depth / 2 - edgeOffset, -depth / 2 + edgeOffset].map((zPosition) => (
        selectedVariant === "on-top" ? (
          <Fragment key={`vertical-${zPosition}`}>
            <ConfirmatFastener3D position={[-sideX, bottomY - thickness / 2 + 0.25, zPosition]} />
            <ConfirmatFastener3D position={[sideX, bottomY - thickness / 2 + 0.25, zPosition]} />
          </Fragment>
        ) : (
          <Fragment key={`horizontal-${zPosition}`}>
            <ConfirmatFastener3D position={[-sideX - thickness / 2 - 0.25, bottomY, zPosition]} rotation={[0, 0, -Math.PI / 2]} />
            <ConfirmatFastener3D position={[sideX + thickness / 2 + 0.25, bottomY, zPosition]} rotation={[0, 0, Math.PI / 2]} />
          </Fragment>
        )
      )) : null}
    </group>
  );
}

export default function ConstructionRule3DPreview({ selectedVariant, offsetMm, showFasteners = false, depthMm = 500, edgeOffsetMm = 50 }) {
  return (
    <div
      className="construction-rule-3d-preview"
      aria-label="3D попередній перегляд конструкції"
      onContextMenu={(event) => event.preventDefault()}
    >
      <Canvas shadows dpr={[1, 2]}>
        <PerspectiveCamera makeDefault fov={30} position={[9, 7, 11]} />
        <color attach="background" args={["#f6f8f6"]} />
        <ambientLight intensity={1.15} />
        <hemisphereLight args={["#fffdf8", "#cdd8d0", 1.7]} />
        <directionalLight castShadow intensity={2.8} position={[5, 10, 7]} shadow-mapSize={[1024, 1024]} />
        <directionalLight intensity={0.55} position={[-6, 4, -4]} />
        <ConstructionRuleModel depthMm={depthMm} edgeOffsetMm={edgeOffsetMm} offsetMm={offsetMm} selectedVariant={selectedVariant} showFasteners={showFasteners} />
        <ContactShadows color="#718078" opacity={0.2} blur={2.6} far={5} position={[0, -3.7, 0]} scale={9} />
        <OrbitControls enablePan maxDistance={17} minDistance={7} target={[0, 0, 0]} />
      </Canvas>
    </div>
  );
}
