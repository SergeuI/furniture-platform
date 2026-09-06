import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import { getManualMaterialFormValidity } from "../src/materialManualForm.js";

const appSource = readFileSync(
  fileURLToPath(new URL("../src/App.jsx", import.meta.url)),
  "utf8",
);

test("manual material form requires only name and price for submit", () => {
  assert.match(
    appSource,
    /materialCreateMode === "source"\s*\n\s*\? \(loading \|\| !newMaterialSourceUrl\.trim\(\) \|\| isMaterialCreationBlockedByQuota\)\s*\n\s*: \(!manualMaterialFormValid \|\| isMaterialCreationBlockedByQuota\)/,
  );
  assert.match(appSource, /materialManualName[\s\S]*?required[\s\S]*?type="text"/);
  assert.match(appSource, /materialManualPrice[\s\S]*?required[\s\S]*?type="number"/);
  assert.match(appSource, /manualMaterialFormValid/);
});

test("manual material state transition allows zero and positive prices", () => {
  assert.deepEqual(getManualMaterialFormValidity("DELETE_PROTECTION_SMOKE_TEST", "0"), {
    nameValid: true,
    priceValid: true,
    formValid: true,
  });
  assert.equal(
    getManualMaterialFormValidity("DELETE_PROTECTION_SMOKE_TEST", "0.01").formValid,
    true,
  );
});

test("manual price input does not display a fake zero for an empty state", () => {
  const priceInputStart = appSource.indexOf("onChange={(event) => setNewMaterialPrice(event.target.value)}");
  const priceInputEnd = appSource.indexOf("/>", priceInputStart);
  const priceInputSource = appSource.slice(priceInputStart, priceInputEnd);

  assert.ok(priceInputStart > -1);
  assert.ok(priceInputEnd > priceInputStart);
  assert.doesNotMatch(priceInputSource, /placeholder=\"0\"/);
  assert.match(priceInputSource, /value=\{newMaterialPrice\}/);
});

test("manual material state transition blocks missing fields", () => {
  assert.equal(getManualMaterialFormValidity("DELETE_PROTECTION_SMOKE_TEST", "").formValid, false);
  assert.equal(getManualMaterialFormValidity("", "0").formValid, false);
});

test("manual material state transition rejects invalid prices", () => {
  assert.equal(getManualMaterialFormValidity("Material", "abc").formValid, false);
  assert.equal(getManualMaterialFormValidity("Material", "-0.01").formValid, false);
});

test("manual material payload keeps DSP fallback and optional fields", () => {
  assert.match(appSource, /category: materialCategoryFilter \|\| "dsp",/);
  assert.match(appSource, /article: isSourceMode \? null : newMaterialArticle\.trim\(\) \|\| null,/);
  assert.match(appSource, /source_url: isSourceMode \? newMaterialSourceUrl\.trim\(\) \|\| null : null,/);
  assert.match(appSource, /image_url: isSourceMode \? null : newMaterialImageUrl \|\| null,/);
  assert.match(appSource, /if \(materialCreateMode === "manual" && String\(newMaterialManufacturerId \|\| ""\)\.trim\(\)\)/);
});

test("manual form explains why the submit action is unavailable", () => {
  assert.match(appSource, /materialManualRequiredHint/);
  assert.match(
    appSource,
    /materialCreateMode === "manual" && !manualMaterialFormValid/,
  );
  assert.match(appSource, /role="status"/);
});

test("manual material image preview uses the generated data URL and resets on close", () => {
  assert.match(appSource, /className="material-manual-image-preview"/);
  assert.match(appSource, /alt={t\.materialManualImage\}[\s\S]*src={newMaterialImageUrl}/);
  assert.match(appSource, /newMaterialImageUrl \? \([\s\S]*material-manual-image-preview/);
  assert.match(appSource, /function closeMaterialCreateModal\(\) \{[\s\S]*setNewMaterialImageUrl\(""\);/);
});

test("manual material preview keeps a fixed contain layout", () => {
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(stylesSource, /\.material-manual-image-preview \{[\s\S]*height: 112px;[\s\S]*max-width: 180px;[\s\S]*overflow: hidden;/);
  assert.match(stylesSource, /\.material-manual-image-preview img \{[\s\S]*object-fit: contain;/);
});
