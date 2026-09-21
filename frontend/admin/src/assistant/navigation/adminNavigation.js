function buildAdminUrl(search) {
  if (typeof window === "undefined") {
    return "";
  }

  return `${window.location.pathname}${search}${window.location.hash || ""}`;
}

export function navigateAdmin(search) {
  if (typeof window === "undefined") {
    return false;
  }

  const nextUrl = buildAdminUrl(search);
  const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash || ""}`;

  if (nextUrl === currentUrl) {
    return true;
  }

  window.history.pushState(null, document.title, nextUrl);
  window.dispatchEvent(new PopStateEvent("popstate"));
  return true;
}
