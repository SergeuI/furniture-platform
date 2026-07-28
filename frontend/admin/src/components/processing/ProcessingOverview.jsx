import { getProcessingOverviewCards } from "../../processingWorkspace.js";

export default function ProcessingOverview({ language = "uk" }) {
  const cards = getProcessingOverviewCards(language);

  return (
    <section className="dashboard-panel">
      <div className="dashboard-panel-head">
        <div>
          <h3>{language === "uk" ? "Огляд" : "Overview"}</h3>
          <p>
            {language === "uk"
              ? "У цьому розділі показано стартові блоки нового напрямку та їхній поточний стан."
              : "This section shows the starter blocks for the new direction and their current status."}
          </p>
        </div>
      </div>
      <div className="dashboard-tile-grid">
        {cards.map((card) => (
          <article className="dashboard-tile-card" key={card.key}>
            <div className="dashboard-tile-copy">
              <strong>{card.label}</strong>
              <span>{card.description}</span>
            </div>
            <span className="service-tree-badge subtle">{card.status}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
