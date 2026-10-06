import { Canvas, useThree } from "@react-three/fiber";
import { ContactShadows, Edges, OrbitControls, PerspectiveCamera, useGLTF, useTexture } from "@react-three/drei";
import { EdgesGeometry, LineBasicMaterial, LineSegments, LinearFilter, Quaternion, RepeatWrapping, SRGBColorSpace, Vector3 } from "three";
import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { resolveAdminAssetUrl } from "../api.js";
import { resolveMountingNodeInstanceFrame } from "../mountingNodeGeometry.js";
import { resolveFaceToEdgeHolePlacement } from "../mountingNodeGeometry.js";
import EngineeringHoleOutline from "./processing/EngineeringHoleOutline.jsx";
import { orbitCameraPosition, zoomCameraPosition } from "../constructionRuleCamera.js";

// Local board material assets. Do not replace these with remote URLs.
const WOOD_TEXTURE_ASSETS = {
  face: "/admin/textures/wood_face.jpg",
  edge: "/admin/textures/wood_edge.png",
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
const INITIAL_CAMERA_POSITION = [9, 7, 11];
const INITIAL_CAMERA_TARGET = [0, 0, 0];
const CAMERA_MIN_DISTANCE = 7;
const CAMERA_MAX_DISTANCE = 17;

function ConstructionRuleActiveCamera({ cameraRef }) {
  const { camera } = useThree();
  useEffect(() => {
    cameraRef.current = camera;
    return () => {
      if (cameraRef.current === camera) cameraRef.current = null;
    };
  }, [camera, cameraRef]);
  return null;
}
function ConstructionRuleCameraControls() {
  const { camera } = useThree();
  return <OrbitControls camera={camera} enablePan maxDistance={CAMERA_MAX_DISTANCE} minDistance={CAMERA_MIN_DISTANCE} target={INITIAL_CAMERA_TARGET} />;
}

function ConstructionRuleCameraOverlay({ cameraRef }) {
  const moveCamera = (action) => {
    const camera = cameraRef.current;
    if (!camera) return;
    const target = new Vector3(...INITIAL_CAMERA_TARGET);
    if (["left", "right", "up", "down"].includes(action)) {
      const thetaDelta = action === "left" ? 0.20 : action === "right" ? -0.20 : 0;
      const phiDelta = action === "up" ? -0.16 : action === "down" ? 0.16 : 0;
      camera.position.set(...orbitCameraPosition(camera.position.toArray(), target.toArray(), thetaDelta, phiDelta));
      camera.lookAt(target);
    }
    if (action === "in") camera.position.set(...zoomCameraPosition(camera.position.toArray(), target.toArray(), 1 / 1.12, CAMERA_MIN_DISTANCE, CAMERA_MAX_DISTANCE));
    if (action === "out") camera.position.set(...zoomCameraPosition(camera.position.toArray(), target.toArray(), 1.12, CAMERA_MIN_DISTANCE, CAMERA_MAX_DISTANCE));
    if (action === "home") {
      camera.position.set(...INITIAL_CAMERA_POSITION);
      target.set(...INITIAL_CAMERA_TARGET);
      camera.lookAt(target);
    }
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld(true);
  };
  const button = (action, label, symbol) => <button aria-label={label} title={label} type="button" onClick={() => moveCamera(action)}>{symbol}</button>;
  return <div className="construction-rule-camera-controls" aria-label="Керування камерою">
    <div className="construction-rule-camera-row">{button("up", "Повернути вгору", "↑")}</div>
    <div className="construction-rule-camera-row">{button("left", "Повернути ліворуч", "←")}{button("home", "Початковий вигляд", "⌂")}{button("right", "Повернути праворуч", "→")}</div>
    <div className="construction-rule-camera-row">{button("down", "Повернути вниз", "↓")}</div>
    <div className="construction-rule-camera-zoom-row">{button("out", "Віддалити", "−")}{button("in", "Наблизити", "+")}</div>
  </div>;
}

function getSceneGeometry({ selectedVariant, offsetMm, depthMm, edgeOffsetMm }) {
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
  return { width, height, thickness, depth, edgeOffset, sideX, bottomWidth, offsetScene, bottomY };
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

function Panel({ position, size, woodTexture, chipboardTexture, isSidePanel, transparentPanels }) {
  // BoxGeometry groups: +X, -X, +Y, -Y, +Z, -Z.
  // Side local dimensions are [thickness, height, depth], so +/-X are the two large faces.
  // Bottom local dimensions are [width, thickness, depth], so +/-Y are the two large faces.
  const faceGroups = isSidePanel ? [0, 1] : [2, 3];
  const materialRefs = useRef([]);

  useEffect(() => {
    materialRefs.current.forEach((material) => {
      if (!material) return;
      const slotUsesFaceTexture = faceGroups.includes(materialRefs.current.indexOf(material));
      material.map = slotUsesFaceTexture ? woodTexture || null : chipboardTexture || null;
      material.transparent = transparentPanels;
      material.opacity = transparentPanels ? 0.20 : 1;
      material.depthWrite = !transparentPanels;
      material.depthTest = true;
      material.needsUpdate = true;
    });
  }, [chipboardTexture, transparentPanels, woodTexture]);

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
          transparent={transparentPanels}
          opacity={transparentPanels ? 0.20 : 1}
          depthWrite={!transparentPanels}
          depthTest={true}
          ref={(material) => {
            materialRefs.current[groupIndex] = material;
          }}
          visible={true}
        />
      ))}
      <Edges color={transparentPanels ? "#747c78" : "#8f9693"} opacity={transparentPanels ? 0.55 : 0.22} threshold={15} transparent />
    </mesh>
  );
}

