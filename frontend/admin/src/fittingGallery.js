export function normalizeFittingGalleryImageUrls(imageUrls) {
  const list = Array.isArray(imageUrls) ? imageUrls : imageUrls ? [imageUrls] : [];

  return list
    .map((value) => String(value || "").trim())
    .filter(Boolean);
}

export function getFittingGalleryPrimaryImageUrl(imageUrls) {
  return normalizeFittingGalleryImageUrls(imageUrls)[0] || "";
}

export function moveFittingGalleryImageUrl(imageUrls, fromIndex, direction) {
  const normalized = normalizeFittingGalleryImageUrls(imageUrls);
  const sourceIndex = Number(fromIndex);
  const delta = Number(direction);

  if (!Number.isInteger(sourceIndex) || !Number.isInteger(delta)) {
    return normalized;
  }

  const targetIndex = sourceIndex + delta;
  if (sourceIndex < 0 || sourceIndex >= normalized.length || targetIndex < 0 || targetIndex >= normalized.length) {
    return normalized;
  }

  if (targetIndex === sourceIndex) {
    return normalized;
  }

  const next = [...normalized];
  const [item] = next.splice(sourceIndex, 1);
  next.splice(targetIndex, 0, item);
  return next;
}
