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
  mergeMountingNodePreviewState,
  normalizeMountingNodePreviewState,
  resolveActiveMountingNodeVersion,
  resolveMountingNodeEditorContext,
  resolveMountingNodePreviewUrl,
} from "../src/mountingNodesEditor.js";

test("mounting node preview resolution keeps auto, 3D and custom sources separate", () => {
  assert.equal(resolveMountingNodePreviewUrl({ preview_mode: "custom", preview_custom_image_url: "/custom.png", preview_generated_image_url: "/generated.png" }, "/fallback.png"), "/custom.png");
  assert.equal(resolveMountingNodePreviewUrl({ preview_mode: "custom", preview_generated_image_url: "/generated.png" }, "/fallback.png"), "/fallback.png");
  assert.equal(resolveMountingNodePreviewUrl({ preview_mode: "auto", preview_custom_image_url: "/custom.png", preview_generated_image_url: "/generated.png" }, "/fallback.png"), "/fallback.png");
  assert.equal(resolveMountingNodePreviewUrl({ preview_mode: "auto", preview_auto_image_url: "/auto.png", preview_3d_image_url: "/3d.png" }, "/fallback.png"), "/auto.png");
  assert.equal(resolveMountingNodePreviewUrl({ preview_mode: "three_d", preview_3d_image_url: "/3d.png" }, "/fallback.png"), "/3d.png");
  assert.equal(resolveMountingNodePreviewUrl({ preview_mode: "three_d", preview_generated_image_url: "/legacy.png" }, "/fallback.png"), "/legacy.png");
  assert.equal(resolveMountingNodePreviewUrl({ preview_mode: "auto" }, "/fallback.png"), "/fallback.png");
});

test("mounting node preview state machine keeps only modes with valid sources", () => {
  const current = { name: "Unsaved title", preview_mode: "custom", preview_custom_image_url: "/custom.png", preview_generated_image_url: "/old.png" };
  assert.equal(normalizeMountingNodePreviewState({ preview_mode: "auto" }), "auto");
  assert.equal(normalizeMountingNodePreviewState(current), "custom");
  assert.equal(normalizeMountingNodePreviewState({ preview_mode: "custom", preview_custom_image_url: null }), "auto");
  assert.equal(normalizeMountingNodePreviewState({ preview_mode: "custom", preview_custom_image_url: "   " }), "auto");
  assert.equal(normalizeMountingNodePreviewState({ preview_mode: "three_d", preview_3d_image_url: "/3d.png" }), "three_d");
  assert.equal(normalizeMountingNodePreviewState({ preview_mode: "three_d", preview_generated_image_url: "/legacy.png" }), "three_d");
  assert.equal(normalizeMountingNodePreviewState({ preview_mode: "three_d" }), "auto");
  assert.equal(mergeMountingNodePreviewState(current, "auto").preview_mode, "auto");
  assert.deepEqual(
    (({ preview_mode, preview_generated_image_url, name }) => ({ preview_mode, preview_generated_image_url, name }))(
      mergeMountingNodePreviewState(current, "auto", { resultNode: { preview_mode: "custom", preview_generated_image_url: "/new.png", name: "Server title" } }),
    ),
    { preview_mode: "auto", preview_generated_image_url: "/new.png", name: "Unsaved title" },
  );
  assert.equal(mergeMountingNodePreviewState({ preview_mode: "auto" }, "custom", { resultNode: { preview_custom_image_url: "/uploaded.png" } }).preview_mode, "custom");
  assert.equal(mergeMountingNodePreviewState(current, "custom").preview_mode, "custom");
  const deleted = mergeMountingNodePreviewState(current, "auto", { resultNode: { preview_mode: "custom" }, clearCustom: true });
  assert.equal(deleted.preview_custom_image_url, null);
  assert.equal(deleted.preview_mode, "auto");
  assert.equal(mergeMountingNodePreviewState({ preview_mode: "auto" }, "custom").preview_mode, "auto");
  assert.equal(mergeMountingNodePreviewState({ preview_mode: "auto" }, "three_d", { resultNode: { preview_3d_image_url: "/captured.png" } }).preview_mode, "three_d");
});

