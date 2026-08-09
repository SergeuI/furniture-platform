import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingNodeEditorSavePayload,
  canSaveMountingNodeEditor,
  resolveMountingNodeEditorContext,
} from "../src/mountingNodesEditor.js";

const fixturePoints = [
  {
    id: 29,
    template_id: 7480,
    label: "Through",
    diameter_mm: 7,
    order_index: 0,
    quantity: 1,
  },
  {
    id: 30,
    template_id: 7480,
    label: "Blind",
    diameter_mm: 4.5,
    depth_mm: 34,
    order_index: 1,
    quantity: 1,
  },
];

const fixtureNodeDetail = {
  id: 9,
  code: "mounting-node-node-9039f657",
  name: "петля",
  description: null,
  category_code: "hinges",
  is_active: true,
  items: [
    {
      id: 13,
      node_id: 9,
      fitting_id: 42,
      quantity: 1,
      role: "Основний елемент",
      is_required: true,
      affects_processing: true,
      order_index: 0,
    },
    {
      id: 14,
      node_id: 9,
      fitting_id: 52,
      quantity: 4,
      role: "Основний елемент",
      is_required: true,
      affects_processing: true,
      order_index: 1,
    },
  ],
  templates: [
    {
      id: 13,
      node_id: 9,
      template_id: 7480,
      template_name: "Основний шаблон",
      fitting_id: 42,
      fitting_code: null,
      fitting_article: "23913",
      mounting_variant_key: "surface_mount",
      is_default: true,
      order_index: 0,
      points_count: 2,
      is_active: true,
      template: {
        id: 7480,
        fitting_id: 42,
        name: "Основний шаблон",
        bundle_key: null,
        bundle_name: null,
        bundle_order_index: 0,
        template_type: "manual",
        side: null,
        coordinate_system: "2d",
        mounting_variant_key: "surface_mount",
        is_default: true,
        notes: null,
        is_active: true,
        points: fixturePoints,
      },
    },
  ],
};

const fixtureContext = {
  mountingNodeId: "9",
  nodeDetail: fixtureNodeDetail,
  templateId: "7480",
};

const nestedLinkNodeDetail = {
  ...fixtureNodeDetail,
  templates: [
    {
      ...fixtureNodeDetail.templates[0],
      mounting_variant_key: "angled_two_planes",
      template: {
        ...fixtureNodeDetail.templates[0].template,
        mounting_variant_key: "angled_two_planes",
        points: fixturePoints,
      },
    },
  ],
};

const flatLegacyNodeDetail = {
  id: 11,
  code: "legacy-node",
  name: "Legacy node",
  description: null,
  is_active: true,
  items: [
    {
      id: 21,
      node_id: 11,
      fitting_id: 77,
      quantity: 1,
      role: "primary",
      is_required: true,
      affects_processing: true,
      order_index: 0,
    },
  ],
  templates: [
    {
      id: 8800,
      fitting_id: 77,
      name: "Legacy template",
      template_id: 8800,
      mounting_variant_key: "drawer_slides",
      points: fixturePoints,
    },
  ],
};

