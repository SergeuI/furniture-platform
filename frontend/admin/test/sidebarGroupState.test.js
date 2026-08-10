import assert from "node:assert/strict";
import test from "node:test";

import { getSidebarGroupVisualState } from "../src/sidebarGroupState.js";

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
