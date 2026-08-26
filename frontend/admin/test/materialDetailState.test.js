import assert from "node:assert/strict";
import test from "node:test";

import {
  isMaterialDetailInitialReady,
  shouldOpenMaterialDetailModal,
  shouldShowOwnersCount,
  shouldShowOwnersEmptyState,
  shouldShowOwnersLoadingState,
  shouldShowSupplierEmptyState,
  shouldShowSupplierErrorState,
  shouldShowSupplierLoadingState,
  shouldShowSupplierTabs,
} from "../src/components/materialDetailState.js";

test("material detail supplier and owner lifecycle only shows empty state after loaded data", () => {
  assert.equal(shouldShowSupplierLoadingState("idle"), true);
  assert.equal(shouldShowSupplierLoadingState("loading"), true);
  assert.equal(shouldShowSupplierLoadingState("loaded"), false);
  assert.equal(shouldShowSupplierLoadingState("error"), false);

  assert.equal(shouldShowSupplierTabs("loading", []), false);
  assert.equal(shouldShowSupplierEmptyState("loading", []), false);
  assert.equal(shouldShowSupplierTabs("loaded", []), false);
  assert.equal(shouldShowSupplierEmptyState("loaded", []), true);
  assert.equal(shouldShowSupplierTabs("loaded", [{ id: 1 }]), true);
  assert.equal(shouldShowSupplierEmptyState("loaded", [{ id: 1 }]), false);
  assert.equal(shouldShowSupplierErrorState("error"), true);

  assert.equal(shouldShowOwnersLoadingState("idle"), true);
  assert.equal(shouldShowOwnersLoadingState("loading"), true);
  assert.equal(shouldShowOwnersLoadingState("loaded"), false);
  assert.equal(shouldShowOwnersCount("loaded", [{ id: 1 }]), true);
  assert.equal(shouldShowOwnersEmptyState("loaded", []), true);
  assert.equal(shouldShowOwnersEmptyState("loading", []), false);

  assert.equal(isMaterialDetailInitialReady("loading", "loading"), false);
  assert.equal(isMaterialDetailInitialReady("loaded", "loading"), false);
  assert.equal(isMaterialDetailInitialReady("loaded", "loaded"), true);
  assert.equal(isMaterialDetailInitialReady("error", "loaded"), true);

  assert.equal(shouldOpenMaterialDetailModal("loading", "loaded", "loaded"), false);
  assert.equal(shouldOpenMaterialDetailModal("loaded", "loaded", "loaded"), true);
  assert.equal(shouldOpenMaterialDetailModal("loaded", "loaded", "error"), true);
  assert.equal(shouldOpenMaterialDetailModal("loaded", "error", "loaded"), true);
  assert.equal(shouldOpenMaterialDetailModal("error", "loaded", "loaded"), false);
});
