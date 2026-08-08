import { ArrowLeft, ChevronRight, LayoutGrid, List, Plus, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  MOUNTING_NODE_CREATE_ROLE_OPTIONS,
  addMountingNodeCreateDraftItem,
  clearMountingNodeCreateDraft,
  createMountingNodeCreateDraft,
  createMountingNodeCreateDraftItemFromFitting,
  loadMountingNodeCreateDraft,
  removeMountingNodeCreateDraftItem,
  saveMountingNodeCreateDraft,
  updateMountingNodeCreateDraftItem,
  validateMountingNodeCreateDraft,
} from "../../mountingNodesCreateDraft.js";
import { getProcessingTemplateMountingVariantLabel } from "../../processingTemplates.js";
import surfaceMountIcon from "../../assets/hole-mounting/surface_mount.png";
import angledTwoPlanesIcon from "../../assets/hole-mounting/angled_two_planes.png";
import faceToEdgeIcon from "../../assets/hole-mounting/face_to_edge.png";
import edgeToEdgeIcon from "../../assets/hole-mounting/edge_to_edge.png";
import drawerSlidesIcon from "../../assets/hole-mounting/drawer_slides.png";
import MountingNodesFittingSelectorModal from "./MountingNodesFittingSelectorModal.jsx";

const MOUNTING_VARIANT_KEYS = [
  "surface_mount",
  "face_to_edge",
  "edge_to_edge",
  "angled_two_planes",
  "drawer_slides",
];

const MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY = "mountingNodesCreateFittingSelectorView";

function normalizeText(value) {
  return String(value ?? "").trim();
}

