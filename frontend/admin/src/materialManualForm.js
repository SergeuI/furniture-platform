export function getManualMaterialFormValidity(name, rawPrice) {
  const nameValid = String(name ?? "").trim().length > 0;
  const priceEmpty = rawPrice === "" || rawPrice === null || rawPrice === undefined;
  const numericPrice = priceEmpty ? Number.NaN : Number(rawPrice);
  const priceValid = !priceEmpty && Number.isFinite(numericPrice) && numericPrice >= 0;

  return {
    nameValid,
    priceValid,
    formValid: nameValid && priceValid,
  };
}
