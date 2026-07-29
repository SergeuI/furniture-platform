import { useEffect, useMemo, useRef, useState } from "react";

import { getProcessingOperationsPreview, getFittingsCatalog, listFittingHoleTemplatesByFitting } from "../../api.js";
import {
  formatOperationCoordinates,
  formatOperationTitle,
  getOperationEstimateStatus,
  getOperationServiceStatus,
  getProcessingTestingOperationTypeLabel,
  getVisibleOperationFields,
} from "../../processingTesting.js";
import {
  filterProcessingTemplates,
  buildProcessingTemplateEditorContext,
  clearProcessingTemplatesReturnState,
  getProcessingFittingDisplayLabel,
  getProcessingFittingSearchText,
  getProcessingTemplateCardSubtitle,
  getProcessingTemplateCardTitle,
  getProcessingTemplateDefaultLabel,
  getProcessingTemplateFutureCategories,
  getProcessingTemplateMountingVariantLabel,
  getProcessingTemplatePreviewCountLabel,
  getProcessingTemplateStatusLabel,
  getProcessingTemplateTypeLabel,
  getProcessingTemplateVariantOptions,
  readProcessingTemplatesReturnState,
  saveProcessingTemplatesReturnState,
} from "../../processingTemplates.js";

function formatValue(value, language) {
  if (value === null || value === undefined || value === "") {
    return language === "uk" ? "Не визначено" : "Not set";
  }

  if (typeof value === "boolean") {
    return value ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No");
  }

  return String(value);
}

