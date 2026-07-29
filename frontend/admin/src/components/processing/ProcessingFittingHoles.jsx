export default function ProcessingFittingHoles({
  language = "uk",
  onOpenFittingHolesEditor = null,
}) {
  return (
    <section className="dashboard-panel">
      <div className="dashboard-panel-head">
        <div>
          <h3>{language === "uk" ? "Монтажні вузли" : "Mounting nodes"}</h3>
          <p>
            {language === "uk"
              ? "Це чинний редактор монтажних вузлів. Тут залишаємо поточну робочу реалізацію без дублювання."
              : "This is the current mounting nodes editor. The existing working implementation stays here without duplication."}
          </p>
        </div>
      </div>

      <div className="settings-card">
        <p>
          {language === "uk"
            ? "У цьому каркасі лише посилання на чинний редактор. Сам редактор не дублюється."
            : "This card only links to the existing editor. The editor itself is not duplicated."}
        </p>
        {typeof onOpenFittingHolesEditor === "function" ? (
          <button className="primary-button" onClick={onOpenFittingHolesEditor} type="button">
            {language === "uk" ? "Відкрити монтажні вузли" : "Open mounting nodes editor"}
          </button>
        ) : null}
      </div>
    </section>
  );
}
