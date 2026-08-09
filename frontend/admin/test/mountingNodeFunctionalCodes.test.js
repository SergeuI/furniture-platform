import assert from "node:assert/strict";
import test from "node:test";

import {
  MOUNTING_NODE_FUNCTIONAL_CODES,
  getMountingNodeFunctionalLabel,
  getMountingNodeFunctionalOptions,
  normalizeMountingNodeFunctionalCode,
} from "../src/mountingNodeFunctionalCodes.js";

test("mounting node functional registry exposes stable codes and labels", () => {
  assert.deepEqual(MOUNTING_NODE_FUNCTIONAL_CODES, [
    "connector",
    "door_hinge",
    "drawer_slide",
    "furniture_handle",
    "profile_handle",
    "cabinet_leg",
    "wall_hanger",
    "sink",
    "cooktop",
    "ventilation_grille",
    "electrical_socket",
  ]);
  assert.equal(normalizeMountingNodeFunctionalCode(" door_hinge "), "door_hinge");
  assert.equal(getMountingNodeFunctionalLabel("door_hinge", "uk"), "Меблева завіса");
  assert.equal(getMountingNodeFunctionalLabel("door_hinge", "en"), "Door hinge");
  assert.equal(getMountingNodeFunctionalLabel("invalid", "uk"), "");
  assert.deepEqual(getMountingNodeFunctionalOptions("uk")[0], {
    code: "connector",
    label: "Кріплення деталей",
  });
});
