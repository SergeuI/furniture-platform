import { useEffect, useMemo, useState } from "react";

import ProcessingFittingHoles from "./ProcessingFittingHoles.jsx";
import ProcessingOperations from "./ProcessingOperations.jsx";
import ProcessingOverview from "./ProcessingOverview.jsx";
import ProcessingPricingRules from "./ProcessingPricingRules.jsx";
import ProcessingServicesPrices from "./ProcessingServicesPrices.jsx";
import ProcessingTemplates from "./ProcessingTemplates.jsx";
import ProcessingTesting from "./ProcessingTesting.jsx";
import {
  getProcessingTabLabel,
  getProcessingTabStatus,
  getProcessingWorkspaceTabs,
  normalizeProcessingWorkspaceTab,
  PROCESSING_WORKSPACE_STORAGE_KEY,
} from "../../processingWorkspace.js";

function buildProcessingWorkspaceIntro(language) {
  if (language === "uk") {
    return {
      description: "Перший каркас нового напрямку без дублювання існуючого редактора.",
      title: "Обробка деталей",
    };
  }

  return {
    description: "The first skeleton of the new direction without duplicating the existing editor.",
    title: "Processing",
  };
}

export default function ProcessingWorkspace({
  canUseFittingHoles = false,
  isAdmin = false,
  language = "uk",
  onOpenFittingHolesEditor = null,
  token = "",
}) {
  const tabs = useMemo(
    () =>
      getProcessingWorkspaceTabs({
        canUseFittingHoles,
        isAdmin,
        language,
      }),
    [canUseFittingHoles, isAdmin, language],
  );
  const [activeTab, setActiveTab] = useState(() =>
    normalizeProcessingWorkspaceTab(localStorage.getItem(PROCESSING_WORKSPACE_STORAGE_KEY) || "overview", {
      canUseFittingHoles,
      isAdmin,
    }),
  );

  useEffect(() => {
    const nextTab = normalizeProcessingWorkspaceTab(activeTab, {
      canUseFittingHoles,
      isAdmin,
    });

    if (nextTab !== activeTab) {
      setActiveTab(nextTab);
    }
  }, [activeTab, canUseFittingHoles, isAdmin]);

  useEffect(() => {
    localStorage.setItem(PROCESSING_WORKSPACE_STORAGE_KEY, activeTab);
  }, [activeTab]);

  const currentTab = tabs.find((tab) => tab.key === activeTab) || tabs[0] || null;
  const intro = buildProcessingWorkspaceIntro(language);

  return (
    <section className="dashboard-layout">
      <article className="dashboard-hero-card">
        <div className="dashboard-hero-copy">
          <span className="dashboard-eyebrow">
            {language === "uk" ? "Новий напрямок" : "New workspace"}
          </span>
          <h3>{intro.title}</h3>
          <p>{intro.description}</p>
        </div>
        <div className="dashboard-status-card">
          <div className="dashboard-status-head">
            <div className="dashboard-status-title">
              <strong>{language === "uk" ? "Поточна вкладка" : "Current tab"}</strong>
              <p>{getProcessingTabLabel(activeTab, language)}</p>
            </div>
            <span className="dashboard-status-badge live">
              {getProcessingTabStatus(activeTab, language)}
            </span>
          </div>
          <p>
            {language === "uk"
              ? "Структура поки що каркасна: без записів у БД, без нового router і без дублювання editor."
              : "The structure is skeletal for now: no database writes, no new router, and no duplicated editor."}
          </p>
        </div>
      </article>

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Меню розділу" : "Workspace menu"}</h3>
            <p>
              {language === "uk"
                ? "Тут зібрано майбутні підрозділи нового напрямку."
                : "This groups the future sub-sections of the new direction."}
            </p>
          </div>
        </div>

        <div className="nav-subtabs" role="tablist" aria-label={language === "uk" ? "Обробка деталей" : "Processing"}>
          {tabs.map((tab) => (
            <button
              aria-selected={tab.key === activeTab}
              className={tab.key === activeTab ? "active" : ""}
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              role="tab"
              type="button"
            >
              <span>{tab.label}</span>
              <small>{tab.status}</small>
            </button>
          ))}
        </div>
      </article>

      {activeTab === "overview" ? (
        <ProcessingOverview language={language} />
      ) : activeTab === "operations" ? (
        <ProcessingOperations language={language} />
      ) : activeTab === "templates" ? (
        <ProcessingTemplates
          language={language}
          onOpenFittingHolesEditor={onOpenFittingHolesEditor}
        />
      ) : activeTab === "fitting-holes" ? (
        <ProcessingFittingHoles
          language={language}
          onOpenFittingHolesEditor={onOpenFittingHolesEditor}
        />
      ) : activeTab === "services-prices" ? (
        <ProcessingServicesPrices language={language} />
      ) : activeTab === "pricing-rules" ? (
        <ProcessingPricingRules language={language} />
      ) : activeTab === "testing" ? (
        <ProcessingTesting language={language} token={token} />
      ) : null}
    </section>
  );
}
