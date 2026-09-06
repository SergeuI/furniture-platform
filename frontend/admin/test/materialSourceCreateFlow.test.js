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
  assert.match(sourceModeSource, /materialCreateMode === "source" \? \(/);
  assert.match(appSource, /Артикул, якщо немає прямого URL/);
  assert.match(appSource, /Посилання на товар/);
  assert.match(appSource, /Місто для ціни \/ наявності/);
  assert.match(appSource, /setNewMaterialManufacturerId\(""\);/);
  assert.match(appSource, /materialCreateMode === "manual" && String\(newMaterialManufacturerId \|\| ""\)\.trim\(\)/);
  assert.match(appSource, /!\s*newMaterialSourceUrl\.trim\(\) \|\| isMaterialCreationBlockedByQuota/);
  assert.match(appSource, /const preloadedGalleryImages = Array\.isArray\(refreshedMaterial\?\.images\)/);
  assert.match(appSource, /updateMaterialImportProgress\("gallery", "done"\);/);
  assert.doesNotMatch(sourceModeSource, /t\.materialManufacturer/);
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
});
