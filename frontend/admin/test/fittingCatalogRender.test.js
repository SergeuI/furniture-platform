import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("canonical fitting render pipeline keeps overview counts, commercial rows, and image fallbacks", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const catalogViewPath = fileURLToPath(new URL("../src/fittingCatalogView.js", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const catalogViewSource = readFileSync(catalogViewPath, "utf8");

  assert.match(
    appSource,
    /getCanonicalFittingsOverviewCountLabel\(\{\s*allCards: fittingCanonicalCatalogView\.allCards,\s*language,\s*\}\)/,
  );
  assert.match(
    appSource,
    /const activePageLabel = useMemo\([\s\S]*if \(isCatalogFittingsView\) \{[\s\S]*getCanonicalFittingsOverviewCountLabel\(\{\s*allCards: fittingCanonicalCatalogView\.allCards,\s*language,\s*\}\)[\s\S]*\}\s*,\s*\[[\s\S]*fittingCanonicalCatalogView\.allCards[\s\S]*language[\s\S]*\]\s*\)/,
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
  assert.match(appSource, /commercialSourceItem\.stock \|\| t\.notSet/);
  assert.match(appSource, /className="fitting-availability-cell"/);
  assert.match(appSource, /<span>\{t\.fittingStock\}<\/span>/);
  assert.doesNotMatch(
    appSource.slice(
      appSource.indexOf('<div className="fittings-table-header">'),
      appSource.indexOf('<div className="fittings-table-list">', appSource.indexOf('<div className="fittings-table-header">')),
    ),
    /commercialSourceItem\.stock \|\| t\.notSet/,
  );
  assert.match(catalogViewSource, /function chooseBestLegacyRow\(rows = \[\], activeCity = "", options = \{\}\)/);
  assert.match(catalogViewSource, /function chooseCommercialLegacyRow\(rows = \[\], representativeRow = null, activeCity = ""\)/);
  assert.match(catalogViewSource, /commercial_legacy_row: commercialLegacyRow/);
});
