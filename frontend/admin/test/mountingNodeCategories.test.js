import assert from "node:assert/strict";
import test from "node:test";

import {
  MOUNTING_NODE_CATEGORY_CODES,
  getMountingNodeCategoryLabel,
  getMountingNodeCategoryOptions,
  normalizeMountingNodeCategoryCode,
} from "../src/mountingNodeCategories.js";

test("mounting node categories expose the expected codes and localized labels", () => {
  assert.deepEqual(MOUNTING_NODE_CATEGORY_CODES, [
    "fastening",
    "hinges",
    "drawer_systems",
    "handles_profiles",
    "supports_legs",
    "hangers",
    "sinks_plumbing",
    "appliances",
    "ventilation",
    "electrical",
    "other",
  ]);

  assert.equal(getMountingNodeCategoryLabel("hinges", "uk"), "Завіси");
  assert.equal(getMountingNodeCategoryLabel("hinges", "en"), "Hinges");
  assert.equal(normalizeMountingNodeCategoryCode("  electrical  "), "electrical");
  assert.equal(normalizeMountingNodeCategoryCode("something_invalid"), "");

  assert.deepEqual(getMountingNodeCategoryOptions("uk"), [
    { code: "fastening", label: "Кріплення деталей" },
    { code: "hinges", label: "Завіси" },
    { code: "drawer_systems", label: "Напрямні та висувні системи" },
    { code: "handles_profiles", label: "Ручки та профілі" },
    { code: "supports_legs", label: "Опори та ніжки" },
    { code: "hangers", label: "Підвіси" },
    { code: "sinks_plumbing", label: "Мийки та сантехніка" },
    { code: "appliances", label: "Вбудована техніка" },
    { code: "ventilation", label: "Вентиляція" },
    { code: "electrical", label: "Електрика" },
    { code: "other", label: "Інше" },
  ]);
});
