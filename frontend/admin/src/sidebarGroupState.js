export function getSidebarGroupVisualState({ routeActive = false, flyoutOpen = false } = {}) {
  const isRouteActive = Boolean(routeActive);
  const isFlyoutOpen = Boolean(flyoutOpen) && !isRouteActive;

  return {
    className: isRouteActive ? "is-route-active" : isFlyoutOpen ? "is-flyout-open" : "",
    isFlyoutOpen,
    isRouteActive,
  };
}

export function getCollapsedSidebarVisualActiveGroupKey({
  isCollapsed = false,
  openFlyoutGroupKey = "",
  routeActiveGroupKey = "",
} = {}) {
  if (isCollapsed && openFlyoutGroupKey) {
    return openFlyoutGroupKey;
  }

  return routeActiveGroupKey || "";
}

export function getCollapsedSidebarGroupClickTarget({
  currentView = "",
  groupKey = "",
  userRole = "admin",
} = {}) {
  const targetView =
    groupKey === "processing"
      ? "processing"
      : groupKey === "connections"
        ? "connectionsOverview"
        : groupKey === "catalog"
          ? (userRole === "admin" ? "catalogHub" : "catalogMaterials")
          : "";

  if (!targetView) {
    return null;
  }

  return {
    shouldPreserveFlyoutOnRouteChange: currentView !== targetView,
    targetView,
  };
}

export function getNextCollapsedSidebarFlyoutState({
  currentFlyoutGroupKey = "",
  nextFlyoutGroupKey = "",
  nextTop = 12,
} = {}) {
  if (!nextFlyoutGroupKey) {
    return null;
  }

  if (currentFlyoutGroupKey === nextFlyoutGroupKey) {
    return null;
  }

  return {
    groupKey: nextFlyoutGroupKey,
    top: nextTop,
  };
}