test("mounting node editor hydration normalizes invalid custom preview to auto", () => {
  const hydration = hydrateMountingNodeEditorState({ id: 7, preview_mode: "custom", preview_custom_image_url: null, items: [], templates: [] });
  assert.equal(hydration?.context?.nodeDetail?.preview_mode, "auto");
  const invalid3d = hydrateMountingNodeEditorState({ id: 7, preview_mode: "three_d", items: [], templates: [] });
  assert.equal(invalid3d?.context?.nodeDetail?.preview_mode, "auto");
  const legacy3d = hydrateMountingNodeEditorState({ id: 7, preview_mode: "three_d", preview_generated_image_url: "/legacy.png", items: [], templates: [] });
  assert.equal(legacy3d?.context?.nodeDetail?.preview_mode, "three_d");
});

test("mounting node editor save payload keeps preview mode", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "7",
      templateId: "12",
      nodeDetail: {
        name: "Preview node",
        preview_mode: "custom",
        preview_custom_image_url: "/custom.png",
        items: [],
        templates: [{ template_id: 12, template: { id: 12, fitting_id: 4, mounting_variant_key: "surface_mount", points: [] } }],
      },
    },
    points: [],
    pointsLoaded: true,
    selectedTemplate: { id: 12, fitting_id: 4, mounting_variant_key: "surface_mount", points: [] },
  });
  assert.equal(payload.preview_mode, "custom");
});

test("mounting node save payload normalizes custom mode without an image to auto", () => {
  const payload = buildMountingNodeEditorSavePayload({
    context: {
      mountingNodeId: "7",
      templateId: "12",
      nodeDetail: {
        name: "Preview node",
        preview_mode: "custom",
        preview_custom_image_url: null,
        items: [],
        templates: [{ template_id: 12, template: { id: 12, fitting_id: 4, mounting_variant_key: "surface_mount", points: [] } }],
      },
    },
    points: [],
    pointsLoaded: true,
    selectedTemplate: { id: 12, fitting_id: 4, mounting_variant_key: "surface_mount", points: [] },
  });
  assert.equal(payload.preview_mode, "auto");
});

test("mounting node save payload keeps valid 3D and rejects missing 3D", () => {
  const context = {
    mountingNodeId: "7", templateId: "12",
    nodeDetail: { name: "Preview node", preview_mode: "three_d", preview_3d_image_url: "/3d.png", items: [], templates: [{ template_id: 12, template: { id: 12, fitting_id: 4, mounting_variant_key: "surface_mount", points: [] } }] },
  };
  const options = { context, points: [], pointsLoaded: true, selectedTemplate: { id: 12, fitting_id: 4, mounting_variant_key: "surface_mount", points: [] } };
  assert.equal(buildMountingNodeEditorSavePayload(options).preview_mode, "three_d");
  assert.equal(buildMountingNodeEditorSavePayload({ ...options, context: { ...context, nodeDetail: { ...context.nodeDetail, preview_3d_image_url: null } } }).preview_mode, "auto");
});