function resolveFittingAnchor({ nodeItem, sideSign, sideX, bottomY, thickness }) {
  const panel = String(nodeItem?.visual_anchor_panel || "").trim();
  const surface = String(nodeItem?.visual_anchor_surface || "").trim();

  if (panel === "vertical_panel") {
    const surfaceOffset = surface === "outer_face" ? thickness / 2 : -thickness / 2;
    return [sideSign * (sideX + surfaceOffset), 0, 0];
  }

  if (panel === "horizontal_panel") {
    return [0, surface === "edge" ? bottomY + thickness / 2 : bottomY, 0];
  }

  return [sideSign * sideX, bottomY, 0];
}

function MountingNodePhysicalFitting({ asset, nodeItem }) {
  const { scene } = useGLTF(resolveAdminAssetUrl(asset.canonical_file_url));
  const model = useMemo(() => {
    const clone = scene.clone(true);
    clone.traverse((object) => {
      if (!object.isMesh || !object.geometry) return;
      const outline = new LineSegments(
        new EdgesGeometry(object.geometry, 15),
        new LineBasicMaterial({ color: "#555d59", depthTest: true, depthWrite: false, opacity: 0.72, transparent: true }),
      );
      outline.name = "fitting-outline";
      object.add(outline);
    });
    return clone;
  }, [scene]);
  useEffect(() => () => {
    model.traverse((object) => {
      if (object.name !== "fitting-outline") return;
      object.geometry?.dispose();
      object.material?.dispose();
    });
  }, [model]);
  const offset = [nodeItem?.visual_offset_x, nodeItem?.visual_offset_y, nodeItem?.visual_offset_z].map((value) => Number(value || 0) * 0.01);
  const rotation = [nodeItem?.visual_rotation_x, nodeItem?.visual_rotation_y, nodeItem?.visual_rotation_z].map((value) => Number(value || 0) * Math.PI / 180);
  return <primitive object={model} scale={[0.01, 0.01, 0.01]} position={offset} rotation={rotation} />;
}

