import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

function readSource(relativeUrl) {
  return readFileSync(fileURLToPath(new URL(relativeUrl, import.meta.url)), "utf8");
}

test("mounting node functional field is wired through create, editor, and detail sources", () => {
  const appSource = readSource("../src/App.jsx");
  const createPanelSource = readSource("../src/components/processing/MountingNodesCreatePanel.jsx");
  const detailPanelSource = readSource("../src/components/processing/MountingNodesPanelRefined.jsx");
  const functionalSource = readSource("../src/mountingNodeFunctionalCodes.js");

  assert.equal(functionalSource.includes("door_hinge"), true);
  assert.equal(createPanelSource.includes("mounting-node-create-functional-field"), true);
  assert.equal(createPanelSource.includes("getMountingNodeFunctionalOptions"), true);
  assert.equal(createPanelSource.includes("normalizeMountingNodeFunctionalCode"), true);
  assert.equal(appSource.includes("mounting-node-editor-functional-field"), true);
  assert.equal(appSource.includes("handleMountingNodeEditorFunctionalChange"), true);
  assert.equal(appSource.includes("mountingNodeEditorFunctionalOptions"), true);
  assert.equal(appSource.includes("getMountingNodeFunctionalLabel"), true);
  assert.equal(detailPanelSource.includes("getMountingNodeFunctionalLabel"), true);
  assert.equal(detailPanelSource.includes("Functional purpose"), true);
});
