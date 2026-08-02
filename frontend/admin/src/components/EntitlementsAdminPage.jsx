import {
  CheckCircle2,
  CircleAlert,
  Pencil,
  Plus,
  RefreshCw,
  Save,
  Search,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  buildEntitlementFeaturePayload,
  applyEntitlementModalScrollLock,
  buildEntitlementMatrixDraft,
  buildEntitlementMatrixUpdateRows,
  cloneEntitlementMatrixDraft,
  createEntitlementFeatureDraft,
  createMatrixCellDraft,
  ENTITLEMENT_BOOLEAN_TABLE_HINT,
  getEntitlementCategoryLabel,
  getEntitlementCategoryFilterOptions,
  filterEntitlementFeatures,
  getEntitlementCellEditorKind,
  getEntitlementCellLabel,
  getEntitlementFeatureScopeLabel,
  getEntitlementValueTypeLabel,
  normalizeEntitlementText,
  getEntitlementRegistrySyncPreviewState,
  sortEntitlementFeatures,
} from "../entitlementsMatrix.js";
import {
  applyEntitlementRegistrySync,
  createEntitlementFeature,
  getEntitlementFeatures,
  getEntitlementMatrix,
  previewEntitlementRegistrySync,
  updateEntitlementFeature,
  updateEntitlementMatrix,
} from "../api.js";

const EMPTY_FEATURE_ERRORS = {
  category: "",
  description_uk: "",
  enum_options_raw: "",
  feature_key: "",
  name_uk: "",
  sort_order: "",
  value_type: "",
};

function createInitialFeatureForm(feature = null) {
  return createEntitlementFeatureDraft(feature);
}

function normalizeBooleanCell(cell, nextValue) {
  return {
    ...createMatrixCellDraft("boolean", cell),
    bool_value: nextValue === null ? null : Boolean(nextValue),
    is_not_applicable: false,
    is_unlimited: false,
  };
}

function normalizeIntegerCell(cell, patch) {
  const next = {
    ...createMatrixCellDraft("integer", cell),
    ...patch,
  };

  if (next.is_not_applicable) {
    return {
      ...next,
      integer_value: null,
      is_unlimited: false,
    };
  }

  if (next.is_unlimited) {
    return {
      ...next,
      integer_value: null,
      is_not_applicable: false,
    };
  }

  return {
    ...next,
    integer_value: normalizeEntitlementText(next.integer_value),
    is_not_applicable: false,
    is_unlimited: false,
  };
}

function normalizeDecimalCell(cell, patch) {
  const next = {
    ...createMatrixCellDraft("decimal", cell),
    ...patch,
  };

  if (next.is_not_applicable) {
    return {
      ...next,
      decimal_value: null,
      is_unlimited: false,
    };
  }

  if (next.is_unlimited) {
    return {
      ...next,
      decimal_value: null,
      is_not_applicable: false,
    };
  }

  return {
    ...next,
    decimal_value: normalizeEntitlementText(next.decimal_value),
    is_not_applicable: false,
    is_unlimited: false,
  };
}

function normalizeTextLikeCell(valueType, cell, patch) {
  const next = {
    ...createMatrixCellDraft(valueType, cell),
    ...patch,
  };

  if (next.is_not_applicable) {
    return {
      ...next,
      text_value: null,
      is_unlimited: false,
    };
  }

  return {
    ...next,
    text_value: normalizeEntitlementText(next.text_value),
    is_not_applicable: false,
    is_unlimited: false,
  };
}

function updateCellDraft(feature, currentCell, patch) {
  const valueType = normalizeEntitlementText(feature?.value_type).toLowerCase();

  if (valueType === "boolean") {
    return normalizeBooleanCell(currentCell, patch.bool_value);
  }

  if (valueType === "integer") {
    return normalizeIntegerCell(currentCell, patch);
  }

  if (valueType === "decimal") {
    return normalizeDecimalCell(currentCell, patch);
  }

  if (valueType === "enum" || valueType === "text") {
    return normalizeTextLikeCell(valueType, currentCell, patch);
  }

  return createMatrixCellDraft(valueType, currentCell);
}

