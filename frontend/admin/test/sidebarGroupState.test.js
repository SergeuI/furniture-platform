import assert from "node:assert/strict";
import test from "node:test";

import {
  getCollapsedSidebarGroupClickTarget,
  getCollapsedSidebarVisualActiveGroupKey,
  getNextCollapsedSidebarFlyoutState,
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

test("collapsed sidebar flyout toggles and visual active key follows the open group", () => {
  let flyoutState = null;

  flyoutState = getNextCollapsedSidebarFlyoutState({
    currentFlyoutGroupKey: flyoutState?.groupKey || "",
    nextFlyoutGroupKey: "processing",
    nextTop: 88,
  });

  assert.deepEqual(flyoutState, {
    groupKey: "processing",
    top: 88,
  });
  assert.equal(
    getCollapsedSidebarVisualActiveGroupKey({
      isCollapsed: true,
      openFlyoutGroupKey: flyoutState?.groupKey || "",
      routeActiveGroupKey: "entitlements",
    }),
    "processing",
  );

  flyoutState = null;
  assert.equal(
    getCollapsedSidebarVisualActiveGroupKey({
      isCollapsed: true,
      openFlyoutGroupKey: flyoutState?.groupKey || "",
      routeActiveGroupKey: "entitlements",
    }),
    "entitlements",
  );

  flyoutState = getNextCollapsedSidebarFlyoutState({
    currentFlyoutGroupKey: flyoutState?.groupKey || "",
    nextFlyoutGroupKey: "connections",
    nextTop: 104,
  });

  assert.deepEqual(flyoutState, {
    groupKey: "connections",
    top: 104,
  });

  flyoutState = getNextCollapsedSidebarFlyoutState({
    currentFlyoutGroupKey: flyoutState?.groupKey || "",
    nextFlyoutGroupKey: "processing",
    nextTop: 120,
  });

  assert.deepEqual(flyoutState, {
    groupKey: "processing",
    top: 120,
  });
  assert.equal(
    getCollapsedSidebarVisualActiveGroupKey({
      isCollapsed: true,
      openFlyoutGroupKey: flyoutState?.groupKey || "",
      routeActiveGroupKey: "entitlements",
    }),
    "processing",
  );

  flyoutState = getNextCollapsedSidebarFlyoutState({
    currentFlyoutGroupKey: flyoutState?.groupKey || "",
    nextFlyoutGroupKey: "processing",
    nextTop: 120,
  });

  assert.equal(flyoutState, null);
});

test("collapsed sidebar group clicks navigate through canonical overview routes in sequence", () => {
  const clickSequence = ["processing", "connections", "catalog", "catalog"];
  let currentView = "entitlements";

  const results = clickSequence.map((groupKey) => {
    const target = getCollapsedSidebarGroupClickTarget({
      currentView,
      groupKey,
      userRole: "admin",
    });

    assert.ok(target);
    currentView = target.targetView;
    return {
      groupKey,
      currentView,
      preserveFlyout: target.shouldPreserveFlyoutOnRouteChange,
    };
  });

  assert.deepEqual(results, [
    {
      groupKey: "processing",
      currentView: "processing",
      preserveFlyout: true,
    },
    {
      groupKey: "connections",
      currentView: "connectionsOverview",
      preserveFlyout: true,
    },
    {
      groupKey: "catalog",
      currentView: "catalogHub",
      preserveFlyout: true,
    },
    {
      groupKey: "catalog",
      currentView: "catalogHub",
      preserveFlyout: false,
    },
  ]);
});
