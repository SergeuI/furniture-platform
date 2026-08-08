import assert from "node:assert/strict";
import test from "node:test";

import {
  MOUNTING_NODE_CREATE_ROLE_OPTIONS,
  MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY,
  clearMountingNodeCreateDraft,
  addMountingNodeCreateDraftItem,
  addMountingNodeCreateDraftPoint,
  createMountingNodeCreateDraft,
  createMountingNodeCreateDraftItemFromFitting,
  createMountingNodeCreateDraftPointFromFitting,
  loadMountingNodeCreateDraft,
  commitMountingNodeCreateDraftPoint,
  isMountingNodeCreateDraftReady,
  prepareMountingNodeCreateDraftPointForm,
  removeMountingNodeCreateDraftItem,
  removeMountingNodeCreateDraftPoint,
  saveMountingNodeCreateDraft,
  updateMountingNodeCreateDraftItem,
  updateMountingNodeCreateDraftPoint,
  validateMountingNodeCreateDraft,
} from "../src/mountingNodesCreateDraft.js";

function withSessionStorageMock(run) {
  const originalWindow = globalThis.window;
  const storageMap = new Map();

  globalThis.window = {
    sessionStorage: {
      getItem(key) {
        return storageMap.has(key) ? storageMap.get(key) : null;
      },
      setItem(key, value) {
        storageMap.set(key, String(value));
      },
      removeItem(key) {
        storageMap.delete(key);
      },
    },
  };

  try {
    return run(storageMap);
  } finally {
    globalThis.window = originalWindow;
  }
}

