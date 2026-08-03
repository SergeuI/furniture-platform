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
  assert.equal(source.includes("mounting-node-toolbar-breadcrumb"), false);
  assert.equal(source.includes("mounting-node-breadcrumb"), false);
  assert.equal(source.includes("Mounting nodes navigation"), false);
  assert.equal(detailHeaderSource.includes("mounting-node-toolbar-breadcrumb"), false);
  assert.equal(detailHeaderSource.includes("mounting-node-breadcrumb"), false);
  assert.equal(detailHeaderSource.includes("<h3>"), false);
  assert.equal(source.includes("onOpenMountingNodeDetail"), true);
  assert.equal(source.includes("onCloseMountingNodeDetail"), true);
  assert.equal(source.includes("listRequestToken"), true);
  assert.equal(source.includes("listRequestTokenRef"), true);
  assert.equal(source.includes("handleSelectNode(nodeId)"), true);
  assert.equal(source.includes("handleBackToList()"), true);
  assert.equal(source.includes("setMountingNodesViewMode(\"list\")"), true);
  assert.equal(source.includes("mounting-node-card-type"), true);
  assert.equal(source.includes("mounting-node-card-layout"), true);
  assert.equal(source.includes("mounting-node-row-layout"), true);
  assert.equal(source.includes("mounting-node-card-visuals"), true);
  assert.equal(source.includes("mounting-node-row-visuals"), true);
  assert.equal(source.includes("mounting-node-card-actions"), true);
  assert.equal(source.includes("mounting-node-row-actions"), true);
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

  const cardVisualsStart = source.indexOf('<div className="mounting-node-card-visuals">');
  const rowVisualsStart = source.indexOf('<div className="mounting-node-row-visuals">');
  const cardGalleryStart = source.indexOf('{renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById)}', cardVisualsStart);
  const cardActionsStart = source.indexOf('{renderNodeCardActions(', cardVisualsStart);
  const rowGalleryStart = source.indexOf('{renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById)}', rowVisualsStart);
  const rowActionsStart = source.indexOf('<div className="mounting-node-row-actions">', rowVisualsStart);

  assert.equal(cardVisualsStart >= 0 && cardGalleryStart >= 0 && cardActionsStart >= 0, true);
  assert.equal(rowVisualsStart >= 0 && rowGalleryStart >= 0 && rowActionsStart >= 0, true);
  assert.equal(cardGalleryStart < cardActionsStart, true);
  assert.equal(rowGalleryStart < rowActionsStart, true);
});

test("toolbar breadcrumb for mounting nodes uses stable App primitives", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("catalogHolesDetailOpen"), true);
  assert.equal(source.includes("catalogHolesBreadcrumbNodeId"), true);
  assert.equal(source.includes("catalogHolesBreadcrumbNodeName"), true);
  assert.equal(source.includes("catalogHolesListRequestToken"), true);
  assert.equal(source.includes("handleOpenMountingNodeEditor"), true);
  assert.equal(source.includes("handleOpenCatalogHolesDetail"), true);
  assert.equal(source.includes("handleCloseCatalogHolesDetail"), true);
  assert.equal(source.includes("handleCatalogHolesToolbarListClick"), true);
  assert.equal(source.includes("renderCatalogHolesToolbarBreadcrumb("), true);
  assert.equal(source.includes("getCatalogHolesToolbarBreadcrumbItems()"), true);
  assert.equal(source.includes("if (catalogHolesDetailOpen)"), true);
  assert.equal(source.includes("setCatalogHolesDetailOpen(true)"), true);
  assert.equal(source.includes("setCatalogHolesDetailOpen(false)"), true);
  assert.equal(source.includes("mounting-node-toolbar-breadcrumb"), true);
  assert.equal(source.includes("Створення вузла"), true);
  assert.equal(source.includes("Отвори та 3D"), true);
  assert.equal(source.includes("onNavigationChange"), false);
  assert.equal(source.includes("catalogHolesNavigationState"), false);
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

test("mounting nodes tile and list layouts keep the responsive grid contract in CSS", () => {
  const sourcePath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes(".settings-grid {"), true);
  assert.equal(source.includes(".settings-grid.mounting-nodes-grid {"), true);
  assert.equal(
    source.indexOf(".settings-grid.mounting-nodes-grid {") > source.indexOf(".settings-grid {\n  display: grid;"),
    true,
  );
  assert.equal(source.includes("grid-template-columns: repeat(3, minmax(0, 1fr));"), true);
  assert.equal(source.includes("@media (max-width: 1450px) {"), true);
  assert.equal(source.includes("grid-template-columns: repeat(2, minmax(0, 1fr));"), true);
  assert.equal(source.includes("@media (max-width: 760px) {"), true);
  assert.equal(source.includes("grid-template-columns: 1fr;"), true);
  assert.equal(source.includes(".mounting-nodes-list {"), true);
  assert.equal(source.includes("display: flex;"), true);
  assert.equal(source.includes("flex-direction: column;"), true);
});
