import { Canvas } from "@react-three/fiber";
import { Bounds, Html, OrbitControls, useGLTF } from "@react-three/drei";
import { Suspense, Component } from "react";

import { resolveAdminAssetUrl } from "../api.js";

class ViewerErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    return this.state.hasError
      ? <Html center>Не вдалося завантажити 3D-модель.</Html>
      : this.props.children;
  }
}

function FittingModel({ url }) {
  const { scene } = useGLTF(url);
  return <primitive object={scene} />;
}

function Fitting3DCanvas({ url }) {
  return (
    <Canvas
      className="fitting-3d-viewer-canvas"
      camera={{ fov: 42, position: [2, 2, 2] }}
      dpr={[1, 2]}
      frameloop="demand"
      gl={{ antialias: true }}
    >
      <color attach="background" args={["#eef2f1"]} />
      <ambientLight intensity={1.5} />
      <directionalLight intensity={2.2} position={[4, 6, 5]} />
      <directionalLight intensity={0.8} position={[-4, 2, -3]} />
      <ViewerErrorBoundary>
        <Suspense fallback={<Html center>Завантаження 3D-моделі…</Html>}>
          <Bounds fit clip observe margin={1.2}>
            <FittingModel url={url} />
          </Bounds>
        </Suspense>
      </ViewerErrorBoundary>
      <OrbitControls makeDefault enableDamping enablePan enableZoom />
    </Canvas>
  );
}

function formatDimension(value) {
  return value === null || value === undefined ? "—" : Number(value).toFixed(2);
}

export default function Fitting3DViewer({ asset }) {
  const url = resolveAdminAssetUrl(asset?.canonical_file_url);
  const dimensions = [asset?.dimensions_x, asset?.dimensions_y, asset?.dimensions_z]
    .map(formatDimension)
    .join(" × ");
  const sources = Array.isArray(asset?.sources)
    ? asset.sources.map((source) => String(source.file_format || "").toUpperCase()).filter(Boolean).join(", ")
    : "—";

  return (
    <div className="fitting-3d-viewer">
      {url ? (
        <div className="fitting-3d-viewer-stage">
          <Fitting3DCanvas url={url} />
        </div>
      ) : (
        <div className="fitting-3d-viewer-state">Не вдалося завантажити 3D-модель.</div>
      )}
      <dl className="fitting-3d-viewer-meta">
        <div><dt>Статус</dt><dd>{asset?.status === "validated" ? "Перевірено" : asset?.status || "—"}</dd></div>
        <div><dt>Формат</dt><dd>{String(asset?.canonical_format || "—").toUpperCase()}</dd></div>
        <div><dt>Розміри</dt><dd>{dimensions}</dd></div>
        <div><dt>Одиниці</dt><dd>{asset?.units === "unknown" ? "Не визначено" : asset?.units || "—"}</dd></div>
        <div><dt>Джерела</dt><dd>{sources}</dd></div>
      </dl>
    </div>
  );
}
