import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting source modal keeps preview compact and source flow stateful", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");
  const modalStart = appSource.indexOf("      {fittingSourceModalOpen ? (");
  const modalEnd = appSource.indexOf("      {selectedProject && projectOverviewOpen ? (", modalStart);
  const modalSource = modalStart >= 0 && modalEnd > modalStart ? appSource.slice(modalStart, modalEnd) : appSource;
  const sourceModeStart = modalSource.indexOf('fittingCreateMode === "source" ? (');
  const sourceModeEnd = modalSource.indexOf(') : (', sourceModeStart);
  const sourceModeSource =
    sourceModeStart >= 0 && sourceModeEnd > sourceModeStart
      ? modalSource.slice(sourceModeStart, sourceModeEnd)
      : modalSource;

  assert.match(appSource, /previewFittingSource\(token, \{/);
  assert.match(appSource, /handlePreviewFittingSource/);
  assert.match(appSource, /setFittingSourcePreview\(null\);\s*setFittingSourcePreviewError\(""\);\s*setFittingSourcePreviewSelectedImageUrl\(""\);/);
  assert.match(appSource, /const fittingSourcePreviewReady = Boolean\(/);
  assert.match(appSource, /fittingSourcePreviewSelectedImageUrl/);
  assert.match(appSource, /className=\{\`compact-button\$\{fittingSourcePreviewReady \? " ghost-button" : " primary-button recommended-action"\}\`\}/);
  assert.match(
    appSource,
    /className=\{fittingModalMode === "create" && fittingCreateMode === "source" && !fittingSourcePreviewReady[\s\S]*\?\s*"ghost-button"[\s\S]*:\s*"primary-button recommended-action"\s*\}/,
  );
  assert.match(appSource, /disabled=\{loading \|\| \(fittingModalMode === "create" && fittingCreateMode === "source" && !fittingSourcePreviewReady\)\}/);
  assert.match(appSource, /if \(\s*fittingModalMode === "create"\s*&&\s*fittingCreateMode === "source"\s*&&\s*\(!fittingSourcePreview \|\| fittingSourcePreviewLoading \|\| fittingSourcePreviewError\)\s*\)/);
  assert.match(appSource, /renderSourceBadge\(getFittingSourceMeta\(fittingSourcePreview \|\| newFittingForm\)\)/);
  assert.doesNotMatch(appSource, /renderSourceBadge\(getFittingSourceMeta\(fittingSourcePreview \|\| newFittingForm\), true\)/);
  assert.match(appSource, /fittingSourcePreview\?\.supplier \? null : \(/);
  assert.match(appSource, /Оберіть постачальника\./);
  assert.match(appSource, /Зображення не знайдено/);
  assert.match(appSource, /Отримати дані/);
  assert.doesNotMatch(appSource, /fitting-source-preview-grid/);
  assert.doesNotMatch(appSource, /fitting-source-preview-item\.is-image/);

  assert.doesNotMatch(modalSource, /canonical/i);
  assert.doesNotMatch(modalSource, /Supplier detected:/);
  assert.doesNotMatch(modalSource, /Постачальник визначений/);
  assert.match(modalSource, /Supplier and price/);
  assert.match(modalSource, /fittingSourcePreview\?\.supplier \? null : \(/);
  assert.match(modalSource, /Оберіть постачальника\./);
  assert.doesNotMatch(sourceModeSource, /Постачальник і ціна/);
  assert.doesNotMatch(sourceModeSource, /Supplier and price/);

  assert.match(stylesSource, /\.fitting-source-modal \{\s*display: flex;[\s\S]*max-height: min\(90vh, calc\(100vh - 32px\)\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \{\s*display: grid;[\s\S]*overflow: auto;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-body \{\s*display: grid;[\s\S]*grid-template-columns: minmax\(180px, 220px\) minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-image \{\s*align-items: center;[\s\S]*height: 190px;[\s\S]*max-width: 220px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-thumbs \{\s*display: flex;[\s\S]*overflow-x: auto;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-thumb \{\s*align-items: center;[\s\S]*height: 56px;[\s\S]*width: 56px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-summary \{\s*display: grid;[\s\S]*gap: 6px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-row \{\s*align-items: start;[\s\S]*grid-template-columns: minmax\(140px, 180px\) minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-empty \{/);
  assert.match(
    stylesSource,
    /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form \.fitting-source-preview-body,\s*\.fitting-source-modal-form \.fitting-source-preview-row \{\s*grid-template-columns: minmax\(0, 1fr\);/,
  );
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form \.fitting-source-preview-thumb \{\s*height: 52px;[\s\S]*width: 52px;/);
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form \.fitting-source-preview-image \{\s*max-width: none;[\s\S]*width: 100%;/);
});
