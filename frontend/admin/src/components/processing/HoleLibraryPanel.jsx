import { useEffect, useMemo, useState } from "react";

import {
  createProcessingHoleLibraryItem,
  listProcessingHoleLibraryItems,
  updateProcessingHoleLibraryItem,
} from "../../api.js";

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }

  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1).replace(/\.0$/, "");
}

const HOLE_LIBRARY_LABELS_UK = {
  operation_type: {
    blind: "Глухий",
    through: "Наскрізний",
    edge: "Торцевий",
    deep_edge: "Глибокий торцевий",
    countersink: "Із зенкуванням",
    hinge_cup: "Чашка завіси",
  },
  surface_type: {
    plane: "Площина",
    edge: "Торець",
  },
  depth_mode: {
    through: "Наскрізь",
    fixed: "Фіксована глибина",
    range: "Діапазон",
    material_relative: "Залежить від товщини матеріалу",
  },
};

function getHoleLibraryLabel(group, value, language) {
  const code = String(value ?? "").trim();
  if (language !== "uk") {
    return code || "—";
  }
  return HOLE_LIBRARY_LABELS_UK[group]?.[code] || code || "—";
}

function getSuggestedHoleName(form, language) {
  const operationLabel = getHoleLibraryLabel("operation_type", form?.operation_type, language);
  const diameter = formatNumber(form?.diameter_mm);
  return operationLabel !== "—" && diameter !== "—" ? `${operationLabel} отвір Ø${diameter}` : "";
}

function getHoleDisplayName(item, language) {
  const name = String(item?.name ?? "").trim();
  if (!item?.is_system || !/\b(standard|deep|blind|edge|plane)\b/i.test(name)) {
    return name || "—";
  }

  const suggested = getSuggestedHoleName(item, language);
  return suggested || name || "—";
}

function formatDepthRule(item, language) {
  switch (item.depth_mode) {
    case "material_relative":
      return language === "uk"
        ? `товщина матеріалу ${Number(item.material_depth_offset_mm || 0) < 0 ? "−" : "+"} ${formatNumber(Math.abs(item.material_depth_offset_mm || 0))} мм`
        : `material thickness ${Number(item.material_depth_offset_mm || 0) < 0 ? "−" : "+"} ${formatNumber(Math.abs(item.material_depth_offset_mm || 0))} mm`;
    case "through":
      return language === "uk" ? "наскрізь" : "through";
    case "range":
      return `${formatNumber(item.min_depth_mm)}–${formatNumber(item.max_depth_mm)} мм`;
    case "fixed":
      return `${formatNumber(item.fixed_depth_mm)} мм`;
    default:
      return getHoleLibraryLabel("depth_mode", item.depth_mode, language);
  }
}

function getMappingLabel(mapping, language) {
  if (!mapping) {
    return language === "uk" ? "Не знайдено" : "Missing";
  }

  const serviceName = mapping.service_catalog_item?.name || mapping.service_external_code || "—";
  const article = mapping.service_article ? ` · ${mapping.service_article}` : "";
  return `${serviceName}${article}`;
}

function getStatusLabel(status, language) {
  switch (status) {
    case "resolved":
      return language === "uk" ? "Прив'язано" : "mapped";
    case "service_only":
      return language === "uk" ? "Послугу знайдено" : "Service found";
    case "missing_service":
    case "missing":
    case "unresolved":
      return language === "uk" ? "Не прив'язано" : "Not mapped";
    default:
      return language === "uk" ? "Не прив'язано" : "Not mapped";
  }
}

function normalizeEditorFormFromItem(item) {
  return {
    name: String(item?.name ?? ""),
    is_system: Boolean(item?.is_system ?? false),
    operation_type: String(item?.operation_type ?? ""),
    surface_type: String(item?.surface_type ?? ""),
    diameter_mm: item?.diameter_mm ?? "",
    depth_mode: String(item?.depth_mode ?? ""),
    fixed_depth_mm: item?.fixed_depth_mm ?? "",
    min_depth_mm: item?.min_depth_mm ?? "",
    max_depth_mm: item?.max_depth_mm ?? "",
    material_depth_offset_mm: item?.material_depth_offset_mm ?? "",
    is_countersink: Boolean(item?.is_countersink ?? false),
    is_active: Boolean(item?.is_active ?? true),
    notes: String(item?.notes ?? ""),
  };
}

