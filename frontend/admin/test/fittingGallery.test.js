import assert from "node:assert/strict";
import test from "node:test";

import {
  getFittingGalleryPrimaryImageUrl,
  moveFittingGalleryImageUrl,
  normalizeFittingGalleryImageUrls,
} from "../src/fittingGallery.js";

test("fitting gallery helpers normalize and reorder image URLs", () => {
  assert.deepEqual(normalizeFittingGalleryImageUrls(["  one  ", "", null, "two"]), ["one", "two"]);
  assert.deepEqual(normalizeFittingGalleryImageUrls(" single "), ["single"]);
  assert.equal(getFittingGalleryPrimaryImageUrl(["  first  ", "second"]), "first");
  assert.deepEqual(moveFittingGalleryImageUrl(["a", "b", "c"], 1, -1), ["b", "a", "c"]);
  assert.deepEqual(moveFittingGalleryImageUrl(["a", "b", "c"], 0, 1), ["b", "a", "c"]);
  assert.deepEqual(moveFittingGalleryImageUrl(["a", "b", "c"], 2, 1), ["a", "b", "c"]);
});
