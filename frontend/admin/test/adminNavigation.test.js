import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("admin app uses canonical section-based navigation helpers", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const source = readFileSync(appPath, "utf8");

  assert.match(source, /const initialAdminRoute = readAdminRouteFromLocation\(\);/);
  assert.match(source, /activeView === "processing"[\s\S]*activeView === "catalogHoles"/);
  assert.match(source, /updateAdminHistory\(\{\s*mountingNodesRoute: nextMountingNodesRoute,\s*processingTab: nextProcessingTab,\s*view: nextView,/);
  assert.match(source, /processingTab: "overview"/);
  assert.match(source, /setMountingNodesRouteState\(nextRoute\);\s*setMountingNodesRouteReady\(true\);\s*setMountingNodesInitialState\(null\);\s*setCatalogHolesMode\("create"\);/);
  assert.match(source, /connectionsOverview: "connections-overview"/);
  assert.match(source, /switchView\("connectionsOverview"\)/);
  assert.match(source, /getConnectionsWorkspaceSidebarTabs\(\{ language \}\)/);
  assert.match(source, /const isConnectionsWorkspaceView =[\s\S]*const isConnectionsNavigationView = shouldAutoOpenConnectionsMenu\(activeView\) \|\| isConnectionsWorkspaceView;/);
  assert.match(source, /getCollapsedSidebarGroupClickTarget\(\{\s*currentView: activeViewRef\.current,\s*groupKey: "processing",\s*userRole: user\?\.role,\s*}\)/);
  assert.match(source, /sidebarFlyoutPreserveRouteChangeRef\.current = true;/);
  assert.match(source, /isConnectionsWorkspaceView \?\s*\(\r?\n\s*<ConnectionsWorkspace/);
  assert.match(
    source,
    /function resetFittingCatalogNavigation\(\) \{[\s\S]*localStorage\.removeItem\(FITTING_CATEGORY_STORAGE_KEY\);[\s\S]*setSelectedFittingCategory\(""\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /function openFittingCatalogRoot\(\) \{[\s\S]*resetFittingCatalogNavigation\(\);[\s\S]*switchView\("catalogFittings"\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /sidebarFlyout\?\.groupKey === "catalog"[\s\S]*key: "catalogFittings"[\s\S]*onClick: \(\) => \{[\s\S]*openFittingCatalogRoot\(\);[\s\S]*closeSidebarOnMobile\(\);[\s\S]*closeSidebarFlyout\(\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /isCatalogMenuOpen \? \(\r?\n\s*<div className="nav-subtabs">[\s\S]*openFittingCatalogRoot\(\);[\s\S]*closeSidebarOnMobile\(\);[\s\S]*closeSidebarFlyout\(\);[\s\S]*\}/,
  );
  assert.match(source, /onClick=\{\(\) => \{[\s\S]*setSelectedFittingCategory\(category\.code\);[\s\S]*\}\}/);
});
