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
