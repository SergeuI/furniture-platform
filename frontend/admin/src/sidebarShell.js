export const SIDEBAR_COLLAPSE_BREAKPOINT = 1180;
export const SIDEBAR_COLLAPSED_STORAGE_KEY = "furniture_admin_sidebar_collapsed";

export function readPersistedSidebarCollapsedState(storage = typeof window !== "undefined" ? window.localStorage : null) {
  if (!storage) {
    return false;
  }

  return storage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === "true";
}

export function writePersistedSidebarCollapsedState(
  storage = typeof window !== "undefined" ? window.localStorage : null,
  isSidebarCollapsed = false,
) {
  if (!storage) {
    return;
  }

  storage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, isSidebarCollapsed ? "true" : "false");
}

export function shouldUseCollapsedSidebar({ isCompactSidebarMode = false, isSidebarCollapsed = false } = {}) {
  return !isCompactSidebarMode && Boolean(isSidebarCollapsed);
}
