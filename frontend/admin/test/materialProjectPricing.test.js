import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { getProjectMaterialPriceRows } from "../src/materialProjectPricing.js";

const appSource = readFileSync(
  fileURLToPath(new URL("../src/App.jsx", import.meta.url)),
  "utf8",
);

test("project picker uses a single supplier price summary row", () => {
  assert.deepEqual(
    getProjectMaterialPriceRows([
      { unit: "лист", currency: "UAH", min_price: 4657.44, max_price: 4657.44, offer_count: 1 },
    ], null),
    [{ key: "UAH:лист:0", priceText: "4657.44", currency: "UAH", unit: "лист" }],
  );
});

test("project picker formats a same-unit price range", () => {
  const rows = getProjectMaterialPriceRows([
    { unit: "лист", currency: "UAH", min_price: 4220, max_price: 4657.44, offer_count: 2 },
  ], null);

  assert.equal(rows[0].priceText, "4220 – 4657.44");
});

test("project picker keeps different units as separate rows", () => {
  const rows = getProjectMaterialPriceRows([
    { unit: "лист", currency: "UAH", min_price: 4220, max_price: 4657.44, offer_count: 2 },
    { unit: "м²", currency: "UAH", min_price: 800, max_price: 850, offer_count: 2 },
  ], null);

  assert.deepEqual(rows.map((row) => `${row.priceText} ${row.currency} / ${row.unit}`), [
    "4220 – 4657.44 UAH / лист",
    "800 – 850 UAH / м²",
  ]);
});

test("project picker falls back to legacy current_price", () => {
  assert.deepEqual(
    getProjectMaterialPriceRows([], 1000),
    [{ key: "legacy", priceText: "1000", currency: "UAH", unit: "" }],
  );
});

test("project picker shows no price when both sources are empty", () => {
  assert.deepEqual(getProjectMaterialPriceRows([], null), []);
});

test("project picker reloads material data when its city context changes", () => {
  assert.match(appSource, /const projectMaterialContextKey = getMaterialCatalogContextKey/);
  assert.match(appSource, /city: activeCity \|\| ""/);
  assert.match(appSource, /materialItemsLoadedContext === projectMaterialContextKey/);
  assert.match(appSource, /activeCity,\s*\n\s*fittingItems\.length/);
});

test("project picker keeps current_price as legacy fallback only", () => {
  const pickerStart = appSource.indexOf("const projectMaterialPickerItems");
  const pickerEnd = appSource.indexOf("const projectHandlePickerItems", pickerStart);
  const pickerSource = appSource.slice(pickerStart, pickerEnd);
  const renderStart = appSource.lastIndexOf('className="project-option-picker-card-price"');
  const renderEnd = appSource.indexOf('className="project-option-picker-card-meta"', renderStart);
  const renderSource = appSource.slice(renderStart, renderEnd);

  assert.match(pickerSource, /getProjectMaterialPriceRows\(item\.price_summary, item\.current_price\)/);
  assert.match(renderSource, /item\.projectPriceRows\?\.length/);
  assert.doesNotMatch(renderSource, /item\.current_price !== null/);
});
