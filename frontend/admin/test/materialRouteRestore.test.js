import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("materials route survives hard reload and does not fall back to fittings", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(appPath, "utf8");

  assert.match(source, /catalogMaterials: "catalog-materials"/);
  assert.match(
    source,
    /const \[activeView, setActiveView\] = useState\(\s*\(\) => initialAdminRoute\.view \|\| normalizeCatalogView\(localStorage\.getItem\(ACTIVE_VIEW_STORAGE_KEY\) \|\| "home"\),\s*\);/,
  );
  assert.match(
    source,
    /if \(section === ADMIN_MOUNTING_NODES_SECTION\) \{[\s\S]*view: "catalogHoles",[\s\S]*\}/,
  );
  assert.match(
    source,
    /const mappedView = ADMIN_VIEW_BY_SECTION\[section\];[\s\S]*return \{[\s\S]*view: mappedView,[\s\S]*\};/,
  );
  assert.match(
    source,
    /return \{[\s\S]*view: "home",[\s\S]*\};\s*\n\}/,
  );
  assert.match(
    source,
    /function openMaterialCatalogRoot\(\) \{[\s\S]*updateAdminHistory\(\{\s*view: "catalogMaterials",\s*\}\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /function openMaterialCategoryCatalog\(categoryCode\) \{[\s\S]*updateAdminHistory\(\{\s*view: "catalogMaterials",\s*\}\);[\s\S]*\}/,
  );
  assert.match(source, /function openFittingCatalogRoot\(\) \{[\s\S]*switchView\("catalogFittings"\);[\s\S]*\}/);
  assert.match(source, /buildAdminHistoryUrl\(/);
  assert.match(source, /params\.set\("section", ADMIN_SECTION_BY_VIEW\[normalizedView\] \|\| "home"\);/);
});
