import { Plus, Search } from "lucide-react";
import { useState } from "react";

// Approved MPFC catalogue/list reference: preserve breadcrumbs, header geometry,
// title typography, found-count placement, subtitle typography, right-side
// search/action alignment, standard page background, and no generic outer frame.
export default function ConstructionRulesReferencePage() {
  const [searchInput, setSearchInput] = useState("");

  return (
    <section className="dashboard-panel mounting-node-catalog-page">
      <div className="mounting-node-catalog-intro">
        <header className="mounting-node-catalog-header">
          <div className="mounting-node-catalog-heading-row">
            <div className="mounting-node-catalog-heading-copy">
              <div className="mounting-node-catalog-title-row">
                <h1>Правила складання</h1>
                  <span className="mounting-node-catalog-count">Знайдено: 0</span>
              </div>
                <p>Правила взаємного розташування деталей та способів їх кріплення.</p>
            </div>
            <div className="mounting-nodes-header-actions">
                <form className="mounting-node-catalog-search" onSubmit={(event) => event.preventDefault()}>
                  <Search aria-hidden="true" size={17} />
                  <input
                    aria-label="Пошук правил"
                    onChange={(event) => setSearchInput(event.target.value)}
                    placeholder="Пошук правил (назва, код, опис...)"
                    type="search"
                    value={searchInput}
                  />
                </form>
              <button className="primary-button mounting-node-create-button" onClick={() => {}} type="button">
                <Plus size={16} />
                Створити правило
              </button>
            </div>
          </div>
        </header>
      </div>
    </section>
  );
}
