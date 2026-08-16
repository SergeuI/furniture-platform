import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting ui stabilization keeps refresh, toast, menu, and detail rendering compact", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /await refreshFittingsCatalogView\(\);/);
  assert.match(
    appSource,
    /const dismissDelay =\s*statusTone === "error" \? 4500 : statusTone === "warning" \? 3000 : 2000;/,
  );
  assert.match(appSource, /const timeoutId = window\.setTimeout\(\(\) => \{\s*setStatusState\(null\);\s*\}, dismissDelay\);/);
  assert.match(appSource, /return \(\) => window\.clearTimeout\(timeoutId\);/);
  assert.match(appSource, /<div className="status-overlay" role="presentation">/);
  assert.match(appSource, /function isAvailabilityChecked\(value\) \{/);
  assert.match(appSource, /className="fitting-source-field-inline fitting-source-field-checkbox-only"/);
  assert.match(appSource, /aria-label=\{t\.fittingStock\}/);
  assert.match(appSource, /checked=\{isAvailabilityChecked\(newFittingForm\.stock\)\}/);
  assert.match(appSource, /onChange=\{\(event\) => setManualFittingAvailability\(event\.target\.checked\)\}/);
  assert.match(appSource, /checked=\{isAvailabilityChecked\(newFittingForm\.supplier_offer\?\.stock\)\}/);
  assert.match(appSource, /onChange=\{\(event\) => setManualSupplierAvailability\(event\.target\.checked\)\}/);
  assert.match(appSource, /document\.addEventListener\("pointerdown", handleFittingMenuDocumentPointerDown\);/);
  assert.match(appSource, /document\.addEventListener\("keydown", handleFittingMenuDocumentKeyDown\);/);
  assert.match(appSource, /document\.removeEventListener\("pointerdown", handleFittingMenuDocumentPointerDown\);/);
  assert.match(appSource, /document\.removeEventListener\("keydown", handleFittingMenuDocumentKeyDown\);/);
  assert.match(appSource, /className="material-card-menu-dropdown fitting-action-menu-panel"/);
  assert.match(appSource, /position: "fixed"/);
  assert.match(appSource, /openFittingMenuActionCountRef\.current = canEditFittingItemHelper\(user, commercialSourceItem\) \? 2 : 1;/);
  assert.match(appSource, /left: `\$\{openFittingMenuPosition\.left\}px`,[\s\S]*top: `\$\{openFittingMenuPosition\.top\}px`/);
  assert.match(appSource, /setOpenFittingMenuPosition\(null\);\s*onEdit\(\);/);
  assert.match(appSource, /setOpenFittingMenuPosition\(null\);\s*onDelete\(\);/);
  assert.match(stylesSource, /\.status-overlay \{\s*align-items: flex-start;[\s\S]*pointer-events: none;/);
  assert.match(stylesSource, /\.status-toast \{\s*align-items: center;[\s\S]*pointer-events: auto;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-source-field-checkbox-only \{\s*align-items: center;[\s\S]*min-height: 36px;/);

  assert.match(stylesSource, /\.fitting-action-menu-panel \{\s*max-height: calc\(100vh - 16px\);[\s\S]*position: fixed;[\s\S]*width: 220px;[\s\S]*z-index: 120;/);
  assert.match(stylesSource, /\.fitting-row-menu \{\s*overflow: visible;[\s\S]*z-index: 20;/);
  assert.match(stylesSource, /\.fitting-item-card,\s*\.fitting-item-card-head \{\s*overflow: visible;/);
  assert.match(stylesSource, /\.fittings-table-shell \{\s*border: 1px solid #dbe1e7;[\s\S]*overflow: visible;/);
  assert.match(stylesSource, /\.fittings-table-header,\s*\.fittings-table-row \{\s*align-items: center;[\s\S]*minmax\(110px, 0\.8fr\)[\s\S]*minmax\(120px, 0\.9fr\);/);
  assert.match(stylesSource, /\.fittings-table-row \{\s*background: #ffffff;[\s\S]*overflow: visible;[\s\S]*position: relative;/);
  assert.match(stylesSource, /\.fitting-availability-cell \{\s*min-width: 0;/);
  assert.match(stylesSource, /\.fitting-availability-badge \{\s*display: inline-flex;[\s\S]*min-width: 92px;[\s\S]*white-space: nowrap;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-manual-gallery-remove \{\s*align-items: center;[\s\S]*background: rgba\(255, 255, 255, 0\.72\);[\s\S]*opacity: 0\.72;[\s\S]*height: 20px;[\s\S]*right: 5px;[\s\S]*top: 5px;[\s\S]*width: 20px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.fitting-manual-gallery-remove:hover,[\s\S]*:focus-visible \{/);
  assert.match(appSource, /<X size=\{12\} \/>/);
  assert.doesNotMatch(
    appSource.slice(
      appSource.indexOf('<div className="fittings-table-header">'),
      appSource.indexOf('</article>', appSource.indexOf('<div className="fittings-table-header">')),
    ),
    /commercialSourceItem\.stock \|\| t\.notSet/,
  );

  assert.match(appSource, /\{Object\.entries\(selectedFittingDetail\.characteristics \|\| \{\}\)\.length \? \(/);
  assert.match(appSource, /className="fitting-details-offers-list"/);
  assert.match(appSource, /className="fitting-details-offer-card-header"/);
  assert.match(appSource, /className="fitting-details-offer-grid"/);
  assert.match(appSource, /className="fitting-details-offer-meta"/);
  assert.match(appSource, /Постачальника не вказано/);
  assert.match(appSource, /className="fitting-details-empty fitting-details-empty-compact"/);
  assert.doesNotMatch(appSource, /selectedFittingDetail\.supplier_offers\)\s*&&\s*selectedFittingDetail\.supplier_offers\.length\s*\?\s*selectedFittingDetail\.supplier_offers\.length\s*:\s*0/);

  assert.match(stylesSource, /\.fitting-details-offers-list \{\s*display: grid;[\s\S]*gap: 12px;/);
  assert.match(stylesSource, /\.fitting-details-offer-card \{\s*background: #ffffff;[\s\S]*padding: 14px;/);
  assert.match(stylesSource, /\.fitting-details-offer-card-header \{\s*align-items: center;[\s\S]*justify-content: space-between;/);
  assert.match(stylesSource, /\.fitting-details-offer-grid \{\s*display: grid;[\s\S]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);/);
  assert.match(stylesSource, /\.fitting-details-offer-meta \{\s*align-items: center;[\s\S]*flex-wrap: wrap;/);
  assert.match(stylesSource, /\.fitting-details-empty-compact \{\s*background: #f8fafb;[\s\S]*padding: 10px 12px;/);
});
