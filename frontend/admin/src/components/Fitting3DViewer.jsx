import { Canvas } from "@react-three/fiber";
import { Bounds, Html, OrbitControls, useGLTF } from "@react-three/drei";
import { AxesHelper } from "three";
import { Suspense, Component, useEffect, useState } from "react";

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

function FittingModel({ url, transform }) {
  const { scene } = useGLTF(url);
  return <group position={transform.position} rotation={transform.rotation}><primitive object={scene} /></group>;
}

function Fitting3DCanvas({ url, transform }) {
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
      <primitive object={new AxesHelper(10)} />
      <Html position={[10.5, 0, 0]} center className="fitting-3d-axis-label fitting-3d-axis-label-x">X</Html>
      <Html position={[0, 10.5, 0]} center className="fitting-3d-axis-label fitting-3d-axis-label-y">Y</Html>
      <Html position={[0, 0, 10.5]} center className="fitting-3d-axis-label fitting-3d-axis-label-z">Z</Html>
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[0.12, 16, 16]} />
        <meshStandardMaterial color="#d24b4b" />
      </mesh>
      <Html position={[0, 0, 0]} center className="fitting-3d-origin-label">0</Html>
      <ViewerErrorBoundary>
        <Suspense fallback={<Html center>Завантаження 3D-моделі…</Html>}>
          <Bounds fit clip observe margin={1.2}>
            <FittingModel url={url} transform={transform} />
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

export default function Fitting3DViewer({ asset, onSaveCoordinates }) {
  const url = resolveAdminAssetUrl(asset?.canonical_file_url);
  const initialCoordinates = {
    origin_x: Number(asset?.origin_x ?? 0), origin_y: Number(asset?.origin_y ?? 0), origin_z: Number(asset?.origin_z ?? 0),
    rotation_x: Number(asset?.rotation_x ?? 0), rotation_y: Number(asset?.rotation_y ?? 0), rotation_z: Number(asset?.rotation_z ?? 0),
  };
  const [coordinates, setCoordinates] = useState(initialCoordinates);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => setCoordinates(initialCoordinates), [asset?.id, asset?.updated_at]);
  const transform = {
    position: [-coordinates.origin_x, -coordinates.origin_y, -coordinates.origin_z],
    rotation: coordinates.rotation_x * Math.PI / 180,
  };
  transform.rotation = [coordinates.rotation_x * Math.PI / 180, coordinates.rotation_y * Math.PI / 180, coordinates.rotation_z * Math.PI / 180];
  const setValue = (key, value) => setCoordinates((current) => ({ ...current, [key]: Number(value) || 0 }));
  const bbox = { x: [asset?.bbox_min_x, asset?.bbox_max_x], y: [asset?.bbox_min_y, asset?.bbox_max_y], z: [asset?.bbox_min_z, asset?.bbox_max_z] };
  const applyPreset = (axis, side) => setValue(`origin_${axis}`, side === "min" ? bbox[axis][0] : side === "max" ? bbox[axis][1] : ((bbox[axis][0] || 0) + (bbox[axis][1] || 0)) / 2);
  const save = async () => { setSaving(true); setError(""); const result = await onSaveCoordinates?.(coordinates); setSaving(false); if (result?.success) setEditing(false); else setError(result?.error || "Не вдалося зберегти координати."); };
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
          <Fitting3DCanvas url={url} transform={transform} />
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
      <button className="ghost-button compact-button" onClick={() => { setError(""); setEditing(true); }} type="button">Налаштувати координати</button>
      {editing ? (
        <div className="fitting-3d-coordinate-editor">
          <strong className="fitting-3d-coordinate-title">Локальна координатна система</strong>
          <section className="fitting-3d-coordinate-section">
            <strong className="fitting-3d-coordinate-title">Положення нульової точки</strong>
            <div className="fitting-3d-coordinate-row">
              {["x", "y", "z"].map((axis) => <label className="fitting-3d-coordinate-field" key={`o-${axis}`}><span>{axis.toUpperCase()}</span><input type="number" step="any" value={coordinates[`origin_${axis}`]} onChange={(event) => setValue(`origin_${axis}`, event.target.value)} /></label>)}
            </div>
          </section>
          <section className="fitting-3d-coordinate-section">
            <strong className="fitting-3d-coordinate-title">Швидке вирівнювання нуля</strong>
            <div className="fitting-3d-coordinate-presets" title="Мін — мінімальна межа моделі; Центр — центр моделі; Макс — максимальна межа моделі.">
              {["x", "y", "z"].map((axis) => <div className="fitting-3d-coordinate-preset-group" key={axis}><span>{axis.toUpperCase()}</span><button title="Мінімальна межа моделі" type="button" onClick={() => applyPreset(axis, "min")}>Мін</button><button title="Центр моделі" type="button" onClick={() => applyPreset(axis, "center")}>Центр</button><button title="Максимальна межа моделі" type="button" onClick={() => applyPreset(axis, "max")}>Макс</button></div>)}
            </div>
          </section>
          <section className="fitting-3d-coordinate-section">
            <strong className="fitting-3d-coordinate-title">Орієнтація моделі</strong>
            <div className="fitting-3d-coordinate-row">
              {["x", "y", "z"].map((axis) => <label className="fitting-3d-coordinate-field" key={`r-${axis}`}><span>{axis.toUpperCase()}°</span><input type="number" step="1" value={coordinates[`rotation_${axis}`]} onChange={(event) => setValue(`rotation_${axis}`, event.target.value)} /></label>)}
            </div>
          </section>
          <div className="fitting-3d-coordinate-actions"><button className="ghost-button compact-button" onClick={() => setCoordinates({ ...initialCoordinates, rotation_x: 0, rotation_y: 0, rotation_z: 0 })} type="button">Скинути</button><div className="fitting-3d-coordinate-actions-right"><button className="ghost-button compact-button" onClick={() => { setCoordinates(initialCoordinates); setEditing(false); }} type="button">Скасувати</button><button className="primary-button compact-button" disabled={saving} onClick={save} type="button">{saving ? "Зберігаю…" : "Зберегти"}</button></div></div>
          {error ? <p role="alert">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
