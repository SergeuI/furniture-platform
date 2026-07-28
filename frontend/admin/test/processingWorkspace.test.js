import assert from "node:assert/strict";
import test from "node:test";

import {
  getProcessingOverviewCards,
  getProcessingWorkspaceTabs,
  normalizeProcessingWorkspaceTab,
} from "../src/processingWorkspace.js";
import { getProcessingOperationsPreview } from "../src/api.js";

test("processing workspace tabs keep admin pages and restrict non-admin users to fitting holes only", () => {
  const adminTabs = getProcessingWorkspaceTabs({
    canUseFittingHoles: true,
    isAdmin: true,
    language: "uk",
  });
  const fittingUserTabs = getProcessingWorkspaceTabs({
    canUseFittingHoles: true,
    isAdmin: false,
    language: "uk",
  });
  const blockedUserTabs = getProcessingWorkspaceTabs({
    canUseFittingHoles: false,
    isAdmin: false,
    language: "uk",
  });

  assert.deepEqual(
    adminTabs.map((tab) => tab.key),
    [
      "overview",
      "operations",
      "templates",
      "fitting-holes",
      "services-prices",
      "pricing-rules",
      "testing",
    ],
  );
  assert.deepEqual(fittingUserTabs.map((tab) => tab.key), ["fitting-holes"]);
  assert.deepEqual(blockedUserTabs.map((tab) => tab.key), []);
  assert.equal(
    normalizeProcessingWorkspaceTab("testing", {
      canUseFittingHoles: true,
      isAdmin: false,
    }),
    "fitting-holes",
  );
  assert.equal(
    normalizeProcessingWorkspaceTab("unknown", {
      canUseFittingHoles: true,
      isAdmin: true,
    }),
    "overview",
  );
});

test("processing overview cards use the current working and planned statuses", () => {
  const cards = getProcessingOverviewCards("uk");

  assert.ok(cards.some((card) => card.label === "Отвори" && card.status === "Працює"));
  assert.ok(cards.some((card) => card.label === "operations-preview" && card.status === "Працює"));
  assert.ok(cards.some((card) => card.label === "Пази" && card.status === "Заплановано"));
  assert.ok(cards.some((card) => card.label === "Ціни компаній" && card.status === "Заплановано"));
});

test("operations-preview api helper calls the new read-only endpoint", async () => {
  const originalFetch = global.fetch;
  const calls = [];

  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return {
      ok: true,
      status: 200,
      text: async () =>
        JSON.stringify({
          success: true,
          template: { id: 7 },
          operations: [],
        }),
    };
  };

  try {
    const result = await getProcessingOperationsPreview("test-token", 7);

    assert.equal(result.success, true);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url.endsWith("/fitting-holes/templates/7/operations-preview"), true);
    assert.equal(calls[0].options.headers.Authorization, "Bearer test-token");
  } finally {
    global.fetch = originalFetch;
  }
});
