const PRICING_RULE_CARDS = [
  {
    key: "per-operation",
    title: {
      en: "By one operation",
      uk: "За одну операцію",
    },
    description: {
      en: "A direct price per processing operation.",
      uk: "Пряма ціна за одну операцію обробки.",
    },
  },
  {
    key: "per-hole",
    title: {
      en: "By one hole",
      uk: "За один отвір",
    },
    description: {
      en: "Useful for drilling and hole-based services.",
      uk: "Зручно для свердління та отвірних послуг.",
    },
  },
  {
    key: "per-meter",
    title: {
      en: "By running meter",
      uk: "За погонний метр",
    },
    description: {
      en: "Useful for grooves, milling, and contour work.",
      uk: "Підходить для пазів, фрезерування і контуру.",
    },
  },
  {
    key: "per-area",
    title: {
      en: "By area",
      uk: "За площу",
    },
    description: {
      en: "Useful when a machining rule depends on surface area.",
      uk: "Потрібно, коли правило залежить від площі поверхні.",
    },
  },
  {
    key: "per-contour",
    title: {
      en: "By contour length",
      uk: "За довжиною контуру",
    },
    description: {
      en: "Useful for future finished contour calculations.",
      uk: "Потрібно для майбутнього готового контуру.",
    },
  },
  {
    key: "manual",
    title: {
      en: "Manual price",
      uk: "Ручна ціна",
    },
    description: {
      en: "A final company-managed override.",
      uk: "Фінальне перевизначення ціни з боку компанії.",
    },
  },
];

function pickLocalizedText(source, language) {
  return source?.[language] || source?.uk || source?.en || "";
}

export default function ProcessingPricingRules({ language = "uk" }) {
  return (
    <section className="table-panel full-panel">
      <div className="settings-card-header">
        <div>
          <h3>{language === "uk" ? "Правила розрахунку" : "Pricing rules"}</h3>
          <p>
            {language === "uk"
              ? "Поки це лише каркас майбутніх способів розрахунку без реального редактора і без запису в БД."
              : "This is only the skeleton of future pricing methods, without a real editor or database writes."}
          </p>
        </div>
      </div>

      <div className="dashboard-tile-grid">
        {PRICING_RULE_CARDS.map((card) => (
          <article className="dashboard-tile-card" key={card.key}>
            <div className="dashboard-tile-copy">
              <strong>{pickLocalizedText(card.title, language)}</strong>
              <span>{pickLocalizedText(card.description, language)}</span>
            </div>
            <span className="service-tree-badge subtle">
              {language === "uk" ? "Заплановано" : "Planned"}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
