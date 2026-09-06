function parseProjectPrice(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const numericValue = Number(String(value).replace(",", "."));
  return Number.isFinite(numericValue) ? numericValue : null;
}

function formatProjectPrice(value) {
  return value
    .toFixed(2)
    .replace(/\.00$/, "")
    .replace(/(\.\d)0$/, "$1");
}

export function getProjectMaterialPriceRows(priceSummary, legacyCurrentPrice) {
  const summaryRows = Array.isArray(priceSummary) ? priceSummary : [];
  const normalizedRows = summaryRows
    .map((row, index) => {
      const minPrice = parseProjectPrice(row?.min_price);
      const maxPrice = parseProjectPrice(row?.max_price);
      const priceValue = minPrice ?? maxPrice;

      if (priceValue === null) {
        return null;
      }

      const currency = String(row?.currency || "UAH").trim() || "UAH";
      const unit = String(row?.unit || "").trim();
      const priceText =
        minPrice !== null && maxPrice !== null && minPrice !== maxPrice
          ? `${formatProjectPrice(minPrice)} – ${formatProjectPrice(maxPrice)}`
          : formatProjectPrice(priceValue);

      return {
        key: `${currency}:${unit || "_"}:${index}`,
        priceText,
        currency,
        unit,
      };
    })
    .filter(Boolean);

  if (normalizedRows.length) {
    return normalizedRows;
  }

  const legacyPrice = parseProjectPrice(legacyCurrentPrice);
  return legacyPrice === null
    ? []
    : [{ key: "legacy", priceText: formatProjectPrice(legacyPrice), currency: "UAH", unit: "" }];
}
