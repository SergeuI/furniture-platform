import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  buildMountingNodeEditorSavePayload,
  canAddMountingNodeEditorPoint,
  getMountingNodeSnapshotPointCount,
  getMountingNodeEditorItemFittingId,
  getMountingNodeEditorItemImageUrl,
  getMountingNodeEditorPointDisplayId,
  getMountingNodeEditorPointDisplayLabel,
  hydrateMountingNodeEditorState,
  resolveActiveMountingNodeVersion,
  resolveMountingNodeEditorContext,
} from "../src/mountingNodesEditor.js";

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
    helperBlockSource.replaceAll("export function", "function"),
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
  assert.equal(source.includes("getMountingNodeCategoryLabel"), true);
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
  assert.equal(source.includes("Archive mounting node"), true);
  assert.equal(source.includes("mounting-node-detail-variant-portal"), true);
  assert.equal(source.includes("resolveMountingNodeEditorContext"), true);
  assert.equal(source.includes("findNearestVerticalScrollAncestor"), true);
  assert.equal(source.includes("scrollNearestVerticalAncestorBy"), true);
  assert.equal(source.includes("calculateVariantDropdownScrollDelta"), true);
  assert.equal(source.includes("variantDropdownPreparing"), true);
  assert.equal(source.includes("selectedNodePrimaryTemplate?.template"), true);
  assert.equal(source.includes("selectedTemplateSource"), true);
  assert.equal(source.includes("setSelectedNodeVariantKey(selectedNodeCurrentVariantKey);"), true);
  assert.equal(source.includes("mounting-node-detail-history-card"), true);
  assert.equal(source.includes("mounting-node-version-list"), true);
  assert.equal(source.includes("getMountingNodeVersionSummary"), true);
  assert.equal(source.includes("mounting-node-detail-version-summary-card"), true);
  assert.equal(source.includes("mounting-node-detail-version-summary-grid"), true);
  assert.equal(source.includes('label={language === "uk" ? "Категорія" : "Category"}'), true);
  assert.equal(source.includes("mounting-node-detail-version-preview-note"), true);
  assert.equal(source.includes("mounting-node-version-item-actions"), true);
  assert.equal(source.includes("Active version"), true);
  assert.equal(source.includes("Version history"), true);
  assert.equal(source.includes("Return to active version"), true);
  assert.equal(source.includes("Edit composition and openings"), true);
  assert.equal(source.includes("Переглянути"), true);

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
  assert.equal(source.includes("shouldHydrateMountingNodeDetail"), true);
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
  assert.equal(source.includes("Редагування вузла"), true);
  assert.equal(source.includes('mode === "editor"'), true);
  assert.equal(source.includes("onNavigationChange"), false);
  assert.equal(source.includes("catalogHolesNavigationState"), false);
});

