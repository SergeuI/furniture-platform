import ProcessingOperations from "./ProcessingOperations.jsx";
import HoleLibraryPanel from "./HoleLibraryPanel.jsx";
import ProcessingOverview from "./ProcessingOverview.jsx";
import ProcessingPricingRules from "./ProcessingPricingRules.jsx";
import ProcessingServicesPrices from "./ProcessingServicesPrices.jsx";
import ProcessingTemplates from "./ProcessingTemplates.jsx";
import ProcessingTesting from "./ProcessingTesting.jsx";
import {
  getProcessingTabLabel,
  getProcessingTabStatus,
} from "../../processingWorkspace.js";

function buildProcessingWorkspaceIntro(language) {
  if (language === "uk") {
    return {
      description: "Робочий простір обробки зберігає налаштування та довідники у БД.",
      title: "Обробка деталей",
    };
  }

  return {
    description: "The processing workspace stores settings and reference data in the database.",
    title: "Processing",
  };
}

export default function ProcessingWorkspace({
  activeTab = "overview",
  language = "uk",
  onOpenFittingHolesEditor = null,
  token = "",
}) {
  const intro = buildProcessingWorkspaceIntro(language);
  const currentTabLabel = getProcessingTabLabel(activeTab, language);
  const currentTabStatus = getProcessingTabStatus(activeTab, language);

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
              <p>{currentTabLabel}</p>
            </div>
            <span className="dashboard-status-badge live">
              {currentTabStatus}
            </span>
          </div>
          <p>
            {language === "uk"
              ? "Довідники та налаштування обробки зберігаються у БД."
              : "Processing settings and reference data are stored in the database."}
          </p>
        </div>
      </article>

      {activeTab === "overview" ? (
        <ProcessingOverview language={language} />
      ) : activeTab === "operations" ? (
        <ProcessingOperations language={language} token={token} />
      ) : activeTab === "templates" ? (
        <ProcessingTemplates
          language={language}
          onOpenFittingHolesEditor={
            typeof onOpenFittingHolesEditor === "function"
              ? (context) => onOpenFittingHolesEditor({ ...context, processingTab: activeTab })
              : null
          }
          token={token}
        />
      ) : activeTab === "hole-library" ? (
        <HoleLibraryPanel language={language} token={token} />
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
