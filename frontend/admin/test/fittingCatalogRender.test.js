import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { getCanonicalFittingsCountLabel } from "../src/fittingCatalogView.js";

test("canonical fitting render pipeline keeps overview counts, commercial rows, and image fallbacks", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const catalogViewPath = fileURLToPath(new URL("../src/fittingCatalogView.js", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const catalogViewSource = readFileSync(catalogViewPath, "utf8");

  assert.match(
    appSource,
    /const activePageLabel = useMemo\([\s\S]*if \(isCatalogFittingsView\) \{[\s\S]*getCanonicalFittingsOverviewCountLabel\(\{\s*allCards: fittingCanonicalCatalogView\.allCards,\s*language,\s*\}\)[\s\S]*\}\s*,\s*\[[\s\S]*fittingCanonicalCatalogView\.allCards[\s\S]*language[\s\S]*\]\s*\)/,
  );
  assert.match(
    appSource,
    /getCanonicalFittingsCountLabel\(\{\s*activeCategoryCode: activeFittingCategory,\s*visibleCards: fittingCanonicalCatalogView\.visibleCards,\s*allCards: fittingCanonicalCatalogView\.allCards,\s*language,\s*\}\)/,
  );
  assert.match(
    appSource,
    /function chooseCanonicalPresentationLegacyRow\(item = null\)\s*\{[\s\S]*item\?\.commercial_legacy_row[\s\S]*item\?\.image_legacy_row[\s\S]*item\?\.representative_legacy_row/,
  );
  assert.match(
    appSource,
    /const commercialSourceItem =[\s\S]*item\.commercial_legacy_row[\s\S]*item\.representative_legacy_row[\s\S]*item\.legacy_rows\?\.\[0\][\s\S]*\|\|\s*item;/,
  );
  assert.match(appSource, /const directImageUrl = String\(item\?\.image_url \|\| ""\)\.trim\(\);/);
  assert.match(appSource, /const imageSignature = useMemo\(/);
  assert.match(appSource, /useFittingPrimaryImageObjectUrl\(item, token, enabled, 0\);/);
  assert.match(appSource, /if \(candidates\.length\) \{\s*return \(\s*<img[\s\S]*onError=\{\(event\) => handleFittingImageError\(event, item\)\}/);
  assert.match(appSource, /const previewFallbackCandidates = useMemo\(/);
  assert.match(appSource, /previewFallbackCandidates\[0\] \|\| ""/);
  assert.match(appSource, /commercialSourceItem\.price \?\? t\.notSet/);
  assert.match(appSource, /getFittingSupplierMeta\(item\)/);
  assert.match(appSource, /function getPrimaryFittingSupplierOffer\(item\)/);
  assert.match(appSource, /supplier_logo_url/);
  assert.match(appSource, /item\?\.commercial_legacy_row,/);
  assert.match(appSource, /renderSourceBadge\(supplierMeta\)/);
  assert.match(appSource, /function SourceBadgeLogo\(\{ sourceMeta, showLabel = false, className = "" \}\)/);
  assert.match(appSource, /function ManufacturerBadgeLogo\(\{ manufacturerMeta, className = "" \}\)/);
  assert.match(appSource, /fitting-manufacturer-logo/);
  assert.match(appSource, /className="fitting-manufacturer-logo-image"/);
  assert.match(appSource, /onError=\{\(\) => setHasBrokenLogo\(true\)\}/);
  assert.doesNotMatch(appSource, /manufacturerMeta\.code/);
  assert.match(appSource, /className="fitting-availability-cell"/);
  assert.match(appSource, /<span>\{t\.fittingStock\}<\/span>/);
  assert.match(appSource, /renderFittingAvailabilityBadge\(commercialSourceItem\.stock, t\)/);
  assert.match(appSource, /className="fitting-item-card-head-actions"/);
  assert.match(appSource, /supplierMeta \? renderSourceBadge\(supplierMeta\) : null/);
  const headerBlock = appSource.slice(
    appSource.indexOf('<div className="fittings-table-header">'),
    appSource.indexOf('<div className="fittings-table-list">', appSource.indexOf('<div className="fittings-table-header">')),
  );
  const articleHeaderIndex = headerBlock.indexOf('<span>{t.fittingArticle}</span>');
  const supplierHeaderIndex = headerBlock.indexOf('language === "uk" ? "Постачальник" : "Supplier"');
  const manufacturerHeaderIndex = headerBlock.indexOf('language === "uk" ? "Виробник" : "Manufacturer"');
  assert.ok(articleHeaderIndex !== -1 && supplierHeaderIndex !== -1 && manufacturerHeaderIndex !== -1);
  assert.ok(articleHeaderIndex < supplierHeaderIndex && supplierHeaderIndex < manufacturerHeaderIndex);
  assert.doesNotMatch(headerBlock, /t\.fittingSource/);
  const firstCellStart = appSource.indexOf('<div className="fittings-table-name">');
  const firstCellEnd = appSource.indexOf('<span>{productArticle}</span>', firstCellStart);
  assert.ok(firstCellStart !== -1 && firstCellEnd !== -1);
  assert.doesNotMatch(appSource.slice(firstCellStart, firstCellEnd), /renderSourceBadge\(sourceMeta\)/);
  assert.doesNotMatch(
    appSource.slice(
      appSource.indexOf('<div className="fittings-table-header">'),
      appSource.indexOf('<div className="fittings-table-list">', appSource.indexOf('<div className="fittings-table-header">')),
    ),
    /commercialSourceItem\.stock \|\| t\.notSet/,
  );
  assert.match(appSource, /const fittingTaxonomyManufacturersById = useMemo\(/);
  assert.match(appSource, /const selectedFittingSupplierMeta = selectedFittingDetail/);
  assert.match(appSource, /const selectedFittingManufacturerMeta = selectedFittingDetail/);
  assert.match(appSource, /renderSourceBadge\(selectedFittingSupplierMeta \|\| selectedFittingSourceMeta\)/);
  assert.match(appSource, /renderManufacturerBadge\(selectedFittingManufacturerMeta, \{ className: "fitting-manufacturer-badge" \}\)/);
  assert.match(appSource, /getFittingManufacturerMeta\(item\)/);
  assert.match(appSource, /selectedFittingManufacturerMeta \? \(/);
  assert.match(appSource, /const productManufacturerMeta = getFittingManufacturerMeta\(item\);/);
  assert.match(appSource, /const \[isFittingDescriptionOpen, setIsFittingDescriptionOpen\] = useState\(false\);/);
  assert.match(appSource, /const \[isFittingCharacteristicsOpen, setIsFittingCharacteristicsOpen\] = useState\(false\);/);
  assert.match(appSource, /const \[isFittingSuppliersOpen, setIsFittingSuppliersOpen\] = useState\(false\);/);
  assert.match(appSource, /useEffect\(\(\) => \{\s*setIsFittingDescriptionOpen\(false\);\s*setIsFittingCharacteristicsOpen\(false\);\s*setIsFittingSuppliersOpen\(false\);\s*\}, \[selectedFittingDetail\?\.id\]\);/);
  assert.match(appSource, /fitting-details-section-card\$\{isFittingDescriptionOpen \? " is-open" : ""\}/);
  assert.match(appSource, /className="fitting-details-section-header fitting-details-section-toggle"/);
  assert.match(appSource, /className="fitting-details-section-title"/);
  assert.match(appSource, /onClick=\{\(\) => setIsFittingDescriptionOpen\(\(current\) => !current\)\}/);
  assert.match(appSource, /onClick=\{\(\) => setIsFittingCharacteristicsOpen\(\(current\) => !current\)\}/);
  assert.match(appSource, /onClick=\{\(\) => setIsFittingSuppliersOpen\(\(current\) => !current\)\}/);
  assert.match(appSource, /ChevronRight className=\{isFittingDescriptionOpen \? "expanded" : ""\} size=\{16\} \/>/);
  assert.match(appSource, /ChevronRight className=\{isFittingCharacteristicsOpen \? "expanded" : ""\} size=\{16\} \/>/);
  assert.match(appSource, /ChevronRight className=\{isFittingSuppliersOpen \? "expanded" : ""\} size=\{16\} \/>/);
  assert.match(appSource, /fitting-details-section-title[\s\S]*t\.fittingCharacteristics[\s\S]*Object\.keys\(selectedFittingDetail\.characteristics \|\| \{\}\)\.length/);
  assert.match(appSource, /fitting-details-section-title[\s\S]*Постачальники[\s\S]*selectedFittingDetail\.supplier_offers\.length/);
  assert.match(appSource, /className="fitting-details-offer-list"/);
  assert.match(appSource, /fitting-details-characteristic fitting-details-offer-row/);
  assert.match(appSource, /<dt>Артикул<\/dt>/);
  assert.match(appSource, /<dt>Ціна<\/dt>/);
  assert.match(appSource, /<dt>Одиниця<\/dt>/);
  assert.match(appSource, /<dt>Наявність<\/dt>/);
  assert.match(appSource, /<dt>Джерело<\/dt>/);
  assert.match(appSource, /Відкрити товар/);
  assert.match(appSource, /className="fitting-details-offer-source-link"/);
  assert.doesNotMatch(appSource, /<a href=\{offer\.source_url\} rel="noreferrer" target="_blank">\s*URL\s*<\/a>/);
  const detailMetaBlock = appSource.slice(
    appSource.indexOf('<div className="fitting-details-meta">'),
    appSource.indexOf('{selectedFittingDetail.source_url ? (', appSource.indexOf('<div className="fitting-details-meta">')),
  );
  assert.doesNotMatch(detailMetaBlock, /selectedFittingManufacturerMeta/);
  assert.match(catalogViewSource, /function chooseBestLegacyRow\(rows = \[\], activeCity = "", options = \{\}\)/);
  assert.match(catalogViewSource, /function chooseCommercialLegacyRow\(rows = \[\], representativeRow = null, activeCity = ""\)/);
  assert.match(catalogViewSource, /commercial_legacy_row: commercialLegacyRow/);
});

test("fitting catalog count labels keep root total and active category counts separate", () => {
  const allCards = Array.from({ length: 6 }, (_, index) => ({ id: index + 1 }));

  assert.equal(
    getCanonicalFittingsCountLabel({
      activeCategoryCode: "",
      visibleCards: [],
      allCards,
      language: "uk",
    }),
    "6 товарів",
  );
  assert.equal(
    getCanonicalFittingsCountLabel({
      activeCategoryCode: "drawer_slides",
      visibleCards: [],
      allCards,
      language: "uk",
    }),
    "0 товарів",
  );
  assert.equal(
    getCanonicalFittingsCountLabel({
      activeCategoryCode: "fasteners",
      visibleCards: allCards,
      allCards,
      language: "uk",
    }),
    "6 товарів",
  );
});
