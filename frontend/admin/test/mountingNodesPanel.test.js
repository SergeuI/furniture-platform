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
  assert.equal(source.includes("window.scrollTo({ behavior: \"auto\", top: nextScrollPosition })"), true);
  assert.equal(source.includes("mounting-node-return-button"), true);
  assert.equal(source.includes("mounting-node-editor-button"), true);
  assert.equal(source.includes("mounting-node-delete-button"), true);
  assert.equal(source.includes("mounting-node-ownership-badge"), true);
  assert.equal(source.includes("mounting-node-create-button"), true);
  assert.equal(source.includes("onOpenMountingNodeCreate"), true);
  assert.equal(source.includes("nodeDetail: selectedNodeDetail"), true);
  assert.equal(source.includes("mounting-node-detail-screen"), true);
  assert.equal(source.includes("Return to mounting nodes"), true);
  assert.equal(source.includes("Open point editor"), true);
  assert.equal(source.includes("Відкрити редактор точок"), true);
  assert.equal(source.includes("Delete mounting node"), true);
  assert.equal(source.includes("handleOpenDeleteConfirm"), true);
  assert.equal(source.includes("deleteConfirmNode"), true);
});
test("catalog holes page shows the mounting nodes create mode and editor mode branches", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");
  const createPanelPath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesCreatePanel.jsx", import.meta.url),
  );
  const createPanelSource = readFileSync(createPanelPath, "utf8");

  assert.equal(source.includes('catalogHolesMode === "create" ? ('), true);
  assert.equal(source.includes('catalogHolesMode === "editor" ? ('), true);
  assert.equal(source.includes('onOpenMountingNodeCreate={handleOpenMountingNodeCreate}'), true);
  assert.equal(source.includes('onOpenMountingNodeEditor={(context, returnState) => {'), true);
  assert.equal(source.includes("buildMountingNodeEditorContext"), true);
  assert.equal(source.includes("handleCatalogHolesBackToList"), true);
  assert.equal(source.includes("handleCreateMountingNode"), true);
  assert.equal(source.includes("catalogHolesCreateError"), true);
  assert.equal(source.includes("catalogHolesCreating"), true);
  assert.equal(source.includes("catalogHolesOpenContext?.mountingNodeId"), true);
  assert.equal(source.includes("catalogHolesOpenContext?.nodeDetail"), true);
  assert.equal(source.includes("switchView(\"catalogHoles\", user, context)"), true);
  assert.equal(source.includes('catalogHolesMode === "editor" && catalogHolesOpenContext'), false);
  assert.equal(source.includes("mounting-node-editor-banner-grid"), false);
  assert.equal(source.includes("mounting-node-return-button"), true);
  assert.equal(source.includes("mounting-node-save-button"), true);
  assert.equal(source.includes("Return to node details"), true);
  assert.equal(source.includes("Відкрити редактор точок"), true);
  assert.equal(source.includes('mountingNodeOpenEditor: "Відкрити редактор точок"'), true);
  assert.equal(createPanelSource.includes("MountingNodesCreatePanel"), true);
  assert.equal(createPanelSource.includes("onCreate"), true);
  assert.equal(createPanelSource.includes("isCreating"), true);
  assert.equal(createPanelSource.includes("createError"), true);
  assert.equal(createPanelSource.includes("validateMountingNodeCreateDraft"), true);
  assert.equal(createPanelSource.includes("Створення монтажного вузла"), true);
  assert.equal(createPanelSource.includes("Створення монтажного вузла"), true);
  assert.equal(createPanelSource.includes("Назва монтажного вузла"), true);
  assert.equal(createPanelSource.includes("Опис"), true);
  assert.equal(createPanelSource.includes("Додати фурнітуру"), true);
  assert.equal(createPanelSource.includes("Інформація про фурнітуру"), true);
  assert.equal(createPanelSource.includes("Вибрані фурнітури"), true);
  assert.equal(createPanelSource.includes("Варіант кріплення"), true);
  assert.equal(createPanelSource.includes("Quantity"), true);
  assert.equal(createPanelSource.includes("Add selected"), true);
  assert.equal(createPanelSource.includes("holes-workspace-save-panel"), true);
  assert.equal(createPanelSource.includes("hole-bundle-modal-mode-switch mounting-nodes-display-toggle materials-mode-switch"), true);
  assert.equal(createPanelSource.includes("hole-template-fitting-info"), true);
  assert.equal(createPanelSource.includes("hole-template-fitting-list"), true);
  assert.equal(createPanelSource.includes("MountingNodesCreateDraftPointFromFitting"), false);
  assert.equal(createPanelSource.includes("pointCreateOpen"), false);
  assert.equal(createPanelSource.includes("FittingHolesWorkspace"), false);
  assert.equal(createPanelSource.includes("HolesMountingThreePreview"), false);
  assert.equal(createPanelSource.includes("holes-preview-3d-card"), false);
  assert.equal(createPanelSource.includes("holes-workspace-top-zone"), false);
  assert.equal(createPanelSource.includes("holes-selected-point-panel"), false);
  assert.equal(createPanelSource.includes("createMountingNodeCreateDraftPointFromFitting("), false);
});
