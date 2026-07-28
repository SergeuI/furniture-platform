import assert from "node:assert/strict";
import test from "node:test";

import { getProcessingOperationTypes } from "../src/api.js";
import {
  buildProcessingOperationTypeViewModels,
  getProcessingOperationTypeStatusLabel,
} from "../src/processingOperationTypes.js";

function buildPlannedType(key) {
  return {
    key,
    name: key,
    description: `${key} description`,
    category: "routing",
    status: "planned",
    geometry_kind: "toolpath",
    required_fields: ["field_a"],
    optional_fields: [],
    pricing_units: ["piece"],
    capabilities: {
      template_editor: false,
      operations_preview: false,
      preview_3d: false,
      service_mapping: false,
      estimate_export: false,
      cutting_effect: false,
    },
    version: 1,
  };
}

test("processing operation types api helper calls the new registry endpoint", async () => {
  const calls = [];
  const originalFetch = global.fetch;

  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, items: [], count: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await getProcessingOperationTypes("token-1");

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url.endsWith("/processing/operation-types"), true);
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-1");
  } finally {
    global.fetch = originalFetch;
  }
});

test("processing operation type helpers translate status and keep false capabilities inactive", () => {
  const viewModels = buildProcessingOperationTypeViewModels(
    [
      {
        key: "hole",
        name: "Отвір",
        description: "Current fitting hole workflow",
        category: "drilling",
        status: "available",
        geometry_kind: "cylinder",
        required_fields: ["x_mm", "y_mm", "z_mm", "diameter_mm"],
        optional_fields: null,
        pricing_units: ["piece"],
        capabilities: {
          template_editor: true,
          operations_preview: true,
          preview_3d: true,
          service_mapping: true,
          estimate_export: false,
          cutting_effect: false,
        },
        version: 1,
      },
      buildPlannedType("groove"),
      buildPlannedType("quarter"),
      buildPlannedType("pocket"),
      buildPlannedType("rectangular_cutout"),
      buildPlannedType("contour_cutout"),
      buildPlannedType("radius"),
      buildPlannedType("milling"),
      buildPlannedType("manual_operation"),
    ],
    "uk",
  );

  assert.equal(viewModels.length, 9);
  assert.equal(viewModels[0].status_label, "Працює");
  assert.deepEqual(viewModels[0].optional_fields, []);
  assert.equal(
    viewModels[0].capability_items.find((item) => item.key === "estimate_export").active,
    false,
  );
  assert.equal(
    viewModels[0].capability_items.find((item) => item.key === "estimate_export").state_label,
    "Ще не підтримується",
  );
  assert.equal(getProcessingOperationTypeStatusLabel("needs_configuration", "uk"), "Потребує налаштування");
});
