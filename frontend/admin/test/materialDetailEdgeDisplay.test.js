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
  assert.match(appSource, /recommendedMaterialEdges\.length \?\s*\(/);
  assert.match(appSource, /getMaterialEdgeManufacturerPriority/);
  assert.ok(
    appSource.indexOf("const manufacturerDelta") < appSource.indexOf("const thicknessDelta"),
    "manufacturer priority should sort before thickness",
  );
  assert.match(appSource, /manufacturer === "rehau"/);
  assert.match(appSource, /manufacturer === "hranipex"/);
  assert.match(appSource, /manufacturer === "maag"/);
  assert.match(appSource, /thickness <= 0\.6/);
  assert.match(appSource, /materialEdgesExpanded/);
  assert.match(appSource, /visibleRecommendedMaterialEdges/);
  assert.match(appSource, /seenManufacturers/);
  assert.match(appSource, /function isKnownEdgePlaceholderImage/);
  assert.match(appSource, /function EdgeImage/);
  assert.match(appSource, /onError=\{\(\) => setImageFailed\(true\)\}/);
  assert.match(appSource, /Фото відсутнє/);
  assert.match(appSource, /role="img" aria-label=\{placeholderLabel\}/);
  assert.match(appSource, /<EdgeImage/);
  assert.match(appSource, /image: edgeItem\.material_image \|\| ""/);
  assert.match(appSource, /image_source_url: edgeItem\.material_image \|\| ""/);
  assert.match(appSource, /placeholderClassName="edge-detail-image-placeholder"/);
  assert.match(appSource, /showPlaceholderIcon/);
  assert.match(appSource, /Рекомендована/);
  assert.match(appSource, /materialDetailsScrollRef/);
  assert.match(appSource, /className="material-details-fixed-header"/);
  assert.match(appSource, /className="material-details-main-section"/);
  assert.ok(
    appSource.indexOf("className=\"material-details-main-section\"") < appSource.indexOf("className=\"material-details-layout\""),
    "bounded material section should contain the main layout",
  );
  assert.match(appSource, /material-canonical-edge-section/);
  assert.match(appSource, /openMaterialEdgeDetails\(edgeItem\)/);
  assert.match(appSource, /material-canonical-edge-selector-modal/);
  assert.match(appSource, /attachMaterialCanonicalEdge/);
  assert.match(appSource, /deleteMaterialCanonicalEdge/);
  assert.match(stylesSource, /\.material-edge-card-head-actions\s*\{\s*[\s\S]*display:\s*flex;[\s\S]*flex-direction:\s*row;[\s\S]*flex-wrap:\s*nowrap;[\s\S]*width:\s*max-content;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-edge-card-head-actions > button\s*\{\s*[\s\S]*width:\s*auto;[\s\S]*flex:\s*0 0 auto;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-edge-card-head-actions \.danger-button\s*\{/);
  assert.match(stylesSource, /\.material-edge-card-preview \.material-card-placeholder\s*\{[\s\S]*min-height:\s*64px;[\s\S]*width:\s*100%;[\s\S]*\}/);
  assert.match(stylesSource, /\.fitting-details-media \.edge-detail-image-placeholder\s*\{[\s\S]*aspect-ratio:\s*1 \/ 1;[\s\S]*min-height:\s*280px;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-details-fixed-header\s*\{[\s\S]*position:\s*sticky;[\s\S]*top:\s*0;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-details-main-section\s*\{[\s\S]*gap:\s*18px;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-details-main-section\s*\{[\s\S]*background:\s*#ffffff;[\s\S]*margin:\s*-20px -20px 0;[\s\S]*padding:\s*20px 20px 0;[\s\S]*position:\s*relative;[\s\S]*z-index:\s*1;[\s\S]*\}/);
  assert.match(stylesSource, /\.material-details-fixed-header\s*\{\s*position:\s*static;\s*\}/);
  assert.doesNotMatch(stylesSource, /\.material-canonical-edge-card-head-actions/);
});
