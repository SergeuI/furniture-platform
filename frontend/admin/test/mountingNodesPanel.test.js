import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("mounting nodes panel preserves list state and restores scroll after editor mode", () => {
  const sourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("MountingNodesPanelRefined"), true);
  assert.equal(source.includes("buildMountingNodesReturnState"), true);
  assert.equal(source.includes("pendingReturnStateRef"), true);
  assert.equal(source.includes("hidden={editorMode}"), true);
  assert.equal(source.includes("mountingNodesViewMode"), true);
  assert.equal(source.includes("displayMode"), true);
  assert.equal(source.includes("activeStatusFilter"), true);
  assert.equal(source.includes("activeVariantFilter"), true);
  assert.equal(source.includes("appliedSearch"), true);
  assert.equal(source.includes("nodeDetailsById"), true);
  assert.equal(source.includes("nodeDetailErrorsById"), true);
  assert.equal(source.includes("nodes"), true);
  assert.equal(source.includes("window.scrollTo({ behavior: \"auto\", top: nextScrollPosition })"), true);
  assert.equal(source.includes("mounting-nodes-display-toggle"), true);
  assert.equal(source.includes("aria-pressed={displayMode === \"grid\"}"), true);
  assert.equal(source.includes("aria-pressed={displayMode === \"list\"}"), true);
  assert.equal(source.includes("<LayoutGrid size={16} />"), true);
  assert.equal(source.includes("<List size={16} />"), true);
  assert.equal(source.includes("mounting-nodes-search-button"), true);
  assert.equal(source.includes("mounting-nodes-refresh-button"), true);
  assert.equal(source.includes("mounting-node-return-button"), true);
  assert.equal(source.includes("mounting-node-editor-button"), true);
  assert.equal(source.includes("mounting-node-detail-screen"), true);
  assert.equal(source.includes("Return to mounting nodes"), true);
  assert.equal(source.includes("initialState = null"), true);
});

test("catalog holes page shows the mounting nodes editor only in editor mode", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes('catalogHolesMode === "editor" && catalogHolesOpenContext'), true);
  assert.equal(source.includes('catalogHolesMode === "editor" ? ('), true);
  assert.equal(source.includes('initialState={catalogHolesReturnState}'), true);
  assert.equal(source.includes('onOpenMountingNodeEditor={(context, returnState) => {'), true);
  assert.equal(source.includes("handleCatalogHolesBackToList"), true);
  assert.equal(source.includes('setCatalogHolesMode("list")'), true);
  assert.equal(source.includes("mounting-node-editor-banner-grid"), true);
  assert.equal(source.includes("Return to node details"), true);
  assert.equal(source.includes("Editor open"), true);
  assert.equal(source.includes("Current node context."), true);
});
