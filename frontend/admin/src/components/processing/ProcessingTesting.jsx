import { useEffect, useMemo, useState } from "react";

import { getProcessingOperationsPreview } from "../../api.js";

function formatValue(value, language) {
  if (value === null || value === undefined || value === "") {
    return language === "uk" ? "Не визначено" : "Not set";
  }

  if (typeof value === "boolean") {
    return value ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No");
  }

  return String(value);
}

function OperationPreviewCard({ operation, language }) {
  return (
    <article className="settings-card">
      <div className="settings-card-header">
        <div>
          <strong>{operation.label || (language === "uk" ? "Без мітки" : "Untitled")}</strong>
          <p>
            {operation.operation_type || formatValue(null, language)} ·{" "}
            {operation.source_type || formatValue(null, language)}
          </p>
        </div>
        <span className="service-tree-badge subtle">
          {formatValue(operation.production_effects?.include_in_estimate, language)}
        </span>
      </div>

      <div className="settings-info-grid">
        <div>
          <span>{language === "uk" ? "Координати" : "Coordinates"}</span>
          <strong>
            x: {formatValue(operation.placement?.x_mm, language)}, y: {formatValue(operation.placement?.y_mm, language)}, z: {formatValue(operation.placement?.z_mm, language)}
          </strong>
        </div>
        <div>
          <span>{language === "uk" ? "Панель" : "Panel"}</span>
          <strong>
            {formatValue(operation.placement?.target_panel, language)} / {formatValue(operation.placement?.target_surface, language)} / {formatValue(operation.placement?.target_side, language)}
          </strong>
        </div>
        <div>
          <span>{language === "uk" ? "Геометрія" : "Geometry"}</span>
          <strong>
            d: {formatValue(operation.geometry?.diameter_mm, language)}, h: {formatValue(operation.geometry?.depth_mm, language)}
          </strong>
        </div>
        <div>
          <span>{language === "uk" ? "Кількість" : "Quantity"}</span>
          <strong>
            {formatValue(operation.quantity, language)} · {operation.mirrored ? (language === "uk" ? "дзеркально" : "mirrored") : (language === "uk" ? "звичайно" : "normal")}
          </strong>
        </div>
        <div>
          <span>{language === "uk" ? "Послуга" : "Service"}</span>
          <strong>
            {operation.service_mapping?.found ? (language === "uk" ? "Знайдено" : "Found") : (language === "uk" ? "Не знайдено" : "Not found")}
          </strong>
        </div>
        <div>
          <span>{language === "uk" ? "Каталожний елемент" : "Catalog item"}</span>
          <strong>{formatValue(operation.service_mapping?.resolved_service_catalog_item_id, language)}</strong>
        </div>
      </div>

      <details className="settings-card" style={{ marginTop: "0.75rem" }}>
        <summary>{language === "uk" ? "Технічні JSON-дані" : "Technical JSON data"}</summary>
        <pre style={{ overflowX: "auto", whiteSpace: "pre-wrap" }}>{JSON.stringify(operation, null, 2)}</pre>
      </details>
    </article>
  );
}

export default function ProcessingTesting({
  language = "uk",
  token,
}) {
  const [templateId, setTemplateId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    setPreview(null);
    setError("");
  }, [language]);

  const operations = useMemo(() => preview?.operations || [], [preview]);

  async function handleSubmit(event) {
    event.preventDefault();
    const normalizedTemplateId = String(templateId || "").trim();

    if (!normalizedTemplateId) {
      setError(language === "uk" ? "Вкажіть ID шаблону" : "Enter a template ID");
      return;
    }

    setLoading(true);
    setError("");

    const result = await getProcessingOperationsPreview(token, normalizedTemplateId);

    setLoading(false);

    if (!result.success) {
      setPreview(null);
      setError(
        result.status === 404
          ? (language === "uk" ? "Шаблон не знайдено" : "Template not found")
          : (result.error || (language === "uk" ? "Не вдалося завантажити операції" : "Unable to load operations")),
      );
      return;
    }

    setPreview(result);
  }

  return (
    <section className="dashboard-layout">
      <article className="dashboard-hero-card">
        <div className="dashboard-hero-copy">
          <span className="dashboard-eyebrow">
            {language === "uk" ? "Тестування" : "Testing"}
          </span>
          <h3>
            {language === "uk"
              ? "Перевірка попереднього перегляду операцій"
              : "Read-only operation preview check"}
          </h3>
          <p>
            {language === "uk"
              ? "Ця сторінка лише читає вже готовий перегляд операцій і не створює, не редагує та не зберігає дані."
              : "This page only reads the existing operation preview and does not create, edit, or save data."}
          </p>
        </div>
      </article>

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Завантажити операції" : "Load operations"}</h3>
            <p>
              {language === "uk"
                ? "Введіть ID шаблону, щоб подивитися читабельний результат read-only перегляду."
                : "Enter a template ID to inspect the readable read-only preview result."}
            </p>
          </div>
        </div>

        <form className="settings-info-grid" onSubmit={handleSubmit}>
          <label>
            {language === "uk" ? "ID шаблону" : "Template ID"}
            <input
              inputMode="numeric"
              onChange={(event) => setTemplateId(event.target.value)}
              placeholder="123"
              value={templateId}
            />
          </label>
          <div className="settings-actions">
            <button className="primary-button" disabled={loading} type="submit">
              {loading ? (language === "uk" ? "Завантаження..." : "Loading...") : (language === "uk" ? "Завантажити операції" : "Load operations")}
            </button>
          </div>
        </form>

        {error ? <p className="hole-template-error">{error}</p> : null}
      </article>

      {preview ? (
        <article className="dashboard-panel">
          <div className="dashboard-panel-head">
            <div>
              <h3>{language === "uk" ? "Коротка інформація про шаблон" : "Template summary"}</h3>
              <p>
                {language === "uk"
                  ? "Дані нижче приходять з існуючого read-only перегляду операцій."
                  : "The data below comes from the existing read-only operation preview."}
              </p>
            </div>
          </div>
          <div className="settings-info-grid">
            <div>
              <span>ID</span>
              <strong>{formatValue(preview.template?.id, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Назва" : "Name"}</span>
              <strong>{formatValue(preview.template?.name, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Фурнітура" : "Fitting"}</span>
              <strong>{formatValue(preview.template?.fitting_code, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Варіант кріплення" : "Mounting variant"}</span>
              <strong>{formatValue(preview.template?.mounting_variant_key, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Кількість операцій" : "Operation count"}</span>
              <strong>{operations.length}</strong>
            </div>
          </div>
        </article>
      ) : null}

      {operations.length ? (
        <section className="settings-grid">
          {operations.map((operation) => (
            <OperationPreviewCard key={`${operation.source_type}-${operation.source_id}`} language={language} operation={operation} />
          ))}
        </section>
      ) : preview ? (
        <article className="settings-card">
          <p>{language === "uk" ? "Операції не знайдено." : "No operations were returned."}</p>
        </article>
      ) : null}
    </section>
  );
}
