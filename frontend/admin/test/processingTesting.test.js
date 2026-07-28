import assert from "node:assert/strict";
import test from "node:test";

import {
  getProjectPartOperationsPreview,
} from "../src/api.js";
import {
  getProcessingTestingModeOptions,
  getProcessingTestingOperationTypeLabel,
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
