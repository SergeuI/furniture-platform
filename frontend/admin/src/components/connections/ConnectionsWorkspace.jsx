import { Blocks, CheckCircle2, FolderTree, Scissors, Wrench } from "lucide-react";

import {
  getConnectionsWorkspaceOverviewCards,
  getConnectionsWorkspacePageLabel,
} from "../../connectionsWorkspace.js";
import MountingSchemesPanel from "./MountingSchemesPanel.jsx";

function getPageMeta(activeView, language) {
  if (activeView === "connectionsOverview") {
    return {
      description:
        language === "uk"
          ? "Налаштування монтажних вузлів, схем кріплення, типів з'єднань і правил замін."
          : "Settings for mounting nodes, mounting schemes, connection types, and replacement rules.",
      title: language === "uk" ? "Кріплення та з'єднання" : "Connections",
    };
  }

  return {
    description:
      language === "uk"
        ? "Ця сторінка поки є простим каркасом без бізнес-логіки."
        : "This page is currently a simple placeholder without business logic.",
    title: getConnectionsWorkspacePageLabel(activeView, language),
  };
}

function getCardIcon(cardKey) {
  switch (cardKey) {
    case "mountingNodes":
      return FolderTree;
    case "mountingSchemes":
      return FolderTree;
    case "connectionTypes":
      return Blocks;
    case "mountingCompatibility":
      return Wrench;
    case "connectionsTesting":
      return CheckCircle2;
    default:
      return Scissors;
  }
}

export default function ConnectionsWorkspace({
  activeView = "connectionsOverview",
  language = "uk",
  onNavigate = null,
  token = "",
}) {
  const meta = getPageMeta(activeView, language);
  const overviewCards = getConnectionsWorkspaceOverviewCards({ language });

  if (activeView === "mountingSchemes") {
    return <MountingSchemesPanel language={language} token={token} />;
  }

  if (activeView !== "connectionsOverview") {
    return (
      <section className="dashboard-layout">
        <article className="dashboard-hero-card">
          <div className="dashboard-hero-copy">
            <span className="dashboard-eyebrow">
              {language === "uk" ? "Новий розділ" : "New section"}
            </span>
            <h3>{meta.title}</h3>
            <p>{meta.description}</p>
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="dashboard-layout">
      <article className="dashboard-hero-card">
        <div className="dashboard-hero-copy">
          <span className="dashboard-eyebrow">
            {language === "uk" ? "Окремий розділ" : "Dedicated area"}
          </span>
          <h3>{meta.title}</h3>
          <p>{meta.description}</p>
        </div>
        <div className="dashboard-status-card">
          <div className="dashboard-status-head">
            <div className="dashboard-status-title">
              <strong>{language === "uk" ? "Що тут є" : "What is inside"}</strong>
              <p>{language === "uk" ? "5 карток для швидкого входу" : "5 quick entry cards"}</p>
            </div>
            <span className="dashboard-status-badge live">
              {language === "uk" ? "Готово" : "Ready"}
            </span>
          </div>
          <p>
            {language === "uk"
              ? "Це лише навігаційний каркас. Справжній flow монтажних вузлів лишається без змін."
              : "This is only a navigation scaffold. The real mounting-node flow stays unchanged."}
          </p>
        </div>
      </article>

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Швидкий вхід" : "Quick entry"}</h3>
            <p>
              {language === "uk"
                ? "Кожна картка веде на окрему сторінку або до існуючого монтажного flow."
                : "Each card opens a dedicated page or the existing mounting-node flow."}
            </p>
          </div>
        </div>
        <div className="dashboard-tile-grid">
          {overviewCards.map((card) => {
            const Icon = getCardIcon(card.key);
            return (
              <button
              className="dashboard-tile-card"
              key={card.key}
              onClick={() => {
                if (typeof onNavigate === "function") {
                  onNavigate(card.view || card.key);
                }
              }}
                type="button"
              >
                <span className="dashboard-tile-art">
                  <Icon size={30} />
                </span>
                <div className="dashboard-tile-copy">
                  <strong>{card.label}</strong>
                  <span>{card.description}</span>
                </div>
              </button>
            );
          })}
        </div>
      </article>
    </section>
  );
}
