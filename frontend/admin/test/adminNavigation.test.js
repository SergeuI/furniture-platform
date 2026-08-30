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
  assert.match(source, /catalogSuppliers: "catalog-suppliers"/);
  assert.match(source, /switchView\("catalogSuppliers"\)/);
  assert.match(source, /<FittingSuppliersAdminWorkspace/);
  assert.match(
    source,
    /function resetFittingCatalogNavigation\(\) \{[\s\S]*localStorage\.removeItem\(FITTING_CATEGORY_STORAGE_KEY\);[\s\S]*setSelectedFittingCategory\(""\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /function openFittingCategoryCatalog\(categoryCode\) \{[\s\S]*updateAdminHistory\(\{[\s\S]*category: normalizedCategoryCode,[\s\S]*view: nextFittingView,[\s\S]*\}\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /function openFittingCatalogRoot\(\) \{[\s\S]*resetFittingCatalogNavigation\(\);[\s\S]*switchView\(activeView === "catalogFasteners" \? "catalogFasteners" : "catalogFittings"\);[\s\S]*\}/,
  );
  assert.match(
    source,
    /const \[sidebarCatalogSubmenuKey, setSidebarCatalogSubmenuKey\] = useState\(""\);/,
  );
  assert.match(
    source,
    /sidebarFlyout\?\.groupKey === "catalog"[\s\S]*key: "catalogMaterials"[\s\S]*submenuKey: "materials"/,
  );
  assert.match(
    source,
    /sidebarFlyout\?\.groupKey === "catalog"[\s\S]*key: "catalogFittings"[\s\S]*submenuKey: "fittings"/,
  );
  assert.match(
    source,
    /setSidebarCatalogSubmenuKey\("fittings"\);[\s\S]*openFittingCatalogRoot\(\);[\s\S]*closeSidebarOnMobile\(\);/,
  );
  assert.match(
    source,
    /className="sidebar-flyout sidebar-flyout-submenu"/,
  );
  assert.match(source, /onClick=\{\(\) => \{[\s\S]*openFittingCategoryCatalog\(category\.code\);[\s\S]*setNewFittingForm\(\(current\) => \(\{[\s\S]*fitting_group: category\.group \|\| ""/);
});
