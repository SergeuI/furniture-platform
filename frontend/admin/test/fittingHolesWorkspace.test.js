import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting holes workspace is extracted into a reusable layout shell", () => {
  const workspacePath = fileURLToPath(
    new URL("../src/components/processing/FittingHolesWorkspace.jsx", import.meta.url),
  );
  const workspaceSource = readFileSync(workspacePath, "utf8");
  const threePreviewPath = fileURLToPath(
    new URL("../src/components/processing/HolesMountingThreePreview.jsx", import.meta.url),
  );
  const threePreviewSource = readFileSync(threePreviewPath, "utf8");
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");

  assert.equal(workspaceSource.includes("holes-grid"), true);
  assert.equal(workspaceSource.includes("children"), true);
  assert.equal(workspaceSource.includes("className"), true);
  assert.equal(appSource.includes('import FittingHolesWorkspace from "./components/processing/FittingHolesWorkspace.jsx";'), true);
  assert.equal(appSource.includes('import MountingNodesCreatePanel from "./components/processing/MountingNodesCreatePanel.jsx";'), true);
  assert.equal(appSource.includes('<FittingHolesWorkspace className="mounting-node-editor-workspace">'), true);
  assert.equal(appSource.includes("</FittingHolesWorkspace>"), true);
  assert.equal(appSource.includes("MountingNodesCreatePanel"), true);
  assert.equal(appSource.includes('catalogHolesMode === "create"'), true);
  assert.equal(appSource.includes('catalogHolesMode === "create" ? ('), true);
  assert.equal(appSource.includes(') : catalogHolesMode === "editor" ? ('), true);
  assert.equal(appSource.includes("holes-workspace-save-panel"), true);
  assert.equal(appSource.includes("holes-preview-3d-card"), true);
  assert.equal(appSource.includes("mounting-node-editor-left-column"), true);
  assert.equal(appSource.includes("mounting-node-editor-right-column"), true);
  assert.equal(threePreviewSource.includes("createHoleIdTexture(getSafeHolePointLabel(hole?.label, `P${index + 1}`))"), true);
  assert.equal(threePreviewSource.includes("createHoleIdTexture(getSafeHolePointLabel(hole?.label, `P${index + 1}`), state)"), true);
  assert.equal(threePreviewSource.includes("createHoleIdTexture(String(hole.id))"), false);
});
