import { useEffect, useMemo, useState } from "react";

import {
  getProcessingOperationsPreview,
  getProjectPartOperationsPreview,
  getProjectCutting,
  listProjects,
} from "../../api.js";
import {
  formatOperationCoordinates,
  formatOperationTitle,
  formatPartDimensions,
  getOperationEstimateStatus,
  getOperationServiceStatus,
  getVisibleOperationFields,
  getProcessingTestingModeOptions,
  getProcessingTestingOperationTypeLabel,
} from "../../processingTesting.js";

function formatValue(value, language) {
  if (value === null || value === undefined || value === "") {
    return language === "uk" ? "Не визначено" : "Not set";
  }

  if (typeof value === "boolean") {
    return value ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No");
  }

  return String(value);
}

function formatNumber(value, language) {
  if (value === null || value === undefined || value === "") {
    return formatValue(value, language);
  }

  const numericValue = Number(value);

  if (Number.isNaN(numericValue)) {
    return formatValue(value, language);
  }

  return numericValue % 1 === 0 ? String(numericValue) : numericValue.toFixed(2).replace(/\.00$/, "");
}

function buildOperationTypeCounts(operations) {
  return operations.reduce(
    (accumulator, operation) => {
      const key = String(operation?.operation_type || "").trim();
      if (key in accumulator) {
        accumulator[key] += 1;
      }
      return accumulator;
    },
    { hole: 0, groove: 0, quarter: 0 },
  );
}

function getProjectOptionLabel(project, language) {
  const title = String(project?.project_name || project?.name || "").trim() || (language === "uk" ? "Без назви" : "Untitled");
  const details = [project?.client_name, project?.room_name].filter(Boolean).join(" · ");
  const projectId = formatValue(project?.id, language);

  return details ? `${title} · ${details} · ID ${projectId}` : `${title} · ID ${projectId}`;
}

function getProjectPartOptionLabel(item, language) {
  const name = String(item?.part_name || "").trim() || (language === "uk" ? "Деталь" : "Part");
  const code = String(item?.export_code || "").trim();
  const size = formatPartDimensions(item, language);

  return [name, code ? `ID ${code}` : "", size ? size : ""]
    .filter(Boolean)
    .join(" · ");
}

function SummaryField({ label, value }) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function OperationPreviewCard({ operation, index, language }) {
  const title = formatOperationTitle(operation, index + 1, language);
  const typeLabel = getProcessingTestingOperationTypeLabel(operation.operation_type, language);
  const estimateStatus = getOperationEstimateStatus(operation, language);
  const serviceStatus = getOperationServiceStatus(operation, language);
  const visibleFields = getVisibleOperationFields(operation, language);
  const technicalRows = [
    ["operation_type", language === "uk" ? "Тип операції" : "Operation type", operation.operation_type],
    ["source_type", language === "uk" ? "Джерело" : "Source type", operation.source_type],
    ["source_id", language === "uk" ? "ID джерела" : "Source ID", operation.source_id],
    ["template_id", "Template ID", operation.template_id],
    ["order_index", language === "uk" ? "Порядок" : "Order", operation.order_index],
    ["service_mapping", language === "uk" ? "Прив’язка послуги" : "Service mapping", operation.service_mapping],
    ["production_effects", language === "uk" ? "Виробничі ефекти" : "Production effects", operation.production_effects],
    ["metadata", language === "uk" ? "Метадані" : "Metadata", operation.metadata],
  ];

  return (
    <article className="settings-card">
      <div className="settings-card-header">
        <div>
          <strong>{title}</strong>
          <p>
            {typeLabel || (language === "uk" ? "Без типу" : "Untitled type")}
            {formatOperationCoordinates(operation, language) !== (language === "uk" ? "Не визначено" : "Not set")
              ? ` · ${formatOperationCoordinates(operation, language)}`
              : ""}
          </p>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", justifyContent: "flex-end" }}>
          {estimateStatus ? <span className="service-tree-badge subtle">{estimateStatus}</span> : null}
          {serviceStatus ? <span className="service-tree-badge subtle">{serviceStatus}</span> : null}
        </div>
      </div>

      <div className="settings-info-grid">
        {visibleFields.map((field) => (
          <SummaryField key={field.label} label={field.label} value={field.value} />
        ))}
      </div>

      <details className="settings-card" style={{ marginTop: "0.75rem" }}>
        <summary>{language === "uk" ? "Технічні дані" : "Technical data"}</summary>
        <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
          {technicalRows.map(([key, label, value]) => {
            const renderedValue = key === "service_mapping" || key === "production_effects" || key === "metadata"
              ? JSON.stringify(value ?? null, null, 2)
              : formatValue(value, language);

            return (
              <div key={key}>
                <span>{label}</span>
                <strong style={{ whiteSpace: "pre-wrap" }}>{renderedValue}</strong>
              </div>
            );
          })}
        </div>
        <pre style={{ overflowX: "auto", whiteSpace: "pre-wrap" }}>{JSON.stringify(operation, null, 2)}</pre>
      </details>
    </article>
  );
}

