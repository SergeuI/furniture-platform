const OPERATION_CARDS = [
  {
    key: "hole",
    status: {
      en: "Working",
      uk: "Працює",
    },
    title: {
      en: "Hole",
      uk: "Отвір",
    },
    description: {
      en: "Supported by the current fitting holes workflow.",
      uk: "Підтримується через поточну присадку фурнітури.",
    },
  },
  {
    key: "slot",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Slot",
      uk: "Паз",
    },
    description: {
      en: "Slots will share the same universal operations layer later.",
      uk: "Пази згодом використовуватимуть спільний шар операцій.",
    },
  },
  {
    key: "pocket",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Pocket",
      uk: "Вибірка",
    },
    description: {
      en: "Pocket operations are not wired yet.",
      uk: "Операції вибірок ще не підключені.",
    },
  },
  {
    key: "rect-cutout",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Rectangular cutout",
      uk: "Прямокутний виріз",
    },
    description: {
      en: "Rectangular cutouts will be added in a later step.",
      uk: "Прямокутні вирізи додамо на наступному етапі.",
    },
  },
  {
    key: "contour-cutout",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Contour cutout",
      uk: "Контурний виріз",
    },
    description: {
      en: "Free-form cutouts are reserved for future work.",
      uk: "Довільні контурні вирізи залишено на майбутнє.",
    },
  },
  {
    key: "radius",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Radius",
      uk: "Радіус",
    },
    description: {
      en: "Radius operations will eventually affect contour and edge-band length.",
      uk: "Радіуси згодом впливатимуть на контур і довжину крайки.",
    },
  },
  {
    key: "milling",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Milling",
      uk: "Фрезерування",
    },
    description: {
      en: "Milling will connect to templates and service pricing later.",
      uk: "Фрезерування згодом підключиться до шаблонів і цін.",
    },
  },
  {
    key: "manual",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Manual operation",
      uk: "Ручна операція",
    },
    description: {
      en: "Manual operations are planned as a separate type.",
      uk: "Ручні операції плануються як окремий тип.",
    },
  },
];

function pickLocalizedText(source, language) {
  return source?.[language] || source?.uk || source?.en || "";
}

export default function ProcessingOperations({ language = "uk" }) {
  return (
    <section className="table-panel full-panel">
      <div className="settings-card-header">
        <div>
          <h3>{language === "uk" ? "Операції обробки" : "Processing operations"}</h3>
          <p>
            {language === "uk"
              ? "Показано лише стартовий каркас типів операцій. Тепер робочим є тільки отвір."
              : "This is only the starter skeleton for operation types. Only holes are active now."}
          </p>
        </div>
      </div>

      <div className="dashboard-tile-grid">
        {OPERATION_CARDS.map((card) => (
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
