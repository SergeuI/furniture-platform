const FEATURE_KEY_PATTERN = /^[a-z0-9._]+$/;

export const ENTITLEMENT_PLAN_CODES = ["trial", "free", "pro", "business"];

export const ENTITLEMENT_PLAN_LABELS = {
  trial: "Trial",
  free: "Free",
  pro: "Pro",
  business: "Business",
};

export const ENTITLEMENT_VALUE_TYPES = ["boolean", "integer", "decimal", "text", "enum"];

export const ENTITLEMENT_CATEGORY_LABELS = {
  uk: {
    fittings: "Фурнітура",
    materials: "Матеріали",
    projects: "Проєкти",
    production: "Виробництво",
    ai: "Штучний інтелект",
    fitting_holes: "Присадка фурнітури",
  },
  en: {
    fittings: "Fittings",
    materials: "Materials",
    projects: "Projects",
    production: "Production",
    ai: "Artificial intelligence",
    fitting_holes: "Fitting holes",
  },
};

export const ENTITLEMENT_VALUE_TYPE_LABELS = {
  boolean: "Так / Ні",
  integer: "Число",
  decimal: "Десяткове число",
  text: "Текст",
  enum: "Варіант зі списку",
};

export const ENTITLEMENT_BOOLEAN_TABLE_HINT =
  "Порожня галочка означає, що функція закрита для тарифу";

export const ENTITLEMENT_TABLE_COLUMNS = [
  "Назва",
  "Технічний ключ",
  "Група",
  "Тип",
  "Trial",
  "Free",
  "Pro",
  "Business",
  "Статус",
  "Дії",
];

export function normalizeEntitlementText(value) {
  return String(value ?? "").trim();
}

export function getEntitlementCategoryLabel(category, language = "uk") {
  const normalized = normalizeEntitlementText(category).toLowerCase();
  const localizedLabels = ENTITLEMENT_CATEGORY_LABELS[language] || ENTITLEMENT_CATEGORY_LABELS.uk;
  return localizedLabels[normalized] || normalizeEntitlementText(category);
}

export function getEntitlementCategoryFilterOptions(features, language = "uk") {
  return getEntitlementCategoryOptions(features).map((value) => ({
    value,
    label: getEntitlementCategoryLabel(value, language),
  }));
}

export function getEntitlementValueTypeLabel(valueType) {
  const normalized = normalizeEntitlementText(valueType).toLowerCase();
  return ENTITLEMENT_VALUE_TYPE_LABELS[normalized] || normalizeEntitlementText(valueType);
}

export function isEntitlementSystemFeature(feature) {
  return Boolean(feature?.is_system);
}

export function getEntitlementFeatureScopeLabel(feature) {
  return isEntitlementSystemFeature(feature) ? "Системне" : "Ручне";
}

export function getEntitlementRegistrySyncPreviewState(preview, options = {}) {
  const summary = preview?.summary || preview || null;
  const newFeatures = Array.isArray(summary?.new_features) ? summary.new_features : [];
  const metadataUpdates = Array.isArray(summary?.metadata_updates) ? summary.metadata_updates : [];
  const missingPlanRows = Array.isArray(summary?.missing_plan_rows) ? summary.missing_plan_rows : [];
  const conflicts = Array.isArray(summary?.conflicts) ? summary.conflicts : [];
  const hasChanges = newFeatures.length > 0 || metadataUpdates.length > 0 || missingPlanRows.length > 0;
  const hasUnsavedChanges = Boolean(options.hasUnsavedChanges);
  const applying = Boolean(options.applying);
  const canApply = Boolean(preview?.can_apply) && !applying && !hasUnsavedChanges && conflicts.length === 0 && hasChanges;

  return {
    hasChanges,
    canApply,
    showApplyButton: hasChanges,
    hasConflicts: conflicts.length > 0,
    newFeaturesCount: newFeatures.length,
    metadataUpdatesCount: metadataUpdates.length,
    missingPlanRowsCount: missingPlanRows.length,
    conflictsCount: conflicts.length,
  };
}

export function applyEntitlementModalScrollLock(documentLike) {
  const body = documentLike?.body;
  if (!body?.style) {
    return () => {};
  }

  const previousOverflow = body.style.overflow ?? "";
  body.style.overflow = "hidden";

  return () => {
    body.style.overflow = previousOverflow;
  };
}

