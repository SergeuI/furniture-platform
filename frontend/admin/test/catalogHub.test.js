import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

function countMatches(source, pattern) {
  const matches = source.match(pattern);
  return matches ? matches.length : 0;
}

test("catalog hub renders seven image cards with real counts and responsive layout", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const source = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  const hubStart = source.indexOf("const catalogHubCards = [");
  const hubEnd = source.indexOf("useDismissableCatalogItemMenu({", hubStart);
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
  assert.match(
    source,
    /!isMaterialCleanupView && !isCatalogFittingManufacturersView && !shouldHideFittingsCatalogOuterToolbar && !isCatalogHubView \? \(/,
  );
  assert.match(source, /catalog-breadcrumb-title/);
  assert.match(source, /catalog-breadcrumb-link/);
  assert.match(edgesBlock, /catalog-breadcrumb-title/);
  assert.match(edgesBlock, /catalog-breadcrumb-link/);
  assert.match(materialsBlock, /catalog-breadcrumb-title/);
  assert.match(materialsBlock, /catalog-breadcrumb-link/);
  assert.match(fittingsBlock, /catalog-breadcrumb-title/);
  assert.match(fittingsBlock, /catalog-breadcrumb-link/);
  assert.match(source, /className={`catalog-hub-tile\$\{item\.wide \? " catalog-hub-tile-wide" : ""\}`}/);
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
