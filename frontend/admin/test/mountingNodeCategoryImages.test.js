import assert from "node:assert/strict";
import test from "node:test";

import { getMountingNodeCategoryImageUrl } from "../src/mountingNodeCategories.js";

const EXPECTED_IMAGE_CODES = [
  ["fastening", "fastening.png"],
  ["hinges", "hinges.png"],
  ["drawer_systems", "drawer_systems.png"],
  ["handles_profiles", "handles_profiles.png"],
  ["supports_legs", "supports_legs.png"],
  ["hangers", "hangers.png"],
  ["sinks_plumbing", "sinks_plumbing.png"],
  ["appliances", "appliances.png"],
  ["ventilation", "ventilation.png"],
  ["electrical", "electrical.png"],
  ["other", "other.png"],
  ["uncategorized", "uncategorized.png"],
];

test("mounting node category images map to the expected assets", () => {
  for (const [categoryCode, fileName] of EXPECTED_IMAGE_CODES) {
    assert.equal(getMountingNodeCategoryImageUrl(categoryCode).endsWith(`/assets/mounting-node-categories/${fileName}`), true);
  }

  assert.equal(getMountingNodeCategoryImageUrl("something_invalid"), "");
});
