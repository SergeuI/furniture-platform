import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting source modal keeps preview compact and source validation strict", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");
  const modalStart = appSource.indexOf("      {fittingSourceModalOpen ? (");
  const modalEnd = appSource.indexOf("      {selectedProject && projectOverviewOpen ? (", modalStart);
  const modalSource = modalStart >= 0 && modalEnd > modalStart ? appSource.slice(modalStart, modalEnd) : appSource;
  const sourceModeStart = modalSource.indexOf('fittingCreateMode === "source" ? (');
  const sourceModeEnd = modalSource.indexOf('              ) : (', sourceModeStart);
  const sourceModeSource = sourceModeStart >= 0 && sourceModeEnd > sourceModeStart ? modalSource.slice(sourceModeStart, sourceModeEnd) : modalSource;

  assert.match(appSource, /const \[fittingSourcePreviewState, setFittingSourcePreviewState\] = useState\("idle"\);/);
  assert.match(appSource, /const fittingSourcePreviewReady =\s*fittingSourcePreviewState === "success" && Boolean\(fittingSourcePreview\);/);
  assert.match(appSource, /const fittingSourcePreviewHeaderLabel =/);
  assert.match(appSource, /const fittingSourcePreviewBodyMessage =/);
  assert.match(appSource, /setFittingSourcePreviewState\("idle"\);/);
  assert.match(appSource, /setFittingSourcePreviewState\("loading"\);/);
  assert.match(appSource, /setFittingSourcePreviewState\("error"\);/);
  assert.match(appSource, /setFittingSourcePreviewState\("success"\);/);
  assert.match(appSource, /fittingSourcePreviewState !== "success" \|\| !fittingSourcePreview/);
  assert.match(appSource, /function handleFittingSourceUrlKeyDown\(event\) \{\s*if \(event\.key === "Enter"\) \{\s*event\.preventDefault\(\);\s*event\.stopPropagation\(\);\s*\}\s*\}/);
  assert.match(appSource, /className=\{fittingModalMode === "create" && fittingCreateMode === "source" && !fittingSourcePreviewReady[\s\S]*\?\s*"ghost-button"[\s\S]*:\s*"primary-button recommended-action"\s*\}/);
  assert.match(appSource, /disabled=\{loading \|\| \(fittingModalMode === "create" && fittingCreateMode === "source" && !fittingSourcePreviewReady\)\}/);
  assert.match(appSource, /renderSourceBadge\(getFittingSourceMeta\(fittingSourcePreview \|\| newFittingForm\)\)/);
  assert.doesNotMatch(appSource, /renderSourceBadge\(getFittingSourceMeta\(fittingSourcePreview \|\| newFittingForm\), true\)/);
  assert.match(appSource, /Не вдалося отримати дані/);
  assert.match(appSource, /Перевірте посилання на сторінку товару\./);
  assert.match(appSource, /Знайдено/);
  assert.doesNotMatch(appSource, /fitting-source-preview-grid/);
  assert.doesNotMatch(appSource, /fitting-source-preview-item\.is-image/);

  assert.doesNotMatch(modalSource, /canonical/i);
  assert.doesNotMatch(modalSource, /Supplier detected:/);
  assert.doesNotMatch(modalSource, /Постачальник визначений/);
  assert.match(modalSource, /fittingSourcePreviewState === "success" && fittingSourcePreview \? \(/);
  assert.match(modalSource, /Оберіть постачальника\./);
  assert.doesNotMatch(sourceModeSource, /Supplier and price/);
  assert.match(sourceModeSource, /onKeyDown=\{handleFittingSourceUrlKeyDown\}/);
  assert.match(appSource, /if \(\s*fittingModalMode === "create"\s*&&\s*fittingCreateMode === "source"\s*&&\s*!event\.nativeEvent\?\.submitter\s*\)\s*\{\s*return;\s*\}/);

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