function FeatureModal({
  draft,
  errors,
  isEditing,
  originalFeature,
  onChange,
  onClose,
  onSubmit,
  saving,
}) {
  const valueType = normalizeEntitlementText(draft.value_type).toLowerCase();
  const originalValueType = normalizeEntitlementText(originalFeature?.value_type).toLowerCase();
  const showTypeWarning =
    isEditing &&
    originalValueType &&
    valueType &&
    valueType !== originalValueType;

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="confirm-modal entitlements-modal">
        <header className="confirm-header">
          <div>
            <h3>{isEditing ? "Редагувати право" : "Додати ручне право"}</h3>
            <p>
              {isEditing
                ? "Оновіть опис, групу, тип значення або enum-варіанти."
                : "Створіть нове ручне право для тарифної матриці."}
            </p>
          </div>
          <button className="icon-button" onClick={onClose} type="button">
            <X size={18} />
          </button>
        </header>

        <form className="entitlements-modal-form" onSubmit={onSubmit}>
          <label>
            Технічний ключ
            <input
              disabled={isEditing}
              onChange={(event) => onChange("feature_key", event.target.value)}
              value={draft.feature_key}
            />
            {errors.feature_key ? <small className="field-error">{errors.feature_key}</small> : null}
          </label>

          <label>
            Назва українською
            <input
              onChange={(event) => onChange("name_uk", event.target.value)}
              value={draft.name_uk}
            />
            {errors.name_uk ? <small className="field-error">{errors.name_uk}</small> : null}
          </label>

          <label className="entitlements-modal-full-row">
            Опис
            <textarea
              onChange={(event) => onChange("description_uk", event.target.value)}
              rows="3"
              value={draft.description_uk}
            />
          </label>

          <label>
            Група
            <input
              onChange={(event) => onChange("category", event.target.value)}
              value={draft.category}
            />
            {errors.category ? <small className="field-error">{errors.category}</small> : null}
          </label>

          <label>
            Тип значення
            <select
              onChange={(event) => onChange("value_type", event.target.value)}
              value={draft.value_type}
            >
              <option value="boolean">Boolean</option>
              <option value="integer">Integer</option>
              <option value="decimal">Decimal</option>
              <option value="text">Text</option>
              <option value="enum">Enum</option>
            </select>
            {errors.value_type ? <small className="field-error">{errors.value_type}</small> : null}
          </label>

          {valueType === "enum" ? (
            <label className="entitlements-modal-full-row">
              Варіанти enum
              <textarea
                onChange={(event) => onChange("enum_options_raw", event.target.value)}
                rows="5"
                placeholder="Один варіант на рядок"
                value={draft.enum_options_raw}
              />
              {errors.enum_options_raw ? (
                <small className="field-error">{errors.enum_options_raw}</small>
              ) : null}
            </label>
          ) : null}

          {showTypeWarning ? (
            <div className="entitlements-warning entitlements-modal-full-row" role="note">
              Зміна типу очистить поточні тарифні значення цього права.
            </div>
          ) : null}

          <label>
            <span>Активне</span>
            <div className="inline-toggle">
              <input
                checked={draft.is_active}
                onChange={(event) => onChange("is_active", event.target.checked)}
                type="checkbox"
              />
              <span>{draft.is_active ? "Так" : "Ні"}</span>
            </div>
          </label>

          <label>
            Порядок
            <input
              inputMode="numeric"
              onChange={(event) => onChange("sort_order", event.target.value)}
              type="number"
              value={draft.sort_order}
            />
            {errors.sort_order ? <small className="field-error">{errors.sort_order}</small> : null}
          </label>

          <div className="settings-actions entitlements-modal-actions entitlements-modal-full-row">
            <button className="ghost-button" onClick={onClose} type="button">
              Скасувати
            </button>
            <button className="primary-button" disabled={saving} type="submit">
              <CheckCircle2 size={18} />
              {saving ? "Збереження..." : isEditing ? "Зберегти право" : "Створити право"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function RegistrySyncModal({
  applying,
  language = "uk",
  hasUnsavedChanges,
  loading,
  onApply,
  onClose,
  preview,
  error,
}) {
  const summary = preview?.summary || preview || null;
  const syncState = getEntitlementRegistrySyncPreviewState(preview, {
    applying,
    hasUnsavedChanges,
  });
  const newFeatures = Array.isArray(summary?.new_features) ? summary.new_features : [];
  const metadataUpdates = Array.isArray(summary?.metadata_updates) ? summary.metadata_updates : [];
  const missingPlanRows = Array.isArray(summary?.missing_plan_rows) ? summary.missing_plan_rows : [];
  const conflicts = Array.isArray(summary?.conflicts) ? summary.conflicts : [];
  const orphanedSystemFeatures = Array.isArray(summary?.db_system_features_missing_from_registry)
    ? summary.db_system_features_missing_from_registry
    : [];
  const hasChanges = syncState.hasChanges;
  const canApply = syncState.canApply;

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="confirm-modal entitlements-modal entitlements-sync-modal">
        <header className="confirm-header">
          <div>
            <h3>Синхронізувати права</h3>
            <p>Перевірка системного реєстру покаже нові права, оновлення метаданих і відсутні тарифні рядки перед застосуванням.</p>
          </div>
          <button className="icon-button" onClick={onClose} type="button">
            <X size={18} />
          </button>
        </header>

        {loading ? (
          <div className="entitlements-empty-state">
            <p>Завантаження плану синхронізації...</p>
          </div>
        ) : error ? (
          <div className="entitlements-inline-error" role="alert">
            <CircleAlert size={16} />
            <span>{error}</span>
          </div>
        ) : summary ? (
          <div className="entitlements-sync-content">
            <div className="entitlements-sync-summary">
              <div className="entitlements-sync-stat">
                <strong>{newFeatures.length}</strong>
                <span>Нові права</span>
              </div>
              <div className="entitlements-sync-stat">
                <strong>{metadataUpdates.length}</strong>
                <span>Оновлення метаданих</span>
              </div>
              <div className="entitlements-sync-stat">
                <strong>{missingPlanRows.length}</strong>
                <span>Відсутні тарифні рядки</span>
              </div>
              <div className="entitlements-sync-stat">
                <strong>{conflicts.length}</strong>
                <span>Конфлікти</span>
              </div>
            </div>

            {hasUnsavedChanges ? (
              <div className="entitlements-warning" role="note">
                Спочатку збережіть незбережені зміни матриці. Apply блокується, щоб не загубити локальні правки.
              </div>
            ) : null}

            {newFeatures.length ? (
              <section className="entitlements-sync-section">
                <h4>Нові системні права</h4>
                <ul className="entitlements-sync-list">
                  {newFeatures.map((feature) => (
                    <li key={feature.feature_key}>
                      <strong>{feature.name_uk}</strong>
                      <span>{feature.feature_key}</span>
                      <small>
                        {getEntitlementCategoryLabel(feature.category, language)} · {getEntitlementValueTypeLabel(feature.value_type)}
                      </small>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {metadataUpdates.length ? (
              <section className="entitlements-sync-section">
                <h4>Оновлення метаданих</h4>
                <ul className="entitlements-sync-list">
                  {metadataUpdates.map((item) => (
                    <li key={item.feature_key}>
                      <strong>{item.feature_key}</strong>
                      <span>{Object.keys(item.changes || {}).join(", ")}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {missingPlanRows.length ? (
              <section className="entitlements-sync-section">
                <h4>Потрібні тарифні рядки</h4>
                <ul className="entitlements-sync-list">
                  {missingPlanRows.map((item) => (
                    <li key={item.feature_key}>
                      <strong>{item.feature_key}</strong>
                      <span>{(item.missing_plan_codes || []).join(", ")}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {conflicts.length ? (
              <section className="entitlements-sync-section">
                <h4>Конфлікти</h4>
                <ul className="entitlements-sync-list">
                  {conflicts.map((item) => (
                    <li key={`${item.feature_key}:${item.reason}`}>
                      <strong>{item.feature_key}</strong>
                      <span>{item.reason}</span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {orphanedSystemFeatures.length ? (
              <section className="entitlements-sync-section">
                <h4>Системні права, яких немає в registry</h4>
                <ul className="entitlements-sync-list">
                  {orphanedSystemFeatures.map((featureKey) => (
                    <li key={featureKey}>
                      <strong>{featureKey}</strong>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {!newFeatures.length &&
            !metadataUpdates.length &&
            !missingPlanRows.length &&
            !conflicts.length &&
            !orphanedSystemFeatures.length ? (
              <div className="entitlements-empty-state entitlements-sync-empty">
                <h4>Усі системні права вже синхронізовані</h4>
                <p>Змін для застосування немає.</p>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="settings-actions entitlements-modal-actions entitlements-modal-full-row">
          <button className="ghost-button" onClick={onClose} type="button">
            Закрити
          </button>
          {hasChanges ? (
            <button className="primary-button" disabled={!canApply} onClick={onApply} type="button">
              {applying ? "Синхронізація..." : "Застосувати"}
            </button>
          ) : null}
        </div>
      </section>
    </div>
  );
}

function MatrixCellEditor({
  feature,
  planCode,
  cell,
  onPatch,
}) {
  const valueType = normalizeEntitlementText(feature?.value_type).toLowerCase();
  const kind = getEntitlementCellEditorKind(valueType);
  const cellLabel = getEntitlementCellLabel(valueType, cell);

  if (kind === "boolean") {
    return (
      <div className="entitlements-cell-editor entitlements-boolean-cell">
        <label className="entitlements-cell-toggle">
          <input
            checked={Boolean(cell?.bool_value)}
            aria-label={`${normalizeEntitlementText(feature?.name_uk)} ${planCode}`}
            onChange={(event) =>
              onPatch(feature, planCode, {
                bool_value: event.target.checked,
              })
            }
            type="checkbox"
          />
        </label>
      </div>
    );
  }

  if (kind === "integer") {
    return (
      <div className="entitlements-cell-editor">
        <input
          disabled={Boolean(cell?.is_unlimited) || Boolean(cell?.is_not_applicable)}
          inputMode="numeric"
          onChange={(event) =>
            onPatch(feature, planCode, {
              integer_value: event.target.value,
            })
          }
          placeholder="0"
          type="number"
          value={cell?.integer_value ?? ""}
        />
        <label className="entitlements-cell-flag">
          <input
            checked={Boolean(cell?.is_unlimited)}
            onChange={(event) =>
              onPatch(feature, planCode, {
                is_unlimited: event.target.checked,
              })
            }
            type="checkbox"
          />
          <span>Без обмежень</span>
        </label>
        <label className="entitlements-cell-flag">
          <input
            checked={Boolean(cell?.is_not_applicable)}
            onChange={(event) =>
              onPatch(feature, planCode, {
                is_not_applicable: event.target.checked,
              })
            }
            type="checkbox"
          />
          <span>Не застосовується</span>
        </label>
        <small className="entitlements-cell-hint">{cellLabel}</small>
      </div>
    );
  }

  if (kind === "decimal") {
    return (
      <div className="entitlements-cell-editor">
        <input
          disabled={Boolean(cell?.is_unlimited) || Boolean(cell?.is_not_applicable)}
          inputMode="decimal"
          onChange={(event) =>
            onPatch(feature, planCode, {
              decimal_value: event.target.value,
            })
          }
          placeholder="0.00"
          step="any"
          type="number"
          value={cell?.decimal_value ?? ""}
        />
        <label className="entitlements-cell-flag">
          <input
            checked={Boolean(cell?.is_unlimited)}
            onChange={(event) =>
              onPatch(feature, planCode, {
                is_unlimited: event.target.checked,
              })
            }
            type="checkbox"
          />
          <span>Без обмежень</span>
        </label>
        <label className="entitlements-cell-flag">
          <input
            checked={Boolean(cell?.is_not_applicable)}
            onChange={(event) =>
              onPatch(feature, planCode, {
                is_not_applicable: event.target.checked,
              })
            }
            type="checkbox"
          />
          <span>Не застосовується</span>
        </label>
        <small className="entitlements-cell-hint">{cellLabel}</small>
      </div>
    );
  }

  if (kind === "enum") {
    const options = Array.isArray(feature?.enum_options_json) ? feature.enum_options_json : [];
    return (
      <div className="entitlements-cell-editor">
        <select
          disabled={Boolean(cell?.is_not_applicable)}
          onChange={(event) =>
            onPatch(feature, planCode, {
              text_value: event.target.value,
            })
          }
          value={cell?.text_value ?? ""}
        >
          <option value="">Закрито</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <label className="entitlements-cell-flag">
          <input
            checked={Boolean(cell?.is_not_applicable)}
            onChange={(event) =>
              onPatch(feature, planCode, {
                is_not_applicable: event.target.checked,
              })
            }
            type="checkbox"
          />
          <span>Не застосовується</span>
        </label>
        <small className="entitlements-cell-hint">{cellLabel}</small>
      </div>
    );
  }

  return (
    <div className="entitlements-cell-editor">
      <input
        disabled={Boolean(cell?.is_not_applicable)}
        onChange={(event) =>
          onPatch(feature, planCode, {
            text_value: event.target.value,
          })
        }
        placeholder="Закрито"
        type="text"
        value={cell?.text_value ?? ""}
      />
      <label className="entitlements-cell-flag">
        <input
          checked={Boolean(cell?.is_not_applicable)}
          onChange={(event) =>
            onPatch(feature, planCode, {
              is_not_applicable: event.target.checked,
            })
          }
          type="checkbox"
        />
        <span>Не застосовується</span>
      </label>
      <small className="entitlements-cell-hint">{cellLabel}</small>
    </div>
  );
}

export default function EntitlementsAdminPage({
  language = "uk",
  onDirtyChange = () => {},
  onStatus = () => {},
  token,
  user,
}) {
  const [features, setFeatures] = useState([]);
  const [matrixDraft, setMatrixDraft] = useState({});
  const [matrixBaseline, setMatrixBaseline] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingMatrix, setSavingMatrix] = useState(false);
  const [pageError, setPageError] = useState("");
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [featureModalOpen, setFeatureModalOpen] = useState(false);
  const [editingFeature, setEditingFeature] = useState(null);
  const [featureForm, setFeatureForm] = useState(createInitialFeatureForm());
  const [featureErrors, setFeatureErrors] = useState({ ...EMPTY_FEATURE_ERRORS });
  const [featureSaving, setFeatureSaving] = useState(false);
  const [registrySyncOpen, setRegistrySyncOpen] = useState(false);
  const [registrySyncPreview, setRegistrySyncPreview] = useState(null);
  const [registrySyncLoading, setRegistrySyncLoading] = useState(false);
  const [registrySyncApplying, setRegistrySyncApplying] = useState(false);
  const [registrySyncError, setRegistrySyncError] = useState("");

  const categoryOptions = useMemo(
    () => getEntitlementCategoryFilterOptions(features, language),
    [features, language],
  );
  const filteredFeatures = useMemo(
    () =>
      filterEntitlementFeatures(features, {
        search,
        category: categoryFilter,
        status: statusFilter,
      }),
    [categoryFilter, features, search, statusFilter],
  );
  const changedRows = useMemo(
    () => buildEntitlementMatrixUpdateRows(features, matrixDraft, matrixBaseline),
    [features, matrixBaseline, matrixDraft],
  );
  const hasUnsavedChanges = changedRows.length > 0;

  useEffect(() => {
    onDirtyChange(hasUnsavedChanges);
    return () => onDirtyChange(false);
  }, [hasUnsavedChanges, onDirtyChange]);

  useEffect(() => {
    const shouldLockBody = featureModalOpen || registrySyncOpen;
    if (!shouldLockBody) {
      return undefined;
    }

    return applyEntitlementModalScrollLock(typeof document !== "undefined" ? document : undefined);
  }, [featureModalOpen, registrySyncOpen]);

  const loadEntitlements = useCallback(async () => {
    if (!token || user?.role !== "admin") {
      return;
    }

    setLoading(true);
    setPageError("");

    const [featuresResult, matrixResult] = await Promise.all([
      getEntitlementFeatures(token, false),
      getEntitlementMatrix(token),
    ]);

    if (!featuresResult.success) {
      setFeatures([]);
      setMatrixDraft({});
      setMatrixBaseline({});
      setPageError(featuresResult.error || "Не вдалося завантажити права");
      setLoading(false);
      return;
    }

    const nextFeatures = sortEntitlementFeatures(featuresResult.features || []);
    const matrixRows = matrixResult.success && Array.isArray(matrixResult.matrix) ? matrixResult.matrix : [];
    const nextMatrix = buildEntitlementMatrixDraft(nextFeatures, matrixRows);

    setFeatures(nextFeatures);
    setMatrixDraft(cloneEntitlementMatrixDraft(nextMatrix.draft));
    setMatrixBaseline(cloneEntitlementMatrixDraft(nextMatrix.baseline));
    setPageError(matrixResult.success ? "" : matrixResult.error || "Не вдалося завантажити матрицю");
    setLoading(false);
  }, [token, user?.role]);

  useEffect(() => {
    let cancelled = false;

    if (!token || user?.role !== "admin") {
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }

    void loadEntitlements().then(() => {
      if (cancelled) {
        return;
      }
    });

    return () => {
      cancelled = true;
    };
  }, [loadEntitlements, token, user?.role]);

  const openCreateModal = () => {
    setEditingFeature(null);
    setFeatureForm(createInitialFeatureForm());
    setFeatureErrors({ ...EMPTY_FEATURE_ERRORS });
    setFeatureModalOpen(true);
  };

  const openEditModal = (feature) => {
    if (feature?.is_system) {
      return;
    }
    setEditingFeature(feature);
    setFeatureForm(createInitialFeatureForm(feature));
    setFeatureErrors({ ...EMPTY_FEATURE_ERRORS });
    setFeatureModalOpen(true);
  };

  const closeFeatureModal = () => {
    setFeatureModalOpen(false);
    setEditingFeature(null);
    setFeatureErrors({ ...EMPTY_FEATURE_ERRORS });
  };

  const handleFeatureFieldChange = (field, value) => {
    setFeatureForm((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const handleFeatureSubmit = async (event) => {
    event.preventDefault();

    const prepared = buildEntitlementFeaturePayload(featureForm);
    if (!prepared.valid) {
      setFeatureErrors({
        ...EMPTY_FEATURE_ERRORS,
        ...prepared.errors,
      });
      return;
    }

    setFeatureSaving(true);
    const result = editingFeature
      ? await updateEntitlementFeature(token, editingFeature.id, prepared.payload)
      : await createEntitlementFeature(token, prepared.payload);
    setFeatureSaving(false);

    if (!result.success) {
      const message = result.error || "Не вдалося зберегти право";
      setPageError(message);
      onStatus({ message, tone: "error" });
      return;
    }

    onStatus({
      message: editingFeature ? "Право успішно оновлено" : "Право успішно створено",
      tone: "success",
    });
    closeFeatureModal();
    await loadEntitlements();
  };

  const openRegistrySyncModal = useCallback(async () => {
    if (!token || user?.role !== "admin") {
      return;
    }

    setRegistrySyncOpen(true);
    setRegistrySyncLoading(true);
    setRegistrySyncError("");
    setRegistrySyncPreview(null);

    const result = await previewEntitlementRegistrySync(token);
    setRegistrySyncLoading(false);

    if (!result.success) {
      const message = result.error || "Не вдалося завантажити план синхронізації";
      setRegistrySyncError(message);
      setPageError(message);
      onStatus({ message, tone: "error" });
      return;
    }

    setRegistrySyncPreview(result);
  }, [onStatus, token, user?.role]);

  const closeRegistrySyncModal = () => {
    setRegistrySyncOpen(false);
    setRegistrySyncPreview(null);
    setRegistrySyncLoading(false);
    setRegistrySyncApplying(false);
    setRegistrySyncError("");
  };

  const handleApplyRegistrySync = async () => {
    if (!registrySyncPreview?.can_apply || registrySyncApplying || hasUnsavedChanges) {
      return;
    }

    setRegistrySyncApplying(true);
    const result = await applyEntitlementRegistrySync(token);
    setRegistrySyncApplying(false);

    if (!result.success) {
      const message = result.error || "Не вдалося застосувати синхронізацію прав";
      setRegistrySyncError(message);
      setPageError(message);
      onStatus({ message, tone: "error" });
      return;
    }

    onStatus({
      message: result.applied ? "Системні права синхронізовано" : "Системні права вже синхронізовані",
      tone: "success",
    });
    closeRegistrySyncModal();
    await loadEntitlements();
  };

  const patchMatrixCell = (feature, planCode, patch) => {
    const key = `${feature.id}:${planCode}`;
    setMatrixDraft((current) => {
      const nextCell = updateCellDraft(feature, current[key], patch);
      return {
        ...current,
        [key]: nextCell,
      };
    });
  };

  const handleSaveMatrix = async () => {
    if (!changedRows.length) {
      return;
    }

    setSavingMatrix(true);
    const result = await updateEntitlementMatrix(token, {
      rows: changedRows,
    });
    setSavingMatrix(false);

    if (!result.success) {
      const message = result.error || "Не вдалося зберегти матрицю";
      setPageError(message);
      onStatus({ message, tone: "error" });
      return;
    }

    onStatus({
      message: `Матрицю збережено (${result.updated_count ?? changedRows.length})`,
      tone: "success",
    });
    setPageError("");
    setLoading(true);
    const [featuresResult, matrixResult] = await Promise.all([
      getEntitlementFeatures(token, false),
      getEntitlementMatrix(token),
    ]);
    const nextFeatures = sortEntitlementFeatures(featuresResult.features || []);
    const matrixRows = matrixResult.success && Array.isArray(matrixResult.matrix) ? matrixResult.matrix : [];
    const nextMatrix = buildEntitlementMatrixDraft(nextFeatures, matrixRows);
    setFeatures(nextFeatures);
    setMatrixDraft(cloneEntitlementMatrixDraft(nextMatrix.draft));
    setMatrixBaseline(cloneEntitlementMatrixDraft(nextMatrix.baseline));
    setLoading(false);
  };

  if (user?.role !== "admin") {
    return (
      <section className="settings-panel full-panel entitlements-panel">
        <div className="settings-card">
          <div className="settings-card-header">
            <h3>Тарифи та права</h3>
          </div>
          <p>Доступ до цього розділу мають лише адміністратори.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="settings-panel full-panel entitlements-panel">
      <div className="settings-grid entitlements-grid">
        <article className="settings-card entitlements-card">
          <div className="settings-card-header entitlements-header">
            <div>
              <h3>Тарифи та права</h3>
              <p>Керуйте правами та значеннями для Trial, Free, Pro і Business.</p>
            </div>
            <div className="entitlements-header-actions">
              <button className="ghost-button" onClick={openRegistrySyncModal} type="button">
                <RefreshCw size={16} />
                Синхронізувати права
              </button>
              <button className="ghost-button" onClick={loadEntitlements} type="button">
                <RefreshCw size={16} />
                Оновити
              </button>
              <button className="primary-button" onClick={openCreateModal} type="button">
                <Plus size={16} />
                Додати ручне право
              </button>
              <button
                className="primary-button"
                disabled={!hasUnsavedChanges || savingMatrix}
                onClick={handleSaveMatrix}
                type="button"
              >
                <Save size={16} />
                {savingMatrix ? "Збереження..." : "Зберегти матрицю"}
              </button>
            </div>
          </div>

          <div className="entitlements-toolbar">
            <label className="entitlements-search">
              <Search size={16} />
              <input
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Пошук за назвою, ключем або описом"
                value={search}
              />
            </label>
            <label>
              Група
              <select onChange={(event) => setCategoryFilter(event.target.value)} value={categoryFilter}>
                <option value="">Усі</option>
                {categoryOptions.map((categoryOption) => (
                  <option key={categoryOption.value} value={categoryOption.value}>
                    {categoryOption.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Статус
              <select onChange={(event) => setStatusFilter(event.target.value)} value={statusFilter}>
                <option value="all">Усі</option>
                <option value="active">Активні</option>
                <option value="inactive">Вимкнені</option>
              </select>
            </label>
            <div className="entitlements-status-block">
              {hasUnsavedChanges ? <strong>Є незбережені зміни</strong> : <span>Змін немає</span>}
            </div>
          </div>

          <div className="entitlements-boolean-note" role="note">
            {ENTITLEMENT_BOOLEAN_TABLE_HINT}
          </div>

          {pageError ? (
            <div className="entitlements-inline-error" role="alert">
              <CircleAlert size={16} />
              <span>{pageError}</span>
            </div>
          ) : null}

          {loading ? (
            <div className="entitlements-empty-state">
              <p>Завантаження тарифної матриці...</p>
            </div>
          ) : features.length === 0 ? (
            <div className="entitlements-empty-state">
              <h4>Права ще не створені</h4>
              <p>Додайте перше ручне право, щоб почати керування тарифною матрицею.</p>
              <button className="primary-button" onClick={openCreateModal} type="button">
                <Plus size={16} />
                Додати ручне право
              </button>
            </div>
          ) : filteredFeatures.length === 0 ? (
            <div className="entitlements-empty-state">
              <h4>Нічого не знайдено</h4>
              <p>Спробуйте змінити пошук або фільтри.</p>
            </div>
          ) : (
            <div className="table-scroll entitlements-table-shell">
              <table className="entitlements-table">
                <thead>
                  <tr>
                    <th>Назва</th>
                    <th>Технічний ключ</th>
                    <th>Група</th>
                    <th>Тип</th>
                    <th>Trial</th>
                    <th>Free</th>
                    <th>Pro</th>
                    <th>Business</th>
                    <th>Статус</th>
                    <th>Дії</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFeatures.map((feature) => (
                    <tr key={feature.id}>
                      <td>
                        <strong>{feature.name_uk}</strong>
                        {feature.description_uk ? <small>{feature.description_uk}</small> : null}
                      </td>
                      <td>
                        <code className="entitlements-feature-key">{feature.feature_key}</code>
                      </td>
                      <td>{getEntitlementCategoryLabel(feature.category, language)}</td>
                      <td>{getEntitlementValueTypeLabel(feature.value_type)}</td>
                      {["trial", "free", "pro", "business"].map((planCode) => (
                        <td key={planCode}>
                          <MatrixCellEditor
                            cell={matrixDraft[`${feature.id}:${planCode}`]}
                            feature={feature}
                            onPatch={patchMatrixCell}
                            planCode={planCode}
                          />
                        </td>
                      ))}
                      <td>
                        <div className="entitlements-row-badges">
                          <span className={`status-badge ${feature.is_active ? "success" : "error"}`}>
                            {feature.is_active ? "Активне" : "Вимкнене"}
                          </span>
                          <span className={`feature-scope-badge ${feature.is_system ? "system" : "manual"}`}>
                            {getEntitlementFeatureScopeLabel(feature)}
                          </span>
                        </div>
                      </td>
                      <td>
                        <button
                          className="ghost-button compact-button"
                          disabled={feature.is_system}
                          onClick={() => openEditModal(feature)}
                          type="button"
                        >
                          <Pencil size={16} />
                          {feature.is_system ? "Системне право" : "Редагувати"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </article>
      </div>

      {registrySyncOpen ? (
        <RegistrySyncModal
          applying={registrySyncApplying}
          error={registrySyncError}
          hasUnsavedChanges={hasUnsavedChanges}
          language={language}
          loading={registrySyncLoading}
          onApply={handleApplyRegistrySync}
          onClose={closeRegistrySyncModal}
          preview={registrySyncPreview}
        />
      ) : null}

      {featureModalOpen ? (
        <FeatureModal
          draft={featureForm}
          errors={featureErrors}
          isEditing={Boolean(editingFeature)}
          originalFeature={editingFeature}
          onChange={(field, value) => {
            setFeatureErrors({ ...EMPTY_FEATURE_ERRORS });
            handleFeatureFieldChange(field, value);
          }}
          onClose={closeFeatureModal}
          onSubmit={handleFeatureSubmit}
          saving={featureSaving}
        />
      ) : null}
    </section>
  );
}
