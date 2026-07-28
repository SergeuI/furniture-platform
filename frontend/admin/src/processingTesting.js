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

function formatMm(value) {
  const formatted = formatNumber(value);
  return formatted ? `${formatted} мм` : "";
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

export function formatPartDimensions(part, language = "uk") {
  const dimensions = [part?.width, part?.height, part?.thickness]
    .map((value) => formatNumber(value))
    .filter(Boolean);

  if (!dimensions.length) {
    return language === "uk" ? "Не визначено" : "Not set";
  }

  return `${dimensions.join(" × ")} мм`;
}

export function formatOperationTitle(operation, index = 1, language = "uk") {
  const typeLabel = getProcessingTestingOperationTypeLabel(operation?.operation_type, language);
  const safeIndex = Number(index) > 0 ? Number(index) : 1;

  return `${typeLabel || (language === "uk" ? "Операція" : "Operation")} ${safeIndex}`;
}

export function formatOperationCoordinates(operation, language = "uk") {
  const placement = operation?.placement || {};
  const labels = [
    ["x_mm", "X"],
    ["y_mm", "Y"],
    ["z_mm", "Z"],
  ];

  const values = labels
    .map(([key, label]) => {
      const formatted = formatMm(placement[key]);
      return formatted ? `${label} ${formatted}` : "";
    })
    .filter(Boolean);

  if (!values.length) {
    return language === "uk" ? "Не визначено" : "Not set";
  }

  return values.join(", ");
}

export function getOperationEstimateStatus(operation, language = "uk") {
  if (operation?.production_effects?.include_in_estimate === false) {
    return language === "uk" ? "Не включено до кошторису" : "Not included in estimate";
  }

  if (operation?.production_effects?.include_in_estimate === true) {
    return language === "uk" ? "Включено до кошторису" : "Included in estimate";
  }

  return "";
}

export function getOperationServiceStatus(operation, language = "uk") {
  if (operation?.service_mapping?.found === false) {
    return language === "uk" ? "Послугу ще не прив’язано" : "Service not linked yet";
  }

  if (operation?.service_mapping?.found === true) {
    return language === "uk" ? "Послугу прив’язано" : "Service linked";
  }

  return "";
}

export function getVisibleOperationFields(operation, language = "uk") {
  const fields = [];
  const type = String(operation?.operation_type || "").trim();
  const placement = operation?.placement || {};
  const geometry = operation?.geometry || {};

  const addField = (label, value) => {
    if (value === null || value === undefined || value === "") {
      return;
    }

    fields.push({ label, value: String(value) });
  };

  const addMmField = (label, value) => {
    const formatted = formatMm(value);
    if (formatted) {
      fields.push({ label, value: formatted });
    }
  };

  const coordinates = formatOperationCoordinates(operation, language);
  if (coordinates !== (language === "uk" ? "Не визначено" : "Not set")) {
    addField(language === "uk" ? "Координати" : "Coordinates", coordinates);
  }

  if (type === "hole") {
    addMmField(language === "uk" ? "Діаметр" : "Diameter", geometry.diameter_mm);
    addMmField(language === "uk" ? "Глибина" : "Depth", geometry.depth_mm);

    if (geometry.is_through !== null && geometry.is_through !== undefined) {
      addField(language === "uk" ? "Сквозний" : "Through", geometry.is_through ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No"));
    }

    addField(language === "uk" ? "Кількість" : "Quantity", operation.quantity);

    if (operation.mirrored) {
      addField(language === "uk" ? "Дзеркальне розташування" : "Mirrored", language === "uk" ? "Так" : "Yes");
    }
  } else if (type === "groove") {
    addMmField(language === "uk" ? "Довжина" : "Length", geometry.length_mm);
    addMmField(language === "uk" ? "Ширина" : "Width", geometry.width_mm);
    addMmField(language === "uk" ? "Глибина" : "Depth", geometry.depth_mm);
    addField(language === "uk" ? "Напрямок" : "Direction", geometry.direction);
    addField(language === "uk" ? "Кількість" : "Quantity", operation.quantity);
  } else if (type === "quarter") {
    addMmField(language === "uk" ? "Ширина" : "Width", geometry.width_mm);
    addMmField(language === "uk" ? "Глибина" : "Depth", geometry.depth_mm);
    addField(language === "uk" ? "Край" : "Edge", geometry.edge);
    addField(language === "uk" ? "Кількість" : "Quantity", operation.quantity);
  } else {
    addField(language === "uk" ? "Кількість" : "Quantity", operation.quantity);
  }

  if (placement.target_panel) {
    addField(language === "uk" ? "Панель" : "Panel", placement.target_panel);
  }

  if (placement.target_surface) {
    addField(language === "uk" ? "Поверхня" : "Surface", placement.target_surface);
  }

  if (placement.target_side) {
    addField(language === "uk" ? "Сторона" : "Side", placement.target_side);
  }

  return fields;
}
