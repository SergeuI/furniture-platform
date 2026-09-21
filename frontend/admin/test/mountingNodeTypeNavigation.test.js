import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
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

test("fastening types are presented as a catalog filter instead of an intermediate page", () => {
  assert.ok(source.includes('"Тип кріплення"'));
  assert.ok(source.includes("setSelectedFasteningType(event.target.value || null)"));
  assert.ok(source.includes("mountingNodeTypeTiles.map((tile)"));
  assert.equal(source.includes("mounting-node-types-grid"), false);
});

test("all six type previews reference the corresponding local PNG", () => {
  for (const tile of mountingNodeTypeTiles) {
    const expected = new URL(`../src/assets/mounting-node-types/fastening-type-${tile.code}.png`, import.meta.url);
    assert.equal(tile.imageSrc, expected.href);
    const bytes = readFileSync(expected);
    assert.deepEqual([...bytes.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  }
});

test("catalog opens all nodes before a fastening type is selected", () => {
  assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: "fastening" }), null);
  assert.strictEqual(filterMountingNodesByType(nodes, "all", null), nodes);
  assert.deepEqual(mountingNodeTypeTiles.map((tile) => tile.label), ["Конфірмати", "Мініфікси", "Rafix", "Саморізи", "Шканти", "Інше"]);
});

test("category filter excludes uncategorized nodes without hiding them from all", () => {
  const withLegacyNode = [...nodes, { id: 22, category_code: null, fastening_type: null }];
  assert.equal(filterMountingNodesByType(withLegacyNode, "all", null).length, withLegacyNode.length);
  assert.deepEqual(filterMountingNodesByType(withLegacyNode, "fastening", null).map((node) => node.id), [1, 2, 3, 4, 6]);
  assert.deepEqual(filterMountingNodesByType(withLegacyNode, "null", null).map((node) => node.id), [22]);
});

for (const [type, ids] of [["confirmat", [1]], ["minifix", [2]], ["rafix", []], ["screw", []], ["dowel", []], ["other", [3, 4, 6]]]) {
  test(`${type} filters only matching fastening nodes`, () => {
    assert.deepEqual(filterMountingNodesByType(nodes, "fastening", type).map((node) => node.id), ids);
  });
}

test("legacy route state restores its fastening type as a catalog filter", () => {
  assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: "all", selectedFasteningType: "confirmat" }), "confirmat");
});

test("detail restored after editor keeps its type including legacy NULL", () => {
  for (const node of nodes.filter((node) => node.category_code === "fastening")) {
    assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: "fastening", mountingNodesViewMode: "detail", selectedNodeDetail: node }), node.fastening_type ?? "other");
  }
  assert.equal(resolveMountingNodeTypeSelection({ activeCategoryFilter: "fastening", selectedFasteningType: "minifix" }), "minifix");
});

function navigationHarness(category, type) {
  const block = source.slice(source.indexOf("  function handleBackToList()"), source.indexOf("  function handleScrollToVersionHistory()"));
  return new Function("category", "type", `
    let activeCategoryFilter = category, selectedFasteningType = type, view = "editor";
    const setMountingNodesViewMode = value => { view = value; };
    ${block}
    return { handleBackToList,
      state: () => ({ activeCategoryFilter, selectedFasteningType, view }) };
  `)(category, type);
}

test("Back returns directly to the unified catalog with its type filter", () => {
  const nav = navigationHarness("fastening", "confirmat");
  nav.handleBackToList();
  assert.equal(nav.state().view, "list");
  assert.equal(nav.state().activeCategoryFilter, "fastening");
  assert.equal(nav.state().selectedFasteningType, "confirmat");
});

test("explicit filter reset tells the route to show all nodes", () => {
  const block = source.slice(source.indexOf("  function handleResetFilters()"), source.indexOf("  function handleBackToList()"));
  const events = [];
  const runReset = new Function("onListContextChange", `
    const setSearchInput = () => {}, setAppliedSearch = () => {}, setActiveStatusFilter = () => {};
    const setActiveCategoryFilter = () => {}, setActiveVariantFilter = () => {};
    const setSelectedFasteningType = () => {}, setOwnershipFilter = () => {}, setSortOrder = () => {};
    ${block}
    return handleResetFilters;
  `)((...args) => events.push(args));

  runReset();
  assert.deepEqual(events, [[undefined, null]]);
});
