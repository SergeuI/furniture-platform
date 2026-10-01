import { Plus, RefreshCw, Search } from "lucide-react";
import { useState } from "react";

// Approved MPFC catalogue/list reference: preserve breadcrumbs, header geometry,
// title typography, found-count placement, subtitle typography, right-side
// search/action alignment, standard page background, and no generic outer frame.
function ConstructionRuleDemoVisual() {
  return (
    <div className="mounting-node-card-preview construction-rule-demo-preview" aria-hidden="true">
      <svg className="construction-rule-demo-svg" viewBox="0 0 320 148" role="presentation">
        <rect className="construction-rule-demo-surface" height="148" rx="10" width="320" x="0" y="0" />
        <rect className="construction-rule-demo-panel" height="104" rx="3" width="22" x="78" y="22" />
        <rect className="construction-rule-demo-panel" height="22" rx="3" width="178" x="90" y="104" />
        <rect className="construction-rule-demo-edge" height="104" width="5" x="78" y="22" />
        <rect className="construction-rule-demo-edge" height="5" width="178" x="90" y="121" />
        <circle className="construction-rule-demo-fastener" cx="101" cy="105" r="7" />
        <circle className="construction-rule-demo-fastener" cx="101" cy="105" r="2.5" />
        <path className="construction-rule-demo-guide" d="M112 92h76" />
        <path className="construction-rule-demo-guide" d="M112 92l8-4m-8 4 8 4" />
        <path className="construction-rule-demo-guide" d="M188 92l-8-4m8 4-8 4" />
      </svg>
    </div>
  );
}