export default function ProcessingTesting({
  language = "uk",
  token,
}) {
  const [mode, setMode] = useState("template");
  const [templateId, setTemplateId] = useState("");
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(false);
  const [projectsError, setProjectsError] = useState("");
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [cuttingItems, setCuttingItems] = useState([]);
  const [cuttingLoading, setCuttingLoading] = useState(false);
  const [cuttingError, setCuttingError] = useState("");
  const [selectedPartIdentifier, setSelectedPartIdentifier] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    setPreview(null);
    setError("");
  }, [language, mode]);

  useEffect(() => {
    if (mode !== "project") {
      return undefined;
    }

    let cancelled = false;

    async function loadProjectList() {
      setProjectsLoading(true);
      setProjectsError("");

      const result = await listProjects(token, 50, 0, {});

      if (cancelled) {
        return;
      }

      if (!result.success) {
        setProjects([]);
        setProjectsError(result.error || (language === "uk" ? "Не вдалося завантажити проєкти" : "Unable to load projects"));
        setProjectsLoading(false);
        return;
      }

      setProjects(Array.isArray(result.projects) ? result.projects : []);
      setProjectsLoading(false);
    }

    loadProjectList();

    return () => {
      cancelled = true;
    };
  }, [language, mode, token]);

  useEffect(() => {
    if (mode !== "project") {
      return;
    }

    if (!projects.length) {
      setSelectedProjectId("");
      return;
    }

    setSelectedProjectId((current) => {
      const normalizedCurrent = String(current || "");
      if (normalizedCurrent && projects.some((project) => String(project.id) === normalizedCurrent)) {
        return normalizedCurrent;
      }

      return String(projects[0].id);
    });
  }, [mode, projects]);

  useEffect(() => {
    if (mode !== "project" || !selectedProjectId) {
      return undefined;
    }

    let cancelled = false;

    async function loadProjectCutting() {
      setCuttingLoading(true);
      setCuttingError("");
      setCuttingItems([]);
      setSelectedPartIdentifier("");

      const result = await getProjectCutting(token, selectedProjectId);

      if (cancelled) {
        return;
      }

      if (!result.success) {
        setCuttingError(result.error || (language === "uk" ? "Не вдалося завантажити деталі" : "Unable to load parts"));
        setCuttingLoading(false);
        return;
      }

      const items = Array.isArray(result.items) ? result.items : [];
      setCuttingItems(items);
      setSelectedPartIdentifier(items[0]?.export_code ? String(items[0].export_code) : "");
      setCuttingLoading(false);
    }

    loadProjectCutting();

    return () => {
      cancelled = true;
    };
  }, [language, mode, selectedProjectId, token]);

  const operations = useMemo(() => preview?.operations || [], [preview]);
  const operationCounts = useMemo(() => buildOperationTypeCounts(operations), [operations]);
  const modeOptions = useMemo(() => getProcessingTestingModeOptions(language), [language]);
  const selectedProject = useMemo(
    () => projects.find((project) => String(project.id) === String(selectedProjectId || "")) || null,
    [projects, selectedProjectId],
  );
  const selectedPart = useMemo(
    () => cuttingItems.find((item) => String(item.export_code) === String(selectedPartIdentifier || "")) || null,
    [cuttingItems, selectedPartIdentifier],
  );

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    if (mode === "template") {
      const normalizedTemplateId = String(templateId || "").trim();

      if (!normalizedTemplateId) {
        setError(language === "uk" ? "Вкажіть ID шаблону" : "Enter a template ID");
        return;
      }

      setLoading(true);
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
      return;
    }

    const normalizedProjectId = String(selectedProjectId || "").trim();
    const normalizedPartIdentifier = String(selectedPartIdentifier || "").trim();

    if (!normalizedProjectId) {
      setError(language === "uk" ? "Оберіть проєкт" : "Select a project");
      return;
    }

    if (!normalizedPartIdentifier) {
      setError(language === "uk" ? "Оберіть деталь" : "Select a part");
      return;
    }

    setLoading(true);
    const result = await getProjectPartOperationsPreview(token, normalizedProjectId, normalizedPartIdentifier);
    setLoading(false);

    if (!result.success) {
      setPreview(null);
      setError(
        result.status === 404
          ? (language === "uk" ? "Проєкт або деталь не знайдено" : "Project or part not found")
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
              ? "Ця сторінка лише читає вже наявні read-only перегляди й не створює, не редагує та не зберігає дані."
              : "This page only reads existing read-only previews and does not create, edit, or save data."}
          </p>
        </div>
      </article>

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Режим тестування" : "Testing mode"}</h3>
            <p>
              {language === "uk"
                ? "Оберіть сценарій read-only перевірки без зміни backend-контрактів."
                : "Choose a read-only verification scenario without changing backend contracts."}
            </p>
          </div>
        </div>

        <form className="settings-info-grid" onSubmit={handleSubmit}>
          <label>
            {language === "uk" ? "Режим" : "Mode"}
            <select onChange={(event) => setMode(event.target.value)} value={mode}>
              {modeOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          {mode === "template" ? (
            <label>
              {language === "uk" ? "ID шаблону" : "Template ID"}
              <input
                inputMode="numeric"
                onChange={(event) => setTemplateId(event.target.value)}
                placeholder="123"
                value={templateId}
              />
            </label>
          ) : (
            <>
              <label>
                {language === "uk" ? "Проєкт" : "Project"}
                <select
                  disabled={projectsLoading}
                  onChange={(event) => setSelectedProjectId(event.target.value)}
                  value={selectedProjectId}
                >
                  <option value="">{language === "uk" ? "Оберіть проєкт" : "Select a project"}</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {getProjectOptionLabel(project, language)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                {language === "uk" ? "Деталь" : "Part"}
                <select
                  disabled={cuttingLoading || !selectedProjectId}
                  onChange={(event) => setSelectedPartIdentifier(event.target.value)}
                  value={selectedPartIdentifier}
                >
                  <option value="">{language === "uk" ? "Оберіть деталь" : "Select a part"}</option>
                  {cuttingItems.map((item) => (
                    <option key={item.export_code} value={item.export_code}>
                      {getProjectPartOptionLabel(item, language)}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}

          <div className="settings-actions">
            <button className="primary-button" disabled={loading || projectsLoading || cuttingLoading} type="submit">
              {loading
                ? (language === "uk" ? "Завантаження..." : "Loading...")
                : (language === "uk" ? "Завантажити операції" : "Load operations")}
            </button>
          </div>
        </form>

        {projectsError ? <p className="hole-template-error">{projectsError}</p> : null}
        {cuttingError ? <p className="hole-template-error">{cuttingError}</p> : null}
        {error ? <p className="hole-template-error">{error}</p> : null}
      </article>

      {mode === "project" ? (
        <>
          <article className="dashboard-panel">
            <div className="dashboard-panel-head">
              <div>
                <h3>{language === "uk" ? "Вибраний проєкт" : "Selected project"}</h3>
                <p>
                  {language === "uk"
                    ? "Показано тільки основні дані вибраного проєкту."
                    : "Only the main details of the selected project are shown here."}
                </p>
              </div>
            </div>

            {projectsLoading ? (
              <p>{language === "uk" ? "Завантажуємо список проєктів..." : "Loading project list..."}</p>
            ) : null}

            {!projectsLoading && !projectsError && !projects.length ? (
              <p>{language === "uk" ? "Проєктів не знайдено." : "No projects were returned."}</p>
            ) : null}

            {selectedProject ? (
              <div className="settings-info-grid">
                <SummaryField
                  label={language === "uk" ? "Назва" : "Name"}
                  value={formatValue(selectedProject.project_name || selectedProject.name, language)}
                />
                <SummaryField label="ID" value={formatValue(selectedProject.id, language)} />
                <SummaryField
                  label={language === "uk" ? "Клієнт" : "Client"}
                  value={selectedProject.client_name ? formatValue(selectedProject.client_name, language) : ""}
                />
                <SummaryField
                  label={language === "uk" ? "Кімната" : "Room"}
                  value={selectedProject.room_name ? formatValue(selectedProject.room_name, language) : ""}
                />
              </div>
            ) : null}
          </article>

          {selectedPart ? (
            <article className="dashboard-panel">
              <div className="dashboard-panel-head">
                <div>
                  <h3>{language === "uk" ? "Інформація про деталь" : "Part information"}</h3>
                  <p>
                    {language === "uk"
                      ? "Коротка виробнича інформація про вибрану деталь."
                      : "A short production summary for the selected part."}
                  </p>
                </div>
              </div>

              <div className="settings-info-grid">
                <SummaryField
                  label={language === "uk" ? "Назва" : "Name"}
                  value={formatValue(selectedPart.part_name, language)}
                />
                <SummaryField
                  label={language === "uk" ? "Код" : "Code"}
                  value={formatValue(selectedPart.export_code, language)}
                />
                <SummaryField
                  label={language === "uk" ? "Розміри" : "Dimensions"}
                  value={formatPartDimensions(selectedPart, language)}
                />
                <SummaryField
                  label={language === "uk" ? "Операцій" : "Operations"}
                  value={formatValue(operations.length, language)}
                />
              </div>

              <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
                <SummaryField label={language === "uk" ? "Отвори" : "Holes"} value={operationCounts.hole} />
                <SummaryField label={language === "uk" ? "Пази" : "Grooves"} value={operationCounts.groove} />
                <SummaryField label={language === "uk" ? "Чверті" : "Quarters"} value={operationCounts.quarter} />
              </div>
            </article>
          ) : null}
        </>
      ) : null}

      {mode === "template" && preview ? (
        <article className="dashboard-panel">
          <div className="dashboard-panel-head">
            <div>
              <h3>{language === "uk" ? "Коротка інформація про шаблон" : "Template summary"}</h3>
              <p>
                {language === "uk"
                  ? "Дані нижче походять із існуючого read-only перегляду операцій присадки фурнітури."
                  : "The data below comes from the existing read-only fitting holes operation preview."}
              </p>
            </div>
          </div>
          <div className="settings-info-grid">
            <SummaryField label="ID" value={formatValue(preview.template?.id, language)} />
            <SummaryField
              label={language === "uk" ? "Назва" : "Name"}
              value={formatValue(preview.template?.name, language)}
            />
            <SummaryField
              label={language === "uk" ? "Фурнітура" : "Fitting"}
              value={formatValue(preview.template?.fitting_code, language)}
            />
            <SummaryField
              label={language === "uk" ? "Варіант кріплення" : "Mounting variant"}
              value={formatValue(preview.template?.mounting_variant_key, language)}
            />
            <SummaryField
              label={language === "uk" ? "Операцій" : "Operations"}
              value={operations.length}
            />
          </div>
        </article>
      ) : null}

      {mode === "project" && preview ? (
        <article className="dashboard-panel">
          <div className="dashboard-panel-head">
            <div>
              <h3>{language === "uk" ? "Коротка інформація про деталь" : "Part summary"}</h3>
              <p>
                {language === "uk"
                  ? "Показано вибрану реальну деталь проєкту та результат нового read-only endpoint."
                  : "The selected real project part and the new read-only endpoint result are shown here."}
              </p>
            </div>
          </div>
          <div className="settings-info-grid">
            <SummaryField
              label={language === "uk" ? "Проєкт" : "Project"}
              value={formatValue(preview.project?.id, language)}
            />
            <SummaryField
              label={language === "uk" ? "Деталь" : "Part"}
              value={formatValue(preview.part?.part_name || selectedPart?.part_name, language)}
            />
            <SummaryField
              label={language === "uk" ? "Код деталі" : "Part code"}
              value={formatValue(preview.part?.export_code || selectedPart?.export_code, language)}
            />
            <SummaryField
              label={language === "uk" ? "Розміри" : "Dimensions"}
              value={formatPartDimensions(preview.part || selectedPart, language)}
            />
          </div>
          <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
            <SummaryField label={language === "uk" ? "Отвори" : "Holes"} value={operationCounts.hole} />
            <SummaryField label={language === "uk" ? "Пази" : "Grooves"} value={operationCounts.groove} />
            <SummaryField label={language === "uk" ? "Чверті" : "Quarters"} value={operationCounts.quarter} />
          </div>
        </article>
      ) : null}

      {operations.length ? (
        <section className="settings-grid">
          {operations.map((operation, index) => (
            <OperationPreviewCard
              key={`${operation.source_type}-${operation.source_id}-${operation.order_index}`}
              index={index}
              language={language}
              operation={operation}
            />
          ))}
        </section>
      ) : preview ? (
        <article className="settings-card">
          <p>
            {mode === "template"
              ? (language === "uk" ? "Операції не знайдено." : "No operations were returned.")
              : (language === "uk" ? "Для цієї деталі операції обробки не сформовані." : "No operations were formed for this part.")}
          </p>
        </article>
      ) : null}
    </section>
  );
}