test("mounting node editor keeps compact preview controls in the header", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");
  const actionsStart = source.indexOf('className="service-catalog-header-actions mounting-node-workspace-actions"');
  const actionsEnd = source.indexOf("</ReferenceWorkspaceHeader>", actionsStart);
  const actionsSource = actionsStart >= 0 && actionsEnd > actionsStart ? source.slice(actionsStart, actionsEnd) : "";

  assert.equal(source.includes('className="mounting-node-create-card mounting-node-preview-card"'), false);
  assert.equal(actionsSource.includes('className="mounting-node-preview-strip"'), true);
  assert.equal(actionsSource.includes('onClick={() => applyMountingNodePreviewMode("auto")}'), true);
  assert.equal(actionsSource.includes('applyMountingNodePreviewMode("custom")'), true);
  assert.equal(actionsSource.includes('onClick={handleMountingNodeThreeDPreviewClick}'), true);
  const captureButtonSource = actionsSource.slice(actionsSource.indexOf('is-capture${mountingNodeEditorPreviewMode'), actionsSource.indexOf('className="mounting-node-preview-strip-item mounting-node-preview-strip-custom"'));
  assert.equal(captureButtonSource.includes('is-active'), true);
  assert.equal(captureButtonSource.includes('mounting-node-preview-strip-active'), true);
  assert.equal(actionsSource.includes('onChange={handleMountingNodeCustomPreviewUpload}'), true);
  assert.equal(actionsSource.includes('accept="image/png,image/jpeg,image/webp"'), true);
  assert.equal(source.includes('import previewAutoIcon from "./assets/mounting-node-preview/preview-auto.png"'), true);
  assert.equal(source.includes('import preview3dIcon from "./assets/mounting-node-preview/preview-3d.png"'), true);
  assert.equal(source.includes('import previewCustomIcon from "./assets/mounting-node-preview/preview-custom.png"'), true);
  assert.equal(actionsSource.includes("src={previewAutoIcon}"), true);
  assert.equal(actionsSource.includes("src={preview3dIcon}"), true);
  assert.equal(actionsSource.includes("src={previewCustomIcon}"), true);
  assert.equal((actionsSource.match(/className="mounting-node-preview-strip-thumb"/g) || []).length, 3);
  assert.equal(actionsSource.includes("src={mountingNodeEditorDraft?.preview_generated_image_url"), false);
  assert.equal(actionsSource.includes("src={mountingNodeEditorDraft?.preview_custom_image_url"), false);
  assert.equal(actionsSource.includes("onError="), false);
  assert.equal(source.includes('const mountingNodeEditorHasCustomPreview = Boolean(String(mountingNodeEditorDraft?.preview_custom_image_url || "").trim())'), true);
  assert.equal(actionsSource.includes('if (!mountingNodeEditorHasCustomPreview)'), true);
  assert.equal(actionsSource.includes('{mountingNodeEditorHasCustomPreview ? ('), true);
  assert.equal(actionsSource.includes('querySelector("input[type=file]")?.click()'), true);
  assert.equal(actionsSource.includes('handleDeleteMountingNodeCustomPreview'), true);
  assert.equal(actionsSource.includes("event.stopPropagation();"), true);
  assert.equal(actionsSource.includes('? " is-active" : ""'), true);
  assert.equal(actionsSource.includes('mountingNodeEditorPreviewMode === "auto"'), true);
  assert.equal(actionsSource.includes('mountingNodeEditorPreviewMode === "custom"'), true);
  assert.equal((actionsSource.match(/mounting-node-preview-strip-item/g) || []).length, 3);
  assert.equal((actionsSource.match(/mounting-node-preview-strip-tooltip/g) || []).length, 3);
  assert.equal(actionsSource.includes('aria-label={language === "uk" ? "Автоматичне прев’ю каталогу"'), true);
  assert.equal(actionsSource.includes('aria-label={language === "uk" ? "Створити прев’ю з поточного 3D"'), true);
  assert.equal(actionsSource.includes('aria-label={language === "uk" ? "Власне прев’ю / завантажити зображення"'), true);
  assert.equal(actionsSource.includes('aria-label={language === "uk" ? "Завантажити власне зображення"'), true);
  assert.equal(actionsSource.includes("mounting-node-preview-strip-badge is-auto"), true);
  assert.equal(actionsSource.includes("mounting-node-preview-strip-badge is-capture"), true);
  assert.equal(actionsSource.includes("mounting-node-preview-strip-badge is-custom"), true);
  assert.equal(actionsSource.includes("mounting-node-preview-strip-badge is-upload"), false);
  assert.equal(actionsSource.includes('mounting-node-preview-strip-message'), true);

  const styles = readFileSync(fileURLToPath(new URL("../src/styles.css", import.meta.url)), "utf8");
  assert.match(styles, /\.mounting-node-workspace-actions \.mounting-node-preview-strip-button\{[^}]*flex:0 0 44px;[^}]*height:44px;[^}]*padding:0;[^}]*width:44px\}/);
  assert.match(styles, /\.mounting-node-preview-strip-thumb\{[^}]*height:100%;[^}]*inset:0;[^}]*object-fit:cover;object-position:center;position:absolute;width:100%\}/);
});

