import assert from "node:assert/strict";
import test from "node:test";

import {
  getConnectionsWorkspaceOverviewCards,
  getConnectionsWorkspacePageLabel,
  getConnectionsWorkspaceSidebarTabs,
  resolveActiveConnectionsNavigationKey,
  shouldAutoOpenConnectionsMenu,
} from "../src/connectionsWorkspace.js";

test("connections workspace exposes a stable sidebar and overview card contract", () => {
  const sidebarTabs = getConnectionsWorkspaceSidebarTabs({ language: "en" });
  const overviewCards = getConnectionsWorkspaceOverviewCards({ language: "en" });

  assert.deepEqual(
    sidebarTabs.map((tab) => tab.key),
    [
      "connectionsOverview",
      "mountingNodes",
      "mountingSchemes",
      "connectionTypes",
      "mountingCompatibility",
      "connectionsTesting",
    ],
  );
  assert.deepEqual(
    sidebarTabs.map((tab) => tab.label),
    [
      "Overview",
      "Mounting nodes",
      "Mounting schemes",
      "Connection types",
      "Compatibility and replacements",
      "Testing",
    ],
  );
  assert.deepEqual(
    overviewCards.map((card) => card.section),
    [
      "mounting-nodes",
      "mounting-schemes",
      "connection-types",
      "mounting-compatibility",
      "connections-testing",
    ],
  );
  assert.equal(overviewCards[0].view, "catalogHoles");
  assert.equal(getConnectionsWorkspacePageLabel("mountingSchemes", "en"), "Mounting schemes");
  assert.equal(resolveActiveConnectionsNavigationKey({ activeView: "mountingSchemes" }), "mountingSchemes");
  assert.equal(resolveActiveConnectionsNavigationKey({ activeView: "catalogHoles" }), "mountingNodes");
  assert.equal(shouldAutoOpenConnectionsMenu("connectionsTesting"), true);
  assert.equal(shouldAutoOpenConnectionsMenu("catalogHoles"), true);
  assert.equal(shouldAutoOpenConnectionsMenu("projects"), false);
});
