import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

function readSource(relativeUrl) {
  return readFileSync(fileURLToPath(new URL(relativeUrl, import.meta.url)), "utf8");
}

test("mounting nodes create panel renders compact wizard structure", () => {
  const panelSource = readSource("../src/components/processing/MountingNodesCreatePanel.jsx");
  const appSource = readSource("../src/App.jsx");
  const stylesSource = readSource("../src/styles.css");

  assert.equal(appSource.includes("mounting-node-create-panel-shell"), true);
  assert.equal(appSource.includes('className="table-panel full-panel mounting-node-create-panel-shell"'), true);
  assert.equal(panelSource.includes('catalog-page-header mounting-node-create-header'), false);
  assert.equal(panelSource.includes('className="mounting-node-create-header"'), true);
  assert.equal(panelSource.includes('mounting-node-create-header-copy'), false);
  assert.equal(panelSource.includes('mounting-node-create-breadcrumb'), false);
  assert.equal(panelSource.includes('mounting-node-create-description-input'), true);
  assert.equal(panelSource.includes('{language === "uk" ? "Фурнітура" : "Fittings"}: {selectedItems.length}'), true);
  assert.equal(panelSource.includes('Наприклад, Конфірмат 7×50'), true);
  assert.equal(panelSource.includes('mn_confirmat_7x50'), false);
  assert.equal(panelSource.includes('className="mounting-node-create-card mounting-node-create-main-info-card"'), true);
  assert.equal(panelSource.includes('className="mounting-node-create-card mounting-node-create-variant-card"'), true);
  assert.equal(panelSource.includes('className="mounting-node-create-card mounting-node-create-items-card"'), true);
  assert.equal(panelSource.includes('mounting-node-create-items-head'), true);
  assert.equal(panelSource.includes('mounting-node-create-selected-fitting-info'), false);
  assert.equal(panelSource.includes('mounting-node-create-empty-state mounting-node-create-empty-state-compact'), true);
  assert.equal(panelSource.includes('mounting-node-create-field-error'), true);
  assert.equal(panelSource.includes('mounting-node-create-name-error'), true);
  assert.equal(panelSource.includes('aria-describedby={nameValidationError ? "mounting-node-create-name-error" : undefined}'), true);
  assert.equal(panelSource.includes('Додати фурнітуру'), true);
  assert.equal((panelSource.match(/Додати фурнітуру/g) || []).length, 1);
  assert.equal(panelSource.includes('Створити вузол'), true);
  assert.equal(panelSource.includes('Скасувати'), true);
  assert.equal(panelSource.includes('holes-workspace-save-panel-copy'), false);
  assert.equal(panelSource.includes('Створення монтажного вузла'), false);
  assert.equal(panelSource.includes('mounting-node-create-soft-button'), true);
  assert.equal(panelSource.includes('mounting-node-create-cancel-button'), true);
  assert.equal(panelSource.includes('mounting-node-create-submit-button'), true);
  assert.equal(panelSource.includes('mounting-node-create-banner'), true);
  assert.equal(panelSource.includes('mounting-node-create-section-error'), true);
  assert.equal(panelSource.includes('mounting-node-create-footer'), true);
  assert.equal(panelSource.includes('handleSubmit(event, "editor")'), true);
  assert.equal(panelSource.includes('hole-bundle-modal-row-image'), true);
  assert.equal(panelSource.includes('hole-bundle-modal-card-image'), true);
  assert.equal(panelSource.includes('hole-bundle-modal-body'), true);
  assert.equal(panelSource.includes('hole-bundle-modal-list'), true);
  assert.equal(panelSource.includes('hole-bundle-modal-cards'), true);
  assert.equal(panelSource.includes('Немає фото'), true);
  assert.equal(stylesSource.includes('.hole-bundle-modal-row-image,'), true);
  assert.equal(stylesSource.includes('.hole-bundle-modal-row-image-empty'), true);
  assert.equal(stylesSource.includes('.hole-bundle-modal-card-image,'), true);
  assert.equal(stylesSource.includes('.hole-bundle-modal-card-image-empty'), true);
  assert.equal(stylesSource.includes('object-fit: contain;'), true);
  assert.equal(stylesSource.includes('overflow: hidden;'), true);
  assert.equal(stylesSource.includes('.hole-bundle-modal-card-image {\n  background: #ffffff;'), true);
  assert.equal(stylesSource.includes('.hole-bundle-modal-card-image-empty {\n  background: #f4f7f9;'), true);
});
