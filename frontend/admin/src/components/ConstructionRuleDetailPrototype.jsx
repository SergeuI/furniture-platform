import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import ConstructionRule3DPreview from "./ConstructionRule3DPreview.jsx";

const GEOMETRY_OPTIONS = [
  { key: "on-top", label: "Боковини на дні" },
  { key: "offset", label: "Зі зміщенням" },
  { key: "between", label: "Дно між боковинами" },
];

function GeometryOptionVisual({ offsetMm = 100, variant }) {
  const isBetween = variant === "between";
  const isOffset = variant === "offset";
  const sideLeft = 72;
  const sideRight = 212;
  const sideWidth = 16;
  const bottomX = isOffset || isBetween ? sideLeft + sideWidth : sideLeft;
  const bottomWidth = isOffset || isBetween ? sideRight - (sideLeft + sideWidth) : sideRight + sideWidth - bottomX;
  const normalizedOffset = Math.min(300, Math.max(0, Number(offsetMm) || 0));
  const bottomY = isOffset ? 86 - (normalizedOffset / 300) * 24 : isBetween ? 86 : 100;
  const sideTop = 24;
  const sideHeight = 76;

  return (
    <svg className="construction-rule-geometry-svg" viewBox="0 0 300 128" role="presentation">
      <rect className="construction-rule-geometry-surface" height="128" rx="8" width="300" x="0" y="0" />
      <rect className="construction-rule-geometry-part" height={sideHeight} rx="2" width={sideWidth} x={sideLeft} y={sideTop} />
      <rect className="construction-rule-geometry-part" height={sideHeight} rx="2" width={sideWidth} x={sideRight} y={sideTop} />
      <rect className="construction-rule-geometry-part geometry-bottom" height="14" rx="2" width={bottomWidth} x={bottomX} y={bottomY} />
      {isOffset || isBetween ? (
        <>
          <line className="construction-rule-geometry-fastener" x1={sideLeft - 12} x2={bottomX + 12} y1={bottomY + 7} y2={bottomY + 7} />
          <circle className="construction-rule-geometry-fastener-head" cx={sideLeft - 12} cy={bottomY + 7} r="5" />
          <line className="construction-rule-geometry-fastener" x1={sideRight + sideWidth + 12} x2={bottomX + bottomWidth - 12} y1={bottomY + 7} y2={bottomY + 7} />
          <circle className="construction-rule-geometry-fastener-head" cx={sideRight + sideWidth + 12} cy={bottomY + 7} r="5" />
        </>
      ) : (
        <>
          <line className="construction-rule-geometry-fastener" x1={sideLeft + sideWidth / 2} x2={sideLeft + sideWidth / 2} y1={bottomY + 18} y2={bottomY - 8} />
          <circle className="construction-rule-geometry-fastener-head" cx={sideLeft + sideWidth / 2} cy={bottomY + 22} r="5" />
          <line className="construction-rule-geometry-fastener" x1={sideRight + sideWidth / 2} x2={sideRight + sideWidth / 2} y1={bottomY + 18} y2={bottomY - 8} />
          <circle className="construction-rule-geometry-fastener-head" cx={sideRight + sideWidth / 2} cy={bottomY + 22} r="5" />
        </>
      )}
    </svg>
  );
}

