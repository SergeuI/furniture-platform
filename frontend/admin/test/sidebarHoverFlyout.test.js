import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("collapsed sidebar hover flyout wiring keeps hover separate from click navigation", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const stylesSource = readFileSync(stylesPath, "utf8");

  assert.match(appSource, /onPointerEnter=\{\(event\) => openSidebarFlyoutOnHover\("processing", event\)\}/);
  assert.match(appSource, /onPointerEnter=\{\(event\) => openSidebarFlyoutOnHover\("connections", event\)\}/);
  assert.match(appSource, /onPointerEnter=\{\(event\) => openSidebarFlyoutOnHover\("catalog", event\)\}/);
  assert.match(appSource, /onPointerLeave=\{scheduleSidebarFlyoutClose\}/);
  assert.match(appSource, /sidebarFlyoutCloseTimerRef\.current = window\.setTimeout/);
  assert.match(appSource, /flyoutOpen: isDesktopSidebarCollapsed && isProcessingFlyoutOpen/);
  assert.match(appSource, /routeActive: isProcessingSectionView/);
  assert.match(appSource, /routeActive: isConnectionsNavigationView/);
  assert.match(appSource, /routeActive: isCatalogView/);

  assert.match(stylesSource, /\.sidebar-shell:hover \.sidebar-collapse-handle,/);
  assert.match(stylesSource, /opacity: 0;/);
  assert.match(stylesSource, /pointer-events: none;/);
  assert.match(stylesSource, /transform: translateX\(-100%\);/);
  assert.match(stylesSource, /transform: translateX\(0\);/);
  assert.match(stylesSource, /transition:\s*opacity 0\.18s ease,/);
});