export function parseEntitlementEnumOptions(rawValue) {
  const values = String(rawValue ?? "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  const seen = new Set();
  const normalized = [];

  for (const value of values) {
    if (seen.has(value)) {
      continue;
    }
    seen.add(value);
    normalized.push(value);
  }

  return normalized;
}

export function createEntitlementFeatureDraft(feature = null) {
  return {
    feature_key: normalizeEntitlementText(feature?.feature_key),
    name_uk: normalizeEntitlementText(feature?.name_uk),
    description_uk: normalizeEntitlementText(feature?.description_uk),
    category: normalizeEntitlementText(feature?.category),
    value_type: normalizeEntitlementText(feature?.value_type) || "boolean",
    enum_options_raw: Array.isArray(feature?.enum_options_json)
      ? feature.enum_options_json.join("\n")
      : normalizeEntitlementText(feature?.enum_options_json),
    is_active: feature?.is_active !== false,
    sort_order: String(feature?.sort_order ?? 0),
  };
}

export function validateEntitlementFeatureDraft(draft, originalFeatureKey = "") {
  const errors = {};
  const featureKey = normalizeEntitlementText(draft?.feature_key).toLowerCase();
  const nameUk = normalizeEntitlementText(draft?.name_uk);
  const category = normalizeEntitlementText(draft?.category);
  const valueType = normalizeEntitlementText(draft?.value_type).toLowerCase();

  if (!featureKey) {
    errors.feature_key = "Технічний ключ є обов'язковим";
  } else if (!FEATURE_KEY_PATTERN.test(featureKey)) {
    errors.feature_key = "Технічний ключ може містити лише lowercase letters, digits, dots та underscores";
  }

  if (!nameUk) {
    errors.name_uk = "Назва українською є обов'язковою";
  }

  if (!category) {
    errors.category = "Група є обов'язковою";
  }

  if (!valueType) {
    errors.value_type = "Тип значення є обов'язковим";
  } else if (!ENTITLEMENT_VALUE_TYPES.includes(valueType)) {
    errors.value_type = "Непідтримуваний тип значення";
  }

  if (
    featureKey &&
    originalFeatureKey &&
    featureKey !== normalizeEntitlementText(originalFeatureKey).toLowerCase() &&
    !FEATURE_KEY_PATTERN.test(featureKey)
  ) {
    errors.feature_key = "Технічний ключ може містити лише lowercase letters, digits, dots та underscores";
  }

  if (valueType === "enum") {
    const enumOptions = parseEntitlementEnumOptions(draft?.enum_options_raw);
    if (!enumOptions.length) {
      errors.enum_options_raw = "Для enum потрібен непорожній список варіантів";
    }
  }

  if (valueType && valueType !== "enum" && normalizeEntitlementText(draft?.enum_options_raw)) {
    errors.enum_options_raw = "Варіанти enum надсилаються лише для enum";
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
    normalized: {
      feature_key: featureKey,
      name_uk: nameUk,
      description_uk: normalizeEntitlementText(draft?.description_uk),
      category,
      value_type: valueType,
      enum_options_json:
        valueType === "enum" ? parseEntitlementEnumOptions(draft?.enum_options_raw) : null,
      is_active: draft?.is_active !== false,
      sort_order: Number.isFinite(Number(draft?.sort_order)) ? Number(draft.sort_order) : 0,
    },
  };
}

export function buildEntitlementFeaturePayload(draft) {
  const result = validateEntitlementFeatureDraft(draft);
  if (!result.valid) {
    return {
      valid: false,
      errors: result.errors,
      payload: null,
    };
  }

  const payload = {
    feature_key: result.normalized.feature_key,
    name_uk: result.normalized.name_uk,
    description_uk: result.normalized.description_uk || null,
    category: result.normalized.category,
    value_type: result.normalized.value_type,
    is_active: Boolean(result.normalized.is_active),
    sort_order: Number(result.normalized.sort_order || 0),
  };

  if (result.normalized.value_type === "enum") {
    payload.enum_options_json = result.normalized.enum_options_json;
  }

  return {
    valid: true,
    errors: {},
    payload,
  };
}

export function getEntitlementNavItems(userRole) {
  if (userRole !== "admin") {
    return [];
  }

  return [
    {
      key: "entitlements",
      label: "Тарифи та права",
    },
  ];
}

export function getEntitlementEmptyState(features, filteredFeatures) {
  const featureCount = Array.isArray(features) ? features.length : 0;
  const filteredCount = Array.isArray(filteredFeatures) ? filteredFeatures.length : 0;

  if (!featureCount) {
    return {
      kind: "empty",
      title: "Права ще не створені",
      actionLabel: "Додати ручне право",
    };
  }

  if (!filteredCount) {
    return {
      kind: "filtered-empty",
      title: "Нічого не знайдено",
      actionLabel: "",
    };
  }

  return {
    kind: "ready",
    title: "",
    actionLabel: "",
  };
}

export function sortEntitlementFeatures(features) {
  return [...(Array.isArray(features) ? features : [])].sort((left, right) => {
    const categoryCompare = normalizeEntitlementText(left?.category).localeCompare(
      normalizeEntitlementText(right?.category),
      "uk",
    );
    if (categoryCompare !== 0) {
      return categoryCompare;
    }

    const leftSort = Number(left?.sort_order ?? 0);
    const rightSort = Number(right?.sort_order ?? 0);
    if (leftSort !== rightSort) {
      return leftSort - rightSort;
    }

    return normalizeEntitlementText(left?.feature_key).localeCompare(
      normalizeEntitlementText(right?.feature_key),
      "uk",
    );
  });
}

export function filterEntitlementFeatures(features, filters = {}) {
  const search = normalizeEntitlementText(filters.search).toLowerCase();
  const category = normalizeEntitlementText(filters.category);
  const status = normalizeEntitlementText(filters.status) || "all";

  return sortEntitlementFeatures(features).filter((feature) => {
    if (category && normalizeEntitlementText(feature?.category) !== category) {
      return false;
    }

    if (status === "active" && !feature?.is_active) {
      return false;
    }

    if (status === "inactive" && feature?.is_active) {
      return false;
    }

    if (!search) {
      return true;
    }

    const haystack = [
      feature?.name_uk,
      feature?.feature_key,
      feature?.description_uk,
    ]
      .map((item) => normalizeEntitlementText(item).toLowerCase())
      .join(" ");

    return haystack.includes(search);
  });
}

export function createMatrixCellDraft(featureValueType, apiCell = null) {
  const cell = apiCell || {};
  const valueType = normalizeEntitlementText(featureValueType).toLowerCase();

  return {
    bool_value: valueType === "boolean" ? cell.bool_value ?? null : null,
    integer_value:
      valueType === "integer" && cell.integer_value !== null && cell.integer_value !== undefined
        ? String(cell.integer_value)
        : null,
    decimal_value:
      valueType === "decimal" && cell.decimal_value !== null && cell.decimal_value !== undefined
        ? String(cell.decimal_value)
        : null,
    text_value:
      (valueType === "text" || valueType === "enum") &&
      cell.text_value !== null &&
      cell.text_value !== undefined
        ? String(cell.text_value)
        : null,
    is_unlimited: Boolean(cell.is_unlimited),
    is_not_applicable: Boolean(cell.is_not_applicable),
  };
}

export function buildEntitlementMatrixDraft(features, matrixRows) {
  const draft = {};
  const baseline = {};
  const rowIndex = new Map((Array.isArray(matrixRows) ? matrixRows : []).map((row) => [String(row?.feature?.id ?? row?.feature_id ?? ""), row]));

  for (const feature of Array.isArray(features) ? features : []) {
    const row = rowIndex.get(String(feature?.id ?? "")) || {};

    for (const planCode of ENTITLEMENT_PLAN_CODES) {
      const apiCell = row?.[planCode] || null;
      const cellKey = `${feature.id}:${planCode}`;
      const normalizedCell = createMatrixCellDraft(feature.value_type, apiCell);
      draft[cellKey] = normalizedCell;
      baseline[cellKey] = normalizedCell;
    }
  }

  return {
    draft,
    baseline,
  };
}

export function getEntitlementCellEditorKind(valueType) {
  const normalized = normalizeEntitlementText(valueType).toLowerCase();

  if (normalized === "boolean") {
    return "boolean";
  }

  if (normalized === "integer") {
    return "integer";
  }

  if (normalized === "decimal") {
    return "decimal";
  }

  if (normalized === "enum") {
    return "enum";
  }

  return "text";
}

export function getEntitlementCellLabel(featureValueType, draftCell) {
  const kind = getEntitlementCellEditorKind(featureValueType);

  if (draftCell?.is_not_applicable) {
    return "Не застосовується";
  }

  if (kind === "boolean") {
    if (draftCell?.bool_value === null || draftCell?.bool_value === undefined) {
      return "Закрито";
    }
    return draftCell.bool_value ? "Так" : "Ні";
  }

  if (kind === "integer") {
    if (draftCell?.is_unlimited) {
      return "Без обмежень";
    }
    if (draftCell?.integer_value === null || draftCell?.integer_value === undefined || draftCell.integer_value === "") {
      return "Закрито";
    }
    return String(draftCell.integer_value);
  }

  if (kind === "decimal") {
    if (draftCell?.is_unlimited) {
      return "Без обмежень";
    }
    if (draftCell?.decimal_value === null || draftCell?.decimal_value === undefined || draftCell.decimal_value === "") {
      return "Закрито";
    }
    return String(draftCell.decimal_value);
  }

  if (draftCell?.text_value === null || draftCell?.text_value === undefined || draftCell.text_value === "") {
    return "Закрито";
  }

  return String(draftCell.text_value);
}

export function serializeEntitlementCellDraft(featureValueType, draftCell) {
  const kind = getEntitlementCellEditorKind(featureValueType);
  const cell = draftCell || {};

  if (kind === "boolean") {
    return {
      bool_value: cell.bool_value === null || cell.bool_value === undefined ? null : Boolean(cell.bool_value),
      integer_value: null,
      decimal_value: null,
      text_value: null,
      is_unlimited: false,
      is_not_applicable: Boolean(cell.is_not_applicable),
    };
  }

  if (kind === "integer") {
    if (cell.is_not_applicable) {
      return {
        bool_value: null,
        integer_value: null,
        decimal_value: null,
        text_value: null,
        is_unlimited: false,
        is_not_applicable: true,
      };
    }

    if (cell.is_unlimited) {
      return {
        bool_value: null,
        integer_value: null,
        decimal_value: null,
        text_value: null,
        is_unlimited: true,
        is_not_applicable: false,
      };
    }

    const normalized = normalizeEntitlementText(cell.integer_value);
    return {
      bool_value: null,
      integer_value: normalized ? Number(normalized) : null,
      decimal_value: null,
      text_value: null,
      is_unlimited: false,
      is_not_applicable: false,
    };
  }

  if (kind === "decimal") {
    if (cell.is_not_applicable) {
      return {
        bool_value: null,
        integer_value: null,
        decimal_value: null,
        text_value: null,
        is_unlimited: false,
        is_not_applicable: true,
      };
    }

    if (cell.is_unlimited) {
      return {
        bool_value: null,
        integer_value: null,
        decimal_value: null,
        text_value: null,
        is_unlimited: true,
        is_not_applicable: false,
      };
    }

    const normalized = normalizeEntitlementText(cell.decimal_value);
    return {
      bool_value: null,
      integer_value: null,
      decimal_value: normalized || null,
      text_value: null,
      is_unlimited: false,
      is_not_applicable: false,
    };
  }

  if (kind === "enum" || kind === "text") {
    return {
      bool_value: null,
      integer_value: null,
      decimal_value: null,
      text_value: normalizeEntitlementText(cell.text_value) || null,
      is_unlimited: false,
      is_not_applicable: Boolean(cell.is_not_applicable),
    };
  }

  return {
    bool_value: null,
    integer_value: null,
    decimal_value: null,
    text_value: null,
    is_unlimited: false,
    is_not_applicable: false,
  };
}

export function isEntitlementCellDirty(featureValueType, currentCell, baselineCell) {
  return JSON.stringify(serializeEntitlementCellDraft(featureValueType, currentCell)) !== JSON.stringify(serializeEntitlementCellDraft(featureValueType, baselineCell));
}

export function buildEntitlementMatrixUpdateRows(features, currentDraft, baselineDraft) {
  const rows = [];

  for (const feature of Array.isArray(features) ? features : []) {
    for (const planCode of ENTITLEMENT_PLAN_CODES) {
      const cellKey = `${feature.id}:${planCode}`;
      const currentCell = currentDraft?.[cellKey];
      const baselineCell = baselineDraft?.[cellKey];
      if (!isEntitlementCellDirty(feature.value_type, currentCell, baselineCell)) {
        continue;
      }

      const serializedCell = serializeEntitlementCellDraft(feature.value_type, currentCell);
      rows.push({
        feature_id: Number(feature.id),
        plan_code: planCode,
        ...serializedCell,
      });
    }
  }

  return rows;
}

export function cloneEntitlementMatrixDraft(draft) {
  const clone = {};
  for (const [key, value] of Object.entries(draft || {})) {
    clone[key] = {
      bool_value: value?.bool_value ?? null,
      integer_value: value?.integer_value ?? null,
      decimal_value: value?.decimal_value ?? null,
      text_value: value?.text_value ?? null,
      is_unlimited: Boolean(value?.is_unlimited),
      is_not_applicable: Boolean(value?.is_not_applicable),
    };
  }
  return clone;
}

export function getEntitlementCategoryOptions(features) {
  const categories = new Set();
  for (const feature of Array.isArray(features) ? features : []) {
    const category = normalizeEntitlementText(feature?.category);
    if (category) {
      categories.add(category);
    }
  }
  return [...categories].sort((left, right) => left.localeCompare(right, "uk"));
}
