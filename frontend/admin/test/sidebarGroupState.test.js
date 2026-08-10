import assert from "node:assert/strict";
import test from "node:test";

import {
  getCollapsedSidebarVisualActiveGroupKey,
  getSidebarGroupVisualState,
} from "../src/sidebarGroupState.js";

test("sidebar group visual state keeps route-active and flyout-open separate", () => {
  assert.deepEqual(getSidebarGroupVisualState({ routeActive: true, flyoutOpen: false }), {
    className: "is-route-active",
    isFlyoutOpen: false,
    isRouteActive: true,
  });

  assert.deepEqual(getSidebarGroupVisualState({ routeActive: false, flyoutOpen: true }), {
    className: "is-flyout-open",
    isFlyoutOpen: true,
    isRouteActive: false,
  });

  assert.deepEqual(getSidebarGroupVisualState({ routeActive: true, flyoutOpen: true }), {
    className: "is-route-active",
    isFlyoutOpen: false,
    isRouteActive: true,
  });

  assert.deepEqual(getSidebarGroupVisualState({ routeActive: false, flyoutOpen: false }), {
    className: "",
    isFlyoutOpen: false,
    isRouteActive: false,
  });
});

test("collapsed sidebar visual active key prefers the open flyout", () => {
  assert.equal(
    getCollapsedSidebarVisualActiveGroupKey({
      isCollapsed: true,
      openFlyoutGroupKey: "processing",
      routeActiveGroupKey: "entitlements",
    }),
    "processing",
  );

  assert.equal(
    getCollapsedSidebarVisualActiveGroupKey({
      isCollapsed: true,
      openFlyoutGroupKey: "",
      routeActiveGroupKey: "entitlements",
    }),
    "entitlements",
  );

  assert.equal(
    getCollapsedSidebarVisualActiveGroupKey({
      isCollapsed: false,
      openFlyoutGroupKey: "processing",
      routeActiveGroupKey: "entitlements",
    }),
    "entitlements",
  );
});
