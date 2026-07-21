import assert from "node:assert/strict";
import test from "node:test";

import {
  applyEntitlementModalScrollLock,
  buildEntitlementFeaturePayload,
  buildEntitlementMatrixDraft,
  buildEntitlementMatrixUpdateRows,
  cloneEntitlementMatrixDraft,
  createEntitlementFeatureDraft,
  createMatrixCellDraft,
  ENTITLEMENT_BOOLEAN_TABLE_HINT,
  ENTITLEMENT_CATEGORY_LABELS,
  ENTITLEMENT_PLAN_CODES,
  ENTITLEMENT_PLAN_LABELS,
  ENTITLEMENT_TABLE_COLUMNS,
  ENTITLEMENT_VALUE_TYPE_LABELS,
  filterEntitlementFeatures,
  getEntitlementCellEditorKind,
  getEntitlementCellLabel,
  getEntitlementCategoryFilterOptions,
  getEntitlementCategoryLabel,
  getEntitlementEmptyState,
  getEntitlementFeatureScopeLabel,
  getEntitlementNavItems,
  getEntitlementRegistrySyncPreviewState,
  getEntitlementValueTypeLabel,
  parseEntitlementEnumOptions,
  serializeEntitlementCellDraft,
  sortEntitlementFeatures,
  validateEntitlementFeatureDraft,
} from "../src/entitlementsMatrix.js";

test("admin nav item is visible only for admins", () => {
  assert.deepEqual(getEntitlementNavItems("admin"), [{ key: "entitlements", label: "Тарифи та права" }]);
  assert.deepEqual(getEntitlementNavItems("free"), []);
});

test("empty state distinguishes empty and filtered-empty matrices", () => {
  assert.deepEqual(getEntitlementEmptyState([], []), {
    kind: "empty",
    title: "Права ще не створені",
    actionLabel: "Додати ручне право",
  });

  assert.deepEqual(getEntitlementEmptyState([{ id: 1 }], []), {
    kind: "filtered-empty",
    title: "Нічого не знайдено",
    actionLabel: "",
  });
});

test("table columns stay in the expected order", () => {
  assert.deepEqual(ENTITLEMENT_TABLE_COLUMNS, [
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
  ]);
});

test("plan codes stay in the expected order", () => {
  assert.deepEqual(ENTITLEMENT_PLAN_CODES, ["trial", "free", "pro", "business"]);
  assert.deepEqual(ENTITLEMENT_PLAN_LABELS, {
    trial: "Trial",
    free: "Free",
    pro: "Pro",
    business: "Business",
  });
});

test("system entitlement labels stay localized", () => {
  assert.deepEqual(ENTITLEMENT_CATEGORY_LABELS, {
    fittings: "Фурнітура",
    materials: "Матеріали",
    projects: "Проєкти",
    production: "Виробництво",
    ai: "Штучний інтелект",
  });
  assert.deepEqual(ENTITLEMENT_VALUE_TYPE_LABELS, {
    boolean: "Так / Ні",
    integer: "Число",
    decimal: "Десяткове число",
    text: "Текст",
    enum: "Варіант зі списку",
  });
  assert.equal(getEntitlementCategoryLabel("materials"), "Матеріали");
  assert.equal(getEntitlementCategoryLabel("custom"), "custom");
  assert.equal(getEntitlementValueTypeLabel("enum"), "Варіант зі списку");
  assert.equal(getEntitlementFeatureScopeLabel({ is_system: true }), "Системне");
  assert.equal(getEntitlementFeatureScopeLabel({ is_system: false }), "Ручне");
});

test("category filter options expose localized labels", () => {
  const options = getEntitlementCategoryFilterOptions([
    { category: "fittings" },
    { category: "ai" },
    { category: "fittings" },
  ]);

  assert.deepEqual(options, [
    { value: "ai", label: "Штучний інтелект" },
    { value: "fittings", label: "Фурнітура" },
  ]);
});

test("boolean table hint stays global and singular", () => {
  assert.equal(
    ENTITLEMENT_BOOLEAN_TABLE_HINT,
    "Порожня галочка означає, що функція закрита для тарифу",
  );
});

test("modal scroll lock restores body overflow on cleanup", () => {
  const documentLike = { body: { style: { overflow: "auto" } } };
  const cleanup = applyEntitlementModalScrollLock(documentLike);
  assert.equal(documentLike.body.style.overflow, "hidden");
  cleanup();
  assert.equal(documentLike.body.style.overflow, "auto");
});

