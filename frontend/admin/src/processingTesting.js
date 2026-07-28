const PROCESSING_TESTING_MODES = [
  {
    value: "template",
    label: {
      en: "Fitting template",
      uk: "Шаблон присадки",
    },
  },
  {
    value: "project",
    label: {
      en: "Project part",
      uk: "Деталь проєкту",
    },
  },
];

const PROCESSING_OPERATION_TYPE_LABELS = {
  hole: {
    en: "Hole",
    uk: "Отвір",
  },
  groove: {
    en: "Groove",
    uk: "Паз",
  },
  quarter: {
    en: "Quarter",
    uk: "Чверть",
  },
};

function pickLocalizedText(source, language) {
  if (!source) {
    return "";
  }

  return source[language] || source.uk || source.en || "";
}

export function getProcessingTestingModeOptions(language = "uk") {
  return PROCESSING_TESTING_MODES.map((option) => ({
    value: option.value,
    label: pickLocalizedText(option.label, language),
  }));
}

export function getProcessingTestingOperationTypeLabel(operationType, language = "uk") {
  return pickLocalizedText(PROCESSING_OPERATION_TYPE_LABELS[operationType], language) || String(operationType || "");
}
