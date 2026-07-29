const PROCESSING_TEMPLATE_FUTURE_CATEGORIES = [
  {
    key: "sinks",
    title: {
      en: "Sinks",
      uk: "Мийки",
    },
    description: {
      en: "Future processing templates for sink cutouts.",
      uk: "Майбутні шаблони для вирізів під мийки.",
    },
  },
  {
    key: "hobs",
    title: {
      en: "Hobs",
      uk: "Варильні поверхні",
    },
    description: {
      en: "Future processing templates for hob openings.",
      uk: "Майбутні шаблони для отворів під варильні поверхні.",
    },
  },
  {
    key: "appliances",
    title: {
      en: "Appliances",
      uk: "Побутова техніка",
    },
    description: {
      en: "Future processing templates for built-in appliances.",
      uk: "Майбутні шаблони для вбудованої побутової техніки.",
    },
  },
  {
    key: "grilles",
    title: {
      en: "Ventilation grilles",
      uk: "Вентиляційні решітки",
    },
    description: {
      en: "Future processing templates for vents and grilles.",
      uk: "Майбутні шаблони для вентиляційних отворів і решіток.",
    },
  },
  {
    key: "lighting",
    title: {
      en: "Lighting",
      uk: "Освітлення",
    },
    description: {
      en: "Future processing templates for lights and fixtures.",
      uk: "Майбутні шаблони для світильників і точкових джерел світла.",
    },
  },
  {
    key: "custom",
    title: {
      en: "Custom templates",
      uk: "Користувацькі шаблони",
    },
    description: {
      en: "Reserved for company and user-defined templates.",
      uk: "Місце для компанійських і користувацьких шаблонів.",
    },
  },
];

const PROCESSING_TEMPLATE_MOUNTING_VARIANT_LABELS = {
  surface_mount: {
    en: "Surface mount",
    uk: "Установка фурнітури на площині",
  },
  angled_two_planes: {
    en: "Angled two planes",
    uk: "Кріплення між двома площинами під кутом",
  },
  face_to_edge: {
    en: "Face to edge",
    uk: "Площина до торця",
  },
  edge_to_edge: {
    en: "Edge to edge",
    uk: "Торець до торця",
  },
  drawer_slides: {
    en: "Drawer slides",
    uk: "Напрямні шухляди",
  },
};

const PROCESSING_TEMPLATE_STATUS_LABELS = {
  active: {
    en: "Active",
    uk: "Активний",
  },
  inactive: {
    en: "Inactive",
    uk: "Неактивний",
  },
  all: {
    en: "All",
    uk: "Усі",
  },
};

const PROCESSING_TEMPLATE_TYPE_LABELS = {
  bundle: {
    en: "Bundle template",
    uk: "Шаблон комплекту",
  },
  manual: {
    en: "Manual template",
    uk: "Ручний шаблон",
  },
  default: {
    en: "Default template",
    uk: "Шаблон за замовчуванням",
  },
};

export const PROCESSING_TEMPLATES_RETURN_STATE_STORAGE_KEY = "furniture_admin_processing_templates_return_state";

function pickLocalizedText(source, language) {
  if (!source) {
    return "";
  }

  return source[language] || source.uk || source.en || "";
}

function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  const numericValue = Number(value);

  if (Number.isNaN(numericValue)) {
    return String(value);
  }

  return numericValue % 1 === 0 ? String(numericValue) : numericValue.toFixed(2).replace(/\.00$/, "");
}

export function getProcessingTemplateFutureCategories(language = "uk") {
  return PROCESSING_TEMPLATE_FUTURE_CATEGORIES.map((category) => ({
    key: category.key,
    title: pickLocalizedText(category.title, language),
    description: pickLocalizedText(category.description, language),
  }));
}

export function getProcessingTemplateMountingVariantLabel(variantKey, language = "uk") {
  const normalizedKey = String(variantKey || "").trim();

  if (!normalizedKey) {
    return "";
  }

  const label = PROCESSING_TEMPLATE_MOUNTING_VARIANT_LABELS[normalizedKey];
  return pickLocalizedText(label, language) || normalizedKey;
}

export function getProcessingTemplateStatusLabel(template, language = "uk") {
  if (template?.is_active === false) {
    return pickLocalizedText(PROCESSING_TEMPLATE_STATUS_LABELS.inactive, language);
  }

  if (template?.is_active === true) {
    return pickLocalizedText(PROCESSING_TEMPLATE_STATUS_LABELS.active, language);
  }

  return "";
}

