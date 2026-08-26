import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("material detail edge section renders linked edges and keeps the empty state for missing edges", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");

  assert.match(appSource, /getSortedMaterialEdgeItems\(selectedMaterialDetail\)\.length \?\s*\(/);
  assert.match(appSource, /className="material-edge-grid"/);
  assert.match(appSource, /t\.materialEdgeSlotEmpty/);
  assert.match(appSource, /String\(edgeItem\?\.image_url \|\| edgeItem\?\.image \|\| \"\"\)\.trim\(\)/);
  assert.match(appSource, /const canEditEdge = canEditMaterialItem\(user, selectedMaterialDetail\) && Boolean\(getMaterialEdgeSlot\(edgeItem\.edge_key\)\);/);
});
