const PROCESSING_TAB_DEFINITIONS = [
  {
    key: "overview",
    label: {
      en: "Overview",
      uk: "Огляд",
    },
    status: {
      en: "Working",
      uk: "Працює",
    },
    visibleTo: "admin",
  },
  {
    key: "operations",
    label: {
      en: "Processing operations",
      uk: "Операції обробки",
    },
    status: {
      en: "Working",
      uk: "Працює",
    },
    visibleTo: "admin",
  },
  {
    key: "templates",
    label: {
      en: "Processing templates",
      uk: "Шаблони обробки",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    visibleTo: "admin",
  },
  {
    key: "fitting-holes",
    label: {
      en: "Fitting holes",
      uk: "Присадка фурнітури",
    },
    status: {
      en: "Working",
      uk: "Працює",
    },
    visibleTo: "fitting-holes",
  },
  {
    key: "services-prices",
    label: {
      en: "Services & prices",
      uk: "Послуги та ціни",
    },
    status: {
      en: "Needs setup",
      uk: "Потребує налаштування",
    },
    visibleTo: "admin",
  },
  {
    key: "pricing-rules",
    label: {
      en: "Pricing rules",
      uk: "Правила розрахунку",
    },
    status: {
      en: "Needs setup",
      uk: "Потребує налаштування",
    },
    visibleTo: "admin",
  },
  {
    key: "testing",
    label: {
      en: "Testing",
      uk: "Тестування",
    },
    status: {
      en: "Working",
      uk: "Працює",
    },
    visibleTo: "admin",
  },
];

const PROCESSING_OVERVIEW_CARDS = [
  {
    key: "holes",
    label: {
      en: "Holes",
      uk: "Отвори",
    },
    status: {
      en: "Working",
      uk: "Працює",
    },
    description: {
      en: "The current fitting holes editor remains the active implementation.",
      uk: "Чинна присадка фурнітури залишається робочою реалізацією.",
    },
  },
  {
    key: "operations-preview",
    label: {
      en: "Operation preview",
      uk: "Попередній перегляд операцій",
    },
    status: {
      en: "Working",
      uk: "Працює",
    },
    description: {
      en: "Read-only preview of the current processing operation registry.",
      uk: "Лише для читання: перегляд поточного реєстру операцій обробки.",
    },
  },
  {
    key: "grooves",
    label: {
      en: "Grooves",
      uk: "Пази",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Grooves will reuse the same workspace and pricing layer later.",
      uk: "Пази згодом використовуватимуть той самий workspace і шар цін.",
    },
  },
  {
    key: "pockets",
    label: {
      en: "Pockets",
      uk: "Вибірки",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Pocket operations are reserved for the next iteration.",
      uk: "Операції вибірок зарезервовані для наступної ітерації.",
    },
  },
  {
    key: "cuts",
    label: {
      en: "Cutouts",
      uk: "Вирізи",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Rectangular and contour cutouts will be wired later.",
      uk: "Прямокутні та контурні вирізи підключимо пізніше.",
    },
  },
  {
    key: "radii",
    label: {
      en: "Radii",
      uk: "Радіуси",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Edge radii are a future processing type.",
      uk: "Радіуси крайок та отворів входять у наступні етапи.",
    },
  },
  {
    key: "milling",
    label: {
      en: "Milling",
      uk: "Фрезерування",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Milling will attach to future templates and service rules.",
      uk: "Фрезерування під'єднається до майбутніх шаблонів і правил.",
    },
  },
  {
    key: "estimate",
    label: {
      en: "Estimate impact",
      uk: "Кошторис операцій",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Operation pricing will be surfaced here later.",
      uk: "Тут згодом відобразиться розрахунок операцій.",
    },
  },
  {
    key: "cutting-impact",
    label: {
      en: "Cutting impact",
      uk: "Вплив на порізку",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Cutting, contour, and edge-banding side effects will be tracked here.",
      uk: "Тут відстежуватимемо вплив на порізку, контур і крайкування.",
    },
  },
  {
    key: "company-prices",
    label: {
      en: "Company prices",
      uk: "Ціни компаній",
    },
    status: {
      en: "Planned",
      uk: "Заплановано",
    },
    description: {
      en: "Own company markups and manual services are planned next.",
      uk: "Власні націнки компаній і ручні послуги будуть підключені пізніше.",
    },
  },
];

function pickLocalizedText(source, language) {
  if (!source) {
    return "";
  }

  return source[language] || source.uk || source.en || "";
}

function canSeeTab(definition, isAdmin, canUseFittingHoles) {
  if (definition.visibleTo === "admin") {
    return isAdmin;
  }

  if (definition.visibleTo === "fitting-holes") {
    return isAdmin || canUseFittingHoles;
  }

  return true;
}

export const PROCESSING_WORKSPACE_STORAGE_KEY = "furniture_admin_processing_tab";

export function getProcessingWorkspaceTabs({
  language = "uk",
  isAdmin = false,
  canUseFittingHoles = false,
} = {}) {
  return PROCESSING_TAB_DEFINITIONS
    .filter((definition) => canSeeTab(definition, isAdmin, canUseFittingHoles))
    .map((definition) => ({
      key: definition.key,
      label: pickLocalizedText(definition.label, language),
      status: pickLocalizedText(definition.status, language),
    }));
}

export function getProcessingWorkspaceSidebarTabs({
  language = "uk",
  isAdmin = false,
  canUseFittingHoles = false,
} = {}) {
  return getProcessingWorkspaceTabs({
    language,
    isAdmin,
    canUseFittingHoles,
  }).map(({ key, label }) => ({
    key,
    label,
  }));
}

export function getProcessingWorkspaceTabTargetView(tabKey) {
  return tabKey === "fitting-holes" ? "catalogHoles" : "processing";
}

export function shouldAutoOpenCatalogMenu(activeView) {
  return [
    "catalogHub",
    "catalogMaterials",
    "catalogFittings",
    "catalogFasteners",
    "catalogBundles",
    "catalogServiceRules",
    "catalogDrillingRules",
    "catalogValues",
    "catalogViyar",
    "catalogManual",
  ].includes(String(activeView || ""));
}

export function resolveActiveProcessingNavigationKey({
  activeView = "",
  activeProcessingTab = "overview",
  canUseFittingHoles = false,
  isAdmin = false,
} = {}) {
  if (activeView === "catalogHoles") {
    return "fitting-holes";
  }

  if (activeView !== "processing") {
    return null;
  }

  const normalizedTab = normalizeProcessingWorkspaceTab(activeProcessingTab, {
    canUseFittingHoles,
    isAdmin,
  });

  return normalizedTab === "fitting-holes" ? "overview" : normalizedTab;
}

export function normalizeProcessingWorkspaceTab(
  tabKey,
  {
    isAdmin = false,
    canUseFittingHoles = false,
  } = {},
) {
  const visibleTabs = getProcessingWorkspaceTabs({
    canUseFittingHoles,
    isAdmin,
  });
  const normalizedKey = String(tabKey || "").trim();

  if (visibleTabs.some((tab) => tab.key === normalizedKey)) {
    return normalizedKey;
  }

  return visibleTabs[0]?.key || "overview";
}

export function getProcessingOverviewCards(language = "uk") {
  return PROCESSING_OVERVIEW_CARDS.map((card) => ({
    key: card.key,
    label: pickLocalizedText(card.label, language),
    status: pickLocalizedText(card.status, language),
    description: pickLocalizedText(card.description, language),
  }));
}

export function getProcessingTabLabel(tabKey, language = "uk") {
  const tab = PROCESSING_TAB_DEFINITIONS.find((item) => item.key === tabKey);
  return pickLocalizedText(tab?.label, language) || tabKey;
}

export function getProcessingTabStatus(tabKey, language = "uk") {
  const tab = PROCESSING_TAB_DEFINITIONS.find((item) => item.key === tabKey);
  return pickLocalizedText(tab?.status, language) || (language === "uk" ? "Потребує налаштування" : "Needs setup");
}