export default function ConstructionRulesReferencePage({ onOpenRuleDetail = null }) {
  const [searchInput, setSearchInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [constructionType, setConstructionType] = useState("all");
  const [connectionType, setConnectionType] = useState("all");
  const [sortOrder, setSortOrder] = useState("name-asc");

  return (
    <section className="dashboard-panel mounting-node-catalog-page">
      <div className="mounting-node-catalog-intro">
        <header className="mounting-node-catalog-header">
          <div className="mounting-node-catalog-heading-row">
            <div className="mounting-node-catalog-heading-copy">
              <div className="mounting-node-catalog-title-row">
                <h1>Правила складання</h1>
                <span className="mounting-node-catalog-count">Знайдено: 1</span>
              </div>
              <p>Правила взаємного розташування деталей та способів їх кріплення.</p>
            </div>
            <div className="mounting-nodes-header-actions">
              <form className="mounting-node-catalog-search" onSubmit={(event) => event.preventDefault()}>
                <Search aria-hidden="true" size={17} />
                <input aria-label="Пошук правил" onChange={(event) => setSearchInput(event.target.value)} placeholder="Пошук правил (назва, код, опис...)" type="search" value={searchInput} />
              </form>
              <button className="primary-button mounting-node-create-button" onClick={() => {}} type="button">
                <Plus size={16} />
                Створити правило
              </button>
            </div>
          </div>
        </header>
      </div>

      <div className="mounting-node-catalog-layout">
        <aside className="mounting-node-filter-sidebar" aria-label="Фільтри">
          <div className="mounting-node-filter-title">
            <strong>Фільтри</strong>
            <button className="ghost-button compact-button" onClick={() => { setStatusFilter("all"); setConstructionType("all"); setConnectionType("all"); setSortOrder("name-asc"); }} type="button">Скинути всі</button>
          </div>
          <div className="mounting-node-filter-group">
            <strong>СТАТУС</strong>
            <div className="mounting-node-filter-options" role="radiogroup" aria-label="Статус">
              {[['all', 'Усі', '1'], ['active', 'Активні', '1'], ['inactive', 'Неактивні', '0']].map(([value, label, count]) => (
                <button aria-checked={statusFilter === value} className={`mounting-node-filter-option${statusFilter === value ? " is-active" : ""}`} key={value} onClick={() => setStatusFilter(value)} role="radio" type="button">
                  <span className="mounting-node-filter-check" aria-hidden="true" /><span>{label}</span><small>{count}</small>
                </button>
              ))}
            </div>
          </div>
          <div className="mounting-node-filter-group">
            <strong>ТИП КОНСТРУКЦІЇ</strong>
            <div className="mounting-node-filter-options" role="radiogroup" aria-label="Тип конструкції">
              {[['all', 'Усі', '1'], ['body', 'Корпус', '1'], ['shelf', 'Полиця', '0'], ['divider', 'Перегородка', '0'], ['facade', 'Фасад', '0'], ['drawer', 'Ящик', '0'], ['other', 'Інше', '0']].map(([value, label, count]) => (
                <button aria-checked={constructionType === value} className={`mounting-node-filter-option${constructionType === value ? " is-active" : ""}`} key={value} onClick={() => setConstructionType(value)} role="radio" type="button">
                  <span className="mounting-node-filter-check" aria-hidden="true" /><span>{label}</span><small>{count}</small>
                </button>
              ))}
            </div>
          </div>
          <div className="mounting-node-filter-group">
            <strong>ТИП З&apos;ЄДНАННЯ</strong>
            <div className="mounting-node-filter-options" role="radiogroup" aria-label="Тип з'єднання">
              {[['all', 'Усі', '1'], ['plane-edge', 'Площина ↔ торець', '1'], ['plane-plane', 'Площина ↔ площина', '0'], ['edge-edge', 'Торець ↔ торець', '0']].map(([value, label, count]) => (
                <button aria-checked={connectionType === value} className={`mounting-node-filter-option${connectionType === value ? " is-active" : ""}`} key={value} onClick={() => setConnectionType(value)} role="radio" type="button">
                  <span className="mounting-node-filter-check" aria-hidden="true" /><span>{label}</span><small>{count}</small>
                </button>
              ))}
            </div>
          </div>
          <div className="mounting-node-filter-group">
            <strong>СОРТУВАННЯ</strong>
            <div className="mounting-node-filter-options" role="radiogroup" aria-label="Сортування">
              {[['name-asc', 'За назвою А–Я'], ['name-desc', 'За назвою Я–А']].map(([value, label]) => (
                <button aria-checked={sortOrder === value} className={`mounting-node-filter-option${sortOrder === value ? " is-active" : ""}`} key={value} onClick={() => setSortOrder(value)} role="radio" type="button">
                  <span className="mounting-node-filter-check" aria-hidden="true" /><span>{label}</span>
                </button>
              ))}
            </div>
          </div>
          <button className="ghost-button mounting-nodes-refresh-button" onClick={() => {}} type="button"><RefreshCw size={16} />Повторити</button>
        </aside>

        <div className="mounting-node-catalog-results">
          <div className="settings-grid mounting-nodes-grid">
            <article
              className="settings-card mounting-node-card"
              onClick={onOpenRuleDetail || undefined}
              onKeyDown={(event) => {
                if (onOpenRuleDetail && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  onOpenRuleDetail();
                }
              }}
              role={onOpenRuleDetail ? "button" : undefined}
              tabIndex={onOpenRuleDetail ? 0 : undefined}
            >
              <div className="mounting-node-card-layout">
                <ConstructionRuleDemoVisual />
                <div className="mounting-node-card-copy">
                  <div className="mounting-node-card-main">
                    <strong className="mounting-node-card-title">Боковина ↔ Дно</strong>
                    <p className="mounting-node-card-description">Взаємне розташування боковин і дна та правила їх кріплення.</p>
                  </div>
                  <div className="mounting-node-card-footer">
                    <div className="mounting-node-card-tags"><span>Корпус</span><span>Площина ↔ торець</span><span>5 варіантів</span></div>
                    <div className="mounting-node-card-status"><span aria-hidden="true" />Активне</div>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>
    </section>
  );
}
