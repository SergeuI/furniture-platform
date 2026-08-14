import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting source modal rows stay compact and checkbox labels align left", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /className="confirm-modal fitting-source-modal"/);
  assert.match(appSource, /className="fitting-source-modal-form"/);
  assert.match(appSource, /className="toggle-label fitting-source-field"/);
  assert.match(appSource, /className="fitting-source-url-field fitting-source-span-full"/);
  assert.match(appSource, /fitting-source-help-text/);
  assert.match(stylesSource, /\.fitting-source-modal \{\s*display: flex;[\s\S]*gap: 10px;[\s\S]*padding: 16px 16px 14px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \{\s*display: grid;[\s\S]*gap: 10px;[\s\S]*overflow: auto;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-main-grid,\s*\.fitting-source-modal-form \.fitting-form-grid-offer \{\s*display: grid;[\s\S]*gap: 6px;[\s\S]*grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-field,\s*\.fitting-source-modal-form \.fitting-source-url-field,\s*\.fitting-source-modal-form \.toggle-label \{\s*align-items: center;[\s\S]*grid-template-columns: minmax\(180px, 220px\) minmax\(0, 1fr\);[\s\S]*min-height: 36px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.toggle-label > span \{\s*order: 1;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.toggle-label > input\[type="checkbox"\] \{\s*order: 2;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-help-text \{\s*color: #5c6875;[\s\S]*margin-left: 186px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-field > input:not\(\[type="checkbox"\]\):not\(\[type="file"\]\),[\s\S]*padding-bottom: 7px;[\s\S]*padding-top: 7px;/);
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal \{\s*max-height: calc\(100vh - 24px\);[\s\S]*padding: 14px;/);
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form,\s*\.fitting-source-modal-form \.fitting-source-main-grid,\s*\.fitting-source-modal-form \.fitting-form-grid-offer,\s*\.fitting-source-modal-form \.fitting-source-field,\s*\.fitting-source-modal-form \.fitting-source-url-field,\s*\.fitting-source-modal-form \.toggle-label \{\s*grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form \.fitting-source-help-text \{\s*margin-left: 0;/);
});