function EngineeringMountingFrames({ asset, geometry, nodeItem, positionsMm, holePoints, transparentPanels, showFittings }) {
  const frames = [-1, 1].flatMap((sideSign) => positionsMm.map((schemePositionMm) => resolveMountingNodeInstanceFrame({
    constructionGeometry: geometry,
    joint: sideSign < 0 ? "left" : "right",
    schemePositionMm,
    node: nodeItem,
    holePoints,
  })));

  return frames.map((frame, index) => {
    const direction = new Vector3(...frame.direction).normalize();
    const frameQuaternion = new Quaternion().setFromUnitVectors(new Vector3(1, 0, 0), direction);
    const isBottomToSide = frame.p1Target?.panel === "horizontal_panel"
      && frame.p1Target?.surface === "plane"
      && frame.p2Target?.panel === "vertical_panel"
      && frame.p2Target?.surface === "edge";
    const physicalPosition = isBottomToSide
      ? [
        frame.joint === "right" ? geometry.sideX : -geometry.sideX,
        geometry.bottomY - geometry.thickness / 2,
        frame.position[2],
      ]
      : frame.position;
    const sideSign = frame.joint === "right" ? 1 : -1;
    const panelA = { args: [geometry.thickness, geometry.height, geometry.depth], position: [sideSign * geometry.sideX, 0, frame.position[2]] };
    const panelB = { args: [geometry.bottomWidth, geometry.thickness, geometry.depth], position: [0, geometry.bottomY, frame.position[2]] };
    const holes = holePoints.map((point, pointIndex) => resolveFaceToEdgeHolePlacement({
      panelA,
      panelB,
      point,
      index: pointIndex,
      location: {
        targetPanel: point.target_panel,
        targetSurface: point.target_surface,
        targetSide: point.target_side,
        joint: frame.joint,
      },
      joint: frame.joint,
      constructionGeometry: geometry,
    }));
    return (
      <React.Fragment key={`${frame.joint}-${frame.schemePositionMm}-${index}`}>
        <group position={physicalPosition} quaternion={frameQuaternion}>
          {showFittings && asset?.canonical_file_url ? (
            <Suspense fallback={null}>
              <MountingNodePhysicalFitting asset={asset} nodeItem={nodeItem} />
            </Suspense>
          ) : null}
        </group>
        {transparentPanels ? (
          <group>
            {holes.map((hole, holeIndex) => <EngineeringHoleOutline key={`engineering-hole-${frame.joint}-${frame.schemePositionMm}-${holeIndex}`} marker={hole} color="#16a34a" />)}
          </group>
        ) : null}
      </React.Fragment>
    );
  });
}

function ConstructionRuleModel({ selectedVariant, offsetMm, depthMm, edgeOffsetMm, transparentPanels }) {
  const { gl } = useThree();
  const { width, height, thickness, depth, edgeOffset, sideX, bottomWidth, bottomY } = getSceneGeometry({ selectedVariant, offsetMm, depthMm, edgeOffsetMm });
  const [loadedFaceTexture, loadedEdgeTexture] = useTexture([WOOD_TEXTURE_ASSETS.face, WOOD_TEXTURE_ASSETS.edge]);
  const faceTextures = useMemo(() => {
    if (!loadedFaceTexture) return { side: null, bottom: null };
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
    if (!loadedEdgeTexture) return { side: null, bottom: null };
    const side = loadedEdgeTexture.clone();
    configureTexture(side, gl, [1, Math.max(1, height / BOARD_EDGE_TEXTURE_SCALE)]);
    const bottom = loadedEdgeTexture.clone();
    configureTexture(bottom, gl, [1, Math.max(1, bottomWidth / BOARD_EDGE_TEXTURE_SCALE)]);
    return { side, bottom };
  }, [bottomWidth, gl, height, loadedEdgeTexture]);

  return (
    <group>
          <Panel isSidePanel position={[-sideX, 0, 0]} size={[thickness, height, depth]} chipboardTexture={edgeTextures.side} woodTexture={faceTextures.side} transparentPanels={transparentPanels} />
      <Panel isSidePanel position={[sideX, 0, 0]} size={[thickness, height, depth]} chipboardTexture={edgeTextures.side} woodTexture={faceTextures.side} transparentPanels={transparentPanels} />
      <Panel position={[0, bottomY, 0]} size={[bottomWidth, thickness, depth]} chipboardTexture={edgeTextures.bottom} woodTexture={faceTextures.bottom} transparentPanels={transparentPanels} />
    </group>
  );
}

