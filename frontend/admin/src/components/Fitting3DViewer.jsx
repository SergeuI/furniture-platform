import { Canvas } from "@react-three/fiber";
import { Bounds, Html, OrbitControls, useGLTF } from "@react-three/drei";
import { AxesHelper } from "three";
import { Suspense, Component, useCallback, useEffect, useMemo, useRef, useState } from "react";

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

function FittingModel({ url, transform, materialColor, materialOverrides, onMaterialsDetected }) {
  const { scene } = useGLTF(url);
  const isolatedScene = useMemo(() => {
    const cloned = scene.clone(true);
    const materialKeys = new Map();
    let materialIndex = 0;
    cloned.traverse((node) => {
      if (node.isMesh && node.material) {
        const cloneMaterial = (material) => {
          let descriptor = materialKeys.get(material);
          if (!descriptor) {
            descriptor = { index: materialIndex++, name: material.name || "", nativeColor: material.color ? `#${material.color.getHexString()}`.toUpperCase() : "#FFFFFF" };
            descriptor.key = `${descriptor.index}:${descriptor.name}`;
            materialKeys.set(material, descriptor);
          }
          const clone = material.clone();
          if (clone.color) clone.userData.nativeColor = `#${clone.color.getHexString()}`.toUpperCase();
          clone.userData.materialKey = descriptor.key;
          clone.userData.materialIndex = descriptor.index;
          clone.userData.materialName = descriptor.name;
          return clone;
        };
        node.material = Array.isArray(node.material) ? node.material.map(cloneMaterial) : cloneMaterial(node.material);
      }
    });
    return { scene: cloned, materials: [...materialKeys.values()] };
  }, [scene]);
  useEffect(() => {
    onMaterialsDetected?.(isolatedScene.materials);
  }, [isolatedScene, onMaterialsDetected]);
  useEffect(() => {
    isolatedScene.scene.traverse((node) => {
      if (node.isMesh && node.material) {
        const materials = Array.isArray(node.material) ? node.material : [node.material];
        materials.forEach((material) => {
          const override = materialOverrides?.[material.userData?.materialKey];
          material.color?.set(override || materialColor || material.userData?.nativeColor);
        });
      }
    });
  }, [isolatedScene, materialColor, materialOverrides]);
  return <group position={transform.position} rotation={transform.rotation}><primitive object={isolatedScene.scene} /></group>;
}

