import { LayoutGrid, List, Search, X } from "lucide-react";

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

export default function MountingNodesFittingSelectorModal({
  fittingCategories = [],
  fittingItems = [],
  language = "en",
  onClose = () => {},
  onConfirm = () => {},
  onSearchChange = () => {},
  onCategoryCodeChange = () => {},
  onToggleItem = () => {},
  onViewModeChange = () => {},
  isOpen = false,
  selectedCount = 0,
  selectedIds = [],
  search = "",
  categoryCode = "",
  t = {},
  title = "",
  viewMode = "list",
}) {
  const fittingCategoryOptions = (() => {
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
  })();

  const searchValue = normalizeText(search).toLowerCase();
  const normalizedCategoryCode = normalizeText(categoryCode);
  const visibleItems = (Array.isArray(fittingItems) ? fittingItems : []).filter((item) => {
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

    if (normalizedCategoryCode && itemCategoryCode !== normalizedCategoryCode) {
      return false;
    }

    return !searchValue || haystack.includes(searchValue);
  });

  if (!isOpen || !title) {
    return null;
  }

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <article
        className="confirm-modal hole-template-modal hole-bundle-modal"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="confirm-header">
          <div>
            <strong>{title}</strong>
            <p>
              {language === "uk"
                ? "Виберіть потрібну фурнітуру та підтвердьте зміни."
                : "Choose the fittings you want and confirm the selection."}
            </p>
          </div>
          <button
            aria-label={language === "uk" ? "Закрити" : "Close"}
            className="ghost-button compact-button detail-info-button"
            onClick={onClose}
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
              aria-pressed={viewMode === "list"}
              className={`ghost-button compact-button${viewMode === "list" ? " active" : ""}`}
              onClick={() => onViewModeChange("list")}
              title={language === "uk" ? "Список" : "List"}
              type="button"
            >
              <List size={16} />
              <span>{language === "uk" ? "Список" : "List"}</span>
            </button>
            <button
              aria-pressed={viewMode === "cards"}
              className={`ghost-button compact-button${viewMode === "cards" ? " active" : ""}`}
              onClick={() => onViewModeChange("cards")}
              title={language === "uk" ? "Картки" : "Cards"}
              type="button"
            >
              <LayoutGrid size={16} />
              <span>{language === "uk" ? "Картки" : "Cards"}</span>
            </button>
          </div>
          <span className="service-tree-badge subtle">
            {selectedCount} {language === "uk" ? "вибрано" : "selected"}
          </span>
        </div>

        <div className="hole-bundle-modal-toolbar">
          <label className="service-catalog-search hole-bundle-modal-search">
            <Search size={16} />
            <input
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder={language === "uk" ? "Пошук фурнітури" : "Search fittings"}
              type="search"
              value={search}
            />
          </label>
          <label className="holes-select">
            <span>{language === "uk" ? "Категорія" : "Category"}</span>
            <select onChange={(event) => onCategoryCodeChange(event.target.value)} value={categoryCode}>
              {fittingCategoryOptions.map((category, index) => (
                <option key={`selector-category-${index}-${category.value}`} value={category.value}>
                  {category.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {visibleItems.length ? (
          <div className={`hole-bundle-modal-body${viewMode === "cards" ? " is-cards" : " is-list"}`}>
            {viewMode === "list" ? (
              <div className="hole-bundle-modal-list">
                {visibleItems.map((item, index) => {
                  const fittingId = getFittingId(item);
                  const selected = selectedIds.includes(fittingId);
                  const imageUrl = getFittingImageUrl(item);
                  const selectorItemKey = `selector-item-${index}-${fittingId || getFittingArticle(item) || "fallback"}`;

                  return (
                    <button
                      aria-pressed={selected}
                      className={`hole-bundle-modal-row${selected ? " is-selected" : ""}`}
                      key={selectorItemKey}
                      onClick={() => onToggleItem(item)}
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
                          {getFittingArticle(item) || "—"} ·{" "}
                          {getFittingCategoryLabel(item, language, t, fittingCategories) || humanizeKey(getFittingCategoryCode(item))}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="hole-bundle-modal-cards">
                {visibleItems.map((item, index) => {
                  const fittingId = getFittingId(item);
                  const selected = selectedIds.includes(fittingId);
                  const imageUrl = getFittingImageUrl(item);
                  const selectorItemKey = `selector-item-${index}-${fittingId || getFittingArticle(item) || "fallback"}`;

                  return (
                    <button
                      aria-pressed={selected}
                      className={`hole-bundle-modal-card${selected ? " is-selected" : ""}`}
                      key={selectorItemKey}
                      onClick={() => onToggleItem(item)}
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
          <button className="ghost-button" onClick={onClose} type="button">
            {language === "uk" ? "Скасувати" : "Cancel"}
          </button>
          <button className="primary-button" onClick={onConfirm} type="button">
            {language === "uk" ? "Додати вибране" : "Add selected"}
          </button>
        </div>
      </article>
    </div>
  );
}
