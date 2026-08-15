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
  {
    label: { uk: "\u0422\u0435\u0445\u043d\u0456\u0447\u043d\u0456 \u0442\u043e\u0432\u0430\u0440\u0438", en: "Technical products" },
    view: FITTING_TAXONOMY_VIEWS.products,
  },
];

export const FITTING_CATALOG_UNCATEGORIZED_CODE = "uncategorized";

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

function hasLegacyRowImage(row) {
  return Boolean(
    normalizeText(row?.image_url) ||
      normalizeText(row?.image) ||
      row?.has_cached_image,
  );
}

function parseRowTimestamp(value) {
  const parsed = Date.parse(String(value || ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function scoreLegacyRow(row, activeCity = "", { preferCommercial = false, preferImage = false } = {}) {
  if (!row) {
    return Number.NEGATIVE_INFINITY;
  }

  const normalizedCity = normalizeText(activeCity).toLowerCase();
  const rowCity = normalizeText(row?.city).toLowerCase();
  const cityMatch = normalizedCity && rowCity === normalizedCity;
  const hasCommercialValue = row?.price !== null && row?.price !== undefined && normalizeText(row?.stock);
  const hasImageValue = hasLegacyRowImage(row);
  const activeBoost = row?.is_active !== false ? 1000 : 0;
  const cityBoost = cityMatch ? 50 : 0;
  const commercialBoost = preferCommercial && hasCommercialValue ? 600 : 0;
  const imageBoost = preferImage && hasImageValue ? 600 : 0;
  const sourceBoost = normalizeText(row?.source_url) ? 25 : 0;
  const timestampBoost = Math.max(parseRowTimestamp(row?.updated_at), parseRowTimestamp(row?.created_at)) / 1_000_000_000;
  const idBoost = Number(row?.id || 0) / 1_000_000_000;

  return activeBoost + cityBoost + commercialBoost + imageBoost + sourceBoost + timestampBoost + idBoost;
}

function chooseBestLegacyRow(rows = [], activeCity = "", options = {}) {
  const candidates = Array.isArray(rows) ? rows.filter(Boolean) : [];
  if (!candidates.length) {
    return null;
  }

  return [...candidates].sort((left, right) => {
    const rightScore = scoreLegacyRow(right, activeCity, options);
    const leftScore = scoreLegacyRow(left, activeCity, options);

    if (rightScore !== leftScore) {
      return rightScore - leftScore;
    }

    const rightUpdatedAt = parseRowTimestamp(right?.updated_at) || parseRowTimestamp(right?.created_at);
    const leftUpdatedAt = parseRowTimestamp(left?.updated_at) || parseRowTimestamp(left?.created_at);
    if (rightUpdatedAt !== leftUpdatedAt) {
      return rightUpdatedAt - leftUpdatedAt;
    }

    return Number(right?.id || 0) - Number(left?.id || 0);
  })[0] || null;
}

function chooseRepresentativeLegacyRow(rows = [], activeCity = "") {
  return chooseBestLegacyRow(rows, activeCity, { preferCommercial: false, preferImage: false });
}

function chooseDisplayImageLegacyRow(rows = [], representativeRow = null, activeCity = "") {
  if (hasLegacyRowImage(representativeRow)) {
    return representativeRow;
  }

  return (
    chooseBestLegacyRow(rows, activeCity, { preferImage: true }) ||
    representativeRow ||
    (Array.isArray(rows) ? rows[0] : null) ||
    null
  );
}

function chooseCommercialLegacyRow(rows = [], representativeRow = null, activeCity = "") {
  if (representativeRow?.price !== null && representativeRow?.price !== undefined && normalizeText(representativeRow?.stock)) {
    return representativeRow;
  }

  return (
    chooseBestLegacyRow(rows, activeCity, { preferCommercial: true }) ||
    representativeRow ||
    (Array.isArray(rows) ? rows[0] : null) ||
    null
  );
}

export function getCanonicalFittingOwnershipSource(item = null) {
  const legacyRows = [
    ...(Array.isArray(item?.legacy_rows) ? item.legacy_rows : []),
    ...(Array.isArray(item?.linked_legacy_rows) ? item.linked_legacy_rows : []),
  ];
  const ownedRow = legacyRows.find((row) => row?.owner_user_id);
  if (ownedRow) {
    return ownedRow;
  }

  const systemRow = legacyRows.find((row) => row?.is_system && !row?.owner_user_id);
  if (systemRow) {
    return systemRow;
  }

  return item || null;
}

export function canRenderCanonicalFittingOwnershipBadge(item = null) {
  const ownershipSource = getCanonicalFittingOwnershipSource(item);

  return Boolean(
    ownershipSource &&
      (ownershipSource.is_system || normalizeId(ownershipSource.owner_user_id)),
  );
}

function resolveCategoryCode({
  product = null,
  categoriesById = new Map(),
} = {}) {
  const directCategoryId = normalizeId(product?.category_id);
  if (directCategoryId) {
    const category = categoriesById.get(directCategoryId);
    if (category?.code) {
      return String(category.code);
    }
  }

  return "";
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

export function getCanonicalFittingCatalogCountLabel(visibleCards = [], allCards = [], t = {}) {
  return `${Array.isArray(visibleCards) ? visibleCards.length : 0} ${t.of || "of"} ${Array.isArray(allCards) ? allCards.length : 0}`;
}

function pluralizeUkrainian(count = 0, one = "", few = "", many = "") {
  const normalizedCount = Math.abs(Number(count) || 0);
  const lastDigit = normalizedCount % 10;
  const lastTwoDigits = normalizedCount % 100;

  if (lastDigit === 1 && lastTwoDigits !== 11) {
    return one;
  }

  if (lastDigit >= 2 && lastDigit <= 4 && (lastTwoDigits < 12 || lastTwoDigits > 14)) {
    return few;
  }

  return many;
}

export function getCanonicalFittingsCountLabel({
  activeCategoryCode = "",
  visibleCards = [],
  allCards = [],
  language = "uk",
} = {}) {
  const count = activeCategoryCode
    ? Array.isArray(visibleCards) ? visibleCards.length : 0
    : Array.isArray(allCards) ? allCards.length : 0;

  if (language === "uk") {
    return `${count} ${pluralizeUkrainian(count, "товар", "товари", "товарів")}`;
  }

  return `${count} ${count === 1 ? "product" : "products"}`;
}

export function getCanonicalFittingsOverviewCountLabel({
  allCards = [],
  language = "uk",
} = {}) {
  return getCanonicalFittingsCountLabel({
    activeCategoryCode: "",
    allCards,
    language,
  });
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
      const imageLegacyRow = chooseDisplayImageLegacyRow(legacyRows, representativeLegacyRow);
      const commercialLegacyRow = chooseCommercialLegacyRow(legacyRows, representativeLegacyRow, activeCity);
      const categoryCode = resolveCategoryCode({
        categoriesById: taxonomyCategoriesById,
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
        category_code: categoryCode || FITTING_CATALOG_UNCATEGORIZED_CODE,
        category_name: category?.name || "",
        canonical_article: canonicalProduct?.article || "",
        canonical_brand: canonicalProduct?.brand || "",
        canonical_name: canonicalProduct?.name || "",
        legacy_row_count: legacyRows.length,
        legacy_rows: legacyRows,
        commercial_legacy_row: commercialLegacyRow,
        manufacturer_name: manufacturer?.name || canonicalProduct?.brand || "",
        manufacturer_code: manufacturer?.code || "",
        image_legacy_row: imageLegacyRow,
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
    categoryCounts.set(card.category_code, (categoryCounts.get(card.category_code) || 0) + 1);
  }

  const uncategorizedCount = categoryCounts.get(FITTING_CATALOG_UNCATEGORIZED_CODE) || 0;
  const visibleCategories = [
    ...legacyCategories.map((category) => ({
      ...category,
      canonical_item_count: categoryCounts.get(String(category.code || "")) || 0,
    })),
    ...(uncategorizedCount
      ? [{
          code: FITTING_CATALOG_UNCATEGORIZED_CODE,
          description: "",
          group: "",
          group_name: "",
          name: "Без категорії",
          canonical_item_count: uncategorizedCount,
          item_count: uncategorizedCount,
        }]
      : []),
  ];

  const normalizedSearch = normalizeText(search).toLowerCase();
  const visibleCards = canonicalCards.filter((card) => {
    if (activeCategoryCode) {
      if (activeCategoryCode === FITTING_CATALOG_UNCATEGORIZED_CODE) {
        if (card.category_code !== FITTING_CATALOG_UNCATEGORIZED_CODE) {
          return false;
        }
      } else if (card.category_code !== activeCategoryCode) {
        return false;
      }
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
