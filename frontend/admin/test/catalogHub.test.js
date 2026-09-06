import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

function countMatches(source, pattern) {
  const matches = source.match(pattern);
  return matches ? matches.length : 0;
}

test("catalog hub keeps only primary directory cards with real counts and responsive layout", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const breadcrumbPath = fileURLToPath(new URL("../src/components/CatalogBreadcrumbTrail.jsx", import.meta.url));
  const source = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");
  const breadcrumbSource = readFileSync(breadcrumbPath, "utf8");

  const hubStart = source.indexOf("const catalogHubCards = [");
  const hubEnd = source.indexOf("const materialTaxonomyCards = [", hubStart);
  const edgesStart = source.indexOf(") : isCatalogEdgesView ? (");
  const materialsStart = source.indexOf(") : isCatalogMaterialsView ? (");
  const fittingsStart = source.indexOf(") : isCatalogFittingsView || isCatalogFastenersView ? (");
  const serviceRulesStart = source.indexOf(") : isCatalogServiceRulesView ? (");
  const edgesHeaderEnd = source.indexOf("              <div className=\"fittings-toolbar-row material-category-toolbar-row\">", edgesStart);
  const materialsHeaderEnd = source.indexOf("              {!isCatalogMaterialRootView ? (", materialsStart);
  const fittingsHeaderEnd = source.indexOf("              <div className=\"fittings-toolbar-row\">", fittingsStart);

  assert.ok(hubStart > -1 && hubEnd > hubStart, "catalogHubCards block should exist");
  assert.ok(edgesStart > -1 && materialsStart > edgesStart, "catalogEdges block should exist before catalogMaterials");
  assert.ok(materialsStart > -1 && fittingsStart > materialsStart, "catalogMaterials block should exist before catalogFittings");
  assert.ok(fittingsStart > -1 && serviceRulesStart > fittingsStart, "catalogFittings block should exist before service rules");
  assert.ok(edgesHeaderEnd > edgesStart, "catalogEdges header block should exist");
  assert.ok(materialsHeaderEnd > materialsStart, "catalogMaterials header block should exist");
  assert.ok(fittingsHeaderEnd > fittingsStart, "catalogFittings header block should exist");

  const hubBlock = source.slice(hubStart, hubEnd);
  const edgesBlock = source.slice(edgesStart, edgesHeaderEnd);
  const materialsBlock = source.slice(materialsStart, materialsHeaderEnd);
  const fittingsBlock = source.slice(fittingsStart, fittingsHeaderEnd);

  assert.match(hubBlock, /const catalogHubCards = \[/);
  assert.match(hubBlock, /key: "materials"/);
  assert.match(hubBlock, /key: "edges"/);
  assert.match(hubBlock, /key: "fittings"/);
  assert.match(hubBlock, /key: "viyar"/);
  assert.match(hubBlock, /key: "drilling_rules"/);
  assert.match(hubBlock, /key: "manual"/);
  assert.match(hubBlock, /key: "values"/);
  assert.equal(countMatches(hubBlock, /key: "/g), 7);
  assert.doesNotMatch(hubBlock, /material_(categories|manufacturers|suppliers)/);

  assert.match(hubBlock, /switchView\("catalogMaterials"\)/);
  assert.match(hubBlock, /switchView\("catalogEdges"\)/);
  assert.match(hubBlock, /switchView\("catalogFittings"\)/);
  assert.match(hubBlock, /switchView\("catalogViyar"\)/);
  assert.match(hubBlock, /switchView\("catalogDrillingRules"\)/);
  assert.match(hubBlock, /switchView\("catalogManual"\)/);
  assert.match(hubBlock, /switchView\("catalogValues"\)/);

  assert.match(hubBlock, /materialItems\.length/);
  assert.match(hubBlock, /materialCategories\.length/);
  assert.match(hubBlock, /edgeItems\.length/);
  assert.match(hubBlock, /fittingItems\.length/);
  assert.match(hubBlock, /fittingCategories\.length/);
  assert.match(hubBlock, /viyarServiceCounts\.services/);
  assert.match(hubBlock, /viyarServiceCounts\.folders/);
  assert.match(hubBlock, /drillingRuleItems\.length/);
  assert.match(hubBlock, /manualServiceItems\.length/);
  assert.match(hubBlock, /catalogItems\.length/);
  assert.doesNotMatch(hubBlock, /\b(1482|2986|56|349|1124)\b/);

  assert.match(source, /import catalogMaterialsImage from "\.\/assets\/catalog-hub\/catalog-materials\.png";/);
  assert.match(source, /import catalogEdgesImage from "\.\/assets\/catalog-hub\/catalog-edges\.png";/);
  assert.match(source, /import catalogFittingsImage from "\.\/assets\/catalog-hub\/catalog-fittings\.png";/);
  assert.match(source, /import catalogViyarImage from "\.\/assets\/catalog-hub\/catalog-viyar\.png";/);
  assert.match(source, /import catalogDrillingRulesImage from "\.\/assets\/catalog-hub\/catalog-drilling-rules\.png";/);
  assert.match(source, /import catalogManualServicesImage from "\.\/assets\/catalog-hub\/catalog-manual-services\.png";/);
  assert.match(source, /import catalogValuesImage from "\.\/assets\/catalog-hub\/catalog-values\.png";/);

  assert.match(source, /if \(isCatalogHubView\) \{\s*return "";/);
  assert.match(source, /<div className="catalog-hub-header">/);
  assert.match(source, /<div className="service-catalog-title catalog-hub-header-copy">/);
  assert.match(source, /<h3>\{t\.catalog\}<\/h3>/);
  assert.match(source, /<p>\{t\.catalogHubDescription\}<\/p>/);
  assert.match(source, /async function loadCatalogView\(activeToken = token, viewer = user\) \{\s*await loadCatalogItems\(activeToken, viewer\);\s*await loadMaterialsCatalog\(activeToken, \{ category: "dsp", search: "" \}\);\s*await loadEdgesCatalog\(activeToken\);\s*await loadFittingsCatalog\(activeToken, \{\s*search: "",\s*\}\);\s*await loadViyarServices\(activeToken, viewer\);\s*await loadManualServices\(activeToken, viewer\);\s*\}/);
  assert.doesNotMatch(source, /catalog-hub-card-hero/);
  assert.match(source, /CatalogBreadcrumbTrail/);
  assert.match(breadcrumbSource, /catalog-breadcrumb-title/);
  assert.match(breadcrumbSource, /catalog-breadcrumb-link/);
  assert.match(edgesBlock, /CatalogBreadcrumbTrail/);
  assert.match(materialsBlock, /CatalogBreadcrumbTrail/);
  assert.match(fittingsBlock, /CatalogBreadcrumbTrail/);
  assert.match(source, /className={`catalog-hub-tile\$\{item\.wide \? " catalog-hub-tile-wide" : ""\}\$\{item\.disabled/);
  assert.match(source, /className="catalog-hub-grid" role="list" aria-label=\{t\.catalog\}/);
  assert.match(source, /className="catalog-hub-tile-media"/);
  assert.match(source, /className="catalog-hub-tile-image-frame"/);
  assert.match(source, /className="catalog-hub-tile-icon"/);
  assert.match(source, /className="catalog-hub-tile-chips"/);
  assert.match(source, /className="catalog-hub-tile-link"/);
  assert.match(source, /<ChevronRight size=\{16\} \/>/);
  assert.match(source, /catalog-hub-tile-wide/);
  assert.match(stylesSource, /\.catalog-hub-header-copy h3 \{\s*font-size: 25px;[\s\S]*line-height: 1\.25;/);
  assert.match(stylesSource, /\.catalog-breadcrumb-title \{\s*align-items: center;[\s\S]*font-size: 25px;[\s\S]*font-weight: 800;[\s\S]*line-height: 1\.25;/);
  assert.match(stylesSource, /\.catalog-breadcrumb-link \{\s*background: transparent;[\s\S]*font-size: inherit;[\s\S]*font-weight: 800;[\s\S]*line-height: inherit;/);
  assert.match(stylesSource, /\.catalog-hub-tile \{\s*background: #ffffff;[\s\S]*overflow: visible;/);
  assert.match(stylesSource, /\.catalog-hub-tile-image-frame \{\s*background: #f5f7fa;[\s\S]*overflow: hidden;/);
  assert.match(stylesSource, /\.catalog-hub-tile-image-frame img \{\s*display: block;[\s\S]*object-fit: cover;/);
  assert.match(stylesSource, /\.catalog-hub-tile-icon \{\s*align-items: center;[\s\S]*z-index: 2;/);
  assert.match(source, /catalog-hub-chip/);

  assert.match(stylesSource, /\.catalog-hub-layout \{\s*display: grid;[\s\S]*padding: 16px 24px 24px;/);
  assert.match(stylesSource, /\.catalog-hub-grid \{\s*display: grid;[\s\S]*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/);
  assert.match(stylesSource, /\.catalog-hub-tile \{\s*background: #ffffff;[\s\S]*overflow: visible;[\s\S]*transition: box-shadow 0\.18s ease, transform 0\.18s ease, border-color 0\.18s ease;/);
  assert.match(stylesSource, /\.catalog-hub-tile-wide \{\s*grid-column: 1 \/ -1;[\s\S]*grid-template-columns: minmax\(0, 0\.46fr\) minmax\(0, 0\.54fr\);/);
  assert.match(stylesSource, /\.catalog-hub-tile-media \{\s*display: block;[\s\S]*min-height: 160px;[\s\S]*overflow: visible;/);
  assert.match(stylesSource, /\.catalog-hub-tile-image-frame \{\s*background: #f5f7fa;[\s\S]*overflow: hidden;/);
  assert.match(stylesSource, /\.catalog-hub-tile-icon \{\s*align-items: center;[\s\S]*bottom: -18px;[\s\S]*height: 44px;/);
  assert.match(stylesSource, /\.catalog-hub-chip \{\s*align-items: flex-start;[\s\S]*border-radius: 999px;/);
  assert.match(stylesSource, /@media \(max-width: 1200px\) \{[\s\S]*\.catalog-hub-grid \{\s*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);/);
  assert.match(stylesSource, /@media \(max-width: 640px\) \{[\s\S]*\.catalog-hub-grid \{\s*grid-template-columns: 1fr;/);
  assert.match(stylesSource, /@media \(max-width: 640px\) \{[\s\S]*\.catalog-hub-tile-wide \{\s*grid-column: auto;[\s\S]*grid-template-columns: 1fr;/);
  assert.match(stylesSource, /@media \(max-width: 640px\) \{[\s\S]*\.catalog-hub-tile-media \{\s*min-height: 148px;/);
});

test("material root keeps taxonomy cards in a separate compact auxiliary block", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const source = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");
  const hubStart = source.indexOf("const catalogHubCards = [");
  const hubEnd = source.indexOf("const materialTaxonomyCards = [", hubStart);
  const taxonomyStart = source.indexOf("const materialTaxonomyCards = [");
  const taxonomyEnd = source.indexOf("useDismissableCatalogItemMenu({", taxonomyStart);
  const auxiliaryStart = source.indexOf('className="material-taxonomy-auxiliary-section"');
  const auxiliaryEnd = source.indexOf(") : isCatalogFittingManufacturersView ||", auxiliaryStart);
  const auxiliaryBlock = source.slice(auxiliaryStart, auxiliaryEnd);
  const taxonomyBlock = source.slice(taxonomyStart, taxonomyEnd);
  const auxiliaryStylesStart = stylesSource.indexOf(".material-taxonomy-auxiliary-section {");
  const auxiliaryStylesEnd = stylesSource.indexOf(".dashboard-layout {", auxiliaryStylesStart);
  const auxiliaryStyles = stylesSource.slice(auxiliaryStylesStart, auxiliaryStylesEnd);

  assert.doesNotMatch(source.slice(hubStart, hubEnd), /material_(categories|manufacturers|suppliers)/);
  assert.equal((taxonomyBlock.match(/key: "material_/g) || []).length, 3);
  assert.ok(auxiliaryStart > -1 && auxiliaryEnd > auxiliaryStart);
  assert.match(auxiliaryBlock, /Довідники матеріалів|Material directories/);
  assert.match(auxiliaryBlock, /materialTaxonomyCards\.map/);
  assert.match(taxonomyBlock, /switchView\("catalogMaterialCategories"\)/);
  assert.match(taxonomyBlock, /switchView\("catalogMaterialManufacturers"\)/);
  assert.match(taxonomyBlock, /switchView\("catalogMaterialSuppliers"\)/);
  assert.match(source, /import catalogMaterialCategoriesImage from "\.\/assets\/catalog-hub\/catalog-material-categories\.png";/);
  assert.match(source, /import catalogMaterialManufacturersImage from "\.\/assets\/catalog-hub\/catalog-material-manufacturers\.png";/);
  assert.match(source, /import catalogMaterialSuppliersImage from "\.\/assets\/catalog-hub\/catalog-material-suppliers\.png";/);
  assert.match(source, /material_categories: \{ accent: "#2563eb", icon: FolderTree, image: catalogMaterialCategoriesImage \}/);
  assert.match(source, /material_manufacturers: \{ accent: "#2563eb", icon: Factory, image: catalogMaterialManufacturersImage \}/);
  assert.match(source, /material_suppliers: \{ accent: "#2563eb", icon: Truck, image: catalogMaterialSuppliersImage \}/);
  assert.doesNotMatch(source, /material_(categories|manufacturers|suppliers):[^\n]*image: catalogMaterialsImage/);
  assert.match(source, /const \[materialSupplierDirectoryItems, setMaterialSupplierDirectoryItems\] = useState\(\[\]\);/);
  assert.match(source, /listFittingSuppliers\(activeToken, true\)/);
  assert.match(source, /\.filter\(\(item\) => item\?\.is_active\)/);
  assert.match(source, /value: materialSupplierDirectoryItems\.length/);
  assert.doesNotMatch(source, /value: fittingSupplierItems\.length/);
  const mockedSupplierList = [
    { is_active: true, is_system: true },
    { is_active: true, is_system: true },
    { is_active: true, owner_user_id: "own-1" },
    { is_active: true, owner_user_id: "own-2" },
    { is_active: false, is_system: true },
  ];
  assert.equal(mockedSupplierList.filter((item) => item?.is_active).length, 4);
  assert.match(auxiliaryBlock, /disabled=\{item\.disabled\}/);
  assert.match(auxiliaryBlock, /Немає доступу/);
  assert.match(stylesSource, /\.material-taxonomy-auxiliary-section \{/);
  assert.match(stylesSource, /\.material-taxonomy-auxiliary-grid \{[\s\S]*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\);/);
  assert.match(stylesSource, /\.catalog-hub-tile-compact[\s\S]*min-height: 92px;/);
  assert.doesNotMatch(auxiliaryStyles, /transform:\s*scale/);
});
