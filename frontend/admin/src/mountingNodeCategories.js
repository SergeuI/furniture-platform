const MOUNTING_NODE_CATEGORY_LABELS = {
  fastening: {
    en: "Fastening",
    uk: "Кріплення деталей",
  },
  hinges: {
    en: "Hinges",
    uk: "Завіси",
  },
  drawer_systems: {
    en: "Drawer systems",
    uk: "Напрямні та висувні системи",
  },
  handles_profiles: {
    en: "Handles and profiles",
    uk: "Ручки та профілі",
  },
  supports_legs: {
    en: "Supports and legs",
    uk: "Опори та ніжки",
  },
  hangers: {
    en: "Hangers",
    uk: "Підвіси",
  },
  sinks_plumbing: {
    en: "Sinks and plumbing",
    uk: "Мийки та сантехніка",
  },
  appliances: {
    en: "Built-in appliances",
    uk: "Вбудована техніка",
  },
  ventilation: {
    en: "Ventilation",
    uk: "Вентиляція",
  },
  electrical: {
    en: "Electrical",
    uk: "Електрика",
  },
  other: {
    en: "Other",
    uk: "Інше",
  },
};

export const MOUNTING_NODE_CATEGORY_CODES = Object.freeze(Object.keys(MOUNTING_NODE_CATEGORY_LABELS));

function normalizeLanguage(language) {
  return String(language || "").trim().toLowerCase() === "uk" ? "uk" : "en";
}

export function normalizeMountingNodeCategoryCode(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized && Object.prototype.hasOwnProperty.call(MOUNTING_NODE_CATEGORY_LABELS, normalized)
    ? normalized
    : "";
}

export function getMountingNodeCategoryLabel(categoryCode, language = "en") {
  const normalizedCode = normalizeMountingNodeCategoryCode(categoryCode);
  if (!normalizedCode) {
    return "";
  }

  const normalizedLanguage = normalizeLanguage(language);
  return MOUNTING_NODE_CATEGORY_LABELS[normalizedCode]?.[normalizedLanguage] || "";
}

export function getMountingNodeCategoryOptions(language = "en") {
  const normalizedLanguage = normalizeLanguage(language);

  return MOUNTING_NODE_CATEGORY_CODES.map((code) => ({
    code,
    label: MOUNTING_NODE_CATEGORY_LABELS[code]?.[normalizedLanguage] || code,
  }));
}
