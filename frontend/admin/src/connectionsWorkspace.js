const CONNECTIONS_WORKSPACE_TAB_DEFINITIONS = [
  {
    key: "connectionsOverview",
    label: {
      en: "Overview",
      uk: "Огляд",
    },
    description: {
      en: "A compact start page for mounting nodes and the related placeholder pages.",
      uk: "Коротка стартова сторінка для монтажних вузлів і пов'язаних сторінок-заглушок.",
    },
    section: "connections-overview",
  },
  {
    key: "mountingNodes",
    label: {
      en: "Mounting nodes",
      uk: "Монтажні вузли",
    },
    description: {
      en: "The existing stable mounting-node flow stays here.",
      uk: "Тут лишається стабільний існуючий flow монтажних вузлів.",
    },
    section: "mounting-nodes",
    view: "catalogHoles",
  },
  {
    key: "mountingSchemes",
    label: {
      en: "Mounting schemes",
      uk: "Схеми кріплення",
    },
    description: {
      en: "Rules for counts, offsets, and placement of mounting nodes.",
      uk: "Правила кількості, відступів і розстановки монтажних вузлів.",
    },
    section: "mounting-schemes",
  },
  {
    key: "connectionTypes",
    label: {
      en: "Connection types",
      uk: "Типи з'єднань",
    },
    description: {
      en: "A future catalog of furniture connection types.",
      uk: "Майбутній довідник типів з'єднань елементів меблів.",
    },
    section: "connection-types",
  },
  {
    key: "mountingCompatibility",
    label: {
      en: "Compatibility and replacements",
      uk: "Сумісність і заміни",
    },
    description: {
      en: "Allowed replacements and compatibility rules for mounting nodes.",
      uk: "Дозволені заміни та правила сумісності для монтажних вузлів.",
    },
    section: "mounting-compatibility",
  },
  {
    key: "connectionsTesting",
    label: {
      en: "Testing",
      uk: "Тестування",
    },
    description: {
      en: "A small place for future checks and validation flows.",
      uk: "Невелике місце для майбутніх перевірок і валідації.",
    },
    section: "connections-testing",
  },
];

function pickLocalizedText(source, language) {
  return source?.[language] || source?.uk || source?.en || "";
}

export function getConnectionsWorkspaceSidebarTabs({ language = "uk" } = {}) {
  return CONNECTIONS_WORKSPACE_TAB_DEFINITIONS.map((definition) => ({
    key: definition.key,
    label: pickLocalizedText(definition.label, language),
    view: definition.view || definition.key,
  }));
}

export function getConnectionsWorkspaceOverviewCards({ language = "uk" } = {}) {
  return CONNECTIONS_WORKSPACE_TAB_DEFINITIONS.filter((definition) => definition.key !== "connectionsOverview").map(
    (definition) => ({
      key: definition.key,
      label: pickLocalizedText(definition.label, language),
      description: pickLocalizedText(definition.description, language),
      section: definition.section,
      view: definition.view || definition.key,
    }),
  );
}

export function getConnectionsWorkspacePageLabel(viewKey, language = "uk") {
  const tab = CONNECTIONS_WORKSPACE_TAB_DEFINITIONS.find((item) => item.key === viewKey);
  return tab ? pickLocalizedText(tab.label, language) : pickLocalizedText(CONNECTIONS_WORKSPACE_TAB_DEFINITIONS[0].label, language);
}

export function shouldAutoOpenConnectionsMenu(activeView) {
  return activeView === "catalogHoles" || CONNECTIONS_WORKSPACE_TAB_DEFINITIONS.some((definition) => definition.key === activeView);
}

export function resolveActiveConnectionsNavigationKey({ activeView = "" } = {}) {
  if (activeView === "catalogHoles") {
    return "mountingNodes";
  }

  return CONNECTIONS_WORKSPACE_TAB_DEFINITIONS.some((definition) => definition.key === activeView) ? activeView : null;
}