export default function ConstructionRuleDetailPrototype({ onBack = null }) {
  const [selectedGeometry, setSelectedGeometry] = useState(GEOMETRY_OPTIONS[0].key);
  const [offsetMm, setOffsetMm] = useState(100);
  const [showFasteners, setShowFasteners] = useState(false);
  const [depthMm, setDepthMm] = useState(500);
  const [edgeOffsetMm, setEdgeOffsetMm] = useState(50);
  const selectedGeometryLabel = GEOMETRY_OPTIONS.find((option) => option.key === selectedGeometry)?.label || "";

  return (
    <section className="dashboard-panel mounting-node-catalog-page construction-rule-detail-page">
      <div className="mounting-node-catalog-intro">
        <header className="mounting-node-catalog-header">
          <div className="mounting-node-catalog-heading-row">
            <div className="mounting-node-catalog-heading-copy">
              <div className="mounting-node-catalog-title-row">
                <h1>Правило з&apos;єднання: Боковина - Дно</h1>
                <span className="construction-rule-detail-status"><span aria-hidden="true" />Активне</span>
              </div>
              <p>Визначає взаємне розташування боковин і дна та спосіб їх кріплення.</p>
            </div>
            <div className="mounting-nodes-header-actions">
              <button className="ghost-button compact-button" onClick={onBack || undefined} type="button">
                <ArrowLeft size={16} />
                Назад
              </button>
            </div>
          </div>
        </header>
      </div>

      <section className="construction-rule-geometry-section" aria-labelledby="construction-rule-geometry-title">
        <div className="construction-rule-geometry-heading">
          <h2 id="construction-rule-geometry-title">Варіант конструкції</h2>
          <p>Оберіть спосіб встановлення дна відносно боковин.</p>
        </div>
        <div className="construction-rule-geometry-options">
          {GEOMETRY_OPTIONS.map((option) => (
            <button
              aria-pressed={selectedGeometry === option.key}
              className={`settings-card construction-rule-geometry-option${selectedGeometry === option.key ? " is-selected" : ""}`}
              key={option.key}
              onClick={() => setSelectedGeometry(option.key)}
              type="button"
            >
              <GeometryOptionVisual offsetMm={offsetMm} variant={option.key} />
              <span>{option.label}</span>
            </button>
          ))}
        </div>
        <div className="construction-rule-workspace">
          <section className="construction-rule-settings-card" aria-labelledby="construction-rule-settings-title">
            <h2 id="construction-rule-settings-title">Налаштування варіанта</h2>
            <p className="construction-rule-selected-variant">{selectedGeometryLabel}</p>
            <section className="construction-rule-position-parameters" aria-labelledby="construction-rule-dimensions-title">
              <h3 id="construction-rule-dimensions-title">Параметри конструкції</h3>
              <label className="construction-rule-position-field">
                <span>Глибина конструкції</span>
                <span className="construction-rule-position-input-wrap">
                  <input max="800" min="200" onChange={(event) => setDepthMm(Math.min(800, Math.max(200, Number(event.target.value) || 200)))} step="10" type="number" value={depthMm} />
                  <span>мм</span>
                </span>
              </label>
            </section>
            {selectedGeometry === "offset" ? (
              <section className="construction-rule-position-parameters" aria-labelledby="construction-rule-position-parameters-title">
                <h3 id="construction-rule-position-parameters-title">Параметри розташування</h3>
                <label className="construction-rule-position-field">
                  <span>Відступ дна від нижнього торця боковин</span>
                  <span className="construction-rule-position-input-wrap">
                    <input
                      max="300"
                      min="0"
                      onChange={(event) => setOffsetMm(Math.min(300, Math.max(0, Number(event.target.value) || 0)))}
                      step="1"
                      type="number"
                      value={offsetMm}
                    />
                    <span>мм</span>
                  </span>
                </label>
                <p>Визначає висоту підйому нижньої площини дна відносно нижніх торців боковин.</p>
              </section>
            ) : null}
            <section className="construction-rule-fastening-summary" aria-labelledby="construction-rule-fastening-title">
              <h3 id="construction-rule-fastening-title">Кріплення</h3>
              <strong>Конфірмат 7×50</strong>
              <label className="construction-rule-position-field">
                <span>Схема кріплення</span>
                <select defaultValue="symmetric-two-points" aria-label="Схема кріплення">
                  <option value="symmetric-two-points">Симетрично, 2 точки</option>
                </select>
              </label>
              <label className="construction-rule-position-field">
                <span>Відступ від краю</span>
                <span className="construction-rule-position-input-wrap">
                  <input max={Math.max(0, Math.floor(depthMm / 2) - 10)} min="0" onChange={(event) => setEdgeOffsetMm(Math.min(Math.max(0, Math.floor(depthMm / 2) - 10), Math.max(0, Number(event.target.value) || 0)))} step="10" type="number" value={edgeOffsetMm} />
                  <span>мм</span>
                </span>
              </label>
              <p>2 точки на сторону</p>
            </section>
          </section>
          <section className="construction-rule-large-preview" aria-labelledby="construction-rule-preview-title">
            <h2 id="construction-rule-preview-title">Візуалізація</h2>
            <label className="construction-rule-fastener-toggle">
              <input checked={showFasteners} onChange={(event) => setShowFasteners(event.target.checked)} type="checkbox" />
              <span>Показати кріплення</span>
            </label>
            <ConstructionRule3DPreview depthMm={depthMm} edgeOffsetMm={edgeOffsetMm} offsetMm={offsetMm} selectedVariant={selectedGeometry} showFasteners={showFasteners} />
          </section>
        </div>
      </section>
    </section>
  );
}