test("mounting node editor payload keeps node fields, items, template id, and stable point ids", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "1",
      templateId: "7428",
      nodeDetail: {
        code: "node-1",
        name: "Node 1",
        description: "Main node",
        category_code: "hinges",
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
  assert.equal(payload.category_code, "hinges");
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

test("mounting node editor payload keeps null category_code empty instead of auto-filling a fallback", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "1",
      templateId: "7428",
      nodeDetail: {
        code: "node-1",
        name: "Node 1",
        category_code: null,
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

  assert.equal(payload.category_code, undefined);
});

test("mounting node editor payload prefers the explicit editor category code over a stale node snapshot", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "1",
      templateId: "7428",
      category_code: "hinges",
      nodeDetail: {
        code: "node-1",
        name: "Node 1",
        category_code: null,
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

  assert.equal(payload.category_code, "hinges");
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

test("resolveMountingNodeEditorContext prefers the real template id for nested links", () => {
  const context = resolveMountingNodeEditorContext(nestedLinkNodeDetail, "fallback-node");

  assert.equal(context.mountingNodeId, "9");
  assert.equal(context.nodeName, "петля");
  assert.equal(context.fittingId, "42");
  assert.equal(context.templateId, "7480");
  assert.equal(context.mountingVariantKey, "angled_two_planes");
  assert.deepEqual(context.points.map((point) => point.id), [29, 30]);
});

test("resolveMountingNodeEditorContext accepts legacy flat template objects", () => {
  const context = resolveMountingNodeEditorContext(flatLegacyNodeDetail);

  assert.equal(context.mountingNodeId, "11");
  assert.equal(context.fittingId, "77");
  assert.equal(context.templateId, "8800");
  assert.equal(context.mountingVariantKey, "drawer_slides");
  assert.deepEqual(context.points.map((point) => point.id), [29, 30]);
});

test("resolveMountingNodeEditorContext falls back to surface_mount only when the variant is missing", () => {
  const context = resolveMountingNodeEditorContext({
    ...flatLegacyNodeDetail,
    id: 12,
    templates: [
      {
        id: 9900,
        fitting_id: 77,
        name: "Missing variant template",
        points: [],
      },
    ],
  });

  assert.equal(context.templateId, "9900");
  assert.equal(context.mountingVariantKey, "surface_mount");
});

test("buildMountingNodeEditorSavePayload prefers the real fitting template id for link objects", () => {
  const selectedTemplate = {
    ...fixtureNodeDetail.templates[0],
    template: {
      ...fixtureNodeDetail.templates[0].template,
      mounting_variant_key: "face_to_edge",
    },
  };

  const payload = buildMountingNodeEditorSavePayload({
    context: fixtureContext,
    points: fixturePoints,
    pointsLoaded: true,
    selectedTemplate,
  });

  assert.equal(payload.code, "mounting-node-node-9039f657");
  assert.equal(payload.name, "петля");
  assert.equal(payload.items.length, 2);
  assert.equal(payload.templates[0].template_id, 7480);
  assert.equal(payload.templates[0].template.mounting_variant_key, "face_to_edge");
  assert.deepEqual(
    payload.templates[0].template.points.map((point) => point.id),
    [29, 30],
  );
});

test("buildMountingNodeEditorSavePayload also accepts direct template objects and template_id-only templates", () => {
  const directTemplate = {
    id: 7480,
    fitting_id: 42,
    name: "Основний шаблон",
    bundle_key: null,
    bundle_name: null,
    bundle_order_index: 0,
    template_type: "manual",
    side: null,
    coordinate_system: "2d",
    mounting_variant_key: "drawer_slides",
    is_default: true,
    notes: null,
    is_active: true,
  };

  const payloadFromDirectId = buildMountingNodeEditorSavePayload({
    context: fixtureContext,
    points: fixturePoints,
    pointsLoaded: true,
    selectedTemplate: directTemplate,
  });

  assert.equal(payloadFromDirectId.templates[0].template.mounting_variant_key, "drawer_slides");

  const payloadFromTemplateIdOnly = buildMountingNodeEditorSavePayload({
    context: fixtureContext,
    points: fixturePoints,
    pointsLoaded: true,
    selectedTemplate: {
      template_id: 7480,
      fitting_id: 42,
      name: "Основний шаблон",
      bundle_key: null,
      bundle_name: null,
      bundle_order_index: 0,
      template_type: "manual",
      side: null,
      coordinate_system: "2d",
      mounting_variant_key: "edge_to_edge",
      is_default: true,
      notes: null,
      is_active: true,
    },
  });

  assert.equal(payloadFromTemplateIdOnly.templates[0].template.mounting_variant_key, "edge_to_edge");
});

test("buildMountingNodeEditorSavePayload carries functional code without falling back to category", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "9",
      templateId: "7480",
      functional_code: "door_hinge",
      nodeDetail: {
        code: "mounting-node-node-9039f657",
        name: "петля",
        category_code: "hinges",
        functional_code: "door_hinge",
        is_active: true,
        items: fixtureNodeDetail.items,
        templates: fixtureNodeDetail.templates,
      },
    },
    pointsLoaded: true,
    selectedTemplate: fixtureNodeDetail.templates[0].template,
    points: fixturePoints,
  });

  assert.equal(payload.functional_code, "door_hinge");
  assert.equal(payload.category_code, "hinges");
});
