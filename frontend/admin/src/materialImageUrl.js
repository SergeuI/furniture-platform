export function normalizeMaterialImageUrl(value) {
  const rawUrl = String(value || "").trim();
  if (!rawUrl) {
    return null;
  }

  const wrapperMatch = rawUrl.match(
    /^(?:https?:\/\/(?:www\.)?viyar\.ua)?\/fit=contain\/(https?:\/\/.+)$/i,
  );
  const candidateUrl = wrapperMatch ? wrapperMatch[1] : rawUrl;

  try {
    const parsedUrl = new URL(candidateUrl);
    if (!["http:", "https:"].includes(parsedUrl.protocol)) {
      return null;
    }
    parsedUrl.hash = "";
    parsedUrl.searchParams.delete("size");
    return parsedUrl.toString();
  } catch {
    return null;
  }
}
