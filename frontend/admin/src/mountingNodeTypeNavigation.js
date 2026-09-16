export const mountingNodeTypeTiles = [
  { code: "confirmat", label: "Конфірмати", imageSrc: new URL("./assets/mounting-node-types/fastening-type-confirmat.png", import.meta.url).href },
  { code: "minifix", label: "Мініфікси", imageSrc: new URL("./assets/mounting-node-types/fastening-type-minifix.png", import.meta.url).href },
  { code: "rafix", label: "Rafix", imageSrc: new URL("./assets/mounting-node-types/fastening-type-rafix.png", import.meta.url).href },
  { code: "screw", label: "Саморізи", imageSrc: new URL("./assets/mounting-node-types/fastening-type-screw.png", import.meta.url).href },
  { code: "dowel", label: "Шканти", imageSrc: new URL("./assets/mounting-node-types/fastening-type-dowel.png", import.meta.url).href },
  { code: "other", label: "Інше", imageSrc: new URL("./assets/mounting-node-types/fastening-type-other.png", import.meta.url).href },
];

export function resolveMountingNodeTypeSelection(state = {}) {
  if (state.activeCategoryFilter !== "fastening") return null;
  if (mountingNodeTypeTiles.some((tile) => tile.code === state.selectedFasteningType)) {
    return state.selectedFasteningType;
  }
  const node = state.selectedNodeDetail;
  if (state.mountingNodesViewMode === "detail" && node?.category_code === "fastening") {
    return node.fastening_type ?? "other";
  }
  return null;
}

export function filterMountingNodesByType(nodes, categoryCode, fasteningType) {
  if (categoryCode !== "fastening") return nodes;
  if (!fasteningType) return [];
  return nodes.filter((node) => node.category_code === "fastening" && (
    fasteningType === "other"
      ? node.fastening_type === "other" || node.fastening_type == null
      : node.fastening_type === fasteningType
  ));
}