class ConstructionRule3DErrorBoundary extends React.Component {
  state = { error: null };

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("[ConstructionRule3D fastener error]", error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    const { error } = this.state;
    const stack = error?.stack ? error.stack.split("\n").slice(0, 4).join("\n") : "";
    return (
      <div className="construction-rule-3d-preview-error" role="alert">
        <strong>Помилка 3D кріплення</strong>
        <div>{error?.name || "Error"}: {error?.message || "Невідома помилка"}</div>
        {stack ? <pre>{stack}</pre> : null}
      </div>
    );
  }
}

function ConstructionRule3DPreviewContent({ selectedVariant, offsetMm, transparentPanels = false, showFittings = true, depthMm = 500, edgeOffsetMm = 50, fittingAsset = null, nodeItem = null, schemePositions = [], holePoints = [], assemblyError = "" }) {
  const cameraRef = useRef(null);
  const { width, height, thickness, depth, offsetScene, bottomY } = getSceneGeometry({ selectedVariant, offsetMm, depthMm, edgeOffsetMm });
  const geometry = { width, height, depth, thickness, sideX: (width - thickness) / 2, bottomWidth: selectedVariant === "offset" || selectedVariant === "between" ? width - thickness * 2 : width, bottomY };
  const lowestPanelY = Math.min(-height / 2, bottomY - thickness / 2);
  const groundY = lowestPanelY - 0.08;
  return (
    <div
      className="construction-rule-3d-preview"
      aria-label="3D попередній перегляд конструкції"
      onContextMenu={(event) => event.preventDefault()}
    >
      <Canvas shadows dpr={[1, 2]}>
        <PerspectiveCamera makeDefault fov={30} position={INITIAL_CAMERA_POSITION} />
        <color attach="background" args={["#f6f8f6"]} />
        <ambientLight intensity={1.15} />
        <hemisphereLight args={["#fffdf8", "#cdd8d0", 1.7]} />
        <directionalLight castShadow intensity={2.8} position={[5, 10, 7]} shadow-mapSize={[1024, 1024]} />
        <directionalLight intensity={0.55} position={[-6, 4, -4]} />
        <ConstructionRuleModel depthMm={depthMm} edgeOffsetMm={edgeOffsetMm} offsetMm={offsetMm} selectedVariant={selectedVariant} transparentPanels={transparentPanels} />
        {schemePositions.length && holePoints.length ? (
          <EngineeringMountingFrames asset={fittingAsset} geometry={geometry} holePoints={holePoints} nodeItem={nodeItem} positionsMm={schemePositions} showFittings={showFittings} transparentPanels={transparentPanels} />
        ) : null}
        <ContactShadows color="#718078" opacity={0.2} blur={2.6} far={5} position={[0, groundY, 0]} scale={9} />
        <ConstructionRuleActiveCamera cameraRef={cameraRef} />
        <ConstructionRuleCameraControls />
      </Canvas>
      <ConstructionRuleCameraOverlay cameraRef={cameraRef} />
      {assemblyError ? <div className="construction-rule-3d-preview-error">{assemblyError}</div> : null}
    </div>
  );
}

export default function ConstructionRule3DPreview(props) {
  return (
    <ConstructionRule3DErrorBoundary>
      <ConstructionRule3DPreviewContent {...props} />
    </ConstructionRule3DErrorBoundary>
  );
}
