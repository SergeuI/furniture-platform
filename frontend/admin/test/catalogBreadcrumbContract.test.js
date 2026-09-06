import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

const appSource = readFileSync(
  fileURLToPath(new URL("../src/App.jsx", import.meta.url)),
  "utf8",
);
const breadcrumbSource = readFileSync(
  fileURLToPath(new URL("../src/components/CatalogBreadcrumbTrail.jsx", import.meta.url)),
  "utf8",
);

function liveBranch(startMarker, endMarker) {
  const start = appSource.indexOf(startMarker);
  assert.ok(start >= 0, `missing live branch: ${startMarker}`);
  const end = endMarker
    ? appSource.indexOf(endMarker, start + startMarker.length)
    : appSource.length;
  assert.ok(end > start, `missing branch boundary: ${endMarker}`);
  return appSource.slice(start, end);
}

function assertDirectChildBreadcrumb(branch, currentLabelExpression) {
  assert.match(branch, /<CatalogBreadcrumbTrail[\s\S]*label: t\.catalog/);
  assert.match(branch, /onClick: \(\) => switchView\("catalogHub"\)/);
  assert.match(branch, /current: true[\s\S]*label: /);
  assert.match(branch, new RegExp(currentLabelExpression));
  const currentItemStart = branch.indexOf("current: true");
  const currentItemEnd = branch.indexOf("}", currentItemStart);
  assert.ok(currentItemStart >= 0 && currentItemEnd > currentItemStart);
  assert.doesNotMatch(branch.slice(currentItemStart, currentItemEnd), /onClick:/);
}

test("catalog-manual live route renders the complete direct-child breadcrumb", () => {
  const branch = liveBranch("isCatalogManualView ? (");

  assertDirectChildBreadcrumb(branch, String.raw`label: t\.catalogManual`);
  assert.doesNotMatch(branch, /<h3>\{t\.catalogManual\}<\/h3>/);
  assert.match(breadcrumbSource, /export default function CatalogBreadcrumbTrail/);
});

test("Catalog Hub direct child live branches use the canonical breadcrumb contract", () => {
  const directChildren = [
    ["isCatalogEdgesView ? (", ") : isCatalogMaterialCategoriesView ?", String.raw`label: language === "uk" \? "Крайки" : "Edges"`],
    ["isCatalogFittingsView || isCatalogFastenersView ? (", ") : isCatalogBundlesView &&", String.raw`label: t\.catalogFittings`],
    ["isCatalogBundlesView && activeView === \"catalogBundles\" ? (", ") : isCatalogServiceRulesView", String.raw`label: t\.fittingBundlesTitle`],
    ["isCatalogServiceRulesView ? (", ") : isCatalogValuesView", String.raw`label: t\.holeServiceRulesTitle`],
    ["isCatalogValuesView ? (", ") : isCatalogViyarView", String.raw`label: t\.catalogValues`],
    ["isCatalogViyarView ? (", ") : isCatalogManualView", String.raw`label: t\.viyarServicesTitle`],
    ["isCatalogManualView ? (", "", String.raw`label: t\.catalogManual`],
    ["isCatalogMaterialsView ? (", ") : isCatalogFittingManufacturersView ||", String.raw`label: t\.catalogMaterials`],
  ];

  for (const [start, end, currentLabel] of directChildren) {
    assertDirectChildBreadcrumb(liveBranch(start, end), currentLabel);
  }
});

test("catalog hub remains a root page without a self-breadcrumb", () => {
  const hubBranch = liveBranch("isCatalogHubView ? (", ") : isCatalogEdgesView");

  assert.match(hubBranch, /<h3>\{t\.catalog\}<\/h3>/);
  assert.doesNotMatch(hubBranch, /<CatalogBreadcrumbTrail/);
});
