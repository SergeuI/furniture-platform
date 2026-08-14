import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("canonical fitting delete uses product ids and refreshes both catalogs", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const apiPath = fileURLToPath(new URL("../src/api.js", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const apiSource = readFileSync(apiPath, "utf8");

  assert.match(apiSource, /export async function deleteFittingProduct\(token, itemId\)/);
  assert.match(apiSource, /\/catalog\/fitting-products\/\$\{encodeURIComponent\(String\(itemId \|\| ""\)\)\}/);

  assert.match(appSource, /function openDeleteCanonicalFittingProductConfirm\(item, sourceItem = null\)/);
  assert.match(appSource, /targetId: item\.id,/);
  assert.match(appSource, /deleteFittingProduct\(token, itemId\)/);
  assert.match(appSource, /Promise\.all\(\[\s*loadFittingsCatalog\(token\),\s*loadCanonicalFittingsCatalog\(token\),\s*\]\)/);
  assert.match(appSource, /openDeleteCanonicalFittingProductConfirm\(item, sourceItem\);/);
  assert.match(appSource, /deleteFittingProduct/);
  assert.doesNotMatch(appSource, /openDeleteCanonicalFittingProductConfirm\(sourceItem\)/);
});
