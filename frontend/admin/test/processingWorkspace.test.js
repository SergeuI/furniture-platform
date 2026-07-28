import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  getProcessingOverviewCards,
  getProcessingWorkspaceSidebarTabs,
  getProcessingWorkspaceTabTargetView,
  getProcessingWorkspaceTabs,
  resolveActiveProcessingNavigationKey,
  normalizeProcessingWorkspaceTab,
  shouldAutoOpenCatalogMenu,
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
  assert.equal(getProcessingWorkspaceTabTargetView("fitting-holes"), "catalogHoles");
  assert.equal(getProcessingWorkspaceTabTargetView("overview"), "processing");
});

test("catalog holes no longer auto-opens the directories group", () => {
  assert.equal(shouldAutoOpenCatalogMenu("catalogHoles"), false);
  assert.equal(shouldAutoOpenCatalogMenu("catalogMaterials"), true);
  assert.equal(shouldAutoOpenCatalogMenu("catalogFittings"), true);
  assert.equal(shouldAutoOpenCatalogMenu("catalogValues"), true);
});

test("processing navigation key stays aligned with the real opened page", () => {
  assert.equal(
    resolveActiveProcessingNavigationKey({
      activeView: "catalogHoles",
      activeProcessingTab: "overview",
      canUseFittingHoles: true,
      isAdmin: false,
    }),
    "fitting-holes",
  );
  assert.equal(
    resolveActiveProcessingNavigationKey({
      activeView: "processing",
      activeProcessingTab: "fitting-holes",
      canUseFittingHoles: true,
      isAdmin: true,
    }),
    "overview",
  );
  assert.equal(
    resolveActiveProcessingNavigationKey({
      activeView: "processing",
      activeProcessingTab: "operations",
      canUseFittingHoles: true,
      isAdmin: true,
    }),
    "operations",
  );
  assert.equal(
    resolveActiveProcessingNavigationKey({
      activeView: "users",
      activeProcessingTab: "operations",
      canUseFittingHoles: true,
      isAdmin: true,
    }),
    null,
  );
});

test("processing sidebar tabs show only names without status text", () => {
  const sidebarTabs = getProcessingWorkspaceSidebarTabs({
    canUseFittingHoles: true,
    isAdmin: true,
    language: "uk",
  });

  assert.deepEqual(
    sidebarTabs.map((tab) => tab.label),
    [
      "Огляд",
      "Операції обробки",
      "Шаблони обробки",
      "Присадка фурнітури",
      "Послуги та ціни",
      "Правила розрахунку",
      "Тестування",
    ],
  );
  assert.equal(sidebarTabs.every((tab) => tab.status === undefined), true);
  assert.equal(sidebarTabs.some((tab) => ["Працює", "Заплановано", "Потребує налаштування"].includes(tab.label)), false);
});

test("processing overview cards use the current working and planned statuses", () => {
  const cards = getProcessingOverviewCards("uk");

  assert.ok(cards.some((card) => card.label === "Отвори" && card.status === "Працює"));
  assert.ok(cards.some((card) => card.label === "Попередній перегляд операцій" && card.status === "Працює"));
  assert.equal(cards.some((card) => card.label === "operations-preview"), false);
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

test("processing workspace forwards token to the templates page", () => {
  const workspacePath = fileURLToPath(new URL("../src/components/processing/ProcessingWorkspace.jsx", import.meta.url));
  const source = readFileSync(workspacePath, "utf8");

  assert.match(source, /<ProcessingTemplates[\s\S]*token=\{token\}[\s\S]*\/>/);
});
