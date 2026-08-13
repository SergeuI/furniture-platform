import { FITTING_TAXONOMY_VIEWS } from "./fittingTaxonomyAdmin.js";

export const FITTING_CATALOG_BODY_NAV_ITEMS = [
  {
    label: { uk: "\u041a\u0430\u0442\u0430\u043b\u043e\u0433", en: "Catalog" },
    view: "catalogFittings",
  },
  {
    label: { uk: "\u0412\u0438\u0440\u043e\u0431\u043d\u0438\u043a\u0438", en: "Manufacturers" },
    view: FITTING_TAXONOMY_VIEWS.manufacturers,
  },
  {
    label: { uk: "\u0421\u0435\u0440\u0456\u0457", en: "Series" },
    view: FITTING_TAXONOMY_VIEWS.series,
  },
  {
    label: { uk: "\u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457", en: "Categories" },
    view: FITTING_TAXONOMY_VIEWS.categories,
  },
];

function normalizeText(value) {
  return String(value || "").trim();
}

function normalizeId(value) {
  const normalized = normalizeText(value);
  return normalized ? normalized : "";
}

function buildLookup(items = []) {
  return new Map(items.filter((item) => item && item.id !== undefined && item.id !== null).map((item) => [String(item.id), item]));
}

function chooseRepresentativeLegacyRow(rows = [], activeCity = "") {
  if (!Array.isArray(rows) || !rows.length) {
    return null;
  }

  const normalizedCity = normalizeText(activeCity).toLowerCase();
  if (normalizedCity) {
    const exactCityRow = rows.find((row) => normalizeText(row?.city).toLowerCase() === normalizedCity);
    if (exactCityRow) {
      return exactCityRow;
    }
  }

  const activeRow = rows.find((row) => row?.is_active !== false);
  return activeRow || rows[0] || null;
}

function resolveCategoryCode({
  product = null,
  legacyRows = [],
  categoriesById = new Map(),
} = {}) {
  const directCategoryId = normalizeId(product?.category_id);
  if (directCategoryId) {
    const category = categoriesById.get(directCategoryId);
    if (category?.code) {
      return String(category.code);
    }
  }

  const categoryCounts = new Map();
  for (const row of Array.isArray(legacyRows) ? legacyRows : []) {
    const code = normalizeText(row?.fitting_type);
    if (!code) {
      continue;
    }

    categoryCounts.set(code, (categoryCounts.get(code) || 0) + 1);
  }

  if (!categoryCounts.size) {
    return "";
  }

  return [...categoryCounts.entries()]
    .sort((left, right) => {
      if (right[1] !== left[1]) {
        return right[1] - left[1];
      }

      return String(left[0]).localeCompare(String(right[0]), "uk");
    })[0][0];
}

function buildSearchText(parts = []) {
  return parts
    .flatMap((part) => {
      if (Array.isArray(part)) {
        return part;
      }

      return [part];
    })
    .filter(Boolean)
    .map((part) => String(part))
    .join(" ")
    .toLowerCase();
}

export function getFittingCatalogBodyNavItems(language = "uk") {
  return FITTING_CATALOG_BODY_NAV_ITEMS.map((item) => ({
    ...item,
    isActive: false,
    label: item.label?.[language] || item.label?.uk || item.label?.en || item.view,
  }));
}

export function buildCanonicalFittingCatalogView({
  activeCategoryCode = "",
  activeCity = "",
  canonicalProducts = [],
  legacyCategories = [],
  legacyItems = [],
  manufacturers = [],
  search = "",
  series = [],
  taxonomyCategories = [],
} = {}) {
  const productsById = buildLookup(canonicalProducts);
  const manufacturersById = buildLookup(manufacturers);
  const seriesById = buildLookup(series);
  const taxonomyCategoriesById = buildLookup(taxonomyCategories);
  const taxonomyCategoriesByCode = new Map(
    taxonomyCategories
      .filter((item) => normalizeText(item?.code))
      .map((item) => [String(item.code), item]),
  );

  const legacyGroups = new Map();
  for (const item of Array.isArray(legacyItems) ? legacyItems : []) {
    const technicalProductId = normalizeId(item?.technical_product_id);
    if (!technicalProductId) {
      continue;
    }

    const bucket = legacyGroups.get(technicalProductId) || [];
    bucket.push(item);
    legacyGroups.set(technicalProductId, bucket);
  }

  const canonicalCards = canonicalProducts
    .map((product) => {
      const productId = normalizeId(product?.id);
      const legacyRows = legacyGroups.get(productId) || [];
      const representativeLegacyRow = chooseRepresentativeLegacyRow(legacyRows, activeCity);
      const categoryCode = resolveCategoryCode({
        categoriesById: taxonomyCategoriesById,
        legacyRows,
        product,
      });
      const category = categoryCode ? taxonomyCategoriesByCode.get(categoryCode) || null : null;
      const manufacturer = normalizeId(product?.manufacturer_id)
        ? manufacturersById.get(normalizeId(product.manufacturer_id)) || null
        : null;
      const seriesItem = normalizeId(product?.series_id)
        ? seriesById.get(normalizeId(product.series_id)) || null
        : null;
      const canonicalProduct = productsById.get(productId) || product;
      const searchText = buildSearchText([
        canonicalProduct?.name,
        canonicalProduct?.article,
        canonicalProduct?.code,
        canonicalProduct?.brand,
        manufacturer?.name,
        seriesItem?.name,
        category?.name,
        categoryCode,
        legacyRows.map((row) => [
          row?.name,
          row?.article,
          row?.code,
          row?.city,
          row?.source_url,
          row?.description,
        ]),
      ]);

      return {
        ...canonicalProduct,
        category_code: categoryCode || "",
        category_name: category?.name || "",
        canonical_article: canonicalProduct?.article || "",
        canonical_brand: canonicalProduct?.brand || "",
        canonical_name: canonicalProduct?.name || "",
        legacy_row_count: legacyRows.length,
        legacy_rows: legacyRows,
        manufacturer_name: manufacturer?.name || canonicalProduct?.brand || "",
        manufacturer_code: manufacturer?.code || "",
        representative_legacy_row: representativeLegacyRow,
        search_text: searchText,
        series_name: seriesItem?.name || "",
        series_code: seriesItem?.code || "",
      };
    })
    .sort((left, right) => {
      const leftLabel = normalizeText(left?.canonical_name || left?.canonical_article || left?.article || left?.code);
      const rightLabel = normalizeText(right?.canonical_name || right?.canonical_article || right?.article || right?.code);
      return leftLabel.localeCompare(rightLabel, "uk");
    });

  const categoryCounts = new Map();
  for (const card of canonicalCards) {
    if (!card.category_code) {
      continue;
    }

    categoryCounts.set(card.category_code, (categoryCounts.get(card.category_code) || 0) + 1);
  }

  const visibleCategories = legacyCategories.map((category) => ({
    ...category,
    canonical_item_count: categoryCounts.get(String(category.code || "")) || 0,
  }));

  const normalizedSearch = normalizeText(search).toLowerCase();
  const visibleCards = canonicalCards.filter((card) => {
    if (activeCategoryCode && card.category_code !== activeCategoryCode) {
      return false;
    }

    if (!normalizedSearch) {
      return true;
    }

    return normalizeText(card.search_text).includes(normalizedSearch);
  });

  return {
    activeCategoryCode: normalizeText(activeCategoryCode),
    allCards: canonicalCards,
    categoryCounts,
    categories: visibleCategories,
    visibleCards,
  };
}
