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
    uk: "Operations preview",
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

export const PROCESSING_OPERATION_TYPE_CAPABILITY_KEYS = Object.keys(
  OPERATION_TYPE_CAPABILITY_LABELS,
);

function pickLocalizedText(source, language) {
  return source?.[language] || source?.uk || source?.en || "";
}

export function getProcessingOperationTypeStatusLabel(status, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_STATUS_LABELS[status], language) || String(status || "");
}

export function getProcessingOperationTypeCapabilityLabel(capabilityKey, language = "uk") {
  return pickLocalizedText(OPERATION_TYPE_CAPABILITY_LABELS[capabilityKey], language) || String(capabilityKey || "");
}

export function getProcessingOperationTypeCapabilityStateLabel(active, language = "uk") {
  if (active) {
    return language === "uk" ? "Так" : "Yes";
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