function formatCount(value) {
  const numericValue = Number(value || 0);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

function buildOperationCounts(operations) {
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

function TemplateOperationCard({ operation, index, language }) {
  const typeLabel = getProcessingTestingOperationTypeLabel(operation.operation_type, language);
  const title = operation.label || formatOperationTitle(operation, index + 1, language);
  const visibleFields = getVisibleOperationFields(operation, language);
  const estimateStatus = getOperationEstimateStatus(operation, language);
  const serviceStatus = getOperationServiceStatus(operation, language);
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

function TemplatePreviewPanel({
  error = "",
  language,
  loading = false,
  preview,
  selectedFitting,
  selectedTemplate,
  onOpenEditor,
  showOpenEditorButton = true,
}) {
  if (loading) {
    return (
      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Завантаження попереднього перегляду" : "Operations preview"}</h3>
            <p>
              {language === "uk" ? "Зачекайте, отримуємо операції шаблону…" : "Loading preview..."}
            </p>
          </div>
        </div>
      </article>
    );
  }

  if (error) {
    return (
      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "РџРѕРїРµСЂРµРґРЅС–Р№ РїРµСЂРµРіР»СЏРґ РѕРїРµСЂР°С†С–Р№" : "Operations preview"}</h3>
            <p>{error}</p>
          </div>
        </div>
      </article>
    );
  }

  if (!preview) {
    return (
      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Попередній перегляд операцій" : "Operations preview"}</h3>
            <p>
              {language === "uk"
                ? "Оберіть шаблон і натисніть «Переглянути операції», щоб побачити read-only preview."
                : "Choose a template and click “View operations” to see the read-only preview."}
            </p>
          </div>
        </div>
      </article>
    );
  }

  const operations = Array.isArray(preview.operations) ? preview.operations : [];
  const counts = buildOperationCounts(operations);

  return (
    <article className="dashboard-panel">
      <div className="dashboard-panel-head">
        <div>
          <h3>{language === "uk" ? "Попередній перегляд операцій" : "Operations preview"}</h3>
          <p>
            {language === "uk"
              ? "Показано лише read-only дані поточного шаблону."
              : "Only read-only data for the current template is shown here."}
          </p>
        </div>
        {showOpenEditorButton && typeof onOpenEditor === "function" ? (
          <button
            className="primary-button"
            onClick={() => onOpenEditor(selectedTemplate)}
            type="button"
          >
            {language === "uk" ? "Відкрити цей шаблон у редакторі" : "Open this template in editor"}
          </button>
        ) : null}
      </div>

      <div className="settings-info-grid">
        <SummaryField
          label={language === "uk" ? "Фурнітура" : "Fitting"}
          value={selectedFitting ? getProcessingFittingDisplayLabel(selectedFitting, language) : ""}
        />
        <SummaryField
          label={language === "uk" ? "Шаблон" : "Template"}
          value={getProcessingTemplateCardTitle(preview.template || selectedTemplate, selectedFitting, language)}
        />
        <SummaryField
          label={language === "uk" ? "Варіант кріплення" : "Mounting variant"}
          value={getProcessingTemplateMountingVariantLabel(preview.template?.mounting_variant_key || selectedTemplate?.mounting_variant_key, language)}
        />
        <SummaryField
          label={language === "uk" ? "Операцій" : "Operations"}
          value={getProcessingTemplatePreviewCountLabel(operations.length, language)}
        />
      </div>

      <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
        <SummaryField label={language === "uk" ? "Отвори" : "Holes"} value={counts.hole} />
        <SummaryField label={language === "uk" ? "Пази" : "Grooves"} value={counts.groove} />
        <SummaryField label={language === "uk" ? "Чверті" : "Quarters"} value={counts.quarter} />
      </div>

      {operations.length ? (
        <section className="settings-grid" style={{ marginTop: "0.75rem" }}>
          {operations.map((operation, index) => (
            <TemplateOperationCard
              key={`${operation.source_type}-${operation.source_id}-${operation.order_index}`}
              index={index}
              language={language}
              operation={operation}
            />
          ))}
        </section>
      ) : (
        <article className="settings-card" style={{ marginTop: "0.75rem" }}>
          <p>
            {language === "uk"
              ? "Для цього шаблону операції не сформовані."
              : "No operations were formed for this template."}
          </p>
        </article>
      )}
    </article>
  );
}

function TemplatePreviewModal({
  error = "",
  isOpen = false,
  language,
  loading = false,
  onClose = null,
  onOpenEditor = null,
  preview = null,
  selectedFitting = null,
  selectedTemplate = null,
}) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape" && typeof onClose === "function") {
        event.preventDefault();
        onClose();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const handleBackdropClick = () => {
    if (typeof onClose === "function") {
      onClose();
    }
  };

  const handleDialogClick = (event) => {
    event.stopPropagation();
  };

  return (
    <div className="modal-backdrop" onClick={handleBackdropClick} role="presentation">
      <section
        aria-label={language === "uk" ? "Попередній перегляд операцій" : "Operations preview"}
        aria-modal="true"
        className="confirm-modal hole-template-modal processing-template-preview-modal"
        onClick={handleDialogClick}
        role="dialog"
      >
        <div className="dashboard-panel-head" style={{ marginBottom: 0 }}>
          <div>
            <h3>{language === "uk" ? "Попередній перегляд операцій" : "Operations preview"}</h3>
            <p>
              {language === "uk"
                ? "Read-only перегляд показано у спливаючому вікні без зміни шаблону."
                : "Read-only preview is shown in a modal without changing the template."}
            </p>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", justifyContent: "flex-end" }}>
            {typeof onOpenEditor === "function" ? (
              <button
                className="primary-button"
                onClick={() => onOpenEditor(selectedTemplate)}
                type="button"
              >
                {language === "uk" ? "Відкрити цей шаблон у редакторі" : "Open this template in editor"}
              </button>
            ) : null}
            <button className="ghost-button" onClick={onClose} type="button">
              {language === "uk" ? "Закрити" : "Close"}
            </button>
          </div>
        </div>

        <div style={{ flex: 1, minHeight: 0, overflowY: "auto", paddingRight: "0.25rem" }}>
          <TemplatePreviewPanel
            error={error}
            language={language}
            loading={loading}
            onOpenEditor={onOpenEditor}
            preview={preview}
            selectedFitting={selectedFitting}
            selectedTemplate={selectedTemplate}
            showOpenEditorButton={false}
          />
        </div>
      </section>
    </div>
  );
}

function FittingOptionLabel(item, language) {
  return getProcessingFittingDisplayLabel(item, language);
}

export default function ProcessingTemplates({ language = "uk", token = "", onOpenFittingHolesEditor = null }) {
  const initialReturnStateRef = useRef(null);
  if (initialReturnStateRef.current === null) {
    initialReturnStateRef.current = readProcessingTemplatesReturnState();
  }
  const initialReturnState = initialReturnStateRef.current || {};
  const [fittings, setFittings] = useState([]);
  const [fittingsLoading, setFittingsLoading] = useState(false);
  const [fittingsError, setFittingsError] = useState("");
  const [fittingSearch, setFittingSearch] = useState(initialReturnState.fittingSearch || "");
  const [selectedFittingId, setSelectedFittingId] = useState(initialReturnState.selectedFittingId || "");
  const [templates, setTemplates] = useState([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesError, setTemplatesError] = useState("");
  const [templateSearch, setTemplateSearch] = useState(initialReturnState.templateSearch || "");
  const [templateStatusFilter, setTemplateStatusFilter] = useState(initialReturnState.templateStatusFilter || "all");
  const [mountingVariantFilter, setMountingVariantFilter] = useState(initialReturnState.mountingVariantFilter || "all");
  const [selectedTemplateId, setSelectedTemplateId] = useState(initialReturnState.selectedTemplateId || "");
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [isPreviewOpen, setIsPreviewOpen] = useState(Boolean(initialReturnState.previewWasOpen));
  const previewRestorePendingRef = useRef(Boolean(initialReturnState.previewWasOpen));
  const scrollRestorePositionRef = useRef(initialReturnState.scrollPosition ?? null);
  const scrollRestoreAppliedRef = useRef(false);

  useEffect(() => {
    clearProcessingTemplatesReturnState();
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadFittings() {
      setFittingsLoading(true);
      setFittingsError("");

      const result = await getFittingsCatalog(token, {});

      if (cancelled) {
        return;
      }

      if (!result.success) {
        setFittings([]);
        setFittingsError(result.error || (language === "uk" ? "Не вдалося завантажити фурнітуру" : "Unable to load fittings"));
        setFittingsLoading(false);
        return;
      }

      const items = Array.isArray(result.items) ? result.items : [];
      setFittings(items);
      setFittingsLoading(false);
    }

    loadFittings();

    return () => {
      cancelled = true;
    };
  }, [language, token]);

  useEffect(() => {
    if (!fittings.length) {
      return;
    }

    setSelectedFittingId((current) => {
      const normalizedCurrent = String(current || "");
      if (normalizedCurrent && fittings.some((item) => String(item.id) === normalizedCurrent)) {
        return normalizedCurrent;
      }

      return String(fittings[0].id);
    });
  }, [fittings]);

  useEffect(() => {
    if (!selectedFittingId) {
      setTemplates([]);
      setTemplatesError("");
      setSelectedTemplateId("");
      setPreview(null);
      setPreviewError("");
      setIsPreviewOpen(false);
      return undefined;
    }

    let cancelled = false;

    async function loadTemplates() {
      setTemplatesLoading(true);
      setTemplatesError("");
      setPreview(null);
      setPreviewError("");

      const result = await listFittingHoleTemplatesByFitting(token, selectedFittingId);

      if (cancelled) {
        return;
      }

      if (!result.success) {
        setTemplates([]);
        setTemplatesError(result.error || (language === "uk" ? "Не вдалося завантажити шаблони" : "Unable to load templates"));
        setTemplatesLoading(false);
        return;
      }

      const items = Array.isArray(result.templates) ? result.templates : [];
      setTemplates(items);
      setTemplatesLoading(false);
      setSelectedTemplateId((current) => {
        const normalizedCurrent = String(current || "");

        if (normalizedCurrent && items.some((item) => String(item.id) === normalizedCurrent)) {
          return normalizedCurrent;
        }

        return items[0]?.id ? String(items[0].id) : "";
      });
    }

    loadTemplates();

    return () => {
      cancelled = true;
    };
  }, [language, selectedFittingId, token]);

  const selectedFitting = useMemo(
    () => fittings.find((item) => String(item.id) === String(selectedFittingId || "")) || null,
    [fittings, selectedFittingId],
  );
  const selectedTemplate = useMemo(
    () => templates.find((item) => String(item.id) === String(selectedTemplateId || "")) || null,
    [templates, selectedTemplateId],
  );
  const fittingSearchText = String(fittingSearch || "").trim().toLowerCase();
  const visibleFittings = useMemo(
    () => fittings.filter((fitting) => {
      if (!fittingSearchText) {
        return true;
      }

      return getProcessingFittingSearchText(fitting).includes(fittingSearchText);
    }),
    [fittings, fittingSearchText],
  );
  const fittingOptions = useMemo(() => {
    const nextOptions = [...visibleFittings];
    if (selectedFitting && !nextOptions.some((item) => String(item.id) === String(selectedFitting.id))) {
      nextOptions.unshift(selectedFitting);
    }
    return nextOptions;
  }, [selectedFitting, visibleFittings]);

  const filteredTemplates = useMemo(
    () => filterProcessingTemplates(templates, selectedFitting, {
      search: templateSearch,
      status: templateStatusFilter,
      mountingVariantKey: mountingVariantFilter,
    }),
    [mountingVariantFilter, selectedFitting, templateSearch, templateStatusFilter, templates],
  );
  const variantOptions = useMemo(
    () => [{ value: "all", label: language === "uk" ? "Усі варіанти" : "All variants" }, ...getProcessingTemplateVariantOptions(templates, language)],
    [language, templates],
  );
  const futureCategories = useMemo(() => getProcessingTemplateFutureCategories(language), [language]);

  async function handlePreviewTemplate(template) {
    if (!template?.id) {
      return;
    }

    setSelectedTemplateId(String(template.id));
    setIsPreviewOpen(true);
    setPreviewLoading(true);
    setPreviewError("");

    const result = await getProcessingOperationsPreview(token, template.id);

    if (!result.success) {
      setPreview(null);
      setPreviewError(result.error || (language === "uk" ? "Не вдалося завантажити preview" : "Unable to load preview"));
      setPreviewLoading(false);
      return;
    }

    setPreview(result);
    setPreviewLoading(false);
  }

  const selectedTemplatePreview = preview && String(preview.template?.id || selectedTemplateId || "") === String(selectedTemplateId || "")
    ? preview
    : null;

  useEffect(() => {
    if (
      !previewRestorePendingRef.current ||
      !isPreviewOpen ||
      !selectedTemplate
    ) {
      return;
    }

    previewRestorePendingRef.current = false;
    void handlePreviewTemplate(selectedTemplate);
  }, [isPreviewOpen, selectedTemplate]);

  useEffect(() => {
    if (
      scrollRestoreAppliedRef.current ||
      scrollRestorePositionRef.current === null ||
      fittingsLoading ||
      templatesLoading
    ) {
      return;
    }

    const scrollPosition = Number(scrollRestorePositionRef.current);
    if (!Number.isFinite(scrollPosition) || scrollPosition < 0) {
      scrollRestoreAppliedRef.current = true;
      return;
    }

    scrollRestoreAppliedRef.current = true;
    window.requestAnimationFrame(() => {
      window.scrollTo({ behavior: "auto", top: scrollPosition });
    });
  }, [fittingsLoading, templatesLoading]);

  function handleOpenFittingHolesEditor(template) {
    if (typeof onOpenFittingHolesEditor !== "function") {
      return;
    }

    saveProcessingTemplatesReturnState({
      fittingSearch,
      mountingVariantFilter,
      previewWasOpen: isPreviewOpen,
      processingTab: "templates",
      scrollPosition: typeof window !== "undefined" ? window.scrollY : 0,
      selectedFittingId,
      selectedTemplateId: String(template?.id || selectedTemplateId || "").trim(),
      templateSearch,
      templateStatusFilter,
    });

    onOpenFittingHolesEditor(buildProcessingTemplateEditorContext(template, selectedFitting));
  }

  function handleClosePreviewModal() {
    setIsPreviewOpen(false);
  }

  return (
    <section className="dashboard-layout">
      <article className="dashboard-hero-card">
        <div className="dashboard-hero-copy">
          <span className="dashboard-eyebrow">
            {language === "uk" ? "Шаблони обробки" : "Processing templates"}
          </span>
          <h3>
            {language === "uk"
              ? "Реальні шаблони присадки фурнітури як перша категорія універсальних шаблонів"
              : "Real fitting-hole templates as the first category of universal processing templates"}
          </h3>
          <p>
            {language === "uk"
              ? "Сторінка лише читає чинні шаблони присадки фурнітури, без створення, редагування або копіювання даних."
              : "This page only reads the current fitting-hole templates without creating, editing, or copying data."}
          </p>
        </div>
      </article>

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Фурнітура" : "Fittings"}</h3>
            <p>
              {language === "uk"
                ? "Оберіть реальну фурнітуру, щоб переглянути її наявні шаблони."
                : "Choose a real fitting to browse its existing templates."}
            </p>
          </div>
        </div>

        <div className="settings-info-grid">
          <label>
            {language === "uk" ? "Пошук" : "Search"}
            <input
              onChange={(event) => setFittingSearch(event.target.value)}
              placeholder={language === "uk" ? "Назва, код або артикул" : "Name, code, or article"}
              value={fittingSearch}
            />
          </label>

          <label>
            {language === "uk" ? "Фурнітура" : "Fitting"}
            <select
              disabled={fittingsLoading || !fittingOptions.length}
              onChange={(event) => setSelectedFittingId(event.target.value)}
              value={selectedFittingId}
            >
              {fittingOptions.map((item) => (
                <option key={item.id} value={item.id}>
                  {FittingOptionLabel(item, language)}
                </option>
              ))}
            </select>
          </label>
        </div>

        {fittingsError ? <p className="hole-template-error">{fittingsError}</p> : null}

        {selectedFitting ? (
          <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
            <SummaryField
              label={language === "uk" ? "Назва" : "Name"}
              value={formatValue(selectedFitting.name || selectedFitting.code || selectedFitting.article, language)}
            />
            <SummaryField
              label={language === "uk" ? "Код" : "Code"}
              value={formatValue(selectedFitting.code, language)}
            />
            <SummaryField
              label={language === "uk" ? "Артикул" : "Article"}
              value={formatValue(selectedFitting.article, language)}
            />
            <SummaryField
              label={language === "uk" ? "Тип" : "Type"}
              value={formatValue(selectedFitting.fitting_type_name || selectedFitting.fitting_type, language)}
            />
            <SummaryField
              label={language === "uk" ? "Розділ каталогу" : "Catalog section"}
              value={formatValue(selectedFitting.fitting_group_name || selectedFitting.fitting_group, language)}
            />
            <SummaryField
              label={language === "uk" ? "Доступність" : "Availability"}
              value={selectedFitting.is_active ? (language === "uk" ? "Активна" : "Active") : (language === "uk" ? "Неактивна" : "Inactive")}
            />
          </div>
        ) : null}
      </article>

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Наявні шаблони фурнітури" : "Existing fitting templates"}</h3>
            <p>
              {language === "uk"
                ? "Показано лише реальні шаблони для вибраної фурнітури."
                : "Only real templates for the selected fitting are shown here."}
            </p>
          </div>
        </div>

        <div className="settings-info-grid">
          <label>
            {language === "uk" ? "Пошук у шаблонах" : "Search templates"}
            <input
              onChange={(event) => setTemplateSearch(event.target.value)}
              placeholder={language === "uk" ? "Назва, комплект, варіант" : "Name, bundle, variant"}
              value={templateSearch}
            />
          </label>

          <label>
            {language === "uk" ? "Статус" : "Status"}
            <select onChange={(event) => setTemplateStatusFilter(event.target.value)} value={templateStatusFilter}>
              <option value="all">{language === "uk" ? "Усі" : "All"}</option>
              <option value="active">{language === "uk" ? "Активні" : "Active"}</option>
              <option value="inactive">{language === "uk" ? "Неактивні" : "Inactive"}</option>
            </select>
          </label>

          <label>
            {language === "uk" ? "Варіант кріплення" : "Mounting variant"}
            <select onChange={(event) => setMountingVariantFilter(event.target.value)} value={mountingVariantFilter}>
              {variantOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
          <SummaryField
            label={language === "uk" ? "Шаблонів" : "Templates"}
            value={formatCount(filteredTemplates.length)}
          />
          <SummaryField
            label={language === "uk" ? "Активні" : "Active"}
            value={formatCount(filteredTemplates.filter((template) => template?.is_active !== false).length)}
          />
          <SummaryField
            label={language === "uk" ? "Неактивні" : "Inactive"}
            value={formatCount(filteredTemplates.filter((template) => template?.is_active === false).length)}
          />
        </div>

        {templatesLoading ? (
          <p>{language === "uk" ? "Завантажуємо шаблони..." : "Loading templates..."}</p>
        ) : null}

        {templatesError ? <p className="hole-template-error">{templatesError}</p> : null}

        {!templatesLoading && !templatesError && !filteredTemplates.length ? (
          <article className="settings-card" style={{ marginTop: "0.75rem" }}>
            <p>
              {language === "uk"
                ? "Для цієї фурнітури шаблонів ще немає."
                : "No templates have been created for this fitting yet."}
            </p>
          </article>
        ) : null}

        {filteredTemplates.length ? (
          <section className="settings-grid" style={{ marginTop: "0.75rem" }}>
            {filteredTemplates.map((template) => {
              const statusLabel = getProcessingTemplateStatusLabel(template, language);
              const defaultLabel = getProcessingTemplateDefaultLabel(template, language);
              const cardTitle = getProcessingTemplateCardTitle(template, selectedFitting, language);
              const subtitle = getProcessingTemplateCardSubtitle(template, selectedFitting, language);
              const isSelected = String(template.id) === String(selectedTemplateId || "");
              return (
                <article className={`settings-card${isSelected ? " is-active" : ""}`} key={template.id}>
                  <div className="settings-card-header">
                    <div>
                      <strong>{cardTitle}</strong>
                      {subtitle ? <p>{subtitle}</p> : null}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", justifyContent: "flex-end" }}>
                      {statusLabel ? <span className="service-tree-badge subtle">{statusLabel}</span> : null}
                      {defaultLabel ? <span className="service-tree-badge subtle">{defaultLabel}</span> : null}
                    </div>
                  </div>

                  <div className="settings-info-grid">
                    <SummaryField
                      label={language === "uk" ? "Комплект" : "Bundle"}
                      value={formatValue(template.bundle_name, language)}
                    />
                    <SummaryField
                      label={language === "uk" ? "Тип" : "Type"}
                      value={getProcessingTemplateTypeLabel(template.template_type, language)}
                    />
                    <SummaryField
                      label={language === "uk" ? "Варіант кріплення" : "Mounting variant"}
                      value={getProcessingTemplateMountingVariantLabel(template.mounting_variant_key, language)}
                    />
                    <SummaryField
                      label={language === "uk" ? "Схема" : "Scheme"}
                      value={formatValue(template.coordinate_system, language)}
                    />
                  </div>

                  <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
                    <SummaryField
                      label={language === "uk" ? "Статус" : "Status"}
                      value={statusLabel}
                    />
                    <SummaryField
                      label={language === "uk" ? "ID" : "ID"}
                      value={formatValue(template.id, language)}
                    />
                  </div>

                  <div className="settings-actions" style={{ marginTop: "0.75rem" }}>
                    <button
                      className="primary-button"
                      disabled={previewLoading}
                      onClick={() => {
                        setSelectedTemplateId(String(template.id));
                        void handlePreviewTemplate(template);
                      }}
                      type="button"
                    >
                      {language === "uk" ? "Переглянути операції" : "View operations"}
                    </button>
                    {typeof onOpenFittingHolesEditor === "function" ? (
                      <button
                        className="ghost-button"
                        onClick={() => handleOpenFittingHolesEditor(template)}
                        type="button"
                      >
                        {language === "uk" ? "Відкрити цей шаблон у редакторі" : "Open this template in editor"}
                      </button>
                    ) : null}
                  </div>

                  <details style={{ marginTop: "0.75rem" }}>
                    <summary>{language === "uk" ? "Технічні дані" : "Technical data"}</summary>
                    <div className="settings-info-grid" style={{ marginTop: "0.75rem" }}>
                      <SummaryField
                        label={language === "uk" ? "Код фурнітури" : "Fitting code"}
                        value={formatValue(template.fitting_code, language)}
                      />
                      <SummaryField
                        label={language === "uk" ? "Артикул фурнітури" : "Fitting article"}
                        value={formatValue(template.fitting_article, language)}
                      />
                      <SummaryField
                        label={language === "uk" ? "Ключ комплекту" : "Bundle key"}
                        value={formatValue(template.bundle_key, language)}
                      />
                      <SummaryField
                        label={language === "uk" ? "Порядок" : "Order"}
                        value={formatValue(template.bundle_order_index, language)}
                      />
                    </div>
                  </details>
                </article>
              );
            })}
          </section>
        ) : null}
      </article>

      <TemplatePreviewModal
        error={previewError}
        isOpen={isPreviewOpen && Boolean(selectedTemplateId)}
        language={language}
        loading={previewLoading}
        onClose={handleClosePreviewModal}
        onOpenEditor={handleOpenFittingHolesEditor}
        preview={selectedTemplatePreview}
        selectedFitting={selectedFitting}
        selectedTemplate={selectedTemplate}
      />

      <article className="dashboard-panel">
        <div className="dashboard-panel-head">
          <div>
            <h3>{language === "uk" ? "Майбутні категорії" : "Future categories"}</h3>
            <p>
              {language === "uk"
                ? "Ці категорії поки що тільки інформаційні і не створюють фальшивих даних."
                : "These categories are informational only and do not create fake data."}
            </p>
          </div>
        </div>

        <section className="settings-grid">
          {futureCategories.map((category) => (
            <article className="settings-card" key={category.key}>
              <div className="settings-card-header">
                <div>
                  <strong>{category.title}</strong>
                  <p>{category.description}</p>
                </div>
                <span className="service-tree-badge subtle">{language === "uk" ? "Заплановано" : "Planned"}</span>
              </div>
            </article>
          ))}
        </section>
      </article>

    </section>
  );
}
