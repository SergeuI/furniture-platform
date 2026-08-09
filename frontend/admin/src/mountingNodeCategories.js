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

export function getMountingNodeCategoryImageUrl(categoryCode) {
  const normalizedCode = normalizeMountingNodeCategoryCode(categoryCode);
  const resolvedCode =
    normalizedCode ||
    (String(categoryCode || "").trim().toLowerCase() === "uncategorized" ? "uncategorized" : "");

  switch (resolvedCode) {
    case "fastening":
      return new URL("./assets/mounting-node-categories/fastening.png", import.meta.url).href;
    case "hinges":
      return new URL("./assets/mounting-node-categories/hinges.png", import.meta.url).href;
    case "drawer_systems":
      return new URL("./assets/mounting-node-categories/drawer_systems.png", import.meta.url).href;
    case "handles_profiles":
      return new URL("./assets/mounting-node-categories/handles_profiles.png", import.meta.url).href;
    case "supports_legs":
      return new URL("./assets/mounting-node-categories/supports_legs.png", import.meta.url).href;
    case "hangers":
      return new URL("./assets/mounting-node-categories/hangers.png", import.meta.url).href;
    case "sinks_plumbing":
      return new URL("./assets/mounting-node-categories/sinks_plumbing.png", import.meta.url).href;
    case "appliances":
      return new URL("./assets/mounting-node-categories/appliances.png", import.meta.url).href;
    case "ventilation":
      return new URL("./assets/mounting-node-categories/ventilation.png", import.meta.url).href;
    case "electrical":
      return new URL("./assets/mounting-node-categories/electrical.png", import.meta.url).href;
    case "other":
      return new URL("./assets/mounting-node-categories/other.png", import.meta.url).href;
    case "uncategorized":
      return new URL("./assets/mounting-node-categories/uncategorized.png", import.meta.url).href;
    default:
      return "";
  }
}