test("mounting node preview handlers normalize successful upload, capture, and delete without auto-saving a version", () => {
  const source = readFileSync(fileURLToPath(new URL("../src/App.jsx", import.meta.url)), "utf8");
  const applyMode = source.slice(source.indexOf("function applyMountingNodePreviewMode("), source.indexOf("async function uploadGeneratedMountingNodePreview("));
  const capture = source.slice(source.indexOf("async function uploadGeneratedMountingNodePreview("), source.indexOf("async function handleMountingNodeCustomPreviewUpload("));
  const upload = source.slice(source.indexOf("async function handleMountingNodeCustomPreviewUpload("), source.indexOf("async function handleDeleteMountingNodeCustomPreview("));
  const deletion = source.slice(source.indexOf("async function handleDeleteMountingNodeCustomPreview("), source.indexOf("async function handleCatalogHolesSaveMountingNode("));
  assert.equal(applyMode.includes("mergeMountingNodePreviewState(current, mode, { resultNode, clearCustom })"), true);
  assert.equal(applyMode.includes("setMountingNodeEditorHasChanges(true)"), true);
  assert.equal(capture.includes('applyMountingNodePreviewMode("three_d", {'), true);
  assert.equal(capture.includes('uploadMountingNodePreview(token, nodeId, file, "three_d")'), true);
  assert.equal(upload.includes('applyMountingNodePreviewMode("custom", {'), true);
  assert.equal(deletion.includes('const modeAfterDelete = mountingNodeEditorPreviewMode === "custom" ? "auto" : mountingNodeEditorPreviewMode;'), true);
  assert.equal(deletion.includes('applyMountingNodePreviewMode(modeAfterDelete, {'), true);
  assert.equal(deletion.includes("clearCustom: true"), true);
  assert.equal(deletion.includes('"Власне прев’ю видалено. Увімкнено автоматичне прев’ю."'), true);
  assert.equal(deletion.includes('"Custom preview deleted. Automatic preview enabled."'), true);
  for (const handler of [capture, upload, deletion]) {
    assert.equal(handler.includes("handleCatalogHolesSaveMountingNode()"), false);
  }
});

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
  const functionalNormalizeSource = `
function normalizeMountingNodeFunctionalCode(value) {
  const normalized = String(value || "").trim().toLowerCase();
  return normalized && ["connector","door_hinge","drawer_slide","furniture_handle","profile_handle","cabinet_leg","wall_hanger","sink","cooktop","ventilation_grille","electrical_socket"].includes(normalized)
    ? normalized
    : "";
}
`;

  if (!buildNodeEditorContextSource || !helperBlockSource) {
    throw new Error("Unable to isolate the mounting node editor helper block.");
  }

  const combinedSource = [
    functionalNormalizeSource,
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
  assert.equal(source.includes("onOpenMountingNodeCategories"), true);
  assert.equal(source.includes("onClick={() => handleOpenEditor()}"), true);
  assert.equal(source.includes("onClick={handleOpenEditor}"), false);
  assert.equal(source.includes("selectedNode?.category_code ?? null,"), true);
  assert.equal(source.includes("selectedFasteningType,"), true);
  assert.equal(source.includes("listRequestToken"), true);
  assert.equal(source.includes("listRequestTokenRef"), true);
  assert.equal(source.includes("handleSelectNode(nodeId)"), true);
  assert.equal(source.includes("handleBackToList()"), true);
  assert.equal(source.includes("handleReturnToCategories"), false);
  assert.equal(source.includes("setMountingNodesViewMode(\"list\")"), true);
  assert.equal(source.includes("mounting-node-card-tags"), true);
  assert.equal(source.includes("getMountingNodeCategoryLabel"), true);
  assert.equal(source.includes("getMountingNodeCategoryOptions"), true);
  assert.equal(source.includes("normalizeMountingNodeCategoryCode"), true);
  assert.equal(source.includes("activeCategoryFilter"), true);
  assert.equal(source.includes("handleCategoryFilterChange"), true);
  assert.equal(source.includes("mounting-node-filter-sidebar"), true);
  assert.equal(source.includes("mounting-node-filter-group"), true);
  assert.equal(source.includes("statusCounts[value]"), true);
  assert.equal(source.includes('fasteningTypeCounts[option.code || "all"]'), true);
  assert.equal(source.includes("mounting-node-card-ownership"), true);
  assert.equal(source.includes("window.setTimeout"), true);
  assert.equal(source.includes("categoryFilterOptions"), true);
  assert.equal(source.includes("MOUNTING_NODE_CATEGORY_FILTER_NULL"), true);
  assert.equal(source.includes("mounting-node-card-layout"), true);
  assert.equal(source.includes("mounting-node-row-layout"), true);
  assert.equal(source.includes("mounting-node-card-preview"), true);
  assert.equal(source.includes("mounting-node-row-preview"), true);
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

  const cardVisualsStart = source.indexOf('<div className="mounting-node-card-preview">');
  const rowVisualsStart = source.indexOf('<div className="mounting-node-row-preview">');
  const cardGalleryStart = source.indexOf('{renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById, node.fastening_type, nodeDetail || node)}', cardVisualsStart);
  const cardActionsStart = source.indexOf('{renderNodeCardActions(', cardVisualsStart);
  const rowGalleryStart = source.indexOf('{renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById, node.fastening_type, nodeDetail || node)}', rowVisualsStart);
  const rowActionsStart = source.indexOf('<div className="mounting-node-row-actions">', rowVisualsStart);

  assert.equal(cardVisualsStart >= 0 && cardGalleryStart >= 0 && cardActionsStart >= 0, true);
  assert.equal(rowVisualsStart >= 0 && rowGalleryStart >= 0 && rowActionsStart >= 0, true);
  assert.equal(cardGalleryStart < cardActionsStart, true);
  assert.equal(rowGalleryStart < rowActionsStart, true);

  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const styles = readFileSync(stylesPath, "utf8");
  assert.equal(styles.includes("aspect-ratio: 16 / 10"), true);
  assert.equal(styles.includes("min-height: calc(100vh - 180px)"), true);
  assert.equal(styles.includes("grid-template-columns: repeat(4, minmax(0, 1fr))"), true);
});

