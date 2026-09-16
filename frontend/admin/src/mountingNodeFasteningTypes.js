export const mountingNodeFasteningTypes = [
  { code: "confirmat", label: "Конфірмат" },
  { code: "minifix", label: "Мініфікс" },
  { code: "rafix", label: "Rafix" },
  { code: "screw", label: "Саморіз" },
  { code: "dowel", label: "Шкант" },
  { code: "other", label: "Інше" },
];

export function getMountingNodeFasteningTypeLabel(value) {
  return mountingNodeFasteningTypes.find((option) => option.code === value)?.label || "";
}
