import assert from "node:assert/strict";
import test from "node:test";

import {
  SIDEBAR_COLLAPSED_STORAGE_KEY,
  readPersistedSidebarCollapsedState,
  shouldUseCollapsedSidebar,
  writePersistedSidebarCollapsedState,
} from "../src/sidebarShell.js";

test("sidebar shell helpers persist collapsed state and keep it desktop only", () => {
  const storage = new Map();
  const localStorageMock = {
    getItem(key) {
      return storage.has(key) ? storage.get(key) : null;
    },
    setItem(key, value) {
      storage.set(key, String(value));
    },
  };

  assert.equal(readPersistedSidebarCollapsedState(localStorageMock), false);

  writePersistedSidebarCollapsedState(localStorageMock, true);
  assert.equal(storage.get(SIDEBAR_COLLAPSED_STORAGE_KEY), "true");
  assert.equal(readPersistedSidebarCollapsedState(localStorageMock), true);

  writePersistedSidebarCollapsedState(localStorageMock, false);
  assert.equal(storage.get(SIDEBAR_COLLAPSED_STORAGE_KEY), "false");
  assert.equal(readPersistedSidebarCollapsedState(localStorageMock), false);

  assert.equal(shouldUseCollapsedSidebar({ isCompactSidebarMode: false, isSidebarCollapsed: true }), true);
  assert.equal(shouldUseCollapsedSidebar({ isCompactSidebarMode: true, isSidebarCollapsed: true }), false);
  assert.equal(shouldUseCollapsedSidebar({ isCompactSidebarMode: false, isSidebarCollapsed: false }), false);
});
