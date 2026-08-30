import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("materials route survives hard reload and does not fall back to fittings", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(appPath, "utf8");

  assert.match(source, /catalogMaterials: "catalog-materials"/);
  assert.match(source, /catalogFittings: "catalog-fittings"/);
  assert.match(
    source,
    /const \[materialCategoryFilter, setMaterialCategoryFilter\] = useState\(\s*\(\) =>\s*initialAdminRoute\.view === "catalogMaterials"\s*\?\s*initialAdminRoute\.category \|\| ""\s*:\s*localStorage\.getItem\(MATERIAL_CATEGORY_STORAGE_KEY\) \|\| "",\s*\);/,
  );
  assert.match(
    source,
    /const \[materialCategoryValidationReady, setMaterialCategoryValidationReady\] = useState\(false\);/,
  );
  assert.match(
    source,
    /const \[selectedFittingCategory, setSelectedFittingCategory\] = useState\(\s*\(\) =>\s*initialAdminRoute\.view === "catalogFittings" \|\| initialAdminRoute\.view === "catalogFasteners"\s*\?\s*initialAdminRoute\.category \|\| ""\s*:\s*localStorage\.getItem\(FITTING_CATEGORY_STORAGE_KEY\) \|\| "",\s*\);/,
  );
  assert.match(
    source,
    /if \(section === ADMIN_MOUNTING_NODES_SECTION\) \{[\s\S]*category: null,[\s\S]*view: "catalogHoles",[\s\S]*\}/,
  );
  assert.match(
    source,
    /if \(section === "catalog-materials" \|\| section === "catalog-fittings" \|\| section === "catalog-fasteners"\) \{[\s\S]*category,[\s\S]*view: ADMIN_VIEW_BY_SECTION\[section\],[\s\S]*\}/,
  );
  assert.match(
    source,
    /const mappedView = ADMIN_VIEW_BY_SECTION\[section\];[\s\S]*category: null,[\s\S]*view: mappedView,[\s\S]*\};/,
  );
  assert.match(
    source,
    /return \{[\s\S]*category: null,[\s\S]*view: "home",[\s\S]*\};\s*\n\}/,
  );
  assert.match(
    source,
    /function openMaterialCatalogRoot\(\) \{[\s\S]*updateAdminHistory\(\{[\s\S]*category: null,[\s\S]*view: "catalogMaterials",[\s\S]*\}\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /function openMaterialCategoryCatalog\(categoryCode\) \{[\s\S]*updateAdminHistory\(\{[\s\S]*category: normalizedCategoryCode,[\s\S]*view: "catalogMaterials",[\s\S]*\}\);[\s\S]*\}/,
  );
  assert.match(source, /function openFittingCategoryCatalog\(categoryCode\) \{[\s\S]*updateAdminHistory\(\{[\s\S]*category: normalizedCategoryCode,[\s\S]*view: nextFittingView,[\s\S]*\}\);[\s\S]*\}/);
  assert.match(source, /function openFittingCatalogRoot\(\) \{[\s\S]*switchView\(activeView === "catalogFasteners" \? "catalogFasteners" : "catalogFittings"\);[\s\S]*\}/);
  assert.match(source, /buildAdminHistoryUrl\(/);
  assert.match(source, /params\.set\("category", normalizedCategory\);/);
  assert.match(source, /setMaterialCategoryValidationReady\(true\);/);
  assert.match(
    source,
    /if \(!isCatalogMaterialsView \|\| materialsCatalogLoading \|\| !materialCategoryValidationReady\) \{\s*return;\s*\}/,
  );
  assert.match(source, /setMaterialCategoryFilter\(nextMaterialCategoryFilter\);/);
  assert.match(source, /setSelectedFittingCategory\(nextFittingCategory\);/);
  assert.match(source, /replace: true/);
});