test("mounting node create draft keeps item and point state local", () => {
  const draft = createMountingNodeCreateDraft({
    name: "mn_confirmat_7x50",
    mounting_variant_key: "surface_mount",
    category_code: "hinges",
    is_dirty: true,
  });

  assert.deepEqual(draft.items, []);
  assert.deepEqual(draft.points, []);
  assert.equal(draft.category_code, "hinges");
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

test("mounting node create draft point form stays local until confirmed", () => {
  const draft = createMountingNodeCreateDraft({
    name: "mn_confirmat_7x50",
    mounting_variant_key: "face_to_edge",
    is_dirty: true,
    items: [
      {
        fitting_id: "11",
        article: "ART-11",
        name: "Confirmat",
        image_url: "",
        quantity: 1,
        role: MOUNTING_NODE_CREATE_ROLE_OPTIONS[0],
        is_required: true,
        affects_processing: true,
      },
    ],
    points: [],
  });

  const fitting = {
    id: 11,
    article: "ART-11",
    name: "Confirmat",
    code: "CNF-11",
  };

  const pointForm = prepareMountingNodeCreateDraftPointForm(draft, fitting, {
    label: "P1",
    x_mm: 24,
    y_mm: -8,
    z_mm: 12,
  });

  assert.equal(draft.points.length, 0);
  assert.equal(pointForm.id, null);
  assert.equal(pointForm.client_key.startsWith("mounting-node-create-"), true);
  assert.equal(pointForm.fitting_id, "11");

  const committedDraft = commitMountingNodeCreateDraftPoint(draft, pointForm);

  assert.equal(committedDraft.points.length, 1);
  assert.equal(committedDraft.points[0].id, null);
  assert.equal(committedDraft.points[0].client_key, pointForm.client_key);
  assert.equal(committedDraft.points[0].x_mm, 24);
  assert.equal(committedDraft.points[0].y_mm, -8);
  assert.equal(committedDraft.points[0].z_mm, 12);

  const surfaceMountDraft = createMountingNodeCreateDraft({
    mounting_variant_key: "surface_mount",
    points: [],
  });
  const surfaceMountPointForm = prepareMountingNodeCreateDraftPointForm(surfaceMountDraft, fitting);

  assert.equal(surfaceMountPointForm.panel_key, "vertical_panel");
  assert.equal(surfaceMountPointForm.target_panel, "vertical_panel");
  assert.equal(surfaceMountPointForm.target_surface, "plane");
  assert.equal(surfaceMountPointForm.target_side, "inner_face");
  assert.equal(surfaceMountPointForm.side, "front");

  const angledDraft = createMountingNodeCreateDraft({
    mounting_variant_key: "angled_two_planes",
    points: [],
  });
  const angledPointForm = prepareMountingNodeCreateDraftPointForm(angledDraft, fitting, {
    panel_key: "horizontal_panel",
  });

  assert.equal(angledPointForm.panel_key, "horizontal_panel");
  assert.equal(angledPointForm.target_panel, "horizontal_panel");
  assert.equal(angledPointForm.target_surface, "plane");
  assert.equal(angledPointForm.target_side, "inner_face");
  assert.equal(angledPointForm.side, "inner_face");
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

test("mounting node create draft persists and restores session draft fields", () => {
  withSessionStorageMock((storageMap) => {
    clearMountingNodeCreateDraft();

    const draft = createMountingNodeCreateDraft({
      name: "Draft node",
      description: "Keep me",
      category_code: "ventilation",
      is_active: false,
      ownership_type: "system",
      mounting_variant_key: "face_to_edge",
      template_name: "Face template",
      is_dirty: true,
      items: [
        {
          fitting_id: "11",
          article: "ART-11",
          name: "Confirmat",
          image_url: "",
          quantity: 2,
          role: MOUNTING_NODE_CREATE_ROLE_OPTIONS[1],
          is_required: false,
          affects_processing: false,
        },
      ],
      points: [
        {
          client_key: "mounting-node-create-custom",
          id: 116,
          fitting_id: "11",
          label: "P1",
          panel_key: "vertical_panel",
          target_panel: "vertical_panel",
          target_surface: "plane",
          target_side: "inner_face",
          side: "front",
          x_mm: 10,
          y_mm: -5,
          z_mm: 2,
          diameter_mm: 8,
          depth_mm: 12,
          operation: "drill",
          order_index: 0,
          quantity: 1,
          mirrored: false,
          is_through: false,
          notes: "note",
        },
      ],
    });

    saveMountingNodeCreateDraft(draft);

    assert.equal(storageMap.has(MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY), true);

    const restored = loadMountingNodeCreateDraft();
    assert.equal(restored.name, "Draft node");
    assert.equal(restored.description, "Keep me");
    assert.equal(restored.category_code, "ventilation");
    assert.equal(restored.is_active, false);
    assert.equal(restored.ownership_type, "system");
    assert.equal(restored.mounting_variant_key, "face_to_edge");
    assert.equal(restored.template_name, "Face template");
    assert.equal(restored.is_dirty, true);
    assert.equal(restored.items.length, 1);
    assert.equal(restored.items[0].fitting_id, "11");
    assert.equal(restored.items[0].quantity, 2);
    assert.equal(restored.items[0].role, MOUNTING_NODE_CREATE_ROLE_OPTIONS[1]);
    assert.equal(restored.items[0].is_required, false);
    assert.equal(restored.items[0].affects_processing, false);
    assert.equal(restored.points.length, 1);
    assert.equal(restored.points[0].client_key, "mounting-node-create-custom");
    assert.equal(restored.points[0].id, 116);
    assert.equal(restored.points[0].notes, "note");

    clearMountingNodeCreateDraft();
    assert.equal(storageMap.has(MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY), false);
  });
});

test("mounting node create draft ignores malformed storage payloads", () => {
  withSessionStorageMock((storageMap) => {
    storageMap.set(MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY, "{");

    const restored = loadMountingNodeCreateDraft();

    assert.equal(restored.name, "");
    assert.equal(restored.mounting_variant_key, "");
    assert.equal(storageMap.has(MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY), false);
  });
});

test("mounting node create draft ignores unsupported storage versions", () => {
  withSessionStorageMock((storageMap) => {
    storageMap.set(
      MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY,
      JSON.stringify({
        version: 99,
        draft: {
          name: "Legacy",
          mounting_variant_key: "surface_mount",
        },
      }),
    );

    const restored = loadMountingNodeCreateDraft();

    assert.equal(restored.name, "");
    assert.equal(restored.mounting_variant_key, "");
    assert.equal(storageMap.has(MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY), true);
  });
});

test("mounting node create draft normalizes null entries out of stored arrays", () => {
  withSessionStorageMock((storageMap) => {
    const storedDraft = createMountingNodeCreateDraft({
      name: "Safe draft",
      items: [null, undefined],
      points: [null],
    });

    saveMountingNodeCreateDraft(storedDraft);
    storageMap.set(
      MOUNTING_NODE_CREATE_DRAFT_STORAGE_KEY,
      JSON.stringify({
        version: 1,
        draft: {
          ...storedDraft,
          items: [null, storedDraft.items[0] || null],
          points: [null],
        },
      }),
    );

    const restored = loadMountingNodeCreateDraft();

    assert.equal(Array.isArray(restored.items), true);
    assert.equal(restored.items.length, 0);
    assert.equal(Array.isArray(restored.points), true);
    assert.equal(restored.points.length, 0);
  });
});
