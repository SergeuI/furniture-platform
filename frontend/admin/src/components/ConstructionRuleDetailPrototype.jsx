import { ArrowLeft } from "lucide-react";
import { useState } from "react";

const DETAIL_TABS = [
  "Загальна інформація",
  "Геометрія та розташування",
  "Кріплення",
  "Параметри",
  "Варіації",
  "3D / Візуалізація",
  "Примітки",
];

const GEOMETRY_OPTIONS = [
  { key: "on-top", label: "Боковини на дні" },
  { key: "offset", label: "Зі зміщенням" },
  { key: "between", label: "Дно між боковинами" },
];

function GeometryOptionVisual({ variant }) {
  const isBetween = variant === "between";
  const isOffset = variant === "offset";
  const sideLeft = 72;
  const sideRight = 212;
  const sideWidth = 16;
  const bottomX = isOffset || isBetween ? sideLeft + sideWidth : sideLeft;
  const bottomWidth = isOffset || isBetween ? sideRight - (sideLeft + sideWidth) : sideRight + sideWidth - bottomX;
  const bottomY = isOffset ? 78 : isBetween ? 86 : 100;
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
  const [activeTab, setActiveTab] = useState(DETAIL_TABS[0]);
  const [selectedGeometry, setSelectedGeometry] = useState(GEOMETRY_OPTIONS[0].key);

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

      <div className="construction-rule-detail-tabs" role="tablist" aria-label="Розділи правила">
        {DETAIL_TABS.map((tab) => (
          <button
            aria-selected={activeTab === tab}
            className={`ghost-button compact-button${activeTab === tab ? " active" : ""}`}
            key={tab}
            onClick={() => setActiveTab(tab)}
            role="tab"
            type="button"
          >
            {tab}
          </button>
        ))}
      </div>

      {activeTab === "Геометрія та розташування" ? (
        <section className="construction-rule-geometry-section" aria-labelledby="construction-rule-geometry-title">
          <div className="construction-rule-geometry-heading">
            <h2 id="construction-rule-geometry-title">Взаємне розташування деталей</h2>
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
                <GeometryOptionVisual variant={option.key} />
                <span>{option.label}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}
