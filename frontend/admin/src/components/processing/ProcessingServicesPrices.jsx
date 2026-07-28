const SERVICE_PRICE_CARDS = [
  {
    key: "viyar",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "VR / Viyar",
      uk: "VR / Віяр",
    },
    description: {
      en: "The catalog already exists and will be attached here later.",
      uk: "Довідник уже існує і буде підключений сюди пізніше.",
    },
  },
  {
    key: "company",
    status: {
      en: "Needs setup",
      uk: "Потребує налаштування",
    },
    title: {
      en: "Company prices",
      uk: "Власні ціни компанії",
    },
    description: {
      en: "Company markups and custom price overrides will live here.",
      uk: "Тут буде місце для націнок компанії та власних цін.",
    },
  },
  {
    key: "manual",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Manual services",
      uk: "Ручні послуги",
    },
    description: {
      en: "Manual add-on services are a future stage of the workspace.",
      uk: "Ручні додаткові послуги входять у майбутній етап workspace.",
    },
  },
  {
    key: "history",
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    title: {
      en: "Price history",
      uk: "Історія цін",
    },
    description: {
      en: "Price snapshots and sync history will appear later.",
      uk: "Знімки цін та історія синхронізації з'являться пізніше.",
    },
  },
];

function pickLocalizedText(source, language) {
  return source?.[language] || source?.uk || source?.en || "";
}

export default function ProcessingServicesPrices({ language = "uk" }) {
  return (
    <section className="table-panel full-panel">
      <div className="settings-card-header">
        <div>
          <h3>{language === "uk" ? "Послуги та ціни" : "Services & prices"}</h3>
          <p>
            {language === "uk"
              ? "Цей блок лише готує місце для довідника VR / Віяр, власних цін і ручних послуг."
              : "This block only prepares a place for the VR / Viyar catalog, own prices, and manual services."}
          </p>
        </div>
      </div>

      <div className="dashboard-tile-grid">
        {SERVICE_PRICE_CARDS.map((card) => (
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
