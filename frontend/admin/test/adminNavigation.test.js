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
  assert.match(source, /isConnectionsWorkspaceView \?\s*\(\r?\n\s*<ConnectionsWorkspace/);
});
