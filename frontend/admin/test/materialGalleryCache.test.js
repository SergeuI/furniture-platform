import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

const appSource = readFileSync(
  fileURLToPath(new URL("../src/App.jsx", import.meta.url)),
  "utf8",
);

test("material gallery uses a stable cached image loader", () => {
  const galleryStart = appSource.indexOf("function MaterialDetailGallery");
  const galleryEnd = appSource.indexOf("function LegacyMaterialDetailGallery", galleryStart);
  const gallerySource = appSource.slice(galleryStart, galleryEnd);

  assert.match(gallerySource, /const materialImageLoader = useCallback\(/);
  assert.match(gallerySource, /imageLoader=\{materialImageLoader\}/);
  assert.doesNotMatch(gallerySource, /imageLoader=\{\(image\) =>/);
  assert.match(gallerySource, /materialImageBlobCache\.get\(cacheKey\)/);
  assert.match(gallerySource, /getMaterialImageCacheKey\(article, image\)/);
  assert.match(gallerySource, /is_remote: true, source_url: cachedEntry\.objectUrl/);
});

test("material gallery keeps URL-only success and failure results", () => {
  const galleryStart = appSource.indexOf("function MaterialDetailGallery");
  const galleryEnd = appSource.indexOf("function LegacyMaterialDetailGallery", galleryStart);
  const gallerySource = appSource.slice(galleryStart, galleryEnd);

  assert.match(gallerySource, /materialRemoteImageCache\.get\(sourceUrl\) === true/);
  assert.match(gallerySource, /!materialRemoteImageCache\.has\(sourceUrl\)/);
  assert.match(gallerySource, /rememberMaterialRemoteImageResult\(sourceUrl, false\)/);
  assert.match(gallerySource, /setValidRemoteUrls\(\[\.\.\.cachedValidUrls/);
});

test("fitting gallery keeps its default loader fallback", () => {
  const fittingStart = appSource.indexOf("function FittingDetailGallery");
  const fittingEnd = appSource.indexOf("function useFittingPrimaryImageObjectUrl", fittingStart);
  const fittingSource = appSource.slice(fittingStart, fittingEnd);

  assert.match(fittingSource, /imageLoader\n\s*\? await imageLoader\(image\)/);
  assert.match(fittingSource, /getFittingImageBlob\(token, fittingId, imageId\)/);
});

test("material detail gallery scopes images to the selected supplier", () => {
  const galleryStart = appSource.indexOf("function MaterialDetailGallery");
  const galleryEnd = appSource.indexOf("function LegacyMaterialDetailGallery", galleryStart);
  const gallerySource = appSource.slice(galleryStart, galleryEnd);

  assert.match(gallerySource, /selectedSupplierSource = detectFittingSourceSite/);
  assert.match(gallerySource, /selectedSupplierSource === "viyar" && !supplierImageUrls\.length/);
  assert.match(gallerySource, /detectFittingSourceSite\(image\?\.source_url\) === "viyar"/);
  assert.match(gallerySource, /selectedSupplierSource === "kronas"/);
  assert.match(gallerySource, /if \(supplierScopedGallery\) \{\s*return \[\];/);
  assert.match(gallerySource, /return \[\.\.\.cachedImages, \.\.\.remoteImages\]/);
  assert.match(gallerySource, /allowCanonicalFallback/);
});
