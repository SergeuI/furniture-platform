const MOUNTING_NODE_FUNCTIONAL_LABELS = {
  connector: {
    en: "Connector",
    uk: "Кріплення деталей",
  },
  door_hinge: {
    en: "Door hinge",
    uk: "Меблева завіса",
  },
  drawer_slide: {
    en: "Drawer slide",
    uk: "Напрямна / висувна система",
  },
  furniture_handle: {
    en: "Furniture handle",
    uk: "Меблева ручка",
  },
  profile_handle: {
    en: "Profile handle",
    uk: "Ручка-профіль",
  },
  cabinet_leg: {
    en: "Cabinet leg",
    uk: "Меблева опора / ніжка",
  },
  wall_hanger: {
    en: "Wall hanger",
    uk: "Підвіс меблів",
  },
  sink: {
    en: "Sink",
    uk: "Мийка",
  },
  cooktop: {
    en: "Cooktop",
    uk: "Варильна поверхня",
  },
  ventilation_grille: {
    en: "Ventilation grille",
    uk: "Вентиляційна решітка",
  },
  electrical_socket: {
    en: "Electrical socket",
    uk: "Електрична розетка / електричний елемент",
  },
};

export const MOUNTING_NODE_FUNCTIONAL_CODES = Object.freeze(Object.keys(MOUNTING_NODE_FUNCTIONAL_LABELS));

function normalizeLanguage(language) {
  return String(language || "").trim().toLowerCase() === "uk" ? "uk" : "en";
}

export function normalizeMountingNodeFunctionalCode(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized && Object.prototype.hasOwnProperty.call(MOUNTING_NODE_FUNCTIONAL_LABELS, normalized)
    ? normalized
    : "";
}

export function getMountingNodeFunctionalLabel(functionalCode, language = "en") {
  const normalizedCode = normalizeMountingNodeFunctionalCode(functionalCode);
  if (!normalizedCode) {
    return "";
  }

  const normalizedLanguage = normalizeLanguage(language);
  return MOUNTING_NODE_FUNCTIONAL_LABELS[normalizedCode]?.[normalizedLanguage] || "";
}

export function getMountingNodeFunctionalOptions(language = "en") {
  const normalizedLanguage = normalizeLanguage(language);

  return MOUNTING_NODE_FUNCTIONAL_CODES.map((code) => ({
    code,
    label: MOUNTING_NODE_FUNCTIONAL_LABELS[code]?.[normalizedLanguage] || code,
  }));
}
