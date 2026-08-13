import { getFittingDetails, getFittingImageBlob } from "./api.js";

function normalizeId(value) {
  return String(value || "").trim();
}

function pickPrimaryImage(images = []) {
  const normalizedImages = Array.isArray(images)
    ? images
        .filter((image) => normalizeId(image?.id))
        .sort((left, right) => {
          const leftSort = Number(left?.sort_order ?? 0);
          const rightSort = Number(right?.sort_order ?? 0);

          if (leftSort !== rightSort) {
            return leftSort - rightSort;
          }

          return Number(left?.id ?? 0) - Number(right?.id ?? 0);
        })
    : [];

  return normalizedImages.find((image) => image?.is_primary) || normalizedImages[0] || null;
}

export async function loadPrimaryFittingImageBlob({
  item = null,
  token = "",
  getDetails = getFittingDetails,
  getImageBlob = getFittingImageBlob,
} = {}) {
  const fittingId = normalizeId(item?.id);

  if (!fittingId) {
    return {
      success: false,
      error: "Fitting ID is required",
      fittingId: "",
      imageId: "",
    };
  }

  let sourceItem = item;

  if (!Array.isArray(sourceItem?.images) || !sourceItem.images.length) {
    const detailsResult = await getDetails(token, fittingId);

    if (!detailsResult?.success || !detailsResult?.item) {
      return {
        success: false,
        error: detailsResult?.error || "Failed to load fitting details",
        fittingId,
        imageId: "",
      };
    }

    sourceItem = detailsResult.item;
  }

  const primaryImage = pickPrimaryImage(sourceItem?.images || []);

  if (!primaryImage?.id) {
    return {
      success: false,
      error: "Primary fitting image not found",
      fittingId,
      imageId: "",
    };
  }

  const imageId = normalizeId(primaryImage.id);
  const imageResult = await getImageBlob(token, fittingId, imageId);

  if (!imageResult?.success || !imageResult?.blob) {
    return {
      success: false,
      error: imageResult?.error || "Failed to load fitting image",
      fittingId,
      imageId,
    };
  }

  return {
    success: true,
    fittingId,
    imageId,
    blob: imageResult.blob,
    contentType: imageResult.contentType || primaryImage?.content_type || "",
  };
}