test("registry sync preview state hides apply button for no-op previews", () => {
  const state = getEntitlementRegistrySyncPreviewState(
    {
      can_apply: true,
      summary: {
        new_features: [],
        metadata_updates: [],
        missing_plan_rows: [],
        conflicts: [],
      },
    },
    { applying: false, hasUnsavedChanges: false },
  );

  assert.equal(state.hasChanges, false);
  assert.equal(state.canApply, false);
  assert.equal(state.showApplyButton, false);
});

test("registry sync preview state allows apply only for safe changes", () => {
  const state = getEntitlementRegistrySyncPreviewState(
    {
      can_apply: true,
      summary: {
        new_features: [{ feature_key: "materials.view" }],
        metadata_updates: [],
        missing_plan_rows: [],
        conflicts: [],
      },
    },
    { applying: false, hasUnsavedChanges: false },
  );

  assert.equal(state.hasChanges, true);
  assert.equal(state.canApply, true);
  assert.equal(state.showApplyButton, true);
});

test("feature sorting uses category, sort_order, then feature_key", () => {
  const sorted = sortEntitlementFeatures([
    { feature_key: "zeta", category: "beta", sort_order: 4 },
    { feature_key: "alpha", category: "alpha", sort_order: 2 },
    { feature_key: "omega", category: "alpha", sort_order: 1 },
  ]);

  assert.deepEqual(sorted.map((item) => item.feature_key), ["omega", "alpha", "zeta"]);
});

test("search filters by name, key, and description", () => {
  const features = [
    { feature_key: "ai_scan_limit", name_uk: "Ліміт AI-сканів", description_uk: "Опис", category: "limits", sort_order: 1, is_active: true },
    { feature_key: "support_level", name_uk: "Підтримка", description_uk: "Рівень", category: "support", sort_order: 2, is_active: false },
  ];

  assert.deepEqual(filterEntitlementFeatures(features, { search: "скан" }).map((item) => item.feature_key), ["ai_scan_limit"]);
  assert.deepEqual(filterEntitlementFeatures(features, { search: "support_level" }).map((item) => item.feature_key), ["support_level"]);
  assert.deepEqual(filterEntitlementFeatures(features, { search: "Рівень" }).map((item) => item.feature_key), ["support_level"]);
});

test("category and active filters work together", () => {
  const features = [
    { feature_key: "alpha", name_uk: "Alpha", category: "limits", sort_order: 1, is_active: true },
    { feature_key: "beta", name_uk: "Beta", category: "limits", sort_order: 2, is_active: false },
    { feature_key: "gamma", name_uk: "Gamma", category: "support", sort_order: 1, is_active: true },
  ];

  assert.deepEqual(filterEntitlementFeatures(features, { category: "limits", status: "active" }).map((item) => item.feature_key), ["alpha"]);
  assert.deepEqual(filterEntitlementFeatures(features, { status: "inactive" }).map((item) => item.feature_key), ["beta"]);
});

test("boolean cells use checkbox semantics", () => {
  assert.equal(getEntitlementCellEditorKind("boolean"), "boolean");
  assert.equal(getEntitlementCellLabel("boolean", { bool_value: null }), "Закрито");
  assert.equal(getEntitlementCellLabel("boolean", { bool_value: true }), "Так");
});

test("integer cells expose unlimited and not applicable states", () => {
  assert.equal(getEntitlementCellEditorKind("integer"), "integer");
  assert.equal(getEntitlementCellLabel("integer", { integer_value: null, is_unlimited: true }), "Без обмежень");
  assert.equal(getEntitlementCellLabel("integer", { integer_value: null, is_not_applicable: true }), "Не застосовується");
});

test("decimal cells preserve exact precision", () => {
  const cell = createMatrixCellDraft("decimal", { decimal_value: "167.95" });
  const serialized = serializeEntitlementCellDraft("decimal", cell);
  assert.equal(serialized.decimal_value, "167.95");
});

test("text cells expose text input semantics", () => {
  assert.equal(getEntitlementCellEditorKind("text"), "text");
  assert.equal(getEntitlementCellLabel("text", { text_value: null }), "Закрито");
});

test("enum cells expose select semantics", () => {
  assert.equal(getEntitlementCellEditorKind("enum"), "enum");
  assert.equal(getEntitlementCellLabel("enum", { text_value: "business" }), "business");
});

