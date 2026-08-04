import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

function loadBuildNodeEditorContextFromSource() {
  const sourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const source = readFileSync(sourcePath, "utf8");
  const helperPath = fileURLToPath(new URL("../src/mountingNodesEditor.js", import.meta.url));
  const helperSource = readFileSync(helperPath, "utf8");
  const buildNodeEditorContextSource = source.slice(
    source.indexOf("function buildNodeEditorContext(nodeDetail, fallbackNodeId = \"\") {"),
    source.indexOf("function buildNodeReturnState({"),
  );
  const helperBlockSource = helperSource.slice(
    helperSource.indexOf("function normalizeText(value) {"),
    helperSource.indexOf("function buildTemplatePayload({"),
  );

  if (!buildNodeEditorContextSource || !helperBlockSource) {
    throw new Error("Unable to isolate the mounting node editor helper block.");
  }

  const combinedSource = [
    helperBlockSource.replace("export function resolveMountingNodeEditorContext", "function resolveMountingNodeEditorContext"),
    buildNodeEditorContextSource.replace("export function buildNodeEditorContext", "function buildNodeEditorContext"),
  ].join("\n");
  return new Function(`${combinedSource}; return buildNodeEditorContext;`)();
}

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
  assert.equal(source.includes("onClick={() => handleOpenEditor()}"), true);
  assert.equal(source.includes("onClick={handleOpenEditor}"), false);
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
  assert.equal(source.includes("thumbnailRequestGenerationRef"), true);
  assert.equal(source.includes("buildMountingNodeThumbnailLoadPlan"), true);
  assert.equal(source.includes("buildMountingNodeThumbnailState"), true);
  assert.equal(source.includes("isCurrentMountingNodeThumbnailRequest"), true);
  assert.equal(source.includes("Open editor and 3D"), true);
  assert.equal(source.includes("Delete mounting node"), true);
  assert.equal(source.includes("mounting-node-detail-variant-portal"), true);
  assert.equal(source.includes("resolveMountingNodeEditorContext"), true);
  assert.equal(source.includes("findNearestVerticalScrollAncestor"), true);
  assert.equal(source.includes("scrollNearestVerticalAncestorBy"), true);
  assert.equal(source.includes("calculateVariantDropdownScrollDelta"), true);
  assert.equal(source.includes("variantDropdownPreparing"), true);
  assert.equal(source.includes("selectedNodePrimaryTemplate?.template"), true);
  assert.equal(source.includes("selectedTemplateSource"), true);
  assert.equal(source.includes("setSelectedNodeVariantKey(selectedNodeCurrentVariantKey);"), true);

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

test("mounting nodes panel builds editor context from the full detail template link", () => {
  const buildNodeEditorContext = loadBuildNodeEditorContextFromSource();
  const nodeDetail = {
    id: 9,
    name: "петля",
    templates: [
      {
        id: 13,
        template_id: 7480,
        is_default: true,
        template: {
          id: 7480,
          fitting_id: 42,
          mounting_variant_key: "angled_two_planes",
          points: [],
        },
      },
    ],
    items: [
      {
        fitting_id: 42,
        quantity: 1,
      },
    ],
  };

  assert.deepEqual(buildNodeEditorContext(nodeDetail), {
    mountingNodeId: "9",
    nodeCode: "",
    nodeName: "петля",
    fittingId: "42",
    templateId: "7480",
    mountingVariantKey: "angled_two_planes",
    nodeDetail,
    points: [],
  });
});

test("mounting nodes panel builds editor context from legacy flat template objects", () => {
  const buildNodeEditorContext = loadBuildNodeEditorContextFromSource();
  const nodeDetail = {
    id: 11,
    code: "legacy-node",
    name: "Legacy node",
    templates: [
      {
        id: 8800,
        fitting_id: 77,
        mounting_variant_key: "drawer_slides",
        points: [],
      },
    ],
    items: [
      {
        fitting_id: 77,
        quantity: 1,
      },
    ],
  };

  assert.deepEqual(buildNodeEditorContext(nodeDetail), {
    mountingNodeId: "11",
    nodeCode: "legacy-node",
    nodeName: "Legacy node",
    fittingId: "77",
    templateId: "8800",
    mountingVariantKey: "drawer_slides",
    nodeDetail,
    points: [],
  });
});

test("mounting nodes panel keeps the same image extraction contract for grid and list thumbnails", () => {
  const sourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("getFittingDetails(token, fittingId)"), true);
  assert.equal(source.includes("getFittingImageBlob(token, fittingId, primaryImage.id)"), true);
  assert.equal(source.includes("thumbnailRequestGenerationRef"), true);
  assert.equal(source.includes("buildMountingNodeThumbnailLoadPlan"), true);
  assert.equal(source.includes("buildMountingNodeThumbnailState"), true);
  assert.equal(source.includes("isCurrentMountingNodeThumbnailRequest"), true);
  assert.equal(source.includes('buildMountingNodeThumbnailState("loaded", currentGeneration, imageUrl)'), true);
  assert.equal(source.includes("renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById)"), true);
  assert.equal(source.includes("No images"), true);
  assert.equal(source.includes("getNodeEditorTemplateSource"), true);
  assert.equal(source.includes("actualTemplate"), true);
  assert.equal(source.includes("templateLink"), true);
  assert.equal(source.includes("points,"), true);
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
