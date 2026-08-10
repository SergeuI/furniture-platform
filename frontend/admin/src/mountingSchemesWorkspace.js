const MOUNTING_SCHEMES_SECTION = "mounting-schemes";

export const MOUNTING_SCHEMES_ROUTE_MODES = ["list", "create", "detail", "edit"];

export function normalizeText(value) {
  return String(value ?? "").trim();
}

export function normalizeInteger(value, fallback = null) {
  if (value === "" || value === null || value === undefined) {
    return fallback;
  }

  const parsed = Number(value);
  return Number.isInteger(parsed) ? parsed : fallback;
}

export function normalizeMountingSchemesRoute(route = {}) {
  const mode = MOUNTING_SCHEMES_ROUTE_MODES.includes(normalizeText(route.mode)) ? normalizeText(route.mode) : "list";
  const schemeId = normalizeText(route.schemeId || route.scheme_id);

  if (mode === "list" || mode === "create") {
    return {
      mode,
      schemeId: "",
    };
  }

  return {
    mode,
    schemeId,
  };
}

export function parseMountingSchemesRoute(search = "") {
  const params = new URLSearchParams(String(search || "").replace(/^[?#]/, ""));

  if (normalizeText(params.get("section")) !== MOUNTING_SCHEMES_SECTION) {
    return null;
  }

  return normalizeMountingSchemesRoute({
    mode: params.get("mode"),
    schemeId: params.get("scheme"),
  });
}

export function buildMountingSchemesRouteUrl(route = {}, currentSearch = "", currentHash = "") {
  const params = new URLSearchParams(String(currentSearch || "").replace(/^[?#]/, ""));
  const normalizedRoute = normalizeMountingSchemesRoute(route);

  params.set("section", MOUNTING_SCHEMES_SECTION);
  params.set("mode", normalizedRoute.mode);

  if (normalizedRoute.mode === "detail" || normalizedRoute.mode === "edit") {
    if (normalizedRoute.schemeId) {
      params.set("scheme", normalizedRoute.schemeId);
    } else {
      params.delete("scheme");
    }
  } else {
    params.delete("scheme");
  }

  const queryString = params.toString();
  return `${queryString ? `?${queryString}` : ""}${currentHash || ""}`;
}

export function buildMountingSchemeNodeDraft(node = {}, index = 0) {
  return {
    id: normalizeText(node.id || node.scheme_node_id || `draft-${index}`),
    node_id: normalizeInteger(node.node_id, null),
    group_key: normalizeText(node.group_key || "primary"),
    quantity_per_group: normalizeInteger(node.quantity_per_group, 1) || 1,
    role_code: normalizeText(node.role_code),
    order_index: normalizeInteger(node.order_index, index) ?? index,
    is_required: node.is_required !== false,
    node_code: normalizeText(node.node_code || node.code),
    node_name: normalizeText(node.node_name || node.name),
    category_code: normalizeText(node.category_code || node.category || ""),
    functional_code: normalizeText(node.functional_code || node.functional || ""),
  };
}

export function buildMountingSchemePlacementRuleDraft(rule = {}, index = 0) {
  return {
    id: normalizeText(rule.id || rule.scheme_placement_rule_id || `rule-${index}`),
    group_key: normalizeText(rule.group_key || "primary"),
    distribution_mode: normalizeText(rule.distribution_mode || "equal") || "equal",
    min_group_count: normalizeInteger(rule.min_group_count, 1) || 1,
    max_group_count: rule.max_group_count === null || rule.max_group_count === undefined || rule.max_group_count === ""
      ? ""
      : normalizeInteger(rule.max_group_count, ""),
    fixed_group_count: rule.fixed_group_count === null || rule.fixed_group_count === undefined || rule.fixed_group_count === ""
      ? ""
      : normalizeInteger(rule.fixed_group_count, ""),
    start_offset_mm: rule.start_offset_mm === null || rule.start_offset_mm === undefined || rule.start_offset_mm === ""
      ? ""
      : normalizeInteger(rule.start_offset_mm, ""),
    end_offset_mm: rule.end_offset_mm === null || rule.end_offset_mm === undefined || rule.end_offset_mm === ""
      ? ""
      : normalizeInteger(rule.end_offset_mm, ""),
    max_spacing_mm: rule.max_spacing_mm === null || rule.max_spacing_mm === undefined || rule.max_spacing_mm === ""
      ? ""
      : normalizeInteger(rule.max_spacing_mm, ""),
    fixed_spacing_mm: rule.fixed_spacing_mm === null || rule.fixed_spacing_mm === undefined || rule.fixed_spacing_mm === ""
      ? ""
      : normalizeInteger(rule.fixed_spacing_mm, ""),
  };
}

export function createEmptyMountingSchemeDraft() {
  return {
    code: "",
    name: "",
    description: "",
    is_active: true,
    nodes: [],
    placement_rules: [],
  };
}

export function collectDistinctGroupKeys(nodes = []) {
  const keys = new Set();
  for (const node of Array.isArray(nodes) ? nodes : []) {
    const groupKey = normalizeText(node?.group_key);
    if (groupKey) {
      keys.add(groupKey);
    }
  }
  return Array.from(keys).sort((left, right) => left.localeCompare(right, "en"));
}

export function syncPlacementRulesWithGroupKeys(rules = [], groupKeys = []) {
  const existingByGroup = new Map();

  for (const rule of Array.isArray(rules) ? rules : []) {
    const groupKey = normalizeText(rule?.group_key);
    if (groupKey && !existingByGroup.has(groupKey)) {
      existingByGroup.set(groupKey, buildMountingSchemePlacementRuleDraft(rule, existingByGroup.size));
    }
  }

  return groupKeys.map((groupKey, index) =>
    existingByGroup.get(groupKey) || buildMountingSchemePlacementRuleDraft({ group_key: groupKey }, index),
  );
}

export function buildMountingSchemeDraftFromScheme(scheme = {}) {
  const nodes = Array.isArray(scheme.nodes)
    ? scheme.nodes.map((node, index) => buildMountingSchemeNodeDraft(node, index))
    : [];
  const placementRules = Array.isArray(scheme.placement_rules)
    ? scheme.placement_rules.map((rule, index) => buildMountingSchemePlacementRuleDraft(rule, index))
    : [];

  return {
    code: normalizeText(scheme.code),
    name: normalizeText(scheme.name),
    description: normalizeText(scheme.description),
    is_active: scheme.is_active !== false,
    nodes,
    placement_rules: syncPlacementRulesWithGroupKeys(placementRules, collectDistinctGroupKeys(nodes)),
  };
}

export function validateMountingSchemeDraft(draft = {}) {
  const errors = [];
  const normalizedName = normalizeText(draft.name);
  const nodes = Array.isArray(draft.nodes) ? draft.nodes : [];
  const placementRules = Array.isArray(draft.placement_rules) ? draft.placement_rules : [];

  if (!normalizedName) {
    errors.push("Name is required");
  }

  if (!nodes.length) {
    errors.push("Add at least one mounting node");
  }

  nodes.forEach((node, index) => {
    const rowLabel = `Node ${index + 1}`;
    if (normalizeInteger(node.node_id, null) === null) {
      errors.push(`${rowLabel}: node is required`);
    }
    if (!normalizeText(node.group_key)) {
      errors.push(`${rowLabel}: group key is required`);
    }
    if ((normalizeInteger(node.quantity_per_group, 0) || 0) <= 0) {
      errors.push(`${rowLabel}: quantity per group must be greater than 0`);
    }
  });

  const allowedGroupKeys = new Set(collectDistinctGroupKeys(nodes));

  placementRules.forEach((rule, index) => {
    const rowLabel = `Placement rule ${index + 1}`;
    const groupKey = normalizeText(rule.group_key);

    if (!groupKey) {
      errors.push(`${rowLabel}: group key is required`);
    } else if (!allowedGroupKeys.has(groupKey)) {
      errors.push(`${rowLabel}: group key must match one of the selected nodes`);
    }

    if (!["equal", "fixed_spacing", "centered"].includes(normalizeText(rule.distribution_mode))) {
      errors.push(`${rowLabel}: distribution mode is invalid`);
    }

    if ((normalizeInteger(rule.min_group_count, 0) || 0) <= 0) {
      errors.push(`${rowLabel}: minimum group count must be greater than 0`);
    }

    const maxGroupCount = rule.max_group_count === "" ? null : normalizeInteger(rule.max_group_count, null);
    const fixedGroupCount = rule.fixed_group_count === "" ? null : normalizeInteger(rule.fixed_group_count, null);
    const startOffset = rule.start_offset_mm === "" ? null : normalizeInteger(rule.start_offset_mm, null);
    const endOffset = rule.end_offset_mm === "" ? null : normalizeInteger(rule.end_offset_mm, null);
    const maxSpacing = rule.max_spacing_mm === "" ? null : normalizeInteger(rule.max_spacing_mm, null);
    const fixedSpacing = rule.fixed_spacing_mm === "" ? null : normalizeInteger(rule.fixed_spacing_mm, null);

    if (maxGroupCount !== null && maxGroupCount < (normalizeInteger(rule.min_group_count, 0) || 0)) {
      errors.push(`${rowLabel}: maximum group count must be greater than or equal to minimum`);
    }

    if (fixedGroupCount !== null && fixedGroupCount <= 0) {
      errors.push(`${rowLabel}: fixed group count must be greater than 0`);
    }

    if (startOffset !== null && startOffset < 0) {
      errors.push(`${rowLabel}: start offset cannot be negative`);
    }

    if (endOffset !== null && endOffset < 0) {
      errors.push(`${rowLabel}: end offset cannot be negative`);
    }

    if (maxSpacing !== null && maxSpacing <= 0) {
      errors.push(`${rowLabel}: maximum spacing must be greater than 0`);
    }

    if (fixedSpacing !== null && fixedSpacing <= 0) {
      errors.push(`${rowLabel}: fixed spacing must be greater than 0`);
    }

    if (fixedGroupCount !== null && fixedGroupCount !== (normalizeInteger(rule.min_group_count, 0) || 0)) {
      errors.push(`${rowLabel}: fixed group count must match minimum group count`);
    }

    if (fixedGroupCount !== null && maxGroupCount !== null && fixedGroupCount !== maxGroupCount) {
      errors.push(`${rowLabel}: fixed group count must match maximum group count`);
    }
  });

  return errors;
}

const MOUNTING_SCHEMES_VALIDATION_MESSAGES_UK = {
  "Name is required": "Вкажіть назву схеми.",
  "Add at least one mounting node": "Додайте хоча б один монтажний вузол.",
  "node is required": "виберіть монтажний вузол",
  "group key is required": "вкажіть ключ групи",
  "quantity per group must be greater than 0": "кількість у групі має бути більшою за 0",
  "group key must match one of the selected nodes": "ключ групи має збігатися з одним із вибраних вузлів",
  "distribution mode is invalid": "вкажіть допустимий режим розподілу",
  "minimum group count must be greater than 0": "мінімальна кількість груп має бути більшою за 0",
  "maximum group count must be greater than or equal to minimum": "максимальна кількість груп має бути більшою або дорівнювати мінімальній",
  "fixed group count must be greater than 0": "фіксована кількість груп має бути більшою за 0",
  "start offset cannot be negative": "початкове зміщення не може бути від'ємним",
  "end offset cannot be negative": "кінцеве зміщення не може бути від'ємним",
  "maximum spacing must be greater than 0": "максимальний інтервал має бути більшим за 0",
  "fixed spacing must be greater than 0": "фіксований інтервал має бути більшим за 0",
  "fixed group count must match minimum group count": "фіксована кількість груп має збігатися з мінімальною кількістю груп",
  "fixed group count must match maximum group count": "фіксована кількість груп має збігатися з максимальною кількістю груп",
};

export function localizeMountingSchemeValidationMessage(message = "", language = "uk") {
  const normalizedMessage = normalizeText(message);

  if (!normalizedMessage || language !== "uk") {
    return normalizedMessage;
  }

  if (Object.prototype.hasOwnProperty.call(MOUNTING_SCHEMES_VALIDATION_MESSAGES_UK, normalizedMessage)) {
    return MOUNTING_SCHEMES_VALIDATION_MESSAGES_UK[normalizedMessage];
  }

  const prefixMatch = normalizedMessage.match(/^(Node|Placement rule) (\d+): (.+)$/);
  if (!prefixMatch) {
    return normalizedMessage;
  }

  const [, label, index, detail] = prefixMatch;
  const translatedDetail = MOUNTING_SCHEMES_VALIDATION_MESSAGES_UK[detail] || detail;

  if (label === "Node") {
    return `Вузол ${index}: ${translatedDetail}`;
  }

  return `Правило розміщення ${index}: ${translatedDetail}`;
}

export function getMountingSchemeValidationMessage(draft = {}, { language = "uk", visible = false } = {}) {
  if (!visible) {
    return "";
  }

  const errors = validateMountingSchemeDraft(draft);
  const firstError = errors[0] || "";
  return localizeMountingSchemeValidationMessage(firstError, language);
}

function normalizeDraftRuleValue(value) {
  return value === "" || value === null || value === undefined ? null : value;
}

export function buildMountingSchemePayload(draft = {}) {
  const payload = {
    code: normalizeText(draft.code) || undefined,
    name: normalizeText(draft.name),
    description: normalizeText(draft.description) || undefined,
    is_active: draft.is_active !== false,
    nodes: (Array.isArray(draft.nodes) ? draft.nodes : []).map((node, index) => ({
      node_id: normalizeInteger(node.node_id, null),
      group_key: normalizeText(node.group_key),
      quantity_per_group: normalizeInteger(node.quantity_per_group, 1) || 1,
      role_code: normalizeText(node.role_code) || undefined,
      order_index: normalizeInteger(node.order_index, index) ?? index,
      is_required: node.is_required !== false,
    })),
    placement_rules: (Array.isArray(draft.placement_rules) ? draft.placement_rules : []).map((rule) => ({
      group_key: normalizeText(rule.group_key),
      distribution_mode: normalizeText(rule.distribution_mode) || "equal",
      min_group_count: normalizeInteger(rule.min_group_count, 1) || 1,
      max_group_count: normalizeDraftRuleValue(rule.max_group_count) === null
        ? undefined
        : normalizeInteger(rule.max_group_count, null),
      fixed_group_count: normalizeDraftRuleValue(rule.fixed_group_count) === null
        ? undefined
        : normalizeInteger(rule.fixed_group_count, null),
      start_offset_mm: normalizeDraftRuleValue(rule.start_offset_mm) === null
        ? undefined
        : normalizeInteger(rule.start_offset_mm, null),
      end_offset_mm: normalizeDraftRuleValue(rule.end_offset_mm) === null
        ? undefined
        : normalizeInteger(rule.end_offset_mm, null),
      max_spacing_mm: normalizeDraftRuleValue(rule.max_spacing_mm) === null
        ? undefined
        : normalizeInteger(rule.max_spacing_mm, null),
      fixed_spacing_mm: normalizeDraftRuleValue(rule.fixed_spacing_mm) === null
        ? undefined
        : normalizeInteger(rule.fixed_spacing_mm, null),
    })),
  };

  return payload;
}