test("blank or not-applicable values serialize as closed access", () => {
  assert.deepEqual(serializeEntitlementCellDraft("text", { text_value: "", is_not_applicable: true }), {
    bool_value: null,
    integer_value: null,
    decimal_value: null,
    text_value: null,
    is_unlimited: false,
    is_not_applicable: true,
  });
});

test("matrix draft initializes all four plan columns", () => {
  const features = [
    { id: 11, feature_key: "alpha", name_uk: "Alpha", category: "limits", value_type: "integer", sort_order: 1, is_active: true },
  ];
  const matrix = buildEntitlementMatrixDraft(features, []);
  assert.deepEqual(Object.keys(matrix.draft).sort(), ["11:business", "11:free", "11:pro", "11:trial"]);
  assert.deepEqual(cloneEntitlementMatrixDraft(matrix.draft), matrix.draft);
});

test("matrix updates include only changed rows", () => {
  const features = [
    { id: 11, feature_key: "alpha", name_uk: "Alpha", category: "limits", value_type: "integer", sort_order: 1, is_active: true },
  ];
  const matrix = buildEntitlementMatrixDraft(features, []);
  const current = cloneEntitlementMatrixDraft(matrix.draft);
  current["11:trial"] = {
    ...current["11:trial"],
    integer_value: "25",
  };
  assert.deepEqual(buildEntitlementMatrixUpdateRows(features, current, matrix.baseline), [
    {
      feature_id: 11,
      plan_code: "trial",
      bool_value: null,
      integer_value: 25,
      decimal_value: null,
      text_value: null,
      is_unlimited: false,
      is_not_applicable: false,
    },
  ]);
});

test("system features remain editable in the matrix", () => {
  const features = [
    { id: 21, feature_key: "materials.view", name_uk: "Матеріали", category: "materials", value_type: "boolean", sort_order: 1, is_active: true, is_system: true },
  ];
  const matrix = buildEntitlementMatrixDraft(features, []);
  const current = cloneEntitlementMatrixDraft(matrix.draft);
  current["21:trial"] = {
    ...current["21:trial"],
    bool_value: true,
  };

  assert.deepEqual(buildEntitlementMatrixUpdateRows(features, current, matrix.baseline), [
    {
      feature_id: 21,
      plan_code: "trial",
      bool_value: true,
      integer_value: null,
      decimal_value: null,
      text_value: null,
      is_unlimited: false,
      is_not_applicable: false,
    },
  ]);
});

test("feature draft validation accepts a valid enum feature", () => {
  const result = validateEntitlementFeatureDraft({
    feature_key: "ai_scan_limit",
    name_uk: "Ліміт AI-сканів",
    description_uk: "Опис",
    category: "limits",
    value_type: "enum",
    enum_options_raw: "small\nmedium\nlarge",
    is_active: true,
    sort_order: "7",
  });

  assert.equal(result.valid, true);
  assert.deepEqual(result.normalized.enum_options_json, ["small", "medium", "large"]);
});

test("feature_key validation rejects uppercase and spaces", () => {
  const result = validateEntitlementFeatureDraft({
    feature_key: "Bad Key",
    name_uk: "Назва",
    category: "limits",
    value_type: "boolean",
  });

  assert.equal(result.valid, false);
  assert.match(result.errors.feature_key, /lowercase letters/);
});

test("enum options validation rejects duplicates and empty lists", () => {
  assert.deepEqual(parseEntitlementEnumOptions("basic\npro\nbasic"), ["basic", "pro"]);

  const result = validateEntitlementFeatureDraft({
    feature_key: "plan_tier",
    name_uk: "Рівень",
    category: "limits",
    value_type: "enum",
    enum_options_raw: "\n\n",
  });

  assert.equal(result.valid, false);
  assert.match(result.errors.enum_options_raw, /непорожній/);
});

test("non-enum features must not send enum options", () => {
  const result = buildEntitlementFeaturePayload({
    feature_key: "material_limit",
    name_uk: "Ліміт матеріалів",
    category: "limits",
    value_type: "integer",
    enum_options_raw: "small\nlarge",
  });

  assert.equal(result.valid, false);
  assert.match(result.errors.enum_options_raw, /лише для enum/);
});

test("feature draft preserves readonly key for edit payload preparation", () => {
  const draft = createEntitlementFeatureDraft({
    feature_key: "ai_scan_limit",
    name_uk: "Ліміт AI-сканів",
    category: "limits",
    value_type: "integer",
  });

  assert.equal(draft.feature_key, "ai_scan_limit");
});
