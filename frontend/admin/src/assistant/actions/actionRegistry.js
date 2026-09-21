import { navigateAdmin } from "../navigation/adminNavigation.js";

const ACTIONS = {
  "materials.open": {
    id: "materials.open",
    label: "Матеріали",
    risk: "safe",
    execute: () => navigateAdmin("?section=catalog-materials"),
  },
  "fittings.open": {
    id: "fittings.open",
    label: "Фурнітура",
    risk: "safe",
    execute: () => navigateAdmin("?section=catalog-fittings"),
  },
  "mounting_nodes.open": {
    id: "mounting_nodes.open",
    label: "Монтажні вузли",
    risk: "safe",
    execute: () => navigateAdmin("?section=mounting-nodes&mode=list"),
  },
};

export function getAssistantAction(actionId) {
  return ACTIONS[actionId] || null;
}

export function executeAssistantAction(actionId) {
  const action = getAssistantAction(actionId);

  if (!action) {
    return { success: false, reason: "unknown_action" };
  }

  const result = action.execute();
  return { success: result !== false, action: action.id };
}
