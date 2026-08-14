import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting source modal keeps preview compact with thumbnails", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /previewFittingSource\(token, \{/);
  assert.match(appSource, /handlePreviewFittingSource/);
  assert.match(appSource, /fittingSourcePreviewSelectedImageUrl/);
  assert.match(appSource, /fitting-source-preview-body/);
  assert.match(appSource, /fitting-source-preview-media/);
  assert.match(appSource, /fitting-source-preview-summary/);
  assert.match(appSource, /fitting-source-preview-row/);
  assert.match(appSource, /fitting-source-preview-thumbs/);
  assert.match(appSource, /fitting-source-preview-thumb/);
  assert.match(appSource, /Supplier detected:/);
  assert.match(appSource, /Зображення не знайдено/);
  assert.match(appSource, /Отримати дані/);
  assert.doesNotMatch(appSource, /fitting-source-preview-grid/);
  assert.doesNotMatch(appSource, /fitting-source-preview-item\.is-image/);

  assert.match(stylesSource, /\.fitting-source-modal \{\s*display: flex;[\s\S]*max-height: min\(90vh, calc\(100vh - 32px\)\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \{\s*display: grid;[\s\S]*overflow: auto;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-body \{\s*display: grid;[\s\S]*grid-template-columns: minmax\(180px, 220px\) minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-image \{\s*align-items: center;[\s\S]*height: 190px;[\s\S]*max-width: 220px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-thumbs \{\s*display: flex;[\s\S]*overflow-x: auto;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-thumb \{\s*align-items: center;[\s\S]*height: 56px;[\s\S]*width: 56px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-summary \{\s*display: grid;[\s\S]*gap: 6px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-row \{\s*align-items: start;[\s\S]*grid-template-columns: minmax\(140px, 180px\) minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-row > strong \{\s*color: #24343d;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-empty \{/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-actions-row \{/);
  assert.match(
    stylesSource,
    /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form \.fitting-source-preview-body,\s*\.fitting-source-modal-form \.fitting-source-preview-row \{\s*grid-template-columns: minmax\(0, 1fr\);/,
  );
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form \.fitting-source-preview-thumb \{\s*height: 52px;[\s\S]*width: 52px;/);
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form \.fitting-source-preview-image \{\s*max-width: none;[\s\S]*width: 100%;/);
});