test("mounting node editor renders a single workspace with one hardware block and no variant block", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");
  const workspaceStart = source.indexOf('<FittingHolesWorkspace className="mounting-node-editor-workspace">');
  const workspaceEnd = source.indexOf("</FittingHolesWorkspace>", workspaceStart);
  const workspaceSource =
    workspaceStart >= 0 && workspaceEnd > workspaceStart ? source.slice(workspaceStart, workspaceEnd) : "";

  assert.equal(workspaceSource.includes("mounting-node-editor-workspace"), true);
  assert.equal(workspaceSource.includes("mounting-node-editor-left-column"), true);
  assert.equal(workspaceSource.includes("mounting-node-editor-right-column"), true);
  assert.equal((workspaceSource.match(/Склад фурнітури/g) || []).length, 1);
  assert.equal((workspaceSource.match(/Варіант кріплення/g) || []).length, 0);
  assert.equal(workspaceSource.includes("holeTabPoints"), true);
  assert.equal(workspaceSource.includes("holeWorkspacePreview3dTitle"), true);
  assert.equal(source.includes("MountingNodesFittingSelectorModal"), true);
  assert.equal(source.includes("Редагування вузла"), true);
  assert.equal(source.includes("Зберегти нову версію"), true);
  assert.equal(source.includes('isOpen={mountingNodeEditorSelectorOpen}'), true);
  assert.equal(source.includes("mountingNodeEditorHasChanges"), true);
  assert.equal(source.includes("mountingNodeEditorCanAddPoint"), true);
  assert.equal(source.includes("disabled={!mountingNodeEditorCanAddPoint}"), true);
  assert.equal(source.includes("!mountingNodeEditorHasChanges ||"), true);
  assert.equal(
    source.includes("const mountingNodeEditorPointsLoadedForSave = isMountingNodeEditorMode ? true : holeTemplateDetailsLoaded;"),
    true,
  );
  assert.equal(source.includes("selectedTemplate: mountingNodeEditorSelectedTemplateForSave,"), true);
  assert.equal(source.includes("pointsLoaded: mountingNodeEditorPointsLoadedForSave,"), true);
  assert.equal(source.includes("const holeDisplayLabel = getMountingNodeEditorPointDisplayLabel(hole, index);"), true);
  assert.equal(workspaceSource.includes("#{hole.id}"), false);
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

test("mounting node editor context prefers the active version snapshot over live points", () => {
  const nodeDetail = {
    id: 13,
    code: "mounting-node-test",
    name: "Тест",
    items: [
      {
        fitting_id: 42,
        quantity: 2,
      },
    ],
    templates: [
      {
        id: 11,
        template_id: 7480,
        is_default: true,
        template: {
          id: 7480,
          fitting_id: 42,
          mounting_variant_key: "surface_mount",
          points: [
            {
              id: 112,
              template_id: 7480,
              diameter_mm: 5,
              depth_mm: 13,
            },
          ],
        },
      },
    ],
    versions: [
      {
        id: 91,
        version_number: 1,
        is_current: true,
        snapshot: {
          id: 13,
          code: "mounting-node-test",
          name: "Тест",
          items: [
            {
              fitting_id: 42,
              quantity: 2,
            },
          ],
          templates: [
            {
              id: 11,
              template_id: 7480,
              is_default: true,
              template: {
                id: 7480,
                fitting_id: 42,
                mounting_variant_key: "surface_mount",
                points: [],
              },
            },
          ],
        },
      },
    ],
  };

  const context = resolveMountingNodeEditorContext(nodeDetail);

  assert.equal(context?.mountingNodeId, "13");
  assert.equal(context?.templateId, "7480");
  assert.equal(context?.points.length, 0);
  assert.equal(context?.nodeDetail.templates[0].template.points.length, 0);
  assert.equal(context?.nodeDetail.versions[0].version_number, 1);
});

test("mounting node helpers choose the active version snapshot and keep snapshot points stable", () => {
  const nodeDetail = {
    id: 13,
    code: "mounting-node-test",
    name: "Тест",
    items: [
      {
        fitting_id: 42,
        quantity: 2,
      },
    ],
    templates: [
      {
        id: 11,
        template_id: 7480,
        is_default: true,
        template: {
          id: 7480,
          fitting_id: 42,
          mounting_variant_key: "surface_mount",
          points: [],
        },
      },
    ],
    versions: [
      {
        id: 90,
        version_number: 1,
        snapshot: {
          id: 13,
          items: [
            {
              fitting_id: 42,
              quantity: 2,
            },
          ],
          templates: [
            {
              id: 11,
              template_id: 7480,
              is_default: true,
              template: {
                id: 7480,
                fitting_id: 42,
                mounting_variant_key: "surface_mount",
                points: [],
              },
            },
          ],
        },
      },
      {
        id: 91,
        version_number: 2,
        is_current: true,
        snapshot: {
          id: 13,
          items: [
            {
              fitting_id: 42,
              quantity: 2,
            },
          ],
          templates: [
            {
              id: 11,
              template_id: 7480,
              is_default: true,
              template: {
                id: 7480,
                fitting_id: 42,
                mounting_variant_key: "surface_mount",
                points: [
                  {
                    id: 112,
                    template_id: 7480,
                    diameter_mm: 5,
                    depth_mm: 13,
                  },
                ],
              },
            },
          ],
        },
      },
    ],
  };

  const activeVersion = resolveActiveMountingNodeVersion(nodeDetail);
  const context = resolveMountingNodeEditorContext(nodeDetail);

  assert.equal(activeVersion?.version_number, 2);
  assert.equal(getMountingNodeSnapshotPointCount(activeVersion?.snapshot), 1);
  assert.equal(context?.points.length, 1);
  assert.equal(context?.points[0]?.id, 112);
  assert.equal(context?.nodeDetail.templates[0].template.points.length, 1);
});

test("mounting node hydration helper keeps the canonical editor state aligned across draft, points, and template selection", () => {
  const nodeDetail = {
    id: 13,
    code: "mounting-node-test",
    name: "Тест",
    items: [
      {
        fitting_id: 42,
        quantity: 2,
      },
    ],
    templates: [
      {
        id: 11,
        template_id: 7480,
        is_default: true,
        template: {
          id: 7480,
          fitting_id: 42,
          mounting_variant_key: "surface_mount",
          points: [],
        },
      },
    ],
    versions: [
      {
        id: 90,
        version_number: 1,
        snapshot: {
          id: 13,
          items: [
            {
              fitting_id: 42,
              quantity: 2,
            },
          ],
          templates: [
            {
              id: 11,
              template_id: 7480,
              is_default: true,
              template: {
                id: 7480,
                fitting_id: 42,
                mounting_variant_key: "surface_mount",
                points: [],
              },
            },
          ],
        },
      },
      {
        id: 91,
        version_number: 2,
        is_current: true,
        snapshot: {
          id: 13,
          items: [
            {
              fitting_id: 42,
              quantity: 2,
            },
          ],
          templates: [
            {
              id: 11,
              template_id: 7480,
              is_default: true,
              template: {
                id: 7480,
                fitting_id: 42,
                mounting_variant_key: "surface_mount",
                points: [
                  {
                    id: 112,
                    template_id: 7480,
                    diameter_mm: 5,
                    depth_mm: 13,
                  },
                ],
              },
            },
          ],
        },
      },
    ],
  };

  const hydration = hydrateMountingNodeEditorState(nodeDetail);

  assert.equal(hydration?.activeVersion?.version_number, 2);
  assert.equal(hydration?.context?.mountingNodeId, "13");
  assert.equal(hydration?.context?.templateId, "7480");
  assert.equal(hydration?.points.length, 1);
  assert.equal(hydration?.points[0]?.id, 112);
  assert.equal(hydration?.templateItems.length, 1);
  assert.equal(hydration?.selectedTemplateLink?.template?.points.length, 1);
});

test("mounting node helpers fall back to the highest version number when no current version is marked", () => {
  const nodeDetail = {
    id: 13,
    versions: [
      {
        id: 90,
        version_number: 1,
        snapshot: {
          templates: [],
        },
      },
      {
        id: 91,
        version_number: 2,
        snapshot: {
          templates: [],
        },
      },
    ],
  };

  assert.equal(resolveActiveMountingNodeVersion(nodeDetail)?.version_number, 2);
});

test("mounting node editor save payload omits temporary draft point ids", () => {
  const context = {
    mountingNodeId: "13",
    templateId: "7480",
    nodeDetail: {
      code: "mounting-node-test",
      name: "Тест",
      is_active: true,
      items: [
        {
          fitting_id: 42,
          quantity: 2,
        },
      ],
      templates: [
        {
          template_id: 7480,
          is_default: true,
          template: {
            id: 7480,
            fitting_id: 42,
            mounting_variant_key: "surface_mount",
            points: [],
          },
        },
      ],
    },
  };

  const payload = buildMountingNodeEditorSavePayload({
    context,
    points: [
      {
        id: -123,
        template_id: 7480,
        diameter_mm: 5,
        depth_mm: 13,
        x_mm: 0,
        y_mm: 0,
        z_mm: 0,
        quantity: 1,
        operation: "drill",
      },
    ],
    pointsLoaded: true,
    selectedTemplate: {
      id: 7480,
      fitting_id: 42,
      mounting_variant_key: "surface_mount",
      points: [],
    },
  });

  assert.equal(payload.templates[0].template.points.length, 1);
  assert.equal(Object.hasOwn(payload.templates[0].template.points[0], "id"), false);
  assert.equal(payload.templates[0].template.points[0].diameter_mm, 5);
  assert.equal(payload.templates[0].template.points[0].depth_mm, 13);
});

test("mounting node editor save refreshes cached detail state after a successful save", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("const savedRestoreState = buildMountingNodesRestoreState("), true);
  assert.equal(source.includes('{ mode: "detail", nodeId: savedNode.id }'), true);
  assert.equal(source.includes("setCatalogHolesReturnState((current) => ({"), true);
  assert.equal(source.includes("setMountingNodesInitialState((current) => ({"), true);
});

