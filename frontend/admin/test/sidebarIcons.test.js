import assert from "node:assert/strict";
import test from "node:test";

import {
  getSidebarControlIconAsset,
  getSidebarFlyoutIconAsset,
  getSidebarNavIconAsset,
} from "../src/sidebarIcons.js";

test("sidebar icon assets map to the prepared PNG set", () => {
  assert.match(getSidebarNavIconAsset("home"), /home\.png$/);
  assert.match(getSidebarNavIconAsset("processing"), /processing_operations\.png$/);
  assert.match(getSidebarNavIconAsset("catalog"), /values_guide\.png$/);
  assert.match(getSidebarControlIconAsset("expand"), /sidebar_expand\.png$/);
  assert.match(getSidebarControlIconAsset("collapse"), /sidebar_collapse\.png$/);
  assert.match(getSidebarControlIconAsset("next"), /next_arrow\.png$/);
  assert.match(getSidebarFlyoutIconAsset("processing", "overview"), /overview_eye\.png$/);
  assert.match(getSidebarFlyoutIconAsset("connections", "mountingSchemes"), /fastening_schemes\.png$/);
  assert.match(getSidebarFlyoutIconAsset("catalog", "catalogValues"), /values_guide\.png$/);
  assert.equal(getSidebarNavIconAsset("missing"), null);
});