test("toolbar breadcrumb for mounting nodes uses stable App primitives", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("initialAdminRoute.view === \"catalogHoles\" && initialAdminRoute.mountingNodesRoute"), true);
  assert.equal(source.includes("buildMountingNodesRestoreState(initialAdminRoute.mountingNodesRoute)"), true);
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
  assert.equal(source.includes("getMountingNodesToolbarBreadcrumbItemsCanonical()"), true);
  assert.equal(source.includes("setCatalogHolesMode(\"categories\");"), true);
  assert.equal(source.includes("setCatalogHolesMode(\"list\");"), true);
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

test("mounting node editor category select lives in the App editor flow", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("handleMountingNodeEditorCategoryChange"), true);
  assert.equal(source.includes("mounting-node-editor-category-card"), true);
  assert.equal(source.includes("mounting-node-editor-category-field"), true);
  assert.equal(source.includes("mountingNodeEditorSelectedCategoryCode"), true);
  assert.equal(source.includes("mountingNodeEditorSelectedCategoryLabel"), true);
  assert.equal(source.includes("mountingNodeEditorCategoryOptions"), true);
  assert.equal(source.includes('value={mountingNodeEditorSelectedCategoryCode}'), true);
  assert.equal(source.includes('option value=""'), true);
  assert.equal(source.includes("Category not set"), true);
  assert.equal(source.includes("getMountingNodeCategoryOptions"), true);
  assert.equal(source.includes("normalizeMountingNodeCategoryCode"), true);
  assert.equal(source.includes("mountingNodeEditorCategoryCodeRef"), true);
  assert.equal(source.includes("category_code: selectedCategoryCode || undefined"), true);
  assert.equal(source.includes("category_code: normalizeMountingNodeCategoryCode(nodeDetail.category_code)"), true);
  assert.equal(source.includes("setCatalogHolesOpenContext((current) => {"), true);
  assert.equal(source.includes("mountingNodeEditorCategoryCodeRef.current = resolvedCategoryCode || \"\";"), true);
  assert.equal(source.includes("resolveMountingNodesCategoryCode("), true);
});

test("mounting nodes list renders nodes before the category empty state branch", () => {
  const sourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const source = readFileSync(sourcePath, "utf8");
  const nodesBranchIndex = source.indexOf(") : visibleNodes.length ? (");
  const categoryEmptyStateIndex = source.indexOf(") : activeCategoryFilter !== \"all\" ? (");

  assert.equal(nodesBranchIndex >= 0, true);
  assert.equal(categoryEmptyStateIndex >= 0, true);
  assert.equal(nodesBranchIndex < categoryEmptyStateIndex, true);
});

