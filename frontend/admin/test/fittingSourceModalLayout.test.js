import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting source modal keeps the form compact and scrollable", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /className="confirm-modal fitting-source-modal"/);
  assert.match(appSource, /className="fitting-source-modal-form"/);
  assert.match(appSource, /fitting-source-span-full/);
  assert.match(appSource, /className="fitting-source-field"/);
  assert.match(stylesSource, /\.fitting-source-modal \{\s*display: flex;[\s\S]*max-height: min\(90vh, calc\(100vh - 32px\)\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \{\s*display: grid;[\s\S]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);[\s\S]*overflow: auto;/);
  assert.match(stylesSource, /\.fitting-source-span-full \{\s*grid-column: 1 \/ -1;\s*\}/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-form-grid-offer \{\s*gap: 8px;\s*grid-template-columns: minmax\(0, 1fr\);\s*\}/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-form-grid-offer > label \{\s*align-items: center;[\s\S]*grid-template-columns: minmax\(180px, 220px\) minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-form-grid-offer > \.toggle-label \{\s*display: flex;[\s\S]*flex-direction: row-reverse;/);
  assert.match(stylesSource, /@media \(max-width: 760px\) \{[\s\S]*\.fitting-source-modal-form,\s*\.fitting-source-modal-form \.fitting-form-grid-offer,\s*\.fitting-source-modal-form \.fitting-form-grid-offer > label \{\s*grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-form-grid-offer > \.toggle-label \{\s*display: flex;[\s\S]*flex-direction: row;\s*justify-content: flex-start;/);
});
