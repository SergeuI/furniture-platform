import assert from "node:assert/strict";
import test from "node:test";

import {
  MOUNTING_NODE_CREATE_ROLE_OPTIONS,
  addMountingNodeCreateDraftItem,
  addMountingNodeCreateDraftPoint,
  createMountingNodeCreateDraft,
  createMountingNodeCreateDraftItemFromFitting,
  createMountingNodeCreateDraftPointFromFitting,
  isMountingNodeCreateDraftReady,
  removeMountingNodeCreateDraftItem,
  removeMountingNodeCreateDraftPoint,
  updateMountingNodeCreateDraftItem,
  updateMountingNodeCreateDraftPoint,
  validateMountingNodeCreateDraft,
} from "../src/mountingNodesCreateDraft.js";

test("mounting node create draft keeps item and point state local", () => {
  const draft = createMountingNodeCreateDraft({
    name: "mn_confirmat_7x50",
    mounting_variant_key: "surface_mount",
    is_dirty: true,
  });

  assert.deepEqual(draft.items, []);
  assert.deepEqual(draft.points, []);
  assert.equal(draft.template_name, "Основний шаблон");
  assert.equal(isMountingNodeCreateDraftReady(draft), false);

  const fitting = {
    id: 11,
    article: "ART-11",
    name: "Confirmat",
    code: "CNF-11",
  };

  const draftItem = createMountingNodeCreateDraftItemFromFitting(fitting);
  assert.deepEqual(draftItem, {
    fitting_id: "11",
    article: "ART-11",
    name: "Confirmat",
    image_url: "",
    quantity: 1,
    role: MOUNTING_NODE_CREATE_ROLE_OPTIONS[0],
    is_required: true,
    affects_processing: true,
  });

  const addedItem = addMountingNodeCreateDraftItem(draft, fitting);
  assert.equal(addedItem.duplicate, false);
  assert.equal(addedItem.draft.items.length, 1);
  assert.equal(addedItem.draft.items[0].role, MOUNTING_NODE_CREATE_ROLE_OPTIONS[0]);

  const secondItem = addMountingNodeCreateDraftItem(addedItem.draft, {
    id: 12,
    article: "ART-12",
    name: "Minifix",
    code: "CNF-12",
  });
  assert.equal(secondItem.duplicate, false);
  assert.equal(secondItem.draft.items.length, 2);
  assert.equal(secondItem.draft.items[1].role, MOUNTING_NODE_CREATE_ROLE_OPTIONS[1]);

  const duplicateItem = addMountingNodeCreateDraftItem(addedItem.draft, fitting);
  assert.equal(duplicateItem.duplicate, true);
  assert.equal(duplicateItem.draft.items.length, 1);

  const updatedItem = updateMountingNodeCreateDraftItem(addedItem.draft, "11", {
    quantity: 3,
    role: MOUNTING_NODE_CREATE_ROLE_OPTIONS[1],
    is_required: false,
    affects_processing: false,
  });
  assert.equal(updatedItem.items[0].quantity, 3);
  assert.equal(updatedItem.items[0].role, MOUNTING_NODE_CREATE_ROLE_OPTIONS[1]);
  assert.equal(updatedItem.items[0].is_required, false);
  assert.equal(updatedItem.items[0].affects_processing, false);

  const point = createMountingNodeCreateDraftPointFromFitting(fitting, {
    label: "P1",
    x_mm: 18,
    y_mm: -12,
    z_mm: 4,
    diameter_mm: 8,
    depth_mm: 12,
  });
  assert.equal(point.id, null);
  assert.equal(point.fitting_id, "11");
  assert.equal(point.client_key.startsWith("mounting-node-create-"), true);

  const withPoint = {
    ...updatedItem,
    points: [point],
  };
  const secondPoint = createMountingNodeCreateDraftPointFromFitting(fitting, {
    label: "P2",
    x_mm: 42,
    y_mm: 8,
    z_mm: 10,
    diameter_mm: 8,
    depth_mm: "",
  });
  const withSecondPoint = {
    ...withPoint,
    points: [...withPoint.points, secondPoint],
  };
  assert.equal(withSecondPoint.points.length, 2);
  assert.notEqual(withSecondPoint.points[0].client_key, withSecondPoint.points[1].client_key);

  const addedPoint = addMountingNodeCreateDraftPoint(updatedItem, fitting, {
    label: "P3",
    x_mm: 10,
    y_mm: 12,
    z_mm: 14,
  });
  assert.equal(addedPoint.points.length, 1);
  assert.equal(addedPoint.points[0].id, null);

  const updatedPoint = updateMountingNodeCreateDraftPoint(
    {
      ...addedPoint,
      points: [point],
    },
    point.client_key,
    {
      label: "P1a",
      x_mm: 20,
      is_through: true,
      depth_mm: "",
    },
  );
  assert.equal(updatedPoint.points[0].label, "P1a");
  assert.equal(updatedPoint.points[0].x_mm, 20);
  assert.equal(updatedPoint.points[0].is_through, true);

  const removedPointDraft = removeMountingNodeCreateDraftPoint(updatedPoint, point.client_key);
  assert.equal(removedPointDraft.points.length, 0);

  const removedItemDraft = removeMountingNodeCreateDraftItem(withSecondPoint, "11");
  assert.equal(removedItemDraft.items.length, 0);
  assert.equal(removedItemDraft.points.length, 0);
});

test("mounting node create draft validation blocks missing name, variant and duplicate fittings", () => {
  const draft = createMountingNodeCreateDraft({
    name: "",
    mounting_variant_key: "",
    is_dirty: true,
    items: [
      {
        fitting_id: "11",
        article: "ART-11",
        name: "Confirmat",
        quantity: 0,
        role: "",
        is_required: true,
        affects_processing: true,
      },
      {
        fitting_id: "11",
        article: "ART-11",
        name: "Confirmat",
        quantity: 1,
        role: MOUNTING_NODE_CREATE_ROLE_OPTIONS[0],
        is_required: true,
        affects_processing: true,
      },
    ],
    points: [
      {
        client_key: "",
        fitting_id: "11",
      },
    ],
  });

  const errors = validateMountingNodeCreateDraft(draft);

  assert.equal(errors.some((error) => error.field === "name"), true);
  assert.equal(errors.some((error) => error.field === "mounting_variant_key"), true);
  assert.equal(errors.some((error) => error.message.includes("лише один раз")), true);
  assert.equal(draft.points[0].client_key.startsWith("mounting-node-create-"), true);
  assert.equal(errors.some((error) => error.field === "points"), false);
});