function humanizeKey(value) {
  return normalizeText(value)
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function normalizeCategoryToken(value) {
  return normalizeText(value)
    .toLowerCase()
    .replace(/[^a-z0-9а-яіїєґ]+/giu, "");
}

function findMatchingFittingCategory(categoryCode, fittingCategories = []) {
  const normalizedCategoryToken = normalizeCategoryToken(categoryCode);

  if (!normalizedCategoryToken) {
    return null;
  }

  return (Array.isArray(fittingCategories) ? fittingCategories : []).find((category) => {
    const normalizedCode = normalizeCategoryToken(category?.code);
    const normalizedName = normalizeCategoryToken(category?.name);
    const normalizedHumanizedCode = normalizeCategoryToken(humanizeKey(category?.code));

    return (
      normalizedCategoryToken === normalizedCode ||
      normalizedCategoryToken === normalizedName ||
      normalizedCategoryToken === normalizedHumanizedCode
    );
  }) || null;
}

function getFittingId(item) {
  return normalizeText(item?.id || item?.fitting_id);
}

function getFittingName(item) {
  return normalizeText(item?.name || item?.article || item?.code || item?.fitting_name || item?.fitting_id);
}

function getFittingArticle(item) {
  return normalizeText(item?.article || item?.code);
}

function getFittingCategoryCode(item) {
  return normalizeText(
    item?.category_code || item?.categoryCode || item?.fitting_type || item?.type || item?.code || "",
  );
}

function getFittingCategoryLabel(item, language, t, fittingCategories = []) {
  const categoryCode = getFittingCategoryCode(item);
  const matchingCategory = findMatchingFittingCategory(categoryCode, fittingCategories);
  const localizedLabel = normalizeText(t?.[categoryCode]);

  return (
    normalizeText(matchingCategory?.name) ||
    localizedLabel ||
    normalizeText(item?.category_label || item?.categoryName || item?.category || item?.fitting_category || "") ||
    humanizeKey(categoryCode)
  );
}

function getFittingImageUrl(item) {
  return normalizeText(item?.image_url || item?.image || item?.thumbnail_url || "");
}

function getMountingVariantDescription(variantKey, language) {
  const descriptions = {
    angled_two_planes:
      language === "uk"
        ? "Кріплення між двома непаралельними площинами."
        : "Mounting between two non-parallel planes.",
    drawer_slides:
      language === "uk"
        ? "Напрямні для висувних елементів."
        : "Slides for pull-out elements.",
    edge_to_edge:
      language === "uk"
        ? "Установка фурнітури по торцях панелей."
        : "Hardware mounted on the edges of panels.",
    face_to_edge:
      language === "uk"
        ? "Установка на площині однієї та торці іншої панелі."
        : "Mounting on one panel face and another panel edge.",
    surface_mount:
      language === "uk"
        ? "Установка фурнітури на площині."
        : "Hardware mounted on a panel face.",
  };

  return descriptions[variantKey] || "";
}

function getMountingVariantIcon(variantKey) {
  const icons = {
    angled_two_planes: angledTwoPlanesIcon,
    drawer_slides: drawerSlidesIcon,
    edge_to_edge: edgeToEdgeIcon,
    face_to_edge: faceToEdgeIcon,
    surface_mount: surfaceMountIcon,
  };

  return icons[variantKey] || surfaceMountIcon;
}

function getMountingVariantOptions(language) {
  return MOUNTING_VARIANT_KEYS.map((key) => ({
    description: getMountingVariantDescription(key, language),
    icon: getMountingVariantIcon(key),
    key,
    label: getProcessingTemplateMountingVariantLabel(key, language) || humanizeKey(key),
  }));
}

function normalizeSelectorViewMode(value) {
  return value === "cards" ? "cards" : "list";
}

function readStoredSelectorViewMode() {
  if (typeof window === "undefined" || !window.localStorage) {
    return "list";
  }

  try {
    return normalizeSelectorViewMode(window.localStorage.getItem(MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY));
  } catch {
    return "list";
  }
}

function Field({ children, label }) {
  return (
    <label className="mounting-node-create-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export default function MountingNodesCreatePanel({
  fittingItems = [],
  fittingCategories = [],
  language = "en",
  onCancel = () => {},
  onCreate = () => {},
  createError = "",
  isCreating = false,
  userRole = "",
  t = {},
}) {
  const [draft, setDraft] = useState(() =>
    (() => {
      const loadedDraft = loadMountingNodeCreateDraft();
      const normalizedDraft = createMountingNodeCreateDraft({
        ...loadedDraft,
        mounting_variant_key: loadedDraft.mounting_variant_key || MOUNTING_VARIANT_KEYS[0],
      });

      return normalizedDraft;
    })(),
  );
  const [selectedFittingId, setSelectedFittingId] = useState("");
  const [variantOpen, setVariantOpen] = useState(false);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorSearch, setSelectorSearch] = useState("");
  const [selectorCategoryCode, setSelectorCategoryCode] = useState("");
  const [selectorViewMode, setSelectorViewMode] = useState(() => readStoredSelectorViewMode());
  const [selectorDraftItemIds, setSelectorDraftItemIds] = useState([]);
  const [internalSubmitting, setInternalSubmitting] = useState(false);
  const selectorSearchRef = useRef(null);
  const selectorStateSeededRef = useRef(false);
  const createErrorRef = useRef(createError);
  const canChooseOwnershipType = String(userRole || "").trim().toLowerCase() === "admin";

  const validationErrors = useMemo(() => validateMountingNodeCreateDraft(draft), [draft]);
  const canSubmit = validationErrors.length === 0 && !isCreating && !internalSubmitting && typeof onCreate === "function";

  useEffect(() => {
    if (selectorOpen) {
      selectorSearchRef.current?.focus();
    }
  }, [selectorOpen]);

  useEffect(() => {
    createErrorRef.current = createError;
  }, [createError]);

  useEffect(() => {
    saveMountingNodeCreateDraft(draft);
  }, [draft]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.localStorage) {
      return;
    }

    try {
      window.localStorage.setItem(MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY, selectorViewMode);
    } catch {
      // Ignore storage failures in private browsing or sandboxed environments.
    }
  }, [selectorViewMode]);

  const fittingCategoryOptions = useMemo(() => {
    const options = new Map();
    const categorySource =
      Array.isArray(fittingCategories) && fittingCategories.length
        ? fittingCategories
        : Array.isArray(fittingItems)
          ? fittingItems
          : [];

    for (const item of categorySource) {
      const code = getFittingCategoryCode(item);
      if (!code || options.has(code)) {
        continue;
      }

      options.set(code, {
        value: code,
        label: getFittingCategoryLabel(item, language, t, fittingCategories) || humanizeKey(code),
      });
    }

    return [
      {
        value: "",
        label: language === "uk" ? "Усі категорії" : "All categories",
      },
      ...Array.from(options.values()),
    ];
  }, [fittingCategories, fittingItems, language, t]);

  useEffect(() => {
    if (!selectorCategoryCode && fittingCategoryOptions.length > 1) {
      setSelectorCategoryCode("");
    }
  }, [fittingCategoryOptions, selectorCategoryCode]);

  const selectedItems = Array.isArray(draft.items) ? draft.items : [];
  const selectedVariantKey = normalizeText(draft.mounting_variant_key) || MOUNTING_VARIANT_KEYS[0];
  const mountingVariantOptions = useMemo(() => getMountingVariantOptions(language), [language]);
  const selectedVariantModel = useMemo(
    () => mountingVariantOptions.find((item) => item.key === selectedVariantKey) || mountingVariantOptions[0] || null,
    [mountingVariantOptions, selectedVariantKey],
  );

  const selectedFitting =
    selectedItems.find((item) => getFittingId(item) === selectedFittingId) || selectedItems[0] || null;

  useEffect(() => {
    if (!selectedItems.length) {
      if (selectedFittingId) {
        setSelectedFittingId("");
      }
      return;
    }

    if (!selectedItems.some((item) => getFittingId(item) === selectedFittingId)) {
      setSelectedFittingId(getFittingId(selectedItems[0]));
    }
  }, [selectedFittingId, selectedItems]);

  const visibleSelectorItems = useMemo(() => {
    const search = normalizeText(selectorSearch).toLowerCase();
    const categoryCode = normalizeText(selectorCategoryCode);

    return (Array.isArray(fittingItems) ? fittingItems : []).filter((item) => {
      const itemCategoryCode = getFittingCategoryCode(item);
      const haystack = [
        getFittingId(item),
        getFittingName(item),
        getFittingArticle(item),
        getFittingCategoryLabel(item, language, t, fittingCategories),
        itemCategoryCode,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      if (categoryCode && itemCategoryCode !== categoryCode) {
        return false;
      }

      return !search || haystack.includes(search);
    });
  }, [fittingCategories, fittingItems, selectorCategoryCode, selectorSearch, language, t]);

  const selectorSelectedCount = selectorDraftItemIds.length;
  const selectorTitle =
    language === "uk" ? "Вибір фурнітури для монтажного вузла" : "Choose fittings for the mounting node";

  const updateDraft = (updater) => {
    setDraft((current) => {
      const next = typeof updater === "function" ? updater(current) : updater;
      return next;
    });
  };

  const handleCancel = () => {
    clearMountingNodeCreateDraft();
    onCancel?.();
  };

  const handleNameChange = (value) => {
    updateDraft((current) => ({
      ...current,
      name: value,
      is_dirty: true,
    }));
  };

  const handleDescriptionChange = (value) => {
    updateDraft((current) => ({
      ...current,
      description: value,
      is_dirty: true,
    }));
  };

  const handleOwnershipTypeChange = (value) => {
    updateDraft((current) => ({
      ...current,
      ownership_type: String(value || "").trim() === "system" ? "system" : "mine",
      is_dirty: true,
    }));
  };

  const handleVariantChange = (variantKey) => {
    updateDraft((current) => ({
      ...current,
      mounting_variant_key: variantKey,
      is_dirty: true,
    }));
    setVariantOpen(false);
  };

  const openSelector = () => {
    if (!selectorStateSeededRef.current) {
      setSelectorDraftItemIds(selectedItems.map((item) => getFittingId(item)).filter(Boolean));
      selectorStateSeededRef.current = true;
    }

    setSelectorOpen(true);
  };

  const closeSelector = () => {
    setSelectorOpen(false);
  };

  const handleToggleSelectorFitting = (item) => {
    const fittingId = getFittingId(item);

    if (!fittingId) {
      return;
    }

    setSelectorDraftItemIds((current) =>
      current.includes(fittingId)
        ? current.filter((existingId) => existingId !== fittingId)
        : [...current, fittingId],
    );
  };

  const handleConfirmSelectedFittings = () => {
    const currentItems = Array.isArray(draft.items) ? draft.items : [];
    const currentItemsById = new Map(currentItems.map((item) => [getFittingId(item), item]));
    const selectedIds = selectorDraftItemIds.filter(Boolean);
    const nextItems = [];

    selectedIds.forEach((fittingId) => {
      const existingItem = currentItemsById.get(fittingId);
      if (existingItem) {
        nextItems.push(existingItem);
        return;
      }

      const fitting = (Array.isArray(fittingItems) ? fittingItems : []).find((item) => getFittingId(item) === fittingId);
      if (!fitting) {
        return;
      }

      nextItems.push(createMountingNodeCreateDraftItemFromFitting(fitting));
    });

    updateDraft({
      ...draft,
      items: nextItems,
      is_dirty: true,
    });

    if (!nextItems.some((item) => getFittingId(item) === selectedFittingId)) {
      setSelectedFittingId(getFittingId(nextItems[0]) || "");
    }

    closeSelector();
  };

  const handleRemoveFitting = (fittingId) => {
    const nextDraft = removeMountingNodeCreateDraftItem(draft, fittingId);
    updateDraft(nextDraft);

    if (normalizeText(selectedFittingId) === normalizeText(fittingId)) {
      setSelectedFittingId(normalizeText(nextDraft.items?.[0]?.fitting_id || ""));
    }
  };

  const handleSelectedFittingPatch = (fittingId, patch) => {
    updateDraft(updateMountingNodeCreateDraftItem(draft, fittingId, patch));
  };

  const handleSubmit = async (event, afterCreate = "editor") => {
    event?.preventDefault?.();

    if (!canSubmit) {
      return;
    }

    setInternalSubmitting(true);
    try {
      const created = await onCreate(draft, afterCreate);
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (created || !createErrorRef.current) {
        clearMountingNodeCreateDraft();
      }
    } finally {
      setInternalSubmitting(false);
    }
  };

  const isSubmitting = isCreating || internalSubmitting;
  const primarySubmitLabel = isSubmitting
    ? language === "uk"
      ? "Збереження..."
      : "Saving..."
    : language === "uk"
      ? "Створити вузол"
      : "Create node";
  const nameValidationError = validationErrors.find((error) => error.field === "name") || null;
  const itemsValidationError =
    (draft.is_dirty || Boolean(createError) || isSubmitting)
      ? validationErrors.find((error) => error.field === "items") || null
      : null;
  const generalValidationError =
    (draft.is_dirty || Boolean(createError) || isSubmitting)
      ? validationErrors.find((error) => !["name", "items"].includes(error.field)) || null
      : null;

  return (
    <section aria-label={selectorTitle} className="mounting-node-create-screen">
      <article className="catalog-card service-catalog-card service-catalog-card-full mounting-node-create-section">
        <form onSubmit={(event) => handleSubmit(event, "editor")}>
          <div className="mounting-node-create-header">
            <div className="mounting-node-create-header-meta">
              <span className="service-tree-badge subtle">
                {language === "uk" ? "Фурнітура" : "Fittings"}: {selectedItems.length}
              </span>
              <button className="mounting-node-create-soft-button mounting-node-create-back-button" onClick={handleCancel} type="button">
                <ArrowLeft size={16} />
                {language === "uk" ? "Повернутися" : "Back"}
              </button>
            </div>
          </div>

          <div className="mounting-node-create-top-grid">
            <section className="mounting-node-create-card mounting-node-create-main-info-card">
              <div className="mounting-node-create-card-head">
                <strong>{language === "uk" ? "Основна інформація" : "Basic information"}</strong>
              </div>
              <div className="mounting-node-create-form-grid">
                <label className="mounting-node-create-field mounting-node-create-name-field">
                  <span>{language === "uk" ? "Назва монтажного вузла" : "Mounting node name"}</span>
                  <input
                    aria-describedby={nameValidationError ? "mounting-node-create-name-error" : undefined}
                    aria-invalid={Boolean(nameValidationError)}
                    disabled={isCreating || internalSubmitting}
                    onChange={(event) => handleNameChange(event.target.value)}
                    placeholder={language === "uk" ? "Наприклад, Конфірмат 7×50" : "For example, Confirmat 7x50"}
                    type="text"
                    value={draft.name}
                  />
                  {nameValidationError ? (
                    <div className="mounting-node-create-field-error" id="mounting-node-create-name-error">
                      {nameValidationError.message}
                    </div>
                  ) : null}
                </label>
                <label className="mounting-node-create-field mounting-node-create-description-field">
                  <span>{language === "uk" ? "Опис" : "Description"}</span>
                  <textarea
                    className="mounting-node-create-description-input"
                    disabled={isCreating || internalSubmitting}
                    onChange={(event) => handleDescriptionChange(event.target.value)}
                    placeholder={language === "uk" ? "Необов’язково" : "Optional"}
                    rows="2"
                    value={draft.description}
                  />
                </label>
              </div>
              {canChooseOwnershipType ? (
                <label className="mounting-node-create-field mounting-node-create-ownership-field">
                  <span>{language === "uk" ? "Тип вузла" : "Node type"}</span>
                  <select
                    disabled={isCreating || internalSubmitting}
                    onChange={(event) => handleOwnershipTypeChange(event.target.value)}
                    value={draft.ownership_type || "mine"}
                  >
                    <option value="mine">{language === "uk" ? "Власний" : "Owned"}</option>
                    <option value="system">{language === "uk" ? "Системний" : "System"}</option>
                  </select>
                </label>
              ) : null}
            </section>

            <section className="mounting-node-create-card mounting-node-create-variant-card">
              <div className="mounting-node-create-card-head">
                <strong>{language === "uk" ? "Варіант кріплення" : "Mounting variant"}</strong>
              </div>
              <div className={`holes-mounting-variant-dropdown-shell${variantOpen ? " is-open" : ""}`}>
                <button
                  className="holes-mounting-variant-toggle mounting-node-create-variant-toggle"
                  disabled={isCreating || internalSubmitting}
                  onClick={() => setVariantOpen((current) => !current)}
                  type="button"
                >
                  <span className="holes-mounting-variant-toggle-mark" aria-hidden="true">
                    {selectedVariantModel?.icon ? <img alt="" src={selectedVariantModel.icon} /> : <span>⋯</span>}
                  </span>
                  <span className="holes-mounting-variant-toggle-copy">
                    <strong>{selectedVariantModel?.label || selectedVariantKey}</strong>
                    {selectedVariantModel?.description ? <span>{selectedVariantModel.description}</span> : null}
                  </span>
                  <ChevronRight className="holes-mounting-variant-toggle-arrow" size={16} />
                </button>
                {variantOpen ? (
                  <div className="holes-mounting-variant-menu" role="listbox">
                    {mountingVariantOptions.map((variant, index) => {
                      const isActive = selectedVariantKey === variant.key;

                      return (
                        <button
                          aria-pressed={isActive}
                          className={`holes-mounting-variant-option${isActive ? " active" : ""}`}
                          disabled={isCreating || internalSubmitting}
                          key={`variant-${index}-${variant.key}`}
                          onClick={() => handleVariantChange(variant.key)}
                          type="button"
                        >
                          <span className="holes-mounting-variant-option-mark" aria-hidden="true">
                            <img alt="" src={variant.icon} />
                          </span>
                          <span className="holes-mounting-variant-option-copy">
                            <strong>{variant.label}</strong>
                            {variant.description ? <span>{variant.description}</span> : null}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            </section>
          </div>

          {generalValidationError ? <div className="mounting-node-create-banner">{generalValidationError.message}</div> : null}
          {createError ? <div className="mounting-node-create-banner">{createError}</div> : null}

          <section className="mounting-node-create-card mounting-node-create-items-card">
            <div className="hole-template-fitting-list-head mounting-node-create-items-head">
              <div>
                <h4>{language === "uk" ? "Фурнітура вузла" : "Node fittings"}</h4>
              </div>
              <button
                className="primary-button mounting-node-create-add-button"
                disabled={isCreating || internalSubmitting}
                onClick={openSelector}
                type="button"
              >
                <Plus size={16} />
                {language === "uk" ? "Додати фурнітуру" : "Add fittings"}
              </button>
            </div>

            {itemsValidationError ? (
              <div className="mounting-node-create-section-error">
                {itemsValidationError.message}
              </div>
            ) : selectedItems.length ? (
              null
            ) : (
              <div className="mounting-node-create-empty-state mounting-node-create-empty-state-compact">
                <span>{language === "uk" ? "До монтажного вузла ще не додано фурнітуру." : "No fittings added yet."}</span>
                <span>{language === "uk" ? "Додайте щонайменше одну позицію." : "Add at least one position."}</span>
              </div>
            )}

            <div className="holes-bundle-selected-list mounting-node-create-items-list">
              {selectedItems.length ? (
                selectedItems.map((item, index) => {
                  const fittingId = getFittingId(item);
                  const isActive = normalizeText(selectedFitting?.fitting_id) === normalizeText(fittingId);
                  const itemKey = `selected-item-${index}-${fittingId || getFittingArticle(item) || getFittingName(item) || "fallback"}`;
                  const imageUrl = getFittingImageUrl(item);

                  return (
                    <article
                      aria-label={getFittingName(item) || fittingId}
                      className={`hole-bundle-selected-item hole-bundle-selected-item-compact mounting-node-create-fitting-row${fittingId ? " is-clickable" : ""}${isActive ? " is-active" : ""}`}
                      key={itemKey}
                      onClick={() => setSelectedFittingId(fittingId)}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="hole-bundle-selected-item-media">
                        {imageUrl ? (
                          <img alt="" loading="lazy" src={imageUrl} />
                        ) : (
                          <span className="hole-bundle-selected-item-placeholder">
                            {language === "uk" ? "Немає фото" : "No image"}
                          </span>
                        )}
                      </div>

                      <div className="hole-bundle-selected-item-copy">
                        <strong>{getFittingName(item) || fittingId}</strong>
                        <span>{getFittingArticle(item) || fittingId || "—"}</span>
                      </div>

                      <label className="mounting-node-create-fitting-quantity">
                        <span>{language === "uk" ? "Кількість" : "Quantity"}</span>
                        <input
                          disabled={isCreating || internalSubmitting}
                          min="1"
                          onChange={(event) =>
                            handleSelectedFittingPatch(fittingId, { quantity: Number(event.target.value) || 1 })
                          }
                          type="number"
                          value={item.quantity || 1}
                        />
                      </label>

                      <label className="mounting-node-create-fitting-role">
                        <span>{language === "uk" ? "Роль" : "Role"}</span>
                        <select
                          disabled={isCreating || internalSubmitting}
                          onChange={(event) => handleSelectedFittingPatch(fittingId, { role: event.target.value })}
                          value={item.role || MOUNTING_NODE_CREATE_ROLE_OPTIONS[0]}
                        >
                          {MOUNTING_NODE_CREATE_ROLE_OPTIONS.map((role) => (
                            <option key={role} value={role}>
                              {role}
                            </option>
                          ))}
                        </select>
                      </label>

                      <button
                        aria-label={language === "uk" ? "Видалити" : "Remove fitting"}
                        className="ghost-button mounting-node-create-fitting-remove"
                        disabled={isCreating || internalSubmitting}
                        onClick={(event) => {
                          event.stopPropagation();
                          handleRemoveFitting(fittingId);
                        }}
                        title={language === "uk" ? "Видалити" : "Remove fitting"}
                        type="button"
                      >
                        <X size={14} />
                      </button>
                    </article>
                  );
                })
              ) : null}
            </div>
          </section>

          <div className="holes-workspace-save-panel mounting-node-create-footer">
            <div className="holes-workspace-save-actions mounting-node-create-actions">
              <button
                className="mounting-node-create-soft-button mounting-node-create-cancel-button"
                disabled={isSubmitting}
                onClick={handleCancel}
                type="button"
              >
                {language === "uk" ? "Скасувати" : "Cancel"}
              </button>
              <button
                className="primary-button mounting-node-create-submit-button"
                disabled={!canSubmit}
                onClick={(event) => handleSubmit(event, "editor")}
                type="button"
              >
                {primarySubmitLabel}
              </button>
            </div>
          </div>
        </form>

        {selectorOpen ? (
          <MountingNodesFittingSelectorModal
            categoryCode={selectorCategoryCode}
            isOpen={selectorOpen}
            fittingCategories={fittingCategories}
            fittingItems={fittingItems}
            language={language}
            onCategoryCodeChange={setSelectorCategoryCode}
            onClose={closeSelector}
            onConfirm={handleConfirmSelectedFittings}
            onSearchChange={setSelectorSearch}
            onToggleItem={handleToggleSelectorFitting}
            onViewModeChange={setSelectorViewMode}
            search={selectorSearch}
            selectedCount={selectorSelectedCount}
            selectedIds={selectorDraftItemIds}
            t={t}
            title={selectorTitle}
            viewMode={selectorViewMode}
          />
        ) : null}

        {false ? (
          <div className="modal-backdrop" onClick={closeSelector} role="presentation">
            <article
              className="confirm-modal hole-template-modal hole-bundle-modal"
              onClick={(event) => event.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-label={selectorTitle}
            >
              <header className="confirm-header">
                <div>
                  <strong>{selectorTitle}</strong>
                  <p>
                    {language === "uk"
                      ? "Виберіть потрібну фурнітуру та підтвердьте додавання."
                      : "Choose the fittings you want and confirm the selection."}
                  </p>
                </div>
                <button
                  aria-label={language === "uk" ? "Закрити" : "Close"}
                  className="ghost-button compact-button detail-info-button"
                  onClick={closeSelector}
                  type="button"
                >
                  <X size={16} />
                </button>
              </header>

              <div className="hole-bundle-modal-toolbar">
                <div
                  className="hole-bundle-modal-mode-switch mounting-nodes-display-toggle materials-mode-switch"
                  role="group"
                  aria-label={language === "uk" ? "Вигляд вибору фурнітури" : "Fitting selector view mode"}
                >
                  <button
                    aria-pressed={selectorViewMode === "list"}
                    className={`ghost-button compact-button${selectorViewMode === "list" ? " active" : ""}`}
                    onClick={() => setSelectorViewMode("list")}
                    title={language === "uk" ? "Список" : "List"}
                    type="button"
                  >
                    <List size={16} />
                    <span>{language === "uk" ? "Список" : "List"}</span>
                  </button>
                  <button
                    aria-pressed={selectorViewMode === "cards"}
                    className={`ghost-button compact-button${selectorViewMode === "cards" ? " active" : ""}`}
                    onClick={() => setSelectorViewMode("cards")}
                    title={language === "uk" ? "Картки" : "Cards"}
                    type="button"
                  >
                    <LayoutGrid size={16} />
                    <span>{language === "uk" ? "Картки" : "Cards"}</span>
                  </button>
                </div>
                <span className="service-tree-badge subtle">
                  {selectorSelectedCount} {language === "uk" ? "вибрано" : "selected"}
                </span>
              </div>

              <div className="hole-bundle-modal-toolbar">
                <label className="service-catalog-search hole-bundle-modal-search">
                  <Search size={16} />
                  <input
                    onChange={(event) => setSelectorSearch(event.target.value)}
                    placeholder={language === "uk" ? "Пошук фурнітури" : "Search fittings"}
                    ref={selectorSearchRef}
                    type="search"
                    value={selectorSearch}
                  />
                </label>
                <label className="holes-select">
                  <span>{language === "uk" ? "Категорія" : "Category"}</span>
                  <select onChange={(event) => setSelectorCategoryCode(event.target.value)} value={selectorCategoryCode}>
                    {fittingCategoryOptions.map((category, index) => (
                      <option key={`selector-category-${index}-${category.value}`} value={category.value}>
                        {category.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {visibleSelectorItems.length ? (
                <div className={`hole-bundle-modal-body${selectorViewMode === "cards" ? " is-cards" : " is-list"}`}>
                  {selectorViewMode === "list" ? (
                    <div className="hole-bundle-modal-list">
                      {visibleSelectorItems.map((item, index) => {
                        const fittingId = getFittingId(item);
                        const selected = selectorDraftItemIds.includes(fittingId);
                        const imageUrl = getFittingImageUrl(item);
                        const selectorItemKey = `selector-item-${index}-${fittingId || getFittingArticle(item) || "fallback"}`;

                        return (
                          <button
                            aria-pressed={selected}
                            className={`hole-bundle-modal-row${selected ? " is-selected" : ""}`}
                            key={selectorItemKey}
                            onClick={() => handleToggleSelectorFitting(item)}
                            type="button"
                          >
                            <span className="hole-bundle-modal-row-check" aria-hidden="true">
                              {selected ? "✓" : ""}
                            </span>
                            {imageUrl ? (
                              <img alt="" className="hole-bundle-modal-row-image" loading="lazy" src={imageUrl} />
                            ) : (
                              <span className="hole-bundle-modal-row-image hole-bundle-modal-row-image-empty" aria-hidden="true">
                                {language === "uk" ? "Немає фото" : "No image"}
                              </span>
                            )}
                            <span className="hole-bundle-modal-row-copy">
                              <strong>{getFittingName(item)}</strong>
                              <span>
                                {getFittingArticle(item) || "—"} · {getFittingCategoryLabel(item, language, t, fittingCategories) || humanizeKey(getFittingCategoryCode(item))}
                              </span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="hole-bundle-modal-cards">
                      {visibleSelectorItems.map((item, index) => {
                        const fittingId = getFittingId(item);
                        const selected = selectorDraftItemIds.includes(fittingId);
                        const imageUrl = getFittingImageUrl(item);
                        const selectorItemKey = `selector-item-${index}-${fittingId || getFittingArticle(item) || "fallback"}`;

                        return (
                          <button
                            aria-pressed={selected}
                            className={`hole-bundle-modal-card${selected ? " is-selected" : ""}`}
                            key={selectorItemKey}
                            onClick={() => handleToggleSelectorFitting(item)}
                            type="button"
                          >
                            {imageUrl ? (
                              <img alt="" className="hole-bundle-modal-card-image" loading="lazy" src={imageUrl} />
                            ) : (
                              <span className="hole-bundle-modal-card-image hole-bundle-modal-card-image-empty" aria-hidden="true">
                                {language === "uk" ? "Немає фото" : "No image"}
                              </span>
                            )}
                            <span className="hole-bundle-modal-card-copy">
                              <strong>{getFittingName(item)}</strong>
                              <span>{getFittingArticle(item) || "—"}</span>
                              <span>{getFittingCategoryLabel(item, language, t, fittingCategories) || humanizeKey(getFittingCategoryCode(item))}</span>
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-state compact-empty-state">
                  <span>{language === "uk" ? "Фурнітуру не знайдено." : "No fittings found."}</span>
                </div>
              )}

              <div className="confirm-actions">
                <button className="ghost-button" onClick={closeSelector} type="button">
                  {language === "uk" ? "Скасувати" : "Cancel"}
                </button>
                <button className="primary-button" onClick={handleConfirmSelectedFittings} type="button">
                  {language === "uk" ? "Додати вибране" : "Add selected"}
                </button>
              </div>
            </article>
          </div>
        ) : null}
      </article>
    </section>
  );
}
