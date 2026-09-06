import assert from "node:assert/strict";
import test from "node:test";

import { normalizeMaterialImageUrl } from "../src/materialImageUrl.js";

test("unwraps VIYAR fit=contain image targets", () => {
  assert.equal(
    normalizeMaterialImageUrl(
      "https://www.viyar.ua/fit=contain/https://cdn.example.com/a.jpg",
    ),
    "https://cdn.example.com/a.jpg",
  );
  assert.equal(
    normalizeMaterialImageUrl(
      "https://www.viyar.ua/fit=contain/https://www.viyar.ua/upload/photos/a.jpg",
    ),
    "https://www.viyar.ua/upload/photos/a.jpg",
  );
});

test("keeps direct URLs and rejects empty or unsupported values", () => {
  assert.equal(
    normalizeMaterialImageUrl("https://cdn.example.com/a.jpg"),
    "https://cdn.example.com/a.jpg",
  );
  assert.equal(normalizeMaterialImageUrl(""), null);
  assert.equal(normalizeMaterialImageUrl("javascript:alert(1)"), null);
});
