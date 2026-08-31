import { Anchor, ChevronRight, GitBranch, Link2, Shuffle, TestTube2 } from "lucide-react";

import mountingNodesImage from "../../assets/connections_overview/connections-mounting-nodes.png";
import fasteningSchemesImage from "../../assets/connections_overview/connections-fastening-schemes.png";
import jointTypesImage from "../../assets/connections_overview/connections-joint-types.png";
import compatibilityImage from "../../assets/connections_overview/connections-compatibility.png";
import testingImage from "../../assets/connections_overview/connections-testing.png";
import {
  getConnectionsWorkspacePageDescription,
  getConnectionsWorkspacePageLabel,
} from "../../connectionsWorkspace.js";
import MountingSchemesPanel from "./MountingSchemesPanel.jsx";

const CONNECTIONS_OVERVIEW_CARDS = [
  {
    accent: "#2f6fb3",
    chip: "основний flow",
    description: "Тут лишається стабільний існуючий flow монтажних вузлів.",
    icon: Anchor,
    image: mountingNodesImage,
    key: "mountingNodes",
    label: "Монтажні вузли",
    view: "catalogHoles",
  },
  {
    accent: "#c98219",
    chip: "правила",
    description: "Правила кількості, відступів і розстановки монтажних вузлів.",
    icon: GitBranch,
    image: fasteningSchemesImage,
    key: "mountingSchemes",
    label: "Схеми кріплення",
    view: "mountingSchemes",
  },
  {
    accent: "#0f766e",
    chip: "довідник",
    description: "Майбутній довідник типів з'єднань елементів меблів.",
    icon: Link2,
    image: jointTypesImage,
    key: "connectionTypes",
    label: "Типи з'єднань",
    view: "connectionTypes",
  },
  {
    accent: "#7c3aed",
    chip: "сумісність",
    description: "Дозволені заміни та правила сумісності для монтажних вузлів.",
    icon: Shuffle,
    image: compatibilityImage,
    key: "mountingCompatibility",
    label: "Сумісність і заміни",
    view: "mountingCompatibility",
    wide: true,
  },
  {
    accent: "#1f6b34",
    chip: "валідація",
    description: "Невелике місце для майбутніх перевірок і валідації.",
    icon: TestTube2,
    image: testingImage,
    key: "connectionsTesting",
    label: "Тестування",
    view: "connectionsTesting",
    wide: true,
  },
];

function renderBreadcrumbTrail(items = []) {
  return (
    <div className="fitting-category-breadcrumb fitting-category-breadcrumb-top">
      {items.map((item, index) => {
        const isLast = index === items.length - 1;
        const isCurrent = Boolean(item?.current);
        const label = String(item?.label || "").trim();
        const title = String(item?.title || label || "").trim();

        return (
          <span className="fitting-category-breadcrumb-item" key={`${label || "crumb"}-${index}`}>
            <h3 className="catalog-breadcrumb-title">
              {isCurrent || !item?.onClick ? (
                <span aria-current={isCurrent ? "page" : undefined} title={title || label}>
                  {label}
                </span>
              ) : (
                <button className="catalog-breadcrumb-link" onClick={item.onClick} title={title || label} type="button">
                  {label}
                </button>
              )}
            </h3>
            {!isLast ? <span className="fitting-breadcrumb-separator">/</span> : null}
          </span>
        );
      })}
    </div>
  );
}

function getPageMeta(activeView, language) {
  if (activeView === "connectionsOverview") {
    return {
      description: getConnectionsWorkspacePageDescription(activeView, language),
      title: getConnectionsWorkspacePageLabel(activeView, language),
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

export default function ConnectionsWorkspace({
  activeView = "connectionsOverview",
  language = "uk",
  onNavigate = null,
  token = "",
}) {
  const meta = getPageMeta(activeView, language);

  if (activeView === "mountingSchemes") {
    return <MountingSchemesPanel language={language} onOpenConnectionsOverview={() => onNavigate?.("connectionsOverview")} token={token} />;
  }

  if (activeView !== "connectionsOverview") {
    return (
      <section className="table-panel full-panel connections-placeholder-page">
        <article className="catalog-card service-catalog-card service-catalog-card-full connections-placeholder-card">
          <div className="catalog-page-header material-taxonomy-page-header connections-placeholder-header">
            <div className="service-catalog-title material-taxonomy-page-title">
              {renderBreadcrumbTrail([
                {
                  label: language === "uk" ? "Кріплення та з'єднання" : "Connections",
                  onClick: typeof onNavigate === "function" ? () => onNavigate("connectionsOverview") : undefined,
                  title: language === "uk" ? "Кріплення та з'єднання" : "Connections",
                },
                {
                  current: true,
                  label: meta.title,
                  title: meta.title,
                },
              ])}
              <p>{meta.description}</p>
            </div>
          </div>
          <div className="dashboard-layout">
            <article className="dashboard-hero-card">
              <div className="dashboard-hero-copy">
                <h3>{meta.title}</h3>
                <p>{meta.description}</p>
              </div>
            </article>
          </div>
        </article>
      </section>
    );
  }

  return (
    <section className="table-panel full-panel connections-overview-page">
      <article className="catalog-card service-catalog-card service-catalog-card-full connections-overview-card">
        <div className="catalog-page-header material-taxonomy-page-header connections-overview-header">
          <div className="service-catalog-title material-taxonomy-page-title">
            {renderBreadcrumbTrail([
              {
                current: true,
                label: meta.title,
                title: meta.title,
              },
            ])}
            <p>{meta.description}</p>
          </div>
          <div className="service-catalog-header-actions connections-overview-actions">
            <span className="service-tree-badge subtle">
              {CONNECTIONS_OVERVIEW_CARDS.length} {language === "uk" ? "розділів" : "sections"}
            </span>
          </div>
        </div>
        <div className="catalog-hub-grid" role="list" aria-label={meta.title}>
          {CONNECTIONS_OVERVIEW_CARDS.map((card) => {
            const Icon = card.icon;
            const isClickable = typeof onNavigate === "function";

            return (
              <button
                className="catalog-hub-tile"
                key={card.key}
                onClick={() => {
                  if (isClickable) {
                    onNavigate(card.view);
                  }
                }}
                type="button"
              >
                <span className="catalog-hub-tile-media">
                  <span className="catalog-hub-tile-image-frame">
                    <img alt="" aria-hidden="true" loading="lazy" src={card.image} />
                  </span>
                  <span
                    className="catalog-hub-tile-icon"
                    style={{ "--catalog-accent": card.accent }}
                  >
                    <Icon size={24} />
                  </span>
                </span>
                <span className="catalog-hub-tile-body">
                  <span className="catalog-hub-tile-copy">
                    <strong>{card.label}</strong>
                    <span>{card.description}</span>
                  </span>
                  <span className="catalog-hub-tile-chips">
                    <span className="catalog-hub-chip">
                      <strong>{card.chip}</strong>
                    </span>
                  </span>
                  <span className="catalog-hub-tile-link">
                    {language === "uk" ? "Відкрити розділ" : "Open section"}
                    <ChevronRight size={16} />
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </article>
    </section>
  );
}
