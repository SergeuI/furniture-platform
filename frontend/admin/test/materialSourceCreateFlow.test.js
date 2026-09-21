import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("material source mode uses url-first flow with optional article fallback", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const sourceModeStart = appSource.indexOf('materialCreateMode === "source" ? (');
  const sourceModeEnd = appSource.indexOf(') : (', sourceModeStart);
  const sourceModeSource = sourceModeStart >= 0 && sourceModeEnd > sourceModeStart
    ? appSource.slice(sourceModeStart, sourceModeEnd)
    : appSource;

  assert.match(appSource, /const \[materialCreateMode, setMaterialCreateMode\] = useState\("source"\);/);
  assert.match(appSource, /const \[newMaterialImportRecommendedEdges, setNewMaterialImportRecommendedEdges\] = useState\(true\);/);
  assert.match(sourceModeSource, /materialCreateMode === "source" \? \(/);
  assert.match(appSource, /Артикул, якщо немає прямого URL/);
  assert.match(appSource, /Посилання на товар/);
  assert.match(appSource, /Місто для ціни \/ наявності/);
  assert.match(appSource, /Знайти та додати рекомендовані крайки/);
  assert.match(appSource, /disabled=\{!newMaterialSourceUrl\.trim\(\) \|\| !newMaterialSourceUrl\.toLowerCase\(\)\.includes\("viyar\.ua"\)\}/);
  assert.match(appSource, /Доступно для матеріалів VIYAR/);
  assert.match(appSource, /import_recommended_edges: isSourceMode \? Boolean\(newMaterialImportRecommendedEdges\) : false/);
  assert.match(appSource, /getMaterialImportProgress\(token, importRequestId\)/);
  assert.match(appSource, /window\.setInterval\(\(\) =>/);
  assert.match(appSource, /Шукаємо рекомендовані крайки/);
  assert.match(appSource, /Знайдено \$\{materialImportProgress\.edgeDiscovered\}/);
  assert.match(appSource, /Перевірено \$\{materialImportProgress\.edgeChecked\} з \$\{materialImportProgress\.edgeTotal \?\? materialImportProgress\.edgeDiscovered\}/);
  assert.match(appSource, /Готово до додавання: \$\{materialImportProgress\.edgeParsed\}/);
  assert.match(appSource, /Не вдалося отримати: \$\{materialImportProgress\.edgeFailed\}/);
  assert.match(appSource, /Потребують перевірки: \$\{materialImportProgress\.edgeNeedsReview\}/);
  assert.match(appSource, /Додаємо \$\{materialImportProgress\.edgePersisting\} крайок/);
  assert.match(appSource, /Створюємо зв'язки: \$\{materialImportProgress\.edgePersisted\}/);
  assert.match(appSource, /Додано рекомендованих крайок: \$\{parsed\} з \$\{total\}/);
  assert.match(appSource, /setNewMaterialManufacturerId\(""\);/);
  assert.match(appSource, /materialCreateMode === "manual" && String\(newMaterialManufacturerId \|\| ""\)\.trim\(\)/);
  assert.match(appSource, /!\s*newMaterialSourceUrl\.trim\(\) \|\| isMaterialCreationBlockedByQuota/);
  assert.match(appSource, /const preloadedGalleryImages = Array\.isArray\(refreshedMaterial\?\.images\)/);
  assert.match(appSource, /updateMaterialImportProgress\("gallery", "done"\);/);
  assert.doesNotMatch(sourceModeSource, /t\.materialManufacturer/);
});

test("recommended edge import is opt-out for VIYAR and reset to checked", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");

  assert.match(appSource, /checked=\{newMaterialImportRecommendedEdges\}/);
  assert.match(appSource, /setNewMaterialImportRecommendedEdges\(true\);\s*setMaterialCreateModalOpen\(true\);/);
  assert.match(appSource, /setNewMaterialImportRecommendedEdges\(true\);/);
  assert.match(appSource, /import_recommended_edges: isSourceMode \? Boolean\(newMaterialImportRecommendedEdges\) : false/);
  assert.match(appSource, /formatRecommendedEdgesIncompleteMessage\(progress\)/);
  assert.match(appSource, /completed_with_warnings/);
});

test("material source create completes without a gallery request", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const createStart = appSource.indexOf("async function handleImportMaterial(event) {");
  const createEnd = appSource.indexOf("async function handleEdgeCreateSubmit(event)", createStart);
  const createSource = createStart >= 0 && createEnd > createStart
    ? appSource.slice(createStart, createEnd)
    : appSource;

  assert.doesNotMatch(createSource, /refreshMaterialGallery\(token, refreshedMaterialId\)/);
  assert.match(createSource, /updateMaterialImportProgress\("gallery", "done"\);/);
  assert.match(createSource, /await loadMaterialsCatalog\(token\);/);
  assert.match(createSource, /closeMaterialCreateModal\(\);/);
  assert.match(createSource, /if \(progressResult\.phase === "complete"\)[\s\S]*?closeMaterialCreateModal\(\);/);
});

test("materials catalog uses ownership scopes and the material search placeholder", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const toolbarStart = appSource.indexOf("material-category-toolbar-row");
  const toolbarEnd = appSource.indexOf("materials-catalog-loading-state", toolbarStart);
  const toolbarSource = appSource.slice(toolbarStart, toolbarEnd);

  assert.match(toolbarSource, /placeholder=\{t\.materialSearch\}/);
  assert.match(toolbarSource, /<option value="system">/);
  assert.match(toolbarSource, /<option value="mine">/);
  assert.match(appSource, /ownership_scope: requestedOwnershipScope/);
  assert.match(appSource, /materialSearch: "Search materials"/);
  assert.match(appSource, /materialSearch: "\\u041f\\u043e\\u0448\\u0443\\u043a \\u043c\\u0430\\u0442\\u0435\\u0440\\u0456\\u0430\\u043b\\u0456\\u0432"/);
});