export function getProcessingTemplateDefaultLabel(template, language = "uk") {
  if (!template?.is_default) {
    return "";
  }

  return language === "uk" ? "За замовчуванням" : "Default";
}

export function getProcessingFittingDisplayLabel(fitting, language = "uk") {
  if (!fitting) {
    return language === "uk" ? "Фурнітура" : "Fitting";
  }

  const title = String(fitting?.name || fitting?.code || fitting?.article || "").trim() || (language === "uk" ? "Фурнітура" : "Fitting");
  const details = [fitting?.article, fitting?.code].filter(Boolean).join(" · ");

  return details ? `${title} · ${details}` : title;
}

export function getProcessingFittingSearchText(fitting) {
  return [
    fitting?.name,
    fitting?.code,
    fitting?.article,
    fitting?.description,
    fitting?.fitting_type_name,
    fitting?.fitting_group_name,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function getProcessingTemplateCardTitle(template, fitting, language = "uk") {
  const fallback = getProcessingFittingDisplayLabel(fitting, language);
  return String(template?.name || template?.bundle_name || fallback || "").trim() || fallback;
}

export function getProcessingTemplateCardSubtitle(template, fitting, language = "uk") {
  const parts = [];
  const fittingLabel = getProcessingFittingDisplayLabel(fitting, language);
  const variantLabel = getProcessingTemplateMountingVariantLabel(template?.mounting_variant_key, language);
  const typeLabel = getProcessingTemplateTypeLabel(template?.template_type, language);

  if (fittingLabel) {
    parts.push(fittingLabel);
  }

  if (template?.bundle_name) {
    parts.push(template.bundle_name);
  }

  if (variantLabel) {
    parts.push(variantLabel);
  }

  if (typeLabel) {
    parts.push(typeLabel);
  }

  return parts.join(" · ");
}

export function buildProcessingTemplateEditorContext(template, fitting) {
  const templateId = String(template?.id || "").trim();
  const fittingId = String(template?.fitting_id || fitting?.id || "").trim();
  const mountingVariantKey = String(template?.mounting_variant_key || "").trim();
  const bundleKey = String(template?.bundle_key || "").trim();
  const context = {};

  if (templateId) {
    context.templateId = templateId;
  }

  if (fittingId) {
    context.fittingId = fittingId;
  }

  if (mountingVariantKey) {
    context.mountingVariantKey = mountingVariantKey;
  }

  if (bundleKey) {
    context.bundleKey = bundleKey;
  }

  return context;
}

export function buildProcessingTemplatesReturnState({
  selectedFittingId = "",
  selectedTemplateId = "",
  mountingVariantFilter = "all",
  templateStatusFilter = "all",
  fittingSearch = "",
  templateSearch = "",
  scrollPosition = null,
  previewWasOpen = false,
  processingTab = "",
} = {}) {
  const state = {};
  const normalizedSelectedFittingId = String(selectedFittingId || "").trim();
  const normalizedSelectedTemplateId = String(selectedTemplateId || "").trim();
  const normalizedMountingVariantFilter = String(mountingVariantFilter || "").trim();
  const normalizedTemplateStatusFilter = String(templateStatusFilter || "").trim();
  const normalizedFittingSearch = String(fittingSearch || "").trim();
  const normalizedTemplateSearch = String(templateSearch || "").trim();
  const normalizedProcessingTab = String(processingTab || "").trim();
  const normalizedScrollPosition = Number(scrollPosition);

  if (normalizedSelectedFittingId) {
    state.selectedFittingId = normalizedSelectedFittingId;
  }

  if (normalizedSelectedTemplateId) {
    state.selectedTemplateId = normalizedSelectedTemplateId;
  }

  if (normalizedMountingVariantFilter) {
    state.mountingVariantFilter = normalizedMountingVariantFilter;
  }

  if (normalizedTemplateStatusFilter) {
    state.templateStatusFilter = normalizedTemplateStatusFilter;
  }

  if (normalizedFittingSearch) {
    state.fittingSearch = normalizedFittingSearch;
  }

  if (normalizedTemplateSearch) {
    state.templateSearch = normalizedTemplateSearch;
  }

  if (Number.isFinite(normalizedScrollPosition) && normalizedScrollPosition >= 0) {
    state.scrollPosition = normalizedScrollPosition;
  }

  if (Object.keys(state).length || previewWasOpen) {
    state.previewWasOpen = Boolean(previewWasOpen);
  }

  if (normalizedProcessingTab) {
    state.processingTab = normalizedProcessingTab;
  }

  return state;
}

export function saveProcessingTemplatesReturnState(payload = {}) {
  if (typeof window === "undefined" || typeof window.sessionStorage === "undefined") {
    return null;
  }

  const state = buildProcessingTemplatesReturnState(payload);

  if (!Object.keys(state).length) {
    window.sessionStorage.removeItem(PROCESSING_TEMPLATES_RETURN_STATE_STORAGE_KEY);
    return null;
  }

  window.sessionStorage.setItem(PROCESSING_TEMPLATES_RETURN_STATE_STORAGE_KEY, JSON.stringify(state));
  return state;
}

export function readProcessingTemplatesReturnState() {
  if (typeof window === "undefined" || typeof window.sessionStorage === "undefined") {
    return null;
  }

  const rawValue = window.sessionStorage.getItem(PROCESSING_TEMPLATES_RETURN_STATE_STORAGE_KEY);

  if (!rawValue) {
    return null;
  }

  try {
    const parsedValue = JSON.parse(rawValue);
    return buildProcessingTemplatesReturnState(parsedValue);
  } catch {
    return null;
  }
}

export function clearProcessingTemplatesReturnState() {
  if (typeof window === "undefined" || typeof window.sessionStorage === "undefined") {
    return;
  }

  window.sessionStorage.removeItem(PROCESSING_TEMPLATES_RETURN_STATE_STORAGE_KEY);
}

export function getProcessingTemplateTypeLabel(templateType, language = "uk") {
  const normalizedType = String(templateType || "").trim();

  if (!normalizedType) {
    return "";
  }

  const label = PROCESSING_TEMPLATE_TYPE_LABELS[normalizedType];
  return pickLocalizedText(label, language) || normalizedType;
}

export function getProcessingTemplateSearchText(template, fitting) {
  return [
    template?.name,
    template?.bundle_name,
    template?.template_type,
    template?.mounting_variant_key,
    template?.fitting_code,
    template?.fitting_article,
    fitting?.name,
    fitting?.code,
    fitting?.article,
    fitting?.description,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function getProcessingTemplateVariantOptions(templates, language = "uk") {
  const labels = new Map();

  (Array.isArray(templates) ? templates : []).forEach((template) => {
    const key = String(template?.mounting_variant_key || "").trim();
    if (!key || labels.has(key)) {
      return;
    }

    labels.set(key, getProcessingTemplateMountingVariantLabel(key, language));
  });

  return [...labels.entries()].map(([value, label]) => ({ value, label }));
}

export function filterProcessingTemplates(templates, fitting, filters = {}) {
  const normalizedSearch = String(filters.search || "").trim().toLowerCase();
  const normalizedStatus = String(filters.status || "all").trim();
  const normalizedVariantKey = String(filters.mountingVariantKey || "all").trim();

  return (Array.isArray(templates) ? templates : []).filter((template) => {
    if (normalizedStatus === "active" && template?.is_active === false) {
      return false;
    }

    if (normalizedStatus === "inactive" && template?.is_active !== false) {
      return false;
    }

    if (normalizedVariantKey !== "all" && String(template?.mounting_variant_key || "").trim() !== normalizedVariantKey) {
      return false;
    }

    if (!normalizedSearch) {
      return true;
    }

    const searchText = getProcessingTemplateSearchText(template, fitting);
    return searchText.includes(normalizedSearch);
  });
}

export function getProcessingTemplatePreviewCountLabel(count, language = "uk") {
  const numericCount = Number(count || 0);
  return language === "uk" ? `${numericCount} операцій` : `${numericCount} operations`;
}

export function getProcessingTemplateDimensionsLabel(template, language = "uk") {
  const dimensions = [template?.width, template?.height, template?.thickness]
    .map((value) => formatNumber(value))
    .filter(Boolean);

  if (!dimensions.length) {
    return "";
  }

  return language === "uk" ? `${dimensions.join(" × ")} мм` : `${dimensions.join(" × ")} mm`;
}
