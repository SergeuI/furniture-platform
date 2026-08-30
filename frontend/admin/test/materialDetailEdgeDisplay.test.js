import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("material detail edge section renders linked edges and keeps the empty state for missing edges", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /getSortedMaterialEdgeItems\(selectedMaterialDetail\)\.length \?\s*\(/);
  assert.match(appSource, /className="material-edge-grid"/);
  assert.match(appSource, /t\.materialEdgeSlotEmpty/);
  assert.match(appSource, /String\(edgeItem\?\.image_url \|\| edgeItem\?\.image \|\| \"\"\)\.trim\(\)/);
  assert.match(appSource, /const canEditEdge = canEditMaterialItem\(user, selectedMaterialDetail\) && Boolean\(getMaterialEdgeSlot\(edgeItem\.edge_key\)\);/);
  assert.match(appSource, /getCanonicalMaterialEdgeItems\(selectedMaterialDetail\)\.length \?\s*\(/);
  assert.match(appSource, /material-canonical-edge-section/);
  assert.match(appSource, /openMaterialEdgeDetails\(edgeItem\)/);
  assert.match(appSource, /material-canonical-edge-selector-modal/);
  assert.match(appSource, /attachMaterialCanonicalEdge/);
  assert.match(appSource, /deleteMaterialCanonicalEdge/);
  assert.match(stylesSource, /\.material-edge-card-head-actions\s*\{\s*[\s\S]*display:\s*flex;[\s\S]*flex-direction:\s*row;[\s\S]*flex-wrap:\s*nowrap;[\s\S]*width:\s*max-content;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-edge-card-head-actions > button\s*\{\s*[\s\S]*width:\s*auto;[\s\S]*flex:\s*0 0 auto;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-edge-card-head-actions \.danger-button\s*\{/);
  assert.doesNotMatch(stylesSource, /\.material-canonical-edge-card-head-actions/);
});
