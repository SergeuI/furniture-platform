export const FITTING_TAXONOMY_VIEWS = {
  manufacturers: "catalogFittingManufacturers",
  series: "catalogFittingSeries",
  categories: "catalogFittingCategories",
  products: "catalogFittingProducts",
};

export function normalizeFittingTaxonomyText(value) {
  return String(value || "").trim();
}

export function parseNullableId(value) {
  const normalized = normalizeFittingTaxonomyText(value);
  if (!normalized) {
    return null;
  }

  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function buildManufacturerOptions(items = [], selectedItemId = null) {
  const currentId = parseNullableId(selectedItemId);
  return [...items]
    .filter((item) => Boolean(item?.id))
    .sort((left, right) => {
      const leftName = normalizeFittingTaxonomyText(left?.name || left?.code);
      const rightName = normalizeFittingTaxonomyText(right?.name || right?.code);
      return leftName.localeCompare(rightName, "uk");
    })
    .filter((item) => item?.is_active || (currentId !== null && Number(item.id) === currentId));
}

export function buildSeriesOptions(items = [], manufacturerId = null, selectedSeriesId = null) {
  const normalizedManufacturerId = parseNullableId(manufacturerId);
  const currentSeriesId = parseNullableId(selectedSeriesId);

  return [...items]
    .filter((item) => Boolean(item?.id))
    .filter((item) => {
      if (normalizedManufacturerId === null) {
        return true;
      }

      return Number(item.manufacturer_id) === normalizedManufacturerId;
    })
    .filter((item) => item?.is_active || (currentSeriesId !== null && Number(item.id) === currentSeriesId));
}

export function sortFittingTaxonomyItems(items = []) {
  return [...items].sort((left, right) => {
    const leftName = normalizeFittingTaxonomyText(left?.name || left?.code);
    const rightName = normalizeFittingTaxonomyText(right?.name || right?.code);
    return leftName.localeCompare(rightName, "uk");
  });
}

export function buildCategoryParentOptions(items = [], selectedParentId = null, currentItemId = null) {
  const currentParentId = parseNullableId(selectedParentId);
  const normalizedCurrentItemId = parseNullableId(currentItemId);

  return [...items]
    .filter((item) => Boolean(item?.id))
    .filter((item) => normalizedCurrentItemId === null || Number(item.id) !== normalizedCurrentItemId)
    .filter((item) => item?.is_active || (currentParentId !== null && Number(item.id) === currentParentId))
    .sort((left, right) => {
      const leftName = normalizeFittingTaxonomyText(left?.name || left?.code);
      const rightName = normalizeFittingTaxonomyText(right?.name || right?.code);
      return leftName.localeCompare(rightName, "uk");
    });
}

export function buildProductTaxonomyPayload(form = {}) {
  return {
    manufacturer_id: parseNullableId(form.manufacturer_id),
    series_id: parseNullableId(form.series_id),
    category_id: parseNullableId(form.category_id),
    is_active: Boolean(form.is_active ?? true),
  };
}

export function buildManufacturerForm(item = null) {
  return {
    code: String(item?.code || ""),
    country_code: String(item?.country_code || ""),
    description: String(item?.description || ""),
    is_active: Boolean(item?.is_active ?? true),
    logo_url: String(item?.logo_url || ""),
    name: String(item?.name || ""),
    sort_order: Number(item?.sort_order ?? 0),
    website_url: String(item?.website_url || ""),
  };
}

export function buildSeriesForm(item = null) {
  return {
    code: String(item?.code || ""),
    description: String(item?.description || ""),
    is_active: Boolean(item?.is_active ?? true),
    manufacturer_id: item?.manufacturer_id ? String(item.manufacturer_id) : "",
    name: String(item?.name || ""),
    sort_order: Number(item?.sort_order ?? 0),
  };
}

export function buildCategoryForm(item = null) {
  return {
    code: String(item?.code || ""),
    description: String(item?.description || ""),
    is_active: Boolean(item?.is_active ?? true),
    name: String(item?.name || ""),
    parent_id: item?.parent_id ? String(item.parent_id) : "",
    sort_order: Number(item?.sort_order ?? 0),
  };
}

export function buildProductTaxonomyForm(item = null) {
  return {
    category_id: item?.category_id ? String(item.category_id) : "",
    manufacturer_id: item?.manufacturer_id ? String(item.manufacturer_id) : "",
    series_id: item?.series_id ? String(item.series_id) : "",
    is_active: Boolean(item?.is_active ?? true),
  };
}

export function getCompatibleSeriesId({ manufacturerId = null, seriesId = null, seriesItems = [] } = {}) {
  const normalizedManufacturerId = parseNullableId(manufacturerId);
  const normalizedSeriesId = parseNullableId(seriesId);

  if (normalizedSeriesId === null) {
    return null;
  }

  const selectedSeries = seriesItems.find((item) => Number(item?.id) === normalizedSeriesId) || null;
  if (!selectedSeries) {
    return null;
  }

  if (normalizedManufacturerId === null) {
    return normalizedSeriesId;
  }

  return Number(selectedSeries.manufacturer_id) === normalizedManufacturerId ? normalizedSeriesId : null;
}

export function getFittingTaxonomyViewLabel(view, language = "uk") {
  const labels = {
    [FITTING_TAXONOMY_VIEWS.manufacturers]: language === "uk" ? "Виробники" : "Manufacturers",
    [FITTING_TAXONOMY_VIEWS.series]: language === "uk" ? "Серії" : "Series",
    [FITTING_TAXONOMY_VIEWS.categories]: language === "uk" ? "Категорії" : "Categories",
    [FITTING_TAXONOMY_VIEWS.products]: language === "uk" ? "Технічні товари" : "Technical products",
  };

  return labels[view] || view;
}