test("mounting node editor renders a single workspace with one hardware block and no variant block", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");
  const workspaceMarker = source.indexOf("mounting-node-editor-workspace");
  const workspaceStart = source.lastIndexOf("<FittingHolesWorkspace", workspaceMarker);
  const workspaceEnd = source.indexOf("</FittingHolesWorkspace>", workspaceMarker);
  const workspaceSource =
    workspaceMarker >= 0 && workspaceStart >= 0 && workspaceEnd > workspaceStart
      ? source.slice(workspaceStart, workspaceEnd)
      : "";

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
    functional_code: null,
    fastening_type: null,
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
    functional_code: null,
    fastening_type: null,
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
  assert.equal(source.includes("const savedCategoryCode = resolveMountingNodesCategoryCode("), true);
  assert.equal(source.includes("const contextFunctionalCode = normalizeMountingNodeFunctionalCode("), true);
  assert.equal(source.includes("functional_code: contextFunctionalCode,"), true);
  assert.equal(source.includes("normalizeMountingNodesRoute({"), true);
  assert.equal(source.includes('const savedEditorRoute = buildMountingNodesRouteForMode(savedRestoreRoute, "editor", savedNode.id);'), true);
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
  assert.equal(source.includes("renderNodeItemGallery(nodeDetail?.items, language, t, fittingThumbnailStateById, node.fastening_type, nodeDetail || node)"), true);
  assert.equal(source.includes("resolveMountingNodePreviewUrl(node, existingImageUrl)"), true);
  assert.equal(source.includes("fallbackPreview"), true);
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

test("mounting nodes list exposes the unified catalog toolbar and sidebar filters", () => {
  const sourcePath = fileURLToPath(
    new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url),
  );
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("mounting-nodes-header-actions"), true);
  assert.equal(source.includes("mounting-node-catalog-toolbar"), true);
  assert.equal(source.includes("mounting-node-filter-sidebar"), true);
  assert.equal(source.includes("mounting-node-ownership-tabs"), true);
  assert.equal(source.includes("mounting-nodes-view-toggle materials-mode-switch"), true);
  assert.equal(source.includes("Бібліотека монтажних вузлів для з’єднання деталей."), true);
  assert.equal(source.includes("Пошук вузлів..."), true);
  assert.equal(source.includes("Створити монтажний вузол"), true);
  assert.equal(source.includes("Скинути всі"), true);
  assert.equal(source.includes("Тип кріплення"), true);
  assert.equal(source.includes("Активні"), true);
  assert.equal(source.includes("Неактивні"), true);
  assert.equal(source.includes("Власні"), true);
  assert.equal(source.includes("Системні"), true);
  assert.equal(source.includes("Плитка"), true);
  assert.equal(source.includes("Список"), true);
  assert.equal(source.includes("handleResetFilters"), true);
  assert.equal(source.includes("setOwnershipFilter(value)"), true);
});

test("app opens mounting nodes as the unified list while retaining category compatibility", () => {
  const sourcePath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");

  assert.equal(source.includes("mode === \"categories\""), true);
  assert.equal(source.includes("handleOpenMountingNodesCategoryCatalog"), true);
  assert.equal(source.includes('const nextCatalogHolesMode = contextMountingNodeId ? "editor" : "list";'), true);
  assert.equal(source.includes('contextMountingNodeId ? "editor" : "list"'), true);
  assert.equal(source.includes("setMountingNodesRouteState(nextMountingNodesRoute);"), true);
  assert.equal(source.includes("buildMountingNodesRouteUrl(normalizedRoute, window.location.search)"), true);
  assert.equal(source.includes("mountingNodesCategorySummary"), true);
  assert.equal(source.includes("mountingNodesCategorySummaryLoading"), true);
  assert.equal(source.includes("getMountingNodeCategoryImageUrl"), true);
  assert.equal(source.includes("fitting-category-card mounting-node-category-card"), true);
  assert.equal(source.includes("mounting-node-category-media"), true);
  assert.equal(source.includes("mounting-node-category-meta"), true);
  assert.equal(source.includes("mounting-node-category-card"), true);
});
