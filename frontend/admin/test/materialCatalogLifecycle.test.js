import test from "node:test";
import assert from "node:assert/strict";
import {
  FIXED_PRODUCT_CITY,
  getEffectiveProductCity,
  getMaterialCatalogContextKey,
  shouldShowMaterialSquareMeterBadge,
  shouldRenderMaterialItems,
} from "../src/materialCatalogLifecycle.js";

test("launch mode keeps the effective product city fixed to Kyiv", () => {
  assert.equal(FIXED_PRODUCT_CITY, "kyiv");
  assert.equal(getEffectiveProductCity(), "kyiv");
});

test("material card square-meter badge follows the API support flag", () => {
  assert.equal(shouldShowMaterialSquareMeterBadge({ supports_square_meter_sale: true }), true);
  assert.equal(shouldShowMaterialSquareMeterBadge({ supports_square_meter_sale: false }), false);
  assert.equal(shouldShowMaterialSquareMeterBadge({}), false);
});

test("material cards stay hidden until the current category response is loaded", () => {
  const dsp = getMaterialCatalogContextKey({ category: "dsp", city: "kyiv", search: "", ownershipScope: "all" });
  const mdf = getMaterialCatalogContextKey({ category: "mdf", city: "kyiv", search: "", ownershipScope: "all" });

  assert.equal(shouldRenderMaterialItems({ loading: true, loadedContext: dsp, currentContext: mdf }), false);
  assert.equal(shouldRenderMaterialItems({ loading: false, loadedContext: dsp, currentContext: mdf }), false);
  assert.equal(shouldRenderMaterialItems({ loading: false, loadedContext: mdf, currentContext: mdf }), true);
});

test("late responses cannot make a previous category current", () => {
  const dsp = getMaterialCatalogContextKey({ category: "dsp", city: "kyiv", search: "", ownershipScope: "all" });
  const mdf = getMaterialCatalogContextKey({ category: "mdf", city: "kyiv", search: "", ownershipScope: "all" });
  const root = getMaterialCatalogContextKey({ category: "", city: "kyiv", search: "", ownershipScope: "all" });

  for (const currentContext of [mdf, root, mdf]) {
    assert.equal(shouldRenderMaterialItems({ loading: false, loadedContext: dsp, currentContext }), false);
  }
});

test("category transition keeps a visible loading content area without stale cards", () => {
  const currentContext = getMaterialCatalogContextKey({ category: "mdf", city: "kyiv", search: "", ownershipScope: "all" });
  const previousContext = getMaterialCatalogContextKey({ category: "dsp", city: "kyiv", search: "", ownershipScope: "all" });

  assert.equal(shouldRenderMaterialItems({ loading: true, loadedContext: previousContext, currentContext }), false);
  assert.equal(shouldRenderMaterialItems({ loading: false, loadedContext: null, currentContext }), false);
});

test("project material context changes when active city changes", () => {
  const kyiv = getMaterialCatalogContextKey({ category: "dsp", city: "kyiv", search: "", ownershipScope: "all" });
  const lviv = getMaterialCatalogContextKey({ category: "dsp", city: "lviv", search: "", ownershipScope: "all" });

  assert.notEqual(kyiv, lviv);
});
