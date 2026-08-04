function normalizeThumbnailGeneration(value) {
  const parsedValue = Number(value);

  return Number.isInteger(parsedValue) && parsedValue >= 0 ? parsedValue : 0;
}

function normalizeNodeDetailsMap(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function normalizeThumbnailState(value) {
  if (!value || typeof value !== "object") {
    return null;
  }

  return {
    generation: normalizeThumbnailGeneration(value.generation),
    src: String(value.src || "").trim(),
    status: String(value.status || "").trim(),
  };
}

export function buildMountingNodeThumbnailState(status, generation, src = null) {
  const normalizedStatus = String(status || "").trim();
  const normalizedGeneration = normalizeThumbnailGeneration(generation);

  return {
    generation: normalizedGeneration,
    src: normalizedStatus === "loaded" ? String(src || "").trim() : null,
    status: normalizedStatus,
  };
}

export function isCurrentMountingNodeThumbnailRequest(requestGeneration, currentGeneration, cancelled = false) {
  return !cancelled && normalizeThumbnailGeneration(requestGeneration) === normalizeThumbnailGeneration(currentGeneration);
}

export function shouldLoadMountingNodeThumbnail(existingState, currentGeneration) {
  const normalizedState = normalizeThumbnailState(existingState);
  const normalizedGeneration = normalizeThumbnailGeneration(currentGeneration);

  if (!normalizedState) {
    return true;
  }

  if (normalizedState.status === "loaded" || normalizedState.status === "no-image") {
    return false;
  }

  if (normalizedState.status === "loading") {
    return normalizedState.generation !== normalizedGeneration;
  }

  return true;
}

export function buildMountingNodeThumbnailLoadPlan({
  nodeDetailsById = {},
  fittingThumbnailStateById = {},
  currentGeneration = 0,
} = {}) {
  const normalizedNodeDetailsById = normalizeNodeDetailsMap(nodeDetailsById);
  const normalizedThumbnailStateById = normalizeNodeDetailsMap(fittingThumbnailStateById);
  const loadingPlan = [];
  const seenFittingIds = new Set();
  const normalizedGeneration = normalizeThumbnailGeneration(currentGeneration);

  Object.values(normalizedNodeDetailsById).forEach((nodeDetail) => {
    const items = Array.isArray(nodeDetail?.items) ? nodeDetail.items : [];

    items.forEach((item) => {
      const fittingId = String(item?.fitting_id || "").trim();
      if (!fittingId || seenFittingIds.has(fittingId)) {
        return;
      }

      if (!shouldLoadMountingNodeThumbnail(normalizedThumbnailStateById[fittingId] || null, normalizedGeneration)) {
        return;
      }

      seenFittingIds.add(fittingId);
      loadingPlan.push(fittingId);
    });
  });

  return loadingPlan;
}