test("mounting node editor can add the first draft point without a live template id", () => {
  assert.equal(
    canAddMountingNodeEditorPoint({
      isMountingNodeEditorMode: true,
      holePointSubmitting: false,
      loading: true,
      activeHoleFittingId: "",
      selectedHoleMountingVariantKey: "surface_mount",
      mountingNodeEditorDraft: {
        items: [
          {
            fitting_id: 42,
            quantity: 2,
          },
        ],
        mounting_variant_key: "surface_mount",
      },
    }),
    true,
  );
});

test("legacy fitting holes still require a live fitting id and variant", () => {
  assert.equal(
    canAddMountingNodeEditorPoint({
      isMountingNodeEditorMode: false,
      holePointSubmitting: false,
      loading: false,
      activeHoleFittingId: "",
      selectedHoleMountingVariantKey: "surface_mount",
      mountingNodeEditorDraft: null,
    }),
    false,
  );
});

test("mounting node editor resolves fitting images from fitting_id and keeps draft point labels human readable", () => {
  assert.equal(
    getMountingNodeEditorItemFittingId({
      id: 17,
      fitting_id: 42,
      image_url: "",
    }),
    "42",
  );

  assert.equal(
    getMountingNodeEditorItemImageUrl(
      {
        fitting_id: 42,
        image_url: "",
        image: "",
        thumbnail_url: "",
      },
      {
        id: 42,
        image_url: "https://example.test/fitting-42.png",
      },
    ),
    "https://example.test/fitting-42.png",
  );

  assert.equal(
    getMountingNodeEditorPointDisplayId({
      id: -1786062186076,
    }),
    "—",
  );

  assert.equal(
    getMountingNodeEditorPointDisplayLabel(
      {
        id: -1786062186076,
        label: "",
        order_index: 0,
      },
      0,
    ),
    "P1",
  );
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
  assert.equal(source.includes(".mounting-node-detail-history-card {"), true);
  assert.equal(source.includes(".mounting-node-version-item {"), true);
  assert.equal(source.includes(".mounting-node-version-item-meta {"), true);
  assert.equal(source.includes("grid-template-columns: repeat(3, minmax(0, 1fr));"), true);
  assert.equal(source.includes("@media (max-width: 1450px) {"), true);
  assert.equal(source.includes("grid-template-columns: repeat(2, minmax(0, 1fr));"), true);
  assert.equal(source.includes("@media (max-width: 760px) {"), true);
  assert.equal(source.includes("grid-template-columns: 1fr;"), true);
  assert.equal(source.includes(".mounting-nodes-list {"), true);
  assert.equal(source.includes("display: flex;"), true);
  assert.equal(source.includes("flex-direction: column;"), true);
});
