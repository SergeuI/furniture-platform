const TEMPLATE_CARDS = [
  {
    key: "fittings",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Fittings",
      uk: "Фурнітура",
    },
    description: {
      en: "Templates for hinges, lifts, supports, and other fittings.",
      uk: "Шаблони для петель, підйомників, упорів та іншої фурнітури.",
    },
  },
  {
    key: "sinks",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Sinks",
      uk: "Мийки",
    },
    description: {
      en: "Templates for sink cutouts and related attachments.",
      uk: "Шаблони для мийок, вирізів і супутніх кріплень.",
    },
  },
  {
    key: "hobs",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Hobs",
      uk: "Варильні поверхні",
    },
    description: {
      en: "Templates for hobs and cooktop cutouts.",
      uk: "Шаблони для варильних поверхонь і вирізів під них.",
    },
  },
  {
    key: "appliances",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Appliances",
      uk: "Техніка",
    },
    description: {
      en: "Templates for built-in appliances.",
      uk: "Шаблони для вбудованої побутової техніки.",
    },
  },
  {
    key: "grilles",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Ventilation grilles",
      uk: "Вентиляційні решітки",
    },
    description: {
      en: "Templates for air grilles and vents.",
      uk: "Шаблони для решіток вентиляції та отворів під них.",
    },
  },
  {
    key: "lighting",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Lighting",
      uk: "Освітлення",
    },
    description: {
      en: "Templates for spotlights and other lighting fixtures.",
      uk: "Шаблони для світильників і точкових джерел світла.",
    },
  },
  {
    key: "custom",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "User templates",
      uk: "Користувацькі шаблони",
    },
    description: {
      en: "A reusable slot for company and user-defined templates.",
      uk: "Окреме місце для компанійських і користувацьких шаблонів.",
    },
  },
];

function pickLocalizedText(source, language) {
  return source?.[language] || source?.uk || source?.en || "";
}

export default function ProcessingTemplates({ language = "uk", onOpenFittingHolesEditor = null }) {
  return (
    <section className="table-panel full-panel">
      <div className="settings-card-header">
        <div>
          <h3>{language === "uk" ? "Шаблони обробки" : "Processing templates"}</h3>
          <p>
            {language === "uk"
              ? "Один шаблон у майбутньому міститиме набір операцій для фурнітури, мийок, техніки та інших об'єктів."
              : "A single template will later hold a set of operations for fittings, sinks, appliances, and other objects."}
          </p>
        </div>
        {typeof onOpenFittingHolesEditor === "function" ? (
          <button className="primary-button" onClick={onOpenFittingHolesEditor} type="button">
            {language === "uk" ? "Перейти до присадки фурнітури" : "Open fitting holes"}
          </button>
        ) : null}
      </div>

      <div className="dashboard-tile-grid">
        {TEMPLATE_CARDS.map((card) => (
          <article className="dashboard-tile-card" key={card.key}>
            <div className="dashboard-tile-copy">
              <strong>{pickLocalizedText(card.title, language)}</strong>
              <span>{pickLocalizedText(card.description, language)}</span>
            </div>
            <span className="service-tree-badge subtle">{pickLocalizedText(card.status, language)}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
