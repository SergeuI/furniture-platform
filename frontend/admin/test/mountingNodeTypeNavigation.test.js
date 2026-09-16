import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import postcss from "postcss";
import { filterMountingNodesByType, mountingNodeTypeTiles, resolveMountingNodeTypeSelection } from "../src/mountingNodeTypeNavigation.js";

const nodes = [
  { id: 1, name: "Test", category_code: "fastening", fastening_type: "confirmat" },
  { id: 2, category_code: "fastening", fastening_type: "minifix" },
  { id: 3, category_code: "fastening", fastening_type: null },
  { id: 4, category_code: "fastening", fastening_type: "other" },
  { id: 5, category_code: "hinges", fastening_type: "confirmat" },
  { id: 6, category_code: "fastening" },
];
const source = readFileSync(new URL("../src/components/processing/MountingNodesPanelRefined.jsx", import.meta.url), "utf8");

test("only the type grid has five desktop columns and responsive 3/2/1 columns", () => {
  assert.equal(source.match(/mounting-node-types-grid/g)?.length, 1);
  assert.ok(source.includes('className="settings-grid mounting-nodes-grid mounting-node-types-grid" aria-label="Типи кріплень"'));
  const css = postcss.parse(readFileSync(new URL("../src/styles.css", import.meta.url), "utf8"));
  const selector = ".settings-grid.mounting-nodes-grid.mounting-node-types-grid";
  const rules = [];
  css.walkRules(selector, (rule) => {
    const maxWidth = rule.parent.type === "atrule" ? Number(rule.parent.params.match(/max-width:\s*(\d+)px/)[1]) : Infinity;
    rule.walkDecls("grid-template-columns", (decl) => rules.push({ maxWidth, value: decl.value }));
  });
  for (const [width, count] of [[1920, 5], [1451, 5], [1450, 3], [1201, 3], [1200, 2], [761, 2], [760, 1], [375, 1]]) {
    assert.equal(rules.filter((rule) => width <= rule.maxWidth).at(-1)?.value, `repeat(${count}, minmax(0, 1fr))`);
  }
});

test("all six type previews reference the corresponding local PNG", () => {
  for (const tile of mountingNodeTypeTiles) {
    const expected = new URL(`../src/assets/mounting-node-types/fastening-type-${tile.code}.png`, import.meta.url);
    assert.equal(tile.imageSrc, expected.href);
    const bytes = readFileSync(expected);
    assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  }
});

test("preview and label stay inside the existing clickable type card", () => {
  const card = source.slice(source.indexOf('<button className="settings-card mounting-node-card mounting-node-type-card"'));
  const markup = card.slice(0, card.indexOf("</button>"));
  assert.ok(markup.includes("onClick={() => setSelectedFasteningType(tile.code)}"));
  assert.ok(markup.includes('src={tile.imageSrc}'));
  assert.ok(markup.indexOf("<img") < markup.indexOf("<h3>{tile.label}</h3>"));
  assert.ok(markup.includes('alt="" aria-hidden="true"'));
  const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");
  const previewStyle = css.split(".mounting-node-type-card > .mounting-node-type-preview {")[1].split("}")[0];
  assert.ok(previewStyle.includes("object-fit: contain"));
  assert.ok(previewStyle.includes("height: 104px"));
});

test("fastening category opens six Ukrainian type tiles before any nodes", () => {
  assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: "fastening" }), null);
  assert.deepEqual(filterMountingNodesByType(nodes, "fastening", null), []);
  assert.deepEqual(mountingNodeTypeTiles.map((tile) => tile.label), ["Конфірмати", "Мініфікси", "Rafix", "Саморізи", "Шканти", "Інше"]);
  assert.ok(source.includes('activeCategoryFilter === "fastening" && !selectedFasteningType'));
  assert.ok(source.includes('aria-label="Типи кріплень"'));
  assert.ok(source.includes("onClick={() => setSelectedFasteningType(tile.code)}"));
});

for (const [type, ids] of [["confirmat", [1]], ["minifix", [2]], ["other", [3, 4, 6]], ["rafix", []]]) {
  test(`${type} filters only matching fastening nodes`, () => {
    assert.deepEqual(filterMountingNodesByType(nodes, "fastening", type).map((node) => node.id), ids);
  });
}

test("other categories retain their existing lists", () => {
  for (const category of ["hinges", "drawer_slides", "handles", "legs", "other", "all"]) {
    assert.equal(filterMountingNodesByType(nodes, category, "confirmat"), nodes);
    assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: category, selectedFasteningType: "confirmat" }), null);
  }
});

test("detail restored after editor keeps its type including legacy NULL", () => {
  for (const node of nodes.filter((node) => node.category_code === "fastening")) {
    assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: "fastening", mountingNodesViewMode: "detail", selectedNodeDetail: node }), node.fastening_type ?? "other");
  }
  assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: "fastening", selectedFasteningType: "minifix" }), "minifix");
});

function navigationHarness(category, type) {
  const block = source.slice(source.indexOf("  function handleSelectNode(nodeId)"), source.indexOf("  function handleScrollToVersionHistory()"));
  return new Function("nodes", "category", "type", `
    let activeCategoryFilter = category, selectedFasteningType = type, view = "list", selectedId = null;
    const events = [], pendingReturnStateRef = {};
    const onOpenMountingNodeDetail = (...args) => events.push(args);
    const onCloseMountingNodeDetail = () => {};
    const onOpenMountingNodeCategories = () => events.push("categories");
    const captureReturnState = () => ({ selectedFasteningType });
    const setSelectedNodeId = value => { selectedId = value; };
    const setMountingNodesViewMode = value => { view = value; };
    const setSelectedFasteningType = value => { selectedFasteningType = value; };
    const setActiveCategoryFilter = value => { activeCategoryFilter = value; };
    ${block}
    return { handleSelectNode, handleBackToList, handleReturnToCategories,
      state: () => ({ selectedFasteningType, view, selectedId, events, saved: pendingReturnStateRef.current }) };
  `)(nodes, category, type);
}

test("detail contract stays unchanged and Back traverses type then category", () => {
  const nav = navigationHarness("fastening", "confirmat");
  nav.handleSelectNode(1);
  assert.deepEqual(nav.state().events, [["1", "Test", "fastening"]]);
  assert.equal(nav.state().view, "detail");
  assert.equal(nav.state().saved.selectedFasteningType, "confirmat");
  nav.handleBackToList();
  assert.equal(nav.state().view, "list");
  assert.equal(nav.state().selectedFasteningType, "confirmat");
  nav.handleReturnToCategories();
  assert.equal(nav.state().selectedFasteningType, null);
  assert.equal(nav.state().events.length, 1);
  nav.handleReturnToCategories();
  assert.equal(nav.state().events.at(-1), "categories");
});

test("other category Back goes directly to categories", () => {
  const nav = navigationHarness("hinges", null);
  nav.handleReturnToCategories();
  assert.deepEqual(nav.state().events, ["categories"]);
});
