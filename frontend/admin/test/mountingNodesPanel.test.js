import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("mounting nodes panel keeps the DETAIL white panel free of breadcrumb markup", () => {
  const sourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const source = readFileSync(sourcePath, "utf8");
  const detailHeaderStart = source.indexOf('className="catalog-page-header mounting-node-detail-header"');
  const detailHeaderEnd = source.indexOf('<div className="settings-grid mounting-node-detail-grid">', detailHeaderStart);
  const detailHeaderSource =
    detailHeaderStart >= 0 && detailHeaderEnd > detailHeaderStart ? source.slice(detailHeaderStart, detailHeaderEnd) : "";

  assert.equal(source.includes("MountingNodesPanelRefined"), true);
  assert.equal(source.includes("mountingNodesViewMode"), true);
  assert.equal(source.includes("onNavigationChange"), false);
  assert.equal(source.includes("navigationState"), false);
  assert.equal(source.includes("renderMountingNodesBreadcrumb("), false);
  assert.equal(source.includes("mounting-node-breadcrumb"), false);
  assert.equal(source.includes("Mounting nodes navigation"), false);
  assert.equal(source.includes("mounting-node-ownership-badge"), false);
  assert.equal(detailHeaderSource.includes("mounting-node-ownership-badge"), false);
  assert.equal(detailHeaderSource.includes("mounting-node-badges"), false);
  assert.equal(detailHeaderSource.includes("renderMountingNodesBreadcrumb("), false);
  assert.equal(detailHeaderSource.includes("<h3>"), false);
  assert.equal(source.includes("mounting-node-card-type"), true);
  assert.equal(source.includes("mounting-node-card-layout"), true);
  assert.equal(source.includes("mounting-node-row-layout"), true);
  assert.equal(source.includes("mounting-node-item-gallery"), true);
  assert.equal(source.includes("getFittingDetails"), true);
  assert.equal(source.includes("getFittingImageBlob"), true);
  assert.equal(source.includes("Open editor and 3D"), true);
  assert.equal(source.includes("Delete mounting node"), true);
  assert.equal(source.includes("mounting-node-detail-variant-portal"), true);
  assert.equal(source.includes("findNearestVerticalScrollAncestor"), true);
  assert.equal(source.includes("scrollNearestVerticalAncestorBy"), true);
  assert.equal(source.includes("calculateVariantDropdownScrollDelta"), true);
  assert.equal(source.includes("variantDropdownPreparing"), true);
});

test("toolbar heading for mounting nodes stays simple after the rollback", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("isCatalogHolesView"), true);
  assert.equal(source.includes("t.holeTabTitle"), true);
  assert.equal(source.includes("catalogHolesNavigationState"), false);
  assert.equal(source.includes("getCatalogHolesToolbarBreadcrumbItems()"), false);
  assert.equal(source.includes("onNavigationChange={setCatalogHolesNavigationState}"), false);
});

test("mounting nodes panel keeps the same image extraction contract for grid and list thumbnails", () => {
  const sourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("getFittingDetails(token, fittingId)"), true);
  assert.equal(source.includes("getFittingImageBlob(token, fittingId, primaryImage.id)"), true);
  assert.equal(source.includes("fittingThumbnailStateById[fittingId]"), true);
  assert.equal(source.includes('status: "loaded"'), true);
  assert.equal(source.includes("renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById)"), true);
  assert.equal(source.includes("No images"), true);
});