export default function HoleLibraryPanel({ language = "uk", token = "" }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [includeInactive, setIncludeInactive] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [editingItemId, setEditingItemId] = useState("");
  const [editorError, setEditorError] = useState("");
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorModalOpen, setEditorModalOpen] = useState(false);
  const [editorForm, setEditorForm] = useState({
    name: "",
    is_system: false,
    operation_type: "",
    surface_type: "",
    diameter_mm: "",
    depth_mode: "",
    fixed_depth_mm: "",
    min_depth_mm: "",
    max_depth_mm: "",
    material_depth_offset_mm: "",
    is_countersink: false,
    is_active: true,
    notes: "",
  });

  const visibleItems = useMemo(() => items, [items]);
  const editingItem = items.find((item) => String(item?.id) === String(editingItemId)) || null;

  useEffect(() => {
    if (!editorModalOpen) {
      return undefined;
    }

    function handleKeyDown(event) {
      if (event.key === "Escape" && !editorSaving) {
        handleCancelEdit();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [editorModalOpen, editorSaving]);

  useEffect(() => {
    let cancelled = false;

    async function loadItems() {
      setLoading(true);
      setError("");
      const response = await listProcessingHoleLibraryItems(token, {
        include_inactive: includeInactive,
      });
      if (cancelled) {
        return;
      }
      if (!response.success) {
        setError(response.error || (language === "uk" ? "Не вдалося завантажити бібліотеку отворів" : "Unable to load the hole library"));
        setItems([]);
      } else {
        setItems(Array.isArray(response.items) ? response.items : []);
      }
      if (!cancelled) {
        setLoading(false);
      }
    }

    loadItems();

    return () => {
      cancelled = true;
    };
  }, [includeInactive, language, token]);

  async function handleToggleActive(item) {
    setSavingId(item.id);
    const response = await updateProcessingHoleLibraryItem(token, item.id, {
      is_active: !item.is_active,
    });
    if (response.success) {
      setItems((current) =>
        current.map((entry) => (entry.id === item.id ? response.item : entry)),
      );
    } else {
      setError(response.error || (language === "uk" ? "Не вдалося оновити статус" : "Unable to update status"));
    }
    setSavingId(null);
  }

  function handleStartEdit(item) {
    setEditingItemId(String(item?.id || ""));
    setEditorError("");
    setEditorForm(normalizeEditorFormFromItem(item));
    setEditorModalOpen(true);
  }

  function handleStartCreate() {
    setEditingItemId("");
    setEditorError("");
    setEditorForm(normalizeEditorFormFromItem(null));
    setEditorModalOpen(true);
  }

  function handleCancelEdit() {
    setEditingItemId("");
    setEditorError("");
    setEditorForm(normalizeEditorFormFromItem(null));
    setEditorModalOpen(false);
  }

  async function handleSubmitEditor(event) {
    event.preventDefault();
    setEditorSaving(true);
    setEditorError("");

    try {
      const payload = {
        ...editorForm,
        name: String(editorForm.name || "").trim(),
        operation_type: String(editorForm.operation_type || "").trim(),
        surface_type: String(editorForm.surface_type || "").trim(),
        depth_mode: String(editorForm.depth_mode || "").trim(),
        diameter_mm: editorForm.diameter_mm === "" ? null : editorForm.diameter_mm,
        fixed_depth_mm: editorForm.fixed_depth_mm === "" ? null : editorForm.fixed_depth_mm,
        min_depth_mm: editorForm.min_depth_mm === "" ? null : editorForm.min_depth_mm,
        max_depth_mm: editorForm.max_depth_mm === "" ? null : editorForm.max_depth_mm,
        material_depth_offset_mm:
          editorForm.material_depth_offset_mm === "" ? null : editorForm.material_depth_offset_mm,
        is_system: editingItemId ? Boolean(editorForm.is_system) : false,
        is_countersink: Boolean(editorForm.is_countersink),
        is_active: Boolean(editorForm.is_active),
        notes: String(editorForm.notes || "").trim() || null,
      };

      const response = editingItemId
        ? await updateProcessingHoleLibraryItem(token, editingItemId, payload)
        : await createProcessingHoleLibraryItem(token, payload);

      if (!response.success) {
        setEditorError(response.error || (language === "uk" ? "Не вдалося зберегти запис" : "Unable to save item"));
        setEditorSaving(false);
        return;
      }

      const savedItem = response.item || null;
      setItems((current) => {
        if (!savedItem) {
          return current;
        }

        if (editingItemId) {
          return current.map((item) => (String(item.id) === String(savedItem.id) ? savedItem : item));
        }

        return [savedItem, ...current];
      });
      handleCancelEdit();
    } catch (error) {
      setEditorError(error?.message || (language === "uk" ? "Не вдалося зберегти запис" : "Unable to save item"));
    } finally {
      setEditorSaving(false);
    }
  }

  return (
    <section className="table-panel full-panel">
      <div className="settings-card-header">
        <div>
          <h3>{language === "uk" ? "Бібліотека отворів" : "Hole library"}</h3>
          <p>
            {language === "uk"
              ? "Технологічні отвори та пов'язані послуги обробки."
              : "Technological holes and related processing services."}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.75rem", alignItems: "center", flexWrap: "wrap" }}>
          <label className="toggle-label" style={{ margin: 0 }}>
            <input
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
              type="checkbox"
            />
            <span>{language === "uk" ? "Показати неактивні" : "Show inactive"}</span>
          </label>
          <span className="service-tree-badge subtle">{visibleItems.length}</span>
          <button className="primary-button" onClick={handleStartCreate} type="button">
            {language === "uk" ? "+ Створити отвір" : "+ Create hole"}
          </button>
        </div>
      </div>

      {editorModalOpen ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={() => {
            if (!editorSaving) {
              handleCancelEdit();
            }
          }}
          role="dialog"
        >
          <section className="confirm-modal" onClick={(event) => event.stopPropagation()}>
            <div className="settings-card-header">
              <div>
                <h3>{editingItemId ? (language === "uk" ? "Редагувати отвір" : "Edit hole") : (language === "uk" ? "Створити отвір" : "Create hole")}</h3>
                <p>{language === "uk" ? "Заповніть параметри технологічного отвору." : "Fill in the technological hole parameters."}</p>
              </div>
              <button aria-label={language === "uk" ? "Закрити" : "Close"} className="ghost-button" disabled={editorSaving} onClick={handleCancelEdit} type="button">
                ×
              </button>
            </div>
            <form
        onSubmit={handleSubmitEditor}
        style={{
          display: "grid",
          gap: "0.75rem",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          padding: "0.75rem 0 1rem",
        }}
      >
        <label>
          {language === "uk" ? "Назва" : "Name"}
          <input
            onChange={(event) => setEditorForm((current) => ({ ...current, name: event.target.value }))}
            required
            value={editorForm.name}
          />
        </label>
        <label>
          {language === "uk" ? "Тип отвору" : "Operation"}
          <select
            onChange={(event) => setEditorForm((current) => ({
              ...current,
              operation_type: event.target.value,
              name: current.name || getSuggestedHoleName({ ...current, operation_type: event.target.value }, language),
            }))}
            required
            value={editorForm.operation_type}
          >
            <option value="">{language === "uk" ? "Оберіть тип" : "Choose type"}</option>
            {Object.entries(HOLE_LIBRARY_LABELS_UK.operation_type).map(([code, label]) => (
              <option key={code} value={code}>{language === "uk" ? label : code}</option>
            ))}
          </select>
        </label>
        <label>
          {language === "uk" ? "Поверхня" : "Surface"}
          <select
            onChange={(event) => setEditorForm((current) => ({ ...current, surface_type: event.target.value }))}
            required
            value={editorForm.surface_type}
          >
            <option value="">{language === "uk" ? "Оберіть поверхню" : "Choose surface"}</option>
            {Object.entries(HOLE_LIBRARY_LABELS_UK.surface_type).map(([code, label]) => (
              <option key={code} value={code}>{language === "uk" ? label : code}</option>
            ))}
          </select>
        </label>
        <label>
          {language === "uk" ? "Діаметр, мм" : "Diameter"}
          <input
            onChange={(event) => setEditorForm((current) => ({
              ...current,
              diameter_mm: event.target.value,
              name: current.name || getSuggestedHoleName({ ...current, diameter_mm: event.target.value }, language),
            }))}
            step="any"
            type="number"
            value={editorForm.diameter_mm}
          />
        </label>
        <label>
          {language === "uk" ? "Режим глибини" : "Depth mode"}
          <select
            onChange={(event) => setEditorForm((current) => ({ ...current, depth_mode: event.target.value }))}
            required
            value={editorForm.depth_mode}
          >
            <option value="">{language === "uk" ? "Оберіть режим" : "Choose mode"}</option>
            {Object.entries(HOLE_LIBRARY_LABELS_UK.depth_mode).map(([code, label]) => (
              <option key={code} value={code}>{language === "uk" ? label : code}</option>
            ))}
          </select>
        </label>
        {editorForm.depth_mode === "fixed" ? (
          <label>
            {language === "uk" ? "Глибина, мм" : "Depth, mm"}
            <input
              min="0"
              onChange={(event) => setEditorForm((current) => ({ ...current, fixed_depth_mm: event.target.value }))}
              step="any"
              type="number"
              value={editorForm.fixed_depth_mm}
            />
          </label>
        ) : null}
        {editorForm.depth_mode === "range" ? (
          <>
            <label>
              {language === "uk" ? "Мінімальна глибина, мм" : "Minimum depth, mm"}
              <input
                min="0"
                onChange={(event) => setEditorForm((current) => ({ ...current, min_depth_mm: event.target.value }))}
                step="any"
                type="number"
                value={editorForm.min_depth_mm}
              />
            </label>
            <label>
              {language === "uk" ? "Максимальна глибина, мм" : "Maximum depth, mm"}
              <input
                min="0"
                onChange={(event) => setEditorForm((current) => ({ ...current, max_depth_mm: event.target.value }))}
                step="any"
                type="number"
                value={editorForm.max_depth_mm}
              />
            </label>
          </>
        ) : null}
        {editorForm.depth_mode === "material_relative" ? (
          <label>
            {language === "uk" ? "Відступ від товщини матеріалу, мм" : "Material thickness offset, mm"}
            <input
              onChange={(event) => setEditorForm((current) => ({ ...current, material_depth_offset_mm: event.target.value }))}
              step="any"
              type="number"
              value={editorForm.material_depth_offset_mm}
            />
          </label>
        ) : null}
        <label>
          {language === "uk" ? "Примітка" : "Note"}
          <textarea
            onChange={(event) => setEditorForm((current) => ({ ...current, notes: event.target.value }))}
            rows="2"
            value={editorForm.notes}
          />
        </label>
        <label>
          <span>{language === "uk" ? "Активний" : "Active"}</span>
          <input
            checked={editorForm.is_active}
            onChange={(event) => setEditorForm((current) => ({ ...current, is_active: event.target.checked }))}
            type="checkbox"
          />
        </label>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "end", flexWrap: "wrap" }}>
          <button className="primary-button" disabled={editorSaving} type="submit">
            {editingItemId ? (language === "uk" ? "Зберегти" : "Save") : (language === "uk" ? "Створити" : "Create")}
          </button>
          <button className="ghost-button" disabled={editorSaving} onClick={handleCancelEdit} type="button">
            {language === "uk" ? "Скасувати" : "Cancel"}
          </button>
        </div>
      </form>

            {editorError ? <div className="mounting-schemes-alert error">{editorError}</div> : null}
            {editingItem ? (
              <section className="table-panel" style={{ marginTop: "1rem" }}>
                <div className="settings-card-header">
                  <div>
                    <h4>{language === "uk" ? "Послуги" : "Services"}</h4>
                    <p>{getHoleDisplayName(editingItem, language)}</p>
                  </div>
                </div>
                {Array.isArray(editingItem.mappings) && editingItem.mappings.length ? (
                  <div style={{ display: "grid", gap: "0.5rem" }}>
                    {editingItem.mappings.map((mapping) => (
                      <div key={mapping.id} className="service-tree-row">
                        <strong>{mapping.supplier_code || (language === "uk" ? "Власне виробництво" : "Own production")}</strong>
                        <span>{mapping.service_catalog_item?.name || mapping.service_external_code || "—"}</span>
                        <span>{mapping.service_article || mapping.service_external_code || "—"}</span>
                        <span>{getStatusLabel(mapping.mapping_status, language)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact-empty-state">{language === "uk" ? "Послуги не прив'язані." : "No services mapped."}</div>
                )}
              </section>
            ) : null}
          </section>
        </div>
      ) : null}

      {error ? <div className="mounting-schemes-alert error">{error}</div> : null}
      {loading ? <div className="mounting-schemes-alert subtle">{language === "uk" ? "Завантаження..." : "Loading..."}</div> : null}

      <div style={{ overflowX: "auto" }}>
        <table className="catalog-table" style={{ width: "100%", tableLayout: "fixed" }}>
          <thead>
            <tr>
              <th>{language === "uk" ? "Назва" : "Name"}</th>
              <th>{language === "uk" ? "Тип" : "Type"}</th>
              <th>{language === "uk" ? "Площина / торець" : "Surface"}</th>
              <th>{language === "uk" ? "Ø" : "Ø"}</th>
              <th>{language === "uk" ? "Глибина / правило" : "Depth rule"}</th>
              <th>{language === "uk" ? "Послуга" : "Service"}</th>
              <th>{language === "uk" ? "Постачальник" : "Provider"}</th>
              <th>{language === "uk" ? "Статус прив'язки" : "Mapping"}</th>
              <th>{language === "uk" ? "Активність" : "Active"}</th>
              <th>{language === "uk" ? "Дії" : "Actions"}</th>
            </tr>
          </thead>
          <tbody>
            {visibleItems.map((item) => {
              const mapping = item.primary_mapping || null;
              return (
                <tr key={item.id} style={{ opacity: item.is_active ? 1 : 0.6 }}>
                  <td>
                    <div>{getHoleDisplayName(item, language)}</div>
                  </td>
                  <td>{getHoleLibraryLabel("operation_type", item.operation_type, language)}</td>
                  <td>{getHoleLibraryLabel("surface_type", item.surface_type, language)}</td>
                  <td>{formatNumber(item.diameter_mm)}</td>
                  <td>{formatDepthRule(item, language)}</td>
                  <td>{getMappingLabel(mapping, language)}</td>
                  <td>{mapping?.supplier_code || "—"}</td>
                  <td>{getStatusLabel(mapping?.mapping_status, language)}</td>
                  <td>
                    <button
                      className="ghost-button"
                      disabled={savingId === item.id}
                      onClick={() => handleToggleActive(item)}
                      type="button"
                    >
                      {item.is_active ? (language === "uk" ? "Активний" : "Active") : (language === "uk" ? "Неактивний" : "Inactive")}
                    </button>
                  </td>
                  <td>
                    <button
                      className="ghost-button"
                      disabled={editorSaving}
                      onClick={() => handleStartEdit(item)}
                      type="button"
                      style={{ marginLeft: "0.5rem" }}
                    >
                      {language === "uk" ? "Редагувати" : "Edit"}
                    </button>
                  </td>
                </tr>
              );
            })}
            {!loading && visibleItems.length === 0 ? (
              <tr>
                <td colSpan={10}>
                  <div className="empty-state">
                    {language === "uk" ? "Бібліотека отворів порожня." : "The hole library is empty."}
                  </div>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

    </section>
  );
}