function Fitting3DCanvas({ url, transform, materialColor, materialOverrides, onMaterialsDetected }) {
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
            <FittingModel url={url} transform={transform} materialColor={materialColor} materialOverrides={materialOverrides} onMaterialsDetected={onMaterialsDetected} />
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

export default function Fitting3DViewer({ asset, onSaveCoordinates, onSaveAppearance }) {
  const url = resolveAdminAssetUrl(asset?.canonical_file_url);
  const initialCoordinates = {
    origin_x: Number(asset?.origin_x ?? 0), origin_y: Number(asset?.origin_y ?? 0), origin_z: Number(asset?.origin_z ?? 0),
    rotation_x: Number(asset?.rotation_x ?? 0), rotation_y: Number(asset?.rotation_y ?? 0), rotation_z: Number(asset?.rotation_z ?? 0),
  };
  const [coordinates, setCoordinates] = useState(initialCoordinates);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [materials, setMaterials] = useState([]);
  const [materialOverrides, setMaterialOverrides] = useState({});
  const [appearanceSaving, setAppearanceSaving] = useState(false);
  const [appearanceError, setAppearanceError] = useState("");
  const [appearanceStatus, setAppearanceStatus] = useState("");
  const appearanceStatusTimer = useRef(null);
  useEffect(() => setCoordinates(initialCoordinates), [asset?.id, asset?.updated_at, asset?.canonical_file_url]);
  useEffect(() => {
    const next = {};
    (asset?.material_overrides || []).forEach((override) => {
      next[`${override.material_index}:${override.material_name || ""}`] = override.color.toUpperCase();
    });
    setMaterials([]);
    setMaterialOverrides(next);
  }, [asset?.id, asset?.updated_at, asset?.canonical_file_url, asset?.material_overrides]);
  useEffect(() => () => clearTimeout(appearanceStatusTimer.current), []);
  const clearAppearanceStatus = () => {
    clearTimeout(appearanceStatusTimer.current);
    setAppearanceStatus("");
    setAppearanceError("");
  };
  const markAppearanceSaved = () => {
    clearTimeout(appearanceStatusTimer.current);
    setAppearanceStatus("✓ Зміни збережено");
    appearanceStatusTimer.current = setTimeout(() => setAppearanceStatus(""), 2500);
  };
  const handleMaterialsDetected = useCallback((detected) => {
    setMaterials(detected);
    if (asset?.material_color_override && !(asset?.material_overrides || []).length) {
      setMaterialOverrides((current) => detected.reduce((next, material) => ({ ...next, [material.key]: current[material.key] || asset.material_color_override.toUpperCase() }), current));
    }
  }, [asset?.id, asset?.material_color_override, asset?.material_overrides]);
  const setMaterialDraft = (key, value) => { clearAppearanceStatus(); setMaterialOverrides((current) => ({ ...current, [key]: value.toUpperCase() })); };
  const resetMaterialDraft = (key) => { clearAppearanceStatus(); setMaterialOverrides((current) => { const next = { ...current }; delete next[key]; return next; }); };
  const materialValue = (material) => materialOverrides[material.key] || material.nativeColor || "#FFFFFF";
  const validAppearance = materials.length > 0 && materials.every((material) => !materialOverrides[material.key] || /^#[0-9A-F]{6}$/i.test(materialOverrides[material.key]));
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
          <Fitting3DCanvas url={url} transform={transform} materialColor={null} materialOverrides={materialOverrides} onMaterialsDetected={handleMaterialsDetected} />
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
      <div className="fitting-3d-appearance-controls">
        <strong>Вигляд</strong>
        {materials.map((material) => { const value = materialValue(material); const valid = /^#[0-9A-F]{6}$/i.test(value); return <div className="fitting-3d-material-row" key={material.key}><strong>{material.name || `Матеріал ${material.index + 1}`}</strong><input aria-label={`Палітра ${material.name || material.index + 1}`} className="fitting-3d-appearance-swatch" type="color" value={valid ? value : "#FFFFFF"} onChange={(event) => setMaterialDraft(material.key, event.target.value)} /><div className="fitting-3d-appearance-presets">{[['Білий', '#FFFFFF'], ['Чорний', '#111111'], ['Сірий', '#808080'], ['Нікель', '#B8B8B8']].map(([label, preset]) => <button className="ghost-button compact-button" key={preset} onClick={() => setMaterialDraft(material.key, preset)} type="button">{label}</button>)}</div><label>HEX <input aria-label={`HEX ${material.name || material.index + 1}`} maxLength={7} onChange={(event) => setMaterialDraft(material.key, event.target.value)} placeholder="#FFFFFF" value={value} /></label><button className="ghost-button compact-button" onClick={() => resetMaterialDraft(material.key)} type="button">Скинути</button></div>; })}
        {!materials.length ? <span className="fitting-3d-appearance-hint">Завантаження матеріалів…</span> : null}
        <div className="fitting-3d-appearance-actions"><button className="primary-button compact-button" disabled={appearanceSaving || !validAppearance} onClick={async () => { setAppearanceSaving(true); setAppearanceError(""); setAppearanceStatus(""); const result = await onSaveAppearance?.({ materialColorOverride: null, materialOverrides: materials.filter((material) => materialOverrides[material.key]).map((material) => ({ material_index: material.index, material_name: material.name, color: materialOverrides[material.key] })) }); if (result?.success) markAppearanceSaved(); else setAppearanceError("Не вдалося зберегти зміни."); setAppearanceSaving(false); }} type="button">{appearanceSaving ? "Зберігаю…" : "Зберегти"}</button>{appearanceStatus ? <span className="fitting-3d-appearance-status" role="status">{appearanceStatus}</span> : null}</div>
        {appearanceError ? <p className="fitting-3d-appearance-error" role="alert">{appearanceError}</p> : null}
      </div>
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
