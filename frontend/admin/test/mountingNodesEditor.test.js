import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingNodeEditorSavePayload,
  canSaveMountingNodeEditor,
} from "../src/mountingNodesEditor.js";

test("mounting node editor payload keeps node fields, items, template id, and stable point ids", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "1",
      templateId: "7428",
      nodeDetail: {
        code: "node-1",
        name: "Node 1",
        description: "Main node",
        is_active: true,
        items: [
          {
            fitting_id: 11,
            quantity: 2,
            role: "primary",
            is_required: true,
            affects_processing: true,
            order_index: 1,
          },
        ],
        templates: [
          {
            template_id: 7428,
            is_default: true,
            order_index: 0,
            template: {
              id: 7428,
              fitting_id: 11,
              name: "Main template",
              template_type: "manual",
              mounting_variant_key: "face_to_edge",
              is_default: true,
              is_active: true,
            },
          },
        ],
      },
    },
    pointsLoaded: true,
    selectedTemplate: {
      id: 7428,
      fitting_id: 11,
      name: "Main template",
      template_type: "manual",
      mounting_variant_key: "face_to_edge",
      is_default: true,
      is_active: true,
    },
    points: [
      { id: 29, template_id: 7428, label: "A", diameter_mm: 7, order_index: 0, quantity: 1 },
      { id: 30, template_id: 7428, label: "B", diameter_mm: 4.5, order_index: 1, quantity: 1 },
    ],
  });

  assert.equal(payload.code, "node-1");
  assert.equal(payload.name, "Node 1");
  assert.equal(payload.description, "Main node");
  assert.equal(payload.is_active, true);
  assert.equal(payload.items.length, 1);
  assert.deepEqual(payload.items[0], {
    fitting_id: 11,
    quantity: 2,
    role: "primary",
    is_required: true,
    affects_processing: true,
    order_index: 1,
  });
  assert.equal(payload.templates.length, 1);
  assert.equal(payload.templates[0].template_id, 7428);
  assert.equal(payload.templates[0].template.template_id, 7428);
  assert.deepEqual(payload.templates[0].template.points.map((point) => point.id), [29, 30]);
});

test("mounting node editor payload keeps points empty when the user deleted every loaded point", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "1",
      templateId: "7428",
      nodeDetail: {
        code: "node-1",
        name: "Node 1",
        description: null,
        is_active: true,
        items: [],
        templates: [
          {
            template_id: 7428,
            is_default: true,
            order_index: 0,
            template: {
              id: 7428,
              fitting_id: 11,
              name: "Main template",
              template_type: "manual",
              mounting_variant_key: "face_to_edge",
              is_default: true,
              is_active: true,
            },
          },
        ],
      },
    },
    pointsLoaded: true,
    selectedTemplate: {
      id: 7428,
      fitting_id: 11,
      name: "Main template",
      template_type: "manual",
      mounting_variant_key: "face_to_edge",
      is_default: true,
      is_active: true,
    },
    points: [],
  });

  assert.deepEqual(payload.templates[0].template.points, []);
});

test("mounting node editor payload is blocked until points are hydrated", () => {
  assert.throws(
    () =>
      buildMountingNodeEditorSavePayload({
        context: {
          mountingNodeId: "1",
          templateId: "7428",
          nodeDetail: {
            code: "node-1",
            name: "Node 1",
            description: null,
            is_active: true,
            items: [],
            templates: [],
          },
        },
        pointsLoaded: false,
        selectedTemplate: { id: 7428 },
        points: [],
      }),
    /Template points are not loaded/,
  );
});

test("mounting node editor save guard requires loaded points and node detail", () => {
  assert.equal(
    canSaveMountingNodeEditor({
      context: {
        mountingNodeId: "1",
        templateId: "7428",
        nodeDetail: {
          items: [],
          templates: [],
        },
      },
      pointsLoaded: true,
      selectedTemplate: { id: 7428 },
      saving: false,
    }),
    true,
  );

  assert.equal(
    canSaveMountingNodeEditor({
      context: {
        mountingNodeId: "1",
        templateId: "7428",
        nodeDetail: {
          items: [],
          templates: [],
        },
      },
      pointsLoaded: false,
      selectedTemplate: { id: 7428 },
      saving: false,
    }),
    false,
  );
});
