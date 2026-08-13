import assert from "node:assert/strict";
import test from "node:test";

import { loadPrimaryFittingImageBlob } from "../src/fittingImagePreview.js";

test("primary fitting image loader prefers existing images and falls back to details", async () => {
  const calls = [];
  const blob = new Blob(["image-bytes"], { type: "image/png" });

  const result = await loadPrimaryFittingImageBlob({
    item: {
      id: 53,
      images: [],
    },
    token: "token-123",
    getDetails: async (token, itemId) => {
      calls.push(["details", token, itemId]);
      return {
        success: true,
        item: {
          id: 53,
          images: [
            { id: 50, is_primary: false, sort_order: 2, content_type: "image/jpeg" },
            { id: 51, is_primary: true, sort_order: 1, content_type: "image/png" },
          ],
        },
      };
    },
    getImageBlob: async (token, itemId, imageId) => {
      calls.push(["blob", token, itemId, imageId]);
      return {
        success: true,
        blob,
        contentType: "image/png",
      };
    },
  });

  assert.equal(result.success, true);
  assert.equal(result.fittingId, "53");
  assert.equal(result.imageId, "51");
  assert.equal(result.contentType, "image/png");
  assert.equal(result.blob, blob);
  assert.deepEqual(calls, [
    ["details", "token-123", "53"],
    ["blob", "token-123", "53", "51"],
  ]);
});

test("primary fitting image loader keeps existing image arrays without refetching details", async () => {
  const blob = new Blob(["image-bytes"], { type: "image/jpeg" });

  const result = await loadPrimaryFittingImageBlob({
    item: {
      id: 61136,
      images: [
        { id: 29, is_primary: false, sort_order: 2, content_type: "image/jpeg" },
        { id: 30, is_primary: true, sort_order: 1, content_type: "image/jpeg" },
      ],
    },
    token: "token-123",
    getDetails: async () => {
      throw new Error("details should not be fetched");
    },
    getImageBlob: async (token, itemId, imageId) => {
      assert.equal(token, "token-123");
      assert.equal(itemId, "61136");
      assert.equal(imageId, "30");
      return {
        success: true,
        blob,
        contentType: "image/jpeg",
      };
    },
  });

  assert.equal(result.success, true);
  assert.equal(result.fittingId, "61136");
  assert.equal(result.imageId, "30");
  assert.equal(result.blob, blob);
});
