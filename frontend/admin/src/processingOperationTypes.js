const OPERATION_TYPE_STATUS_LABELS = {
  available: {
    en: "Working",
    uk: "Працює",
  },
  planned: {
    en: "Planned",
    uk: "Заплановано",
  },
  needs_configuration: {
    en: "Needs setup",
    uk: "Потребує налаштування",
  },
};

const OPERATION_TYPE_CAPABILITY_LABELS = {
  template_editor: {
    en: "Template editor",
    uk: "Редактор шаблону",
  },
  operations_preview: {
    en: "Operations preview",
    uk: "Перегляд операцій",
  },
  preview_3d: {
    en: "3D preview",
    uk: "3D-перегляд",
  },
  service_mapping: {
    en: "Service mapping",
    uk: "Прив’язка послуги",
  },
  estimate_export: {
    en: "Estimate export",
    uk: "Передавання в кошторис",
  },
  cutting_effect: {
    en: "Cutting effect",
    uk: "Вплив на порізку",
  },
};

const OPERATION_TYPE_CATEGORY_LABELS = {
  drilling: {
    en: "Drilling",
    uk: "Свердління",
  },
  routing: {
    en: "Routing",
    uk: "Фрезерування",
  },
  contour: {
    en: "Contour processing",
    uk: "Контурна обробка",
  },
  manual: {
    en: "Manual operation",
    uk: "Ручна операція",
  },
};

const OPERATION_TYPE_GEOMETRY_KIND_LABELS = {
  cylinder: {
    en: "Cylinder",
    uk: "Циліндр",
  },
  linear_slot: {
    en: "Linear slot",
    uk: "Лінійний паз",
  },
  rectangular_pocket: {
    en: "Rectangular pocket",
    uk: "Прямокутна вибірка",
  },
  rectangular_cutout: {
    en: "Rectangular cutout",
    uk: "Прямокутний виріз",
  },
  contour: {
    en: "Contour",
    uk: "Контур",
  },
  corner_radius: {
    en: "Corner radius",
    uk: "Радіус кута",
  },
  toolpath: {
    en: "Toolpath",
    uk: "Траєкторія інструмента",
  },
  manual: {
    en: "Manual",
    uk: "Ручна операція",
  },
};

const OPERATION_TYPE_PRICING_UNIT_LABELS = {
  piece: {
    en: "Per piece",
    uk: "За штуку",
  },
  linear_meter: {
    en: "Per linear meter",
    uk: "За погонний метр",
  },
  square_meter: {
    en: "Per square meter",
    uk: "За квадратний метр",
  },
  contour_meter: {
    en: "Per contour meter",
    uk: "За метр контуру",
  },
  fixed: {
    en: "Fixed price",
    uk: "Фіксована ціна",
  },
  minute: {
    en: "Per minute",
    uk: "За хвилину",
  },
};

const OPERATION_TYPE_FIELD_LABELS = {
  x_mm: { en: "X", uk: "X" },
  y_mm: { en: "Y", uk: "Y" },
  z_mm: { en: "Z", uk: "Z" },
  diameter_mm: { en: "Diameter", uk: "Діаметр" },
  depth_mm: { en: "Depth", uk: "Глибина" },
  length_mm: { en: "Length", uk: "Довжина" },
  width_mm: { en: "Width", uk: "Ширина" },
  height_mm: { en: "Height", uk: "Висота" },
  radius_mm: { en: "Radius", uk: "Радіус" },
  corner_radius_mm: { en: "Corner radius", uk: "Радіус кута" },
  quantity: { en: "Quantity", uk: "Кількість" },
  target_panel: { en: "Target panel", uk: "Деталь" },
  target_surface: { en: "Target surface", uk: "Поверхня" },
  target_side: { en: "Target side", uk: "Сторона" },
  is_through: { en: "Through operation", uk: "Наскрізна операція" },
  direction: { en: "Direction", uk: "Напрямок" },
  edge: { en: "Edge", uk: "Край" },
  toolpath: { en: "Toolpath", uk: "Траєкторія" },
  manual_price: { en: "Manual price", uk: "Ручна ціна" },
};

export const PROCESSING_OPERATION_TYPE_CAPABILITY_KEYS = Object.keys(OPERATION_TYPE_CAPABILITY_LABELS);

function pickLocalizedText(source, language) {
  return source?.[language] || source?.uk || source?.en || "";
}

export function getProcessingOperationTypeStatusLabel(status, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_STATUS_LABELS[status], language) || String(status || "");
}

export function getProcessingOperationTypeCapabilityLabel(capabilityKey, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_CAPABILITY_LABELS[capabilityKey], language) || String(capabilityKey || "");
}

export function getProcessingOperationTypeCategoryLabel(category, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_CATEGORY_LABELS[category], language) || String(category || "");
}

export function getProcessingOperationTypeGeometryKindLabel(kind, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_GEOMETRY_KIND_LABELS[kind], language) || String(kind || "");
}

export function getProcessingOperationTypePricingUnitLabel(unit, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_PRICING_UNIT_LABELS[unit], language) || String(unit || "");
}

export function getProcessingOperationTypeFieldLabel(fieldKey, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_FIELD_LABELS[fieldKey], language) || String(fieldKey || "");
}

export function getProcessingOperationTypeCapabilityStateLabel(active, language = "uk") {
  if (active) {
    return language === "uk" ? "Підтримується" : "Supported";
  }

  return language === "uk" ? "Ще не підтримується" : "Not supported yet";
}

export function buildProcessingOperationTypeViewModel(item, language = "uk") {
  const requiredFields = Array.isArray(item?.required_fields) ? item.required_fields : [];
  const optionalFields = Array.isArray(item?.optional_fields) ? item.optional_fields : [];
  const pricingUnits = Array.isArray(item?.pricing_units) ? item.pricing_units : [];
  const capabilities = item?.capabilities || {};

  return {
    ...item,
    required_fields: requiredFields,
    optional_fields: optionalFields,
    pricing_units: pricingUnits,
    category_label: getProcessingOperationTypeCategoryLabel(item?.category, language),
    geometry_kind_label: getProcessingOperationTypeGeometryKindLabel(item?.geometry_kind, language),
    required_field_labels: requiredFields.map((fieldKey) => getProcessingOperationTypeFieldLabel(fieldKey, language)),
    optional_field_labels: optionalFields.map((fieldKey) => getProcessingOperationTypeFieldLabel(fieldKey, language)),
    pricing_unit_labels: pricingUnits.map((unit) => getProcessingOperationTypePricingUnitLabel(unit, language)),
    status_label: getProcessingOperationTypeStatusLabel(item?.status, language),
    capability_items: PROCESSING_OPERATION_TYPE_CAPABILITY_KEYS.map((capabilityKey) => {
      const active = Boolean(capabilities[capabilityKey]);

      return {
        key: capabilityKey,
        label: getProcessingOperationTypeCapabilityLabel(capabilityKey, language),
        active,
        state_label: getProcessingOperationTypeCapabilityStateLabel(active, language),
      };
    }),
  };
}

export function buildProcessingOperationTypeViewModels(items = [], language = "uk") {
  return items.map((item) => buildProcessingOperationTypeViewModel(item, language));
}
