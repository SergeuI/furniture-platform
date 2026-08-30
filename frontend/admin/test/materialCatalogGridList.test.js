import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("material catalog keeps a persisted grid/list toggle and closes menus on layout changes", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /const MATERIAL_CATALOG_VIEW_MODE_STORAGE_KEY = "furniture_admin_material_catalog_view_mode";/);
  assert.match(
    appSource,
    /const \[materialCatalogViewMode, setMaterialCatalogViewMode\] = useState\(\s*\(\) => normalizeMaterialCatalogViewMode\(localStorage\.getItem\(MATERIAL_CATALOG_VIEW_MODE_STORAGE_KEY\) \|\| "grid"\),\s*\);/,
  );
  assert.match(appSource, /localStorage\.setItem\(MATERIAL_CATALOG_VIEW_MODE_STORAGE_KEY, materialCatalogViewMode\);/);
  assert.match(appSource, /function getMaterialSupplierSummaryViewModel\(item\)/);
  assert.match(appSource, /useDismissableCatalogItemMenu\(\{/);
  assert.match(appSource, /const menuResetKeyRef = useRef\(resetKey\);/);
  assert.match(appSource, /const menuWasOpenRef = useRef\(false\);/);
  assert.doesNotMatch(appSource, /if \(\!isOpen\) \{\s*onClose\(\);\s*\}/);
  assert.match(appSource, /if \(!menuWasOpenRef\.current\) \{\s*menuWasOpenRef\.current = true;\s*menuResetKeyRef\.current = resetKey;\s*return;/);
  assert.match(appSource, /if \(menuResetKeyRef\.current !== resetKey\) \{\s*menuResetKeyRef\.current = resetKey;\s*onClose\(\);\s*\}/);
  assert.match(appSource, /const \[openMaterialMenuPosition, setOpenMaterialMenuPosition\] = useState\(null\);/);
  assert.match(appSource, /const openMaterialMenuTriggerRef = useRef\(null\);/);
  assert.match(appSource, /const openMaterialMenuActionCountRef = useRef\(3\);/);
  assert.match(appSource, /const renderMaterialActionMenu = \(item\) => \{/);
  assert.match(appSource, /materialCatalogViewMode === "list" && openMaterialMenuPosition/);
  assert.match(appSource, /createPortal\(menuContent, document\.body\);/);
  assert.match(appSource, /panelSelector: "\.material-card-menu-dropdown"/);
  assert.match(appSource, /triggerSelector: "\.material-card-menu-trigger"/);
  assert.match(appSource, /resetKey: `\$\{activeView\}\|\$\{materialCategoryFilter\}\|\$\{materialCatalogViewMode\}`/);
  assert.match(appSource, /openMaterialEditModal\(item\)/);
  assert.match(appSource, /handleRefreshMaterial\(item\)/);
  assert.match(appSource, /openDeleteMaterialConfirm\(item\)/);

  const listToggleIndex = appSource.indexOf('materialCatalogViewMode === "list" ? " active" : ""');
  const gridToggleIndex = appSource.indexOf('materialCatalogViewMode === "grid" ? " active" : ""');
  assert.ok(listToggleIndex > -1 && gridToggleIndex > -1 && listToggleIndex < gridToggleIndex);
  assert.ok(appSource.includes('<Blocks size={16} />'));
  assert.ok(appSource.includes('<LayoutGrid size={16} />'));
  assert.ok(appSource.indexOf('<Blocks size={16} />') < appSource.indexOf('<LayoutGrid size={16} />'));

  assert.match(
    appSource,
    /className=\{materialCatalogViewMode === "list" \? "material-card-grid material-card-grid-list" : "material-card-grid"\}/,
  );
  assert.match(
    appSource,
    /className=\{`material-card material-card-clickable\$\{materialCatalogViewMode === "list" \? " material-card-list" : ""\}`\}/,
  );
  assert.match(appSource, /className="material-card-menu-trigger"/);
  assert.match(appSource, /className="material-card-menu-action"/);
  assert.match(appSource, /className="material-card-supplier-strip"/);
  assert.match(appSource, /<MaterialSupplierLogo/);
  assert.equal((appSource.match(/renderSourceBadge\(sourceMeta\)/g) || []).length, 1);

  assert.match(stylesSource, /\.material-card-grid \{\s*display: grid;[\s\S]*repeat\(auto-fit, minmax\(280px, 300px\)\);[\s\S]*justify-content: start;/);
  assert.match(stylesSource, /\.material-card-grid-list \{\s*display: grid;[\s\S]*grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /\.material-card-list \{\s*display: grid;[\s\S]*grid-template-columns: 108px minmax\(0, 1fr\);[\s\S]*min-height: 118px;/);
  assert.match(stylesSource, /\.material-card-list \.material-card-media \{\s*border-radius: 8px 0 0 8px;[\s\S]*min-height: 100%;/);
  assert.match(stylesSource, /\.material-card-list \.material-card-body \{\s*align-content: stretch;[\s\S]*grid-template-areas:[\s\S]*grid-template-columns: minmax\(0, 1fr\) minmax\(240px, 280px\) minmax\(170px, 200px\);[\s\S]*padding: 14px 52px 14px 14px;/);
  assert.match(stylesSource, /\.material-card-list \.material-card-menu \{\s*right: 10px;[\s\S]*top: 10px;/);
  assert.match(stylesSource, /\.material-card-list \.material-card-topline \{\s*grid-area: topline;/);
  assert.equal(
    stylesSource.includes(".material-card-list .material-card-body strong {") &&
      stylesSource.includes("overflow-wrap: anywhere;"),
    true,
  );
  assert.match(stylesSource, /\.material-card-list \.material-card-price \{\s*align-content: center;[\s\S]*justify-items: start;/);
  assert.match(stylesSource, /\.material-card-list \.material-card-meta \{\s*align-content: center;[\s\S]*grid-area: suppliers;[\s\S]*justify-items: start;/);
  assert.match(stylesSource, /\.material-card-supplier-strip \{\s*align-items: center;[\s\S]*display: flex;[\s\S]*gap: 6px;[\s\S]*min-width: 0;/);
  assert.match(stylesSource, /\.material-card-supplier-strip \.material-supplier-offer-logo \{\s*height: 22px;[\s\S]*min-width: 40px;/);
  assert.match(stylesSource, /\.material-card-list \.material-card-price b \{\s*white-space: nowrap;/);
  assert.match(stylesSource, /\.material-card-price-summary-row \{\s*display: grid;[\s\S]*justify-items: start;/);
  assert.match(stylesSource, /\.catalog-page-header\.material-taxonomy-page-header \.service-catalog-header-actions \{\s*align-items: center;[\s\S]*max-width: min\(100%, 760px\);/);
  assert.doesNotMatch(stylesSource, /\.material-category-detail-actions \.fittings-view-toggle \{/);
  assert.match(stylesSource, /@media \(max-width: 720px\) \{[\s\S]*\.material-card-grid \{\s*grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /@media \(max-width: 720px\) \{[\s\S]*\.material-card-grid-list \{\s*grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /@media \(max-width: 720px\) \{[\s\S]*\.material-card-list \{\s*grid-template-columns: minmax\(0, 1fr\);/);
  assert.match(stylesSource, /@media \(max-width: 720px\) \{[\s\S]*\.material-card-list \.material-card-body \{\s*grid-template-areas:[\s\S]*grid-template-columns: minmax\(0, 1fr\);[\s\S]*padding-right: 14px;/);
});
