import assert from "node:assert/strict";
import test from "node:test";

import {
  getProjectPartOperationsPreview,
} from "../src/api.js";
import {
  formatOperationCoordinates,
  formatOperationTitle,
  formatPartDimensions,
  getOperationEstimateStatus,
  getOperationServiceStatus,
  getProcessingTestingModeOptions,
  getProcessingTestingOperationTypeLabel,
  getVisibleOperationFields,
} from "../src/processingTesting.js";

test("processing testing helpers expose readable modes and operation labels", () => {
  const modes = getProcessingTestingModeOptions("uk");

  assert.deepEqual(
    modes,
    [
      { value: "template", label: "Шаблон присадки" },
      { value: "project", label: "Деталь проєкту" },
    ],
  );
  assert.equal(getProcessingTestingOperationTypeLabel("hole", "uk"), "Отвір");
  assert.equal(getProcessingTestingOperationTypeLabel("groove", "uk"), "Паз");
  assert.equal(getProcessingTestingOperationTypeLabel("quarter", "uk"), "Чверть");
  assert.equal(formatOperationTitle({ operation_type: "hole" }, 1, "uk"), "Отвір 1");
  assert.equal(
    formatOperationCoordinates({ placement: { x_mm: 50, y_mm: 21, z_mm: 0 } }, "uk"),
    "X 50 мм, Y 21 мм, Z 0 мм",
  );
  assert.equal(
    formatPartDimensions({ width: 500, height: 800, thickness: 18 }, "uk"),
    "500 × 800 × 18 мм",
  );
  assert.equal(
    getOperationEstimateStatus({ production_effects: { include_in_estimate: false } }, "uk"),
    "Не включено до кошторису",
  );
  assert.equal(
    getOperationServiceStatus({ service_mapping: { found: false } }, "uk"),
    "Послугу ще не прив’язано",
  );

  const visibleFields = getVisibleOperationFields(
    {
      operation_type: "hole",
      placement: { x_mm: 50, y_mm: 21, z_mm: 0 },
      geometry: { diameter_mm: 5, depth_mm: 12, is_through: false },
      quantity: 1,
    },
    "uk",
  );

  assert.deepEqual(
    visibleFields.map((field) => field.label),
    ["Координати", "Діаметр", "Глибина", "Сквозний", "Кількість"],
  );
  assert.equal(
    visibleFields.some((field) => ["Панель", "Поверхня", "Сторона"].includes(field.label)),
    false,
  );
});

test("project part operations preview api helper encodes part identifiers", async () => {
  const calls = [];
  const originalFetch = global.fetch;

  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return new Response(JSON.stringify({ success: true, project: { id: "p-1" }, part: {}, operations: [], count: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  };

  try {
    const result = await getProjectPartOperationsPreview("token-1", "project/1", "DRW FRONT");

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url.endsWith("/processing/projects/project%2F1/parts/DRW%20FRONT/operations-preview"), true);
    assert.equal(calls[0].options.headers.Authorization, "Bearer token-1");
  } finally {
    global.fetch = originalFetch;
  }
});
