import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("material gallery opens a local lightbox and keeps the fetch path unchanged", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(appPath, "utf8");

  const galleryStart = source.indexOf("function MaterialDetailGallery");
  const galleryEnd = source.indexOf("async function handleImportMaterial", galleryStart);
  const gallerySource = galleryStart >= 0 && galleryEnd > galleryStart ? source.slice(galleryStart, galleryEnd) : source;
  const lightboxStart = gallerySource.indexOf("const previewLightbox =");
  const lightboxEnd = gallerySource.indexOf("return (", lightboxStart);
  const lightboxSource = lightboxStart >= 0 && lightboxEnd > lightboxStart
    ? gallerySource.slice(lightboxStart, lightboxEnd)
    : gallerySource;

  assert.match(gallerySource, /const \[isPreviewOpen, setIsPreviewOpen\] = useState\(false\);/);
  assert.match(gallerySource, /onClick=\{\(\) => setIsPreviewOpen\(true\)\}/);
  assert.match(gallerySource, /supplierOffer\?\.image_urls/);
  assert.match(gallerySource, /new Image\(\)/);
  assert.match(gallerySource, /preloader\.onload/);
  assert.match(gallerySource, /preloader\.onerror/);
  assert.match(gallerySource, /const cachedValidUrls = remoteCandidateUrls\.filter/);
  assert.match(gallerySource, /setValidRemoteUrls\(\[\.\.\.cachedValidUrls, \.\.\.loadedUrls\.filter\(Boolean\)\]\)/);
  assert.match(gallerySource, /preloader\.src = ""/);
  assert.match(gallerySource, /is_remote: true/);
  assert.match(gallerySource, /normalizeMaterialGalleryUrl/);
  assert.match(gallerySource, /removeFailedGalleryEntry/);
  assert.match(gallerySource, /onError=\{\(\) => removeFailedGalleryEntry/);
  assert.match(gallerySource, /return \[\.\.\.cachedImages, \.\.\.remoteImages\]/);
  assert.match(gallerySource, /window\.addEventListener\("keydown", handleKeyDown\);/);
  assert.match(lightboxSource, /className="fitting-details-preview-backdrop"/);
  assert.match(lightboxSource, /className="fitting-details-preview-panel"/);
  assert.match(lightboxSource, /onClick=\{\(\) => setIsPreviewOpen\(false\)\}/);
  assert.match(lightboxSource, /src=\{activeEntry\.objectUrl \|\| ""\}/);
  assert.doesNotMatch(lightboxSource, /getMaterialImageBlobById/);
});

test("material source import shows a blocking overlay and uses a dedicated busy state", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /const \[materialImportWorking, setMaterialImportWorking\] = useState\(false\);/);
  assert.match(appSource, /const \[materialImportWorkingLongWait, setMaterialImportWorkingLongWait\] = useState\(false\);/);
  assert.match(appSource, /setMaterialImportWorking\(true\);/);
  assert.match(appSource, /setMaterialImportWorking\(false\);/);
  assert.match(appSource, /materialImportWorking \? \(/);
  assert.match(appSource, /Обробка\.\.\./);
  assert.match(appSource, /materialImportWorkingLongWait/);
  assert.match(appSource, /beforeunload/);
  assert.match(appSource, /setStatus\(\{ message: t\.materialUpdated, tone: "success" \}\);/);
  assert.match(appSource, /className="materials-import-form-fieldset" disabled=\{materialImportWorking\}/);
  assert.match(appSource, /className="material-import-processing-backdrop"/);
  assert.match(appSource, /className="material-import-processing-spinner"/);
  assert.match(stylesSource, /\.materials-import-form-fieldset \{/);
  assert.match(stylesSource, /\.material-import-processing-backdrop \{/);
  assert.match(stylesSource, /\.material-import-processing-spinner \{/);
  assert.match(stylesSource, /@keyframes material-import-spin/);
});
