export const FIXED_PRODUCT_CITY = "kyiv";

export function getEffectiveProductCity() {
  return FIXED_PRODUCT_CITY;
}

export function shouldShowMaterialSquareMeterBadge(item) {
  return item?.supports_square_meter_sale === true;
}

export function getMaterialCatalogContextKey({ category, city, search, ownershipScope }) {
  return JSON.stringify({ category, city, search, ownershipScope });
}

export function shouldRenderMaterialItems({ loading, loadedContext, currentContext }) {
  return !loading && loadedContext === currentContext;
}
