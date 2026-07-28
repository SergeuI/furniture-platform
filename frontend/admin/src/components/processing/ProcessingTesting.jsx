import { useEffect, useMemo, useState } from "react";

import {
  getProcessingOperationsPreview,
  getProjectPartOperationsPreview,
  getProjectCutting,
  listProjects,
} from "../../api.js";
import {
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

function formatDimensions(item, language) {
  const dimensions = [
    item?.width ?? item?.width_mm,
    item?.height ?? item?.height_mm,
    item?.thickness ?? item?.depth ?? item?.depth_mm,
  ];

  if (dimensions.every((value) => value === null || value === undefined || value === "")) {
    return language === "uk" ? "Не визначено" : "Not set";
  }

  return dimensions.map((value) => formatNumber(value, language)).join(" × ");
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
  const size = [item?.width, item?.height, item?.thickness]
    .filter((value) => value !== null && value !== undefined && value !== "")
    .map((value) => formatNumber(value, language))
    .join(" × ");

  return [name, code ? `ID ${code}` : "", size ? `${size} мм` : ""]
    .filter(Boolean)
    .join(" · ");
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

function formatGeometrySummary(geometry, language) {
  if (!geometry || typeof geometry !== "object") {
    return language === "uk" ? "Не визначено" : "Not set";
  }

  const rows = [
    ["diameter_mm", language === "uk" ? "Діаметр" : "Diameter"],
    ["depth_mm", language === "uk" ? "Глибина" : "Depth"],
    ["length_mm", language === "uk" ? "Довжина" : "Length"],
    ["width_mm", language === "uk" ? "Ширина" : "Width"],
    ["radius_mm", language === "uk" ? "Радіус" : "Radius"],
    ["edge", language === "uk" ? "Край" : "Edge"],
    ["operation", language === "uk" ? "Операція" : "Operation"],
  ];

  const rendered = rows
    .map(([key, label]) => {
      const value = geometry[key];
      if (value === null || value === undefined || value === "") {
        return null;
      }

      return `${label}: ${formatValue(value, language)}`;
    })
    .filter(Boolean);

  if (geometry.is_through !== null && geometry.is_through !== undefined) {
    rendered.push(`${language === "uk" ? "Наскрізний" : "Through"}: ${formatValue(geometry.is_through, language)}`);
  }

  return rendered.length ? rendered.join(" · ") : (language === "uk" ? "Не визначено" : "Not set");
}

function OperationPreviewCard({ operation, language }) {
  const operationTypeLabel = getProcessingTestingOperationTypeLabel(operation.operation_type, language);
  const includeInEstimateLabel = formatValue(operation.production_effects?.include_in_estimate, language);

  return (
    <article className="settings-card">
      <div className="settings-card-header">
        <div>
          <strong>{operation.label || operationTypeLabel || (language === "uk" ? "Без мітки" : "Untitled")}</strong>
          <p>
            {operationTypeLabel || formatValue(null, language)} ·{" "}
            {operation.source_type || formatValue(null, language)}
          </p>
        </div>
        <span className="service-tree-badge subtle">{includeInEstimateLabel}</span>
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
          <strong>{formatGeometrySummary(operation.geometry, language)}</strong>
        </div>
        <div>
          <span>{language === "uk" ? "Кількість" : "Quantity"}</span>
          <strong>
            {formatValue(operation.quantity, language)} · {operation.mirrored ? (language === "uk" ? "дзеркально" : "mirrored") : (language === "uk" ? "звичайно" : "normal")}
          </strong>
        </div>
        <div>
          <span>{language === "uk" ? "Порядок" : "Order"}</span>
          <strong>{formatValue(operation.order_index, language)}</strong>
        </div>
        <div>
          <span>{language === "uk" ? "Послуга" : "Service"}</span>
          <strong>
            {operation.service_mapping?.found ? (language === "uk" ? "Знайдено" : "Found") : (language === "uk" ? "Не знайдено" : "Not found")}
          </strong>
        </div>
      </div>

      <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
        <div>
          <span>{language === "uk" ? "ID джерела" : "Source ID"}</span>
          <strong>{formatValue(operation.source_id, language)}</strong>
        </div>
        <div>
          <span>{language === "uk" ? "Template ID" : "Template ID"}</span>
          <strong>{formatValue(operation.template_id, language)}</strong>
        </div>
        <div>
          <span>{language === "uk" ? "Збереження в кошторис" : "Estimate"}</span>
          <strong>{includeInEstimateLabel}</strong>
        </div>
        <div>
          <span>{language === "uk" ? "Сервісний елемент" : "Catalog item"}</span>
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
              ? "Ця сторінка лише читає готові read-only перегляди й не створює, не редагує та не зберігає дані."
              : "This page only reads the existing read-only previews and does not create, edit, or save data."}
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
        <article className="dashboard-panel">
          <div className="dashboard-panel-head">
            <div>
              <h3>{language === "uk" ? "Список проєкту" : "Project list"}</h3>
              <p>
                {language === "uk"
                  ? "Оберіть реальний проєкт і його деталь без ручного введення part_identifier."
                  : "Choose a real project and part without typing the part identifier by hand."}
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
              <div>
                <span>{language === "uk" ? "Назва" : "Name"}</span>
                <strong>{formatValue(selectedProject.project_name || selectedProject.name, language)}</strong>
              </div>
              <div>
                <span>ID</span>
                <strong>{formatValue(selectedProject.id, language)}</strong>
              </div>
              <div>
                <span>{language === "uk" ? "Клієнт" : "Client"}</span>
                <strong>{formatValue(selectedProject.client_name, language)}</strong>
              </div>
              <div>
                <span>{language === "uk" ? "Кімната" : "Room"}</span>
                <strong>{formatValue(selectedProject.room_name, language)}</strong>
              </div>
            </div>
          ) : null}
        </article>
      ) : null}

      {mode === "template" && preview ? (
        <article className="dashboard-panel">
          <div className="dashboard-panel-head">
            <div>
              <h3>{language === "uk" ? "Коротка інформація про шаблон" : "Template summary"}</h3>
              <p>
                {language === "uk"
                  ? "Дані нижче приходять з існуючого read-only перегляду операцій присадки фурнітури."
                  : "The data below comes from the existing read-only fitting holes operation preview."}
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

      {mode === "project" && preview ? (
        <article className="dashboard-panel">
          <div className="dashboard-panel-head">
            <div>
              <h3>{language === "uk" ? "Коротка інформація про деталь" : "Part summary"}</h3>
              <p>
                {language === "uk"
                  ? "Показано реальну деталь проєкту та результат нового read-only endpoint."
                  : "The selected real project part and the new read-only endpoint result are shown here."}
              </p>
            </div>
          </div>
          <div className="settings-info-grid">
            <div>
              <span>{language === "uk" ? "Проєкт" : "Project"}</span>
              <strong>{formatValue(preview.project?.id, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Деталь" : "Part"}</span>
              <strong>{formatValue(preview.part?.part_name || selectedPart?.part_name, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Код деталі" : "Part code"}</span>
              <strong>{formatValue(preview.part?.export_code || selectedPart?.export_code, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Розміри" : "Dimensions"}</span>
              <strong>{formatDimensions(preview.part, language)}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Кількість operations" : "Operation count"}</span>
              <strong>{operations.length}</strong>
            </div>
          </div>
          <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
            <div>
              <span>{language === "uk" ? "Отвори" : "Holes"}</span>
              <strong>{operationCounts.hole}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Пази" : "Grooves"}</span>
              <strong>{operationCounts.groove}</strong>
            </div>
            <div>
              <span>{language === "uk" ? "Чверті" : "Quarters"}</span>
              <strong>{operationCounts.quarter}</strong>
            </div>
          </div>
        </article>
      ) : null}

      {operations.length ? (
        <section className="settings-grid">
          {operations.map((operation) => (
            <OperationPreviewCard
              key={`${operation.source_type}-${operation.source_id}-${operation.order_index}`}
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
              : (language === "uk" ? "Для цієї деталі операції не сформовані." : "No operations were formed for this part.")}
          </p>
        </article>
      ) : null}
    </section>
  );
}
