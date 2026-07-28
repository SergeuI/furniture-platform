import { useEffect, useMemo, useState } from "react";

import { getProcessingOperationTypes } from "../../api.js";
import {
  buildProcessingOperationTypeViewModels,
} from "../../processingOperationTypes.js";

function formatList(values, language) {
  if (!Array.isArray(values) || values.length === 0) {
    return language === "uk" ? "Немає" : "None";
  }

  return values.join(", ");
}

function renderRow(label, value, language) {
  return (
    <div>
      <span>
        {label}
        {language === "uk" ? ": " : ": "}
      </span>
      <strong>{value}</strong>
    </div>
  );
}

function OperationTypeCard({ item, language }) {
  const statusBadgeClass = item.status === "available" ? "service-tree-badge live" : "service-tree-badge subtle";

  return (
    <article className="settings-card">
      <div className="settings-card-header">
        <div>
          <strong>{item.name}</strong>
          <p>{item.description}</p>
        </div>
        <span className={statusBadgeClass}>{item.status_label}</span>
      </div>

      <div className="settings-info-grid">
        {renderRow(language === "uk" ? "Категорія" : "Category", item.category_label, language)}
        {renderRow(language === "uk" ? "Геометрія" : "Geometry", item.geometry_kind_label, language)}
        {renderRow(language === "uk" ? "Обов’язкові поля" : "Required fields", formatList(item.required_field_labels, language), language)}
        {renderRow(language === "uk" ? "Додаткові поля" : "Optional fields", formatList(item.optional_field_labels, language), language)}
        {renderRow(language === "uk" ? "Одиниці розрахунку" : "Pricing units", formatList(item.pricing_unit_labels, language), language)}
        {renderRow(language === "uk" ? "Версія" : "Version", item.version, language)}
      </div>

      <div className="settings-actions" style={{ flexWrap: "wrap", gap: "0.5rem", marginTop: "0.75rem" }}>
        {item.capability_items.map((capability) => (
          <span
            className={`service-tree-badge${capability.active ? " live" : " subtle"}`}
            key={capability.key}
          >
            {capability.label}: {capability.state_label}
          </span>
        ))}
      </div>
    </article>
  );
}

export default function ProcessingOperations({ language = "uk", token = "" }) {
  const [operationTypes, setOperationTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadIndex, setReloadIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function loadOperationTypes() {
      setLoading(true);
      setError("");

      const result = await getProcessingOperationTypes(token);

      if (cancelled) {
        return;
      }

      if (!result.success) {
        setOperationTypes([]);
        setError(result.error || (language === "uk" ? "Не вдалося завантажити реєстр" : "Unable to load registry"));
        setLoading(false);
        return;
      }

      setOperationTypes(Array.isArray(result.items) ? result.items : []);
      setLoading(false);
    }

    loadOperationTypes();

    return () => {
      cancelled = true;
    };
  }, [language, reloadIndex, token]);

  const viewModels = useMemo(
    () => buildProcessingOperationTypeViewModels(operationTypes, language),
    [language, operationTypes],
  );

  return (
    <section className="dashboard-layout">
      <article className="dashboard-hero-card">
        <div className="dashboard-hero-copy">
          <span className="dashboard-eyebrow">
            {language === "uk" ? "Реєстр типів" : "Type registry"}
          </span>
          <h3>{language === "uk" ? "Операції обробки" : "Processing operations"}</h3>
          <p>
            {language === "uk"
              ? "Показано стабільний read-only реєстр типів операцій. Дані надходять із backend без записів у БД."
              : "This is a stable read-only registry of operation types. The data is loaded from the backend without database writes."}
          </p>
        </div>
        <div className="dashboard-status-card">
          <div className="dashboard-status-head">
            <div className="dashboard-status-title">
              <strong>{language === "uk" ? "Стан реєстру" : "Registry status"}</strong>
              <p>{loading ? (language === "uk" ? "Завантаження..." : "Loading...") : `${viewModels.length}`}</p>
            </div>
            <span className={`dashboard-status-badge${loading ? "" : " live"}`}>
              {loading ? (language === "uk" ? "Завантаження" : "Loading") : `${viewModels.length} / 9`}
            </span>
          </div>
          <p>
            {language === "uk"
              ? "Ключі та описи беруться з окремого registry-ендпоїнта /processing/operation-types."
              : "Keys and descriptions come from the dedicated /processing/operation-types endpoint."}
          </p>
        </div>
      </article>

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Список типів" : "Type list"}</h3>
            <p>
              {language === "uk"
                ? "Тут видно 9 типів, їхній статус, геометрію, поля та поточні можливості."
                : "This list shows the 9 types, their status, geometry, fields, and current capabilities."}
            </p>
          </div>
          <button className="primary-button" disabled={loading} onClick={() => setReloadIndex((value) => value + 1)} type="button">
            {loading ? (language === "uk" ? "Завантаження..." : "Loading...") : (language === "uk" ? "Оновити" : "Retry")}
          </button>
        </div>

        {error ? <p className="hole-template-error">{error}</p> : null}
      </article>

      {loading ? (
        <article className="settings-card">
          <p>{language === "uk" ? "Завантажуємо реєстр типів операцій..." : "Loading operation type registry..."}</p>
        </article>
      ) : null}

      {!loading && !error ? (
        <section className="settings-grid">
          {viewModels.map((item) => (
            <OperationTypeCard key={item.key} language={language} item={item} />
          ))}
        </section>
      ) : null}
    </section>
  );
}
