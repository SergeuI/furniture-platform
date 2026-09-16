import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { getProcessingTemplateMountingVariantLabel } from "../src/processingTemplates.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");
const create = read("../src/components/processing/MountingNodesCreatePanel.jsx");
const detail = read("../src/components/processing/MountingNodesPanelRefined.jsx");
const app = read("../src/App.jsx");
const editorMarker = app.indexOf("mounting-node-editor-workspace");
const editorStart = app.lastIndexOf("<FittingHolesWorkspace", editorMarker);
const editorEnd = app.indexOf("</FittingHolesWorkspace>", editorMarker);
const editor =
  editorMarker >= 0 && editorStart >= 0 && editorEnd > editorStart
    ? app.slice(editorStart, editorEnd)
    : "";

test("create, edit and detail use mounting node terminology", () => {
  for (const source of [create, detail]) {
    for (const label of ["Тип кріплення", "Спосіб з'єднання деталей", "Склад фурнітури", "Функціональний код"]) {
      assert.ok(source.includes(label), label);
    }
  }
  for (const label of ["Спосіб з'єднання деталей", "Склад фурнітури", "Функціональний код"]) {
    assert.ok(editor.includes(label), label);
  }
  assert.ok(editor.includes("Монтажні отвори"));
  assert.ok(detail.includes('label={language === "uk" ? "Монтажні отвори"'));
  assert.ok(editor.includes("3D монтажного вузла"));
});

test("add hole keeps its handler and enabled state", () => {
  const start = editor.indexOf('disabled={!mountingNodeEditorCanAddPoint}');
  const button = editor.slice(start, editor.indexOf("</button>", start));
  assert.ok(button.includes("onClick={openHolePointCreateForm}"));
  assert.ok(button.includes('"Додати отвір" : t.holePointAdd'));
});

test("connection methods reuse existing localized labels", () => {
  for (const code of ["face_to_edge", "surface_mount", "angled_two_planes", "edge_to_edge", "drawer_slides"]) {
    const label = getProcessingTemplateMountingVariantLabel(code, "uk");
    assert.ok(label);
    assert.notEqual(label, code);
  }
  assert.ok(create.includes("getProcessingTemplateMountingVariantLabel(key, language)"));
  assert.ok(editor.includes("{mountingNodeEditorSelectedVariantLabel}"));
  assert.ok(detail.includes("value={selectedNodeActiveVariantLabel}"));
});

test("functional code remains editable with the same bindings", () => {
  assert.ok(create.includes("handleFunctionalChange(event.target.value)"));
  assert.ok(create.includes("value={selectedFunctionalCode}"));
  assert.ok(editor.includes("handleMountingNodeEditorFunctionalChange(event.target.value)"));
  assert.ok(editor.includes("value={mountingNodeEditorSelectedFunctionalCode}"));
});
