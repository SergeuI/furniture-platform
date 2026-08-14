import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting source modal uses explicit preview and compact rows", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /previewFittingSource\(token, \{/);
  assert.match(appSource, /handlePreviewFittingSource/);
  assert.match(appSource, /Отримати дані/);
  assert.match(appSource, /fittingSourcePreviewLoading/);
  assert.match(appSource, /fittingSourcePreviewError/);
  assert.match(appSource, /fittingSourcePreview\?\.supplier/);
  assert.match(appSource, /fitting-source-actions-row/);
  assert.match(appSource, /fitting-source-readonly/);
  assert.match(
    appSource,
    /fittingModalMode === "create" && fittingCreateMode === "source" && \(!fittingSourcePreview \|\| fittingSourcePreviewLoading\)/,
  );
  assert.match(appSource, /Спочатку натисніть/);
  assert.match(stylesSource, /\.fitting-source-modal \{\s*display: flex;[\s\S]*max-height: min\(90vh, calc\(100vh - 32px\)\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \{\s*display: grid;[\s\S]*overflow: auto;/);
  assert.match(
    stylesSource,
    /\.fitting-source-modal-form \.fitting-source-field,\s*\.fitting-source-modal-form \.fitting-source-url-field,\s*\.fitting-source-modal-form \.toggle-label \{\s*align-items: center;[\s\S]*grid-template-columns: minmax\(180px, 220px\) minmax\(0, 1fr\);/,
  );
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-actions-row \{\s*align-items: center;[\s\S]*grid-template-columns: max-content minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-readonly strong \{\s*color: #24343d;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-preview-empty \{/);
  assert.match(
    stylesSource,
    /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form,\s*\.fitting-source-modal-form \.fitting-source-main-grid,\s*\.fitting-source-modal-form \.fitting-form-grid-offer,\s*\.fitting-source-modal-form \.fitting-source-field,\s*\.fitting-source-modal-form \.fitting-source-url-field,\s*\.fitting-source-modal-form \.toggle-label \{\s*grid-template-columns: minmax\(0, 1fr\);/,
  );
});
