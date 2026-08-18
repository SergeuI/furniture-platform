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
  assert.match(appSource, /className="toggle-label fitting-source-field"/);
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
  assert.match(stylesSource, /\.fitting-source-modal-form \.toggle-label \{\s*align-items: center;[\s\S]*min-height: 36px;/);
  assert.match(stylesSource, /\.fitting-source-modal-form \.toggle-label > input\[type="checkbox"\] \{\s*justify-self: start;[\s\S]*width: 18px;/);

  assert.match(stylesSource, /\.fitting-action-menu-panel \{\s*max-height: calc\(100vh - 16px\);[\s\S]*position: fixed;[\s\S]*width: 220px;[\s\S]*z-index: 120;/);
  assert.match(stylesSource, /\.fitting-row-menu \{\s*overflow: visible;[\s\S]*z-index: 20;/);
  assert.match(stylesSource, /\.fitting-item-card-head-actions \{\s*align-items: end;[\s\S]*justify-items: end;/);
  assert.match(stylesSource, /\.service-tree-badge\.danger \{\s*background: #fdecec;[\s\S]*color: #b42318;/);
  assert.match(stylesSource, /\.fitting-item-card,\s*\.fitting-item-card-head \{\s*overflow: visible;/);
  assert.match(stylesSource, /\.fitting-supplier-empty \{\s*max-width: 100%;/);
  assert.match(stylesSource, /\.fittings-table-shell \{\s*border: 1px solid #dbe1e7;[\s\S]*overflow: visible;/);
  assert.match(stylesSource, /\.fittings-table-header,\s*\.fittings-table-row \{\s*align-items: center;[\s\S]*minmax\(120px, 0\.85fr\)[\s\S]*minmax\(120px, 0\.9fr\);/);
  assert.match(stylesSource, /\.fittings-table-row \{\s*background: #ffffff;[\s\S]*overflow: visible;[\s\S]*position: relative;/);
  assert.match(stylesSource, /\.fitting-availability-cell \{\s*min-width: 0;/);
  assert.match(stylesSource, /\.fitting-availability-badge \{\s*display: inline-flex;[\s\S]*min-width: 92px;[\s\S]*white-space: nowrap;/);
  assert.match(appSource, /getFittingAvailabilityLabel\(selectedFittingDetail\.availability, t\)/);
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
  assert.match(appSource, /const \[isFittingDescriptionOpen, setIsFittingDescriptionOpen\] = useState\(false\);/);
  assert.match(appSource, /const \[isFittingCharacteristicsOpen, setIsFittingCharacteristicsOpen\] = useState\(false\);/);
  assert.match(appSource, /const \[isFittingSuppliersOpen, setIsFittingSuppliersOpen\] = useState\(false\);/);
  assert.match(appSource, /fitting-details-section-card\$\{/);
  assert.match(appSource, /className="fitting-details-section-header fitting-details-section-toggle"/);
  assert.match(appSource, /className="fitting-details-section-title"/);
  assert.match(appSource, /ChevronRight className=\{isFittingDescriptionOpen \? "expanded" : ""\} size=\{16\} \/>/);
  assert.match(appSource, /ChevronRight className=\{isFittingCharacteristicsOpen \? "expanded" : ""\} size=\{16\} \/>/);
  assert.match(appSource, /ChevronRight className=\{isFittingSuppliersOpen \? "expanded" : ""\} size=\{16\} \/>/);
  assert.match(appSource, /onClick=\{\(\) => setIsFittingDescriptionOpen\(\(current\) => !current\)\}/);
  assert.match(appSource, /onClick=\{\(\) => setIsFittingCharacteristicsOpen\(\(current\) => !current\)\}/);
  assert.match(appSource, /onClick=\{\(\) => setIsFittingSuppliersOpen\(\(current\) => !current\)\}/);
  assert.match(appSource, /useEffect\(\(\) => \{\s*setIsFittingDescriptionOpen\(false\);\s*setIsFittingCharacteristicsOpen\(false\);\s*setIsFittingSuppliersOpen\(false\);\s*\}, \[selectedFittingDetail\?\.id\]\);/);
  assert.match(appSource, /Постачальника не вказано/);
  assert.match(appSource, /className="fitting-details-empty fitting-details-empty-compact"/);
  assert.doesNotMatch(appSource, /selectedFittingDetail\.supplier_offers\)\s*&&\s*selectedFittingDetail\.supplier_offers\.length\s*\?\s*selectedFittingDetail\.supplier_offers\.length\s*:\s*0/);

  assert.match(stylesSource, /\.fitting-details-section-card \{\s*background: #ffffff;[\s\S]*gap: 12px;[\s\S]*padding: 14px;/);
  assert.match(stylesSource, /\.fitting-details-section-header \{\s*align-items: center;[\s\S]*cursor: pointer;[\s\S]*width: 100%;/);
  assert.match(stylesSource, /\.fitting-details-section-header svg:not\(\.expanded\) \{\s*transform: rotate\(90deg\);/);
  assert.match(stylesSource, /\.fitting-details-section-header svg\.expanded \{\s*transform: rotate\(-90deg\);/);
  assert.match(stylesSource, /\.fitting-details-section-title \{\s*align-items: center;[\s\S]*gap: 8px;/);
  assert.match(stylesSource, /\.fitting-details-section-body \{\s*display: grid;[\s\S]*gap: 8px;/);
  assert.match(stylesSource, /\.fitting-details-offers-list \{\s*display: grid;[\s\S]*gap: 8px;/);
  assert.match(stylesSource, /\.fitting-details-offer-card \{\s*display: grid;[\s\S]*gap: 8px;/);
  assert.match(stylesSource, /\.fitting-details-offer-card-header \{\s*align-items: center;[\s\S]*justify-content: space-between;/);
  assert.match(stylesSource, /\.fitting-details-offer-list \{\s*background: #ffffff;[\s\S]*border-radius: 12px;[\s\S]*overflow: hidden;/);
  assert.match(stylesSource, /\.fitting-details-empty-compact \{\s*background: #f8fafb;[\s\S]*padding: 10px 12px;/);
});
