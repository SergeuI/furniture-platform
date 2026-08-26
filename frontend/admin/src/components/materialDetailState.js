function normalizeStatus(status) {
  return String(status || "").trim().toLowerCase();
}

function hasItems(items) {
  return Array.isArray(items) && items.length > 0;
}

export function shouldShowSupplierLoadingState(status) {
  const normalized = normalizeStatus(status);
  return normalized === "idle" || normalized === "loading";
}

export function shouldShowSupplierTabs(status, offers) {
  return normalizeStatus(status) === "loaded" && hasItems(offers);
}

export function shouldShowSupplierEmptyState(status, offers) {
  return normalizeStatus(status) === "loaded" && !hasItems(offers);
}

export function shouldShowSupplierErrorState(status) {
  return normalizeStatus(status) === "error";
}

export function shouldShowOwnersLoadingState(status) {
  const normalized = normalizeStatus(status);
  return normalized === "idle" || normalized === "loading";
}

export function shouldShowOwnersCount(status, owners) {
  return normalizeStatus(status) === "loaded" && hasItems(owners);
}

export function shouldShowOwnersEmptyState(status, owners) {
  return normalizeStatus(status) === "loaded" && !hasItems(owners);
}

export function isMaterialDetailInitialReady(supplierStatus, ownersStatus) {
  const normalizedSupplierStatus = normalizeStatus(supplierStatus);
  const normalizedOwnersStatus = normalizeStatus(ownersStatus);

  return (
    (normalizedSupplierStatus === "loaded" || normalizedSupplierStatus === "error") &&
    (normalizedOwnersStatus === "loaded" || normalizedOwnersStatus === "error")
  );
}

export function shouldOpenMaterialDetailModal(canonicalStatus, supplierStatus, ownersStatus) {
  const normalizedCanonicalStatus = normalizeStatus(canonicalStatus);

  if (normalizedCanonicalStatus !== "loaded") {
    return false;
  }

  return isMaterialDetailInitialReady(supplierStatus, ownersStatus);
}
