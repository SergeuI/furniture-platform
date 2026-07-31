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
  assert.equal(source.includes("mounting-node-create-button"), true);
  assert.equal(source.includes("onOpenMountingNodeCreate"), true);
  assert.equal(source.includes("nodeDetail: selectedNodeDetail"), true);
  assert.equal(source.includes("mounting-node-detail-screen"), true);
  assert.equal(source.includes("Return to mounting nodes"), true);
  assert.equal(source.includes("initialState = null"), true);
});

test("catalog holes page shows the mounting nodes create mode and editor mode branches", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");
  const panelSourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const panelSource = readFileSync(panelSourcePath, "utf8");
  const createPanelPath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesCreatePanel.jsx", import.meta.url),
  );
  const createPanelSource = readFileSync(createPanelPath, "utf8");

  assert.equal(source.includes('catalogHolesMode === "editor" && catalogHolesOpenContext'), true);
  assert.equal(source.includes('catalogHolesMode === "create" ? ('), true);
  assert.equal(source.includes('catalogHolesMode === "create" ? null :'), true);
  assert.equal(source.includes('catalogHolesMode === "editor" ? ('), true);
  assert.equal(source.includes('initialState={catalogHolesReturnState}'), true);
  assert.equal(source.includes('onOpenMountingNodeCreate={handleOpenMountingNodeCreate}'), true);
  assert.equal(source.includes('onOpenMountingNodeEditor={(context, returnState) => {'), true);
  assert.equal(source.includes("handleCatalogHolesBackToList"), true);
  assert.equal(source.includes('setCatalogHolesMode("list")'), true);
  assert.equal(panelSource.includes("mounting-node-create-button"), true);
  assert.equal(panelSource.includes("Створити монтажний вузол"), true);
  assert.equal(source.includes("mounting-node-editor-banner-grid"), true);
  assert.equal(source.includes("Return to node details"), true);
  assert.equal(source.includes("Зберегти монтажний вузол"), true);
  assert.equal(source.includes("handleCatalogHolesSaveMountingNode"), true);
  assert.equal(source.includes("catalogHolesSaving"), true);
  assert.equal(source.includes("catalogHolesOpenContext?.mountingNodeId"), true);
  assert.equal(source.includes("catalogHolesOpenContext?.nodeDetail"), true);
  assert.equal(source.includes("const isMountingNodeEditorMode = Boolean("), true);
  assert.equal(source.includes("!isMountingNodeEditorMode ? ("), true);
  assert.equal(source.includes("holes-bundle-create-panel"), true);
  assert.equal(source.includes("holes-workspace-save-panel"), true);
  assert.equal(source.includes("Editor open"), true);
  assert.equal(source.includes("Current node context."), true);
  assert.equal(createPanelSource.includes("MountingNodesCreatePanel"), true);
  assert.equal(createPanelSource.includes("FittingHolesWorkspace"), true);
  assert.equal(createPanelSource.includes("HolesMountingThreePreview"), true);
  assert.equal(createPanelSource.includes("hole-template-fitting-info"), true);
  assert.equal(createPanelSource.includes("holes-workspace-top-zone"), true);
  assert.equal(createPanelSource.includes("holes-preview-3d-card"), true);
  assert.equal(createPanelSource.includes("holes-workspace-save-panel"), true);
  assert.equal(createPanelSource.includes("client_key"), true);
  assert.equal(createPanelSource.includes("local draft"), true);
  assert.equal(createPanelSource.includes("Add point"), true);
  assert.equal(createPanelSource.includes("quantity"), true);
  assert.equal(createPanelSource.includes("role"), true);
  assert.equal(createPanelSource.includes("getFittingCategoryLabel(item, language, t, fittingCategories)"), true);
  assert.equal(createPanelSource.includes("hole-bundle-selected-item-compact"), true);
  assert.equal(createPanelSource.includes("mounting-node-create-fitting-row"), true);
  assert.equal(createPanelSource.includes('aria-label={language === "uk" ? "Роль" : "Role"}'), true);
  assert.equal(createPanelSource.includes('aria-label={language === "uk" ? "Кількість" : "Quantity"}'), true);
  assert.equal(createPanelSource.includes('aria-label={language === "uk" ? "Видалити" : "Remove fitting"}'), true);
  assert.equal(createPanelSource.includes("mounting-node-create-fitting-role"), true);
  assert.equal(createPanelSource.includes("mounting-node-create-fitting-quantity"), true);
  assert.equal(createPanelSource.includes("mounting-node-create-fitting-remove"), true);
  assert.equal(createPanelSource.includes("hole-bundle-selected-item-controls"), false);
  assert.equal(createPanelSource.includes('<span>{language === "uk" ? "Роль" : "Role"}</span>'), false);
  assert.equal(createPanelSource.includes('<span>{language === "uk" ? "К-сть" : "Qty"}</span>'), false);
  assert.equal(createPanelSource.includes("mounting-node-create-name-row"), true);
  assert.equal(createPanelSource.includes("Додати фурнітуру"), true);
  assert.equal(createPanelSource.includes("<Plus size={16} />"), true);
  assert.equal(
    createPanelSource.includes('PointField label={language === "uk" ? "Категорія фурнітури" : "Fitting category"}'),
    false,
  );
  assert.equal(createPanelSource.includes('<span>{language === "uk" ? "Фурнітура" : "Fittings"}</span>'), false);
  assert.equal(createPanelSource.includes("Обов’язкова"), false);
  assert.equal(createPanelSource.includes("handleSelectedFittingPatch(fittingId, { is_required: event.target.checked })"), false);
  assert.equal(createPanelSource.includes("holes-mounting-variant-toggle-mark"), true);
  assert.equal(createPanelSource.includes("selectedVariantModel?.icon"), true);
  assert.equal(createPanelSource.includes("selectorDraftItemIds"), true);
  assert.equal(createPanelSource.includes("selectorStateSeededRef"), true);
  assert.equal(createPanelSource.includes("selectorStateSeededRef.current = true"), true);
  assert.equal(createPanelSource.includes("!selectorStateSeededRef.current"), true);
  assert.equal(createPanelSource.includes("selectorViewMode === \"list\""), true);
  assert.equal(createPanelSource.includes("selectorViewMode === \"cards\""), true);
  assert.equal(createPanelSource.includes("hole-bundle-modal-body"), true);
  assert.equal(createPanelSource.includes("hole-bundle-modal-list"), true);
  assert.equal(createPanelSource.includes("hole-bundle-modal-cards"), true);
  assert.equal(createPanelSource.includes("hole-bundle-modal-mode-switch mounting-nodes-display-toggle materials-mode-switch"), true);
  assert.equal(createPanelSource.includes("<List size={16} />"), true);
  assert.equal(createPanelSource.includes("<LayoutGrid size={16} />"), true);
  assert.equal(createPanelSource.includes("MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY"), true);
  assert.equal(createPanelSource.includes("mountingNodesCreateFittingSelectorView"), true);
  assert.equal(
    createPanelSource.includes("window.localStorage.setItem(MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY, selectorViewMode)"),
    true,
  );
  assert.equal(createPanelSource.includes("readStoredSelectorViewMode"), true);
  assert.equal(createPanelSource.includes("setSelectorSearch(\"\")"), false);
  assert.equal(createPanelSource.includes("setSelectorDraftItemIds([])"), false);
  assert.equal(createPanelSource.includes("handleToggleSelectorFitting"), true);
  assert.equal(createPanelSource.includes("handleConfirmSelectedFittings"), true);
  assert.equal(createPanelSource.includes("Add selected"), true);
  assert.equal(createPanelSource.includes("selectedVariantLabel"), false);
  assert.equal(createPanelSource.includes("selectedVariantKey.slice(0, 2).toUpperCase()"), false);
});
