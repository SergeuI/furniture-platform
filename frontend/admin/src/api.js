function resolveApiBaseUrl() {
  const env = typeof import.meta !== "undefined" && import.meta && import.meta.env ? import.meta.env : {};
  return env.VITE_API_BASE_URL || (env.DEV ? "" : "/api");
}

export const API_BASE_URL = resolveApiBaseUrl();

function extractErrorMessage(payload) {
  if (payload?.detail?.error) {
    return payload.detail.error;
  }

  if (typeof payload?.detail === "string" && payload.detail.trim()) {
    return payload.detail.trim();
  }

  if (payload?.message) {
    return String(payload.message).trim() || "Request failed";
  }

  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((item) => item?.msg || item?.message || item?.error)
      .filter(Boolean)
      .join(", ");
  }

  return payload?.error || "Request failed";
}

function isMaterialSourceImportTimingEnabled(diagnosticLabel) {
  if (diagnosticLabel !== "material-source-import") {
    return false;
  }

  const env = typeof import.meta !== "undefined" && import.meta && import.meta.env ? import.meta.env : {};
  return Boolean(env.DEV || globalThis.__FURNITURE_ADMIN_DEV_TIMING__ === true);
}

function logMaterialSourceImportTiming(phase, fields = {}) {
  const parts = [phase];
  for (const [key, value] of Object.entries(fields)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    parts.push(`${key}=${value}`);
  }
  console.info(`material-source-import ${parts.join(" ")}`);
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const authHeader = String(headers.Authorization || "");
  const authToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs || 30000;
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const diagnosticLabel = options.diagnosticLabel || "";
  const diagnosticEnabled = isMaterialSourceImportTimingEnabled(diagnosticLabel);
  const startedAt = diagnosticEnabled && typeof performance !== "undefined" && performance.now ? performance.now() : Date.now();
  const logElapsed = () => Math.max(0, Math.round(((typeof performance !== "undefined" && performance.now ? performance.now() : Date.now()) - startedAt)));

  if (diagnosticEnabled) {
    logMaterialSourceImportTiming("request started", { path });
  }

  let response;
  let payload = {};

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
      cache: "no-store",
    });

    const responseText = await response.text();

    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch {
        payload = {
          success: false,
          error: responseText.trim().startsWith("<")
            ? `Server returned an HTML error page (HTTP ${response.status})`
            : `Server returned an invalid response (HTTP ${response.status})`,
        };
      }
    }

    if (diagnosticEnabled) {
      logMaterialSourceImportTiming("request resolved", {
        elapsed_ms: logElapsed(),
        status: response.status,
        success: payload?.success ?? response.ok,
      });
    }
  } catch (error) {
    clearTimeout(timeoutId);
    if (diagnosticEnabled) {
      logMaterialSourceImportTiming("request rejected", {
        elapsed_ms: logElapsed(),
        error: error?.name || error?.message || "Network request failed",
      });
    }
    return {
      success: false,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
      status: 0,
    };
  }

  clearTimeout(timeoutId);

  if (!response.ok) {
    if (response.status === 401 && authToken) {
      window.dispatchEvent(
        new CustomEvent("furniture-admin-unauthorized", {
          detail: {
            token: authToken,
            path,
            status: response.status,
          },
        }),
      );
    }

    return {
      success: false,
      error: extractErrorMessage(payload),
      status: response.status,
    };
  }

  return payload;
}

function authHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
  };
}

function dispatchUnauthorized(token, path, status) {
  const authToken = String(token || "").trim();
  if (!authToken) {
    return;
  }

  window.dispatchEvent(
    new CustomEvent("furniture-admin-unauthorized", {
      detail: {
        token: authToken,
        path,
        status,
      },
    }),
  );
}

export function resolveAdminAssetUrl(path) {
  const normalizedPath = String(path || "").trim();

  if (!normalizedPath) {
    return "";
  }

  if (/^(?:https?:\/\/|blob:|data:)/i.test(normalizedPath)) {
    return normalizedPath;
  }

  return `${API_BASE_URL}${normalizedPath.startsWith("/") ? normalizedPath : `/${normalizedPath}`}`;
}

export async function getMaterialImageBlob(token, article, timeoutMs = 30000) {
  const normalizedArticle = String(article || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      status: 0,
      error: "Article is required",
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const imagePath = `/catalog/materials/${encodeURIComponent(normalizedArticle)}/image?v=db`;

  try {
    const response = await fetch(`${API_BASE_URL}${imagePath}`, {
      headers: authHeaders(token),
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 401) {
        const authHeader = String(authHeaders(token).Authorization || "");
        const authToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
        if (authToken) {
          window.dispatchEvent(
            new CustomEvent("furniture-admin-unauthorized", {
              detail: {
                token: authToken,
                path: imagePath,
                status: response.status,
              },
            }),
          );
        }
      }

      return {
        success: false,
        status: response.status,
        error: `HTTP ${response.status}`,
      };
    }

    const blob = await response.blob();

    if (!blob || !blob.size) {
      return {
        success: false,
        status: response.status,
        error: "Empty image response",
      };
    }

    return {
      success: true,
      status: response.status,
      blob,
      contentType: response.headers.get("Content-Type") || blob.type || "",
    };
  } catch (error) {
    return {
      success: false,
      status: 0,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getFittingImageBlob(token, itemId, imageId, timeoutMs = 30000) {
  const normalizedItemId = String(itemId || "").trim();
  const normalizedImageId = String(imageId || "").trim();

  if (!normalizedItemId || !normalizedImageId) {
    return {
      success: false,
      status: 0,
      error: "Fitting and image IDs are required",
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const imagePath = `/catalog/fittings/${encodeURIComponent(normalizedItemId)}/images/${encodeURIComponent(normalizedImageId)}`;

  try {
    const response = await fetch(`${API_BASE_URL}${imagePath}`, {
      headers: authHeaders(token),
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 401) {
        const authHeader = String(authHeaders(token).Authorization || "");
        const authToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
        if (authToken) {
          window.dispatchEvent(
            new CustomEvent("furniture-admin-unauthorized", {
              detail: {
                token: authToken,
                path: imagePath,
                status: response.status,
              },
            }),
          );
        }
      }

      return {
        success: false,
        status: response.status,
        error: `HTTP ${response.status}`,
      };
    }

    const blob = await response.blob();

    if (!blob || !blob.size) {
      return {
        success: false,
        status: response.status,
        error: "Empty image response",
      };
    }

    return {
      success: true,
      status: response.status,
      blob,
      contentType: response.headers.get("Content-Type") || blob.type || "",
    };
  } catch (error) {
    return {
      success: false,
      status: 0,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getMaterialImageBlobById(token, article, imageId, timeoutMs = 30000) {
  const normalizedArticle = String(article || "").trim();
  const normalizedImageId = String(imageId || "").trim();

  if (!normalizedArticle || !normalizedImageId) {
    return {
      success: false,
      status: 0,
      error: "Article and image ID are required",
    };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const imagePath = `/catalog/materials/${encodeURIComponent(normalizedArticle)}/images/${encodeURIComponent(normalizedImageId)}`;

  try {
    const response = await fetch(`${API_BASE_URL}${imagePath}`, {
      headers: authHeaders(token),
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 401) {
        const authHeader = String(authHeaders(token).Authorization || "");
        const authToken = authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";
        if (authToken) {
          window.dispatchEvent(
            new CustomEvent("furniture-admin-unauthorized", {
              detail: {
                token: authToken,
                path: imagePath,
                status: response.status,
              },
            }),
          );
        }
      }

      return {
        success: false,
        status: response.status,
        error: `HTTP ${response.status}`,
      };
    }

    const blob = await response.blob();

    if (!blob || !blob.size) {
      return {
        success: false,
        status: response.status,
        error: "Empty image response",
      };
    }

    return {
      success: true,
      status: response.status,
      blob,
      contentType: response.headers.get("Content-Type") || blob.type || "",
    };
  } catch (error) {
    return {
      success: false,
      status: 0,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function uploadSupplierLogo(token, file, timeoutMs = 30000) {
  if (!file) {
    return {
      success: false,
      status: 0,
      error: "File is required",
    };
  }

  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/catalog/suppliers/logo`, {
      method: "POST",
      headers: authHeaders(token),
      body: formData,
      signal: controller.signal,
    });

    const responseText = await response.text();
    let payload = {};

    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch {
        payload = {
          success: false,
          error: responseText.trim().startsWith("<")
            ? `Server returned an HTML error page (HTTP ${response.status})`
            : `Server returned an invalid response (HTTP ${response.status})`,
        };
      }
    }

    if (!response.ok) {
      if (response.status === 401) {
        dispatchUnauthorized(token, "/catalog/suppliers/logo", response.status);
      }

      return {
        success: false,
        error: extractErrorMessage(payload),
        status: response.status,
      };
    }

    return payload;
  } catch (error) {
    return {
      success: false,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
      status: 0,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function uploadFittingManufacturerLogo(token, file, timeoutMs = 30000) {
  if (!file) {
    return {
      success: false,
      status: 0,
      error: "File is required",
    };
  }

  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/catalog/fitting-manufacturers/logo`, {
      method: "POST",
      headers: authHeaders(token),
      body: formData,
      signal: controller.signal,
    });

    const responseText = await response.text();
    let payload = {};

    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch {
        payload = {
          success: false,
          error: responseText.trim().startsWith("<")
            ? `Server returned an HTML error page (HTTP ${response.status})`
            : `Server returned an invalid response (HTTP ${response.status})`,
        };
      }
    }

    if (!response.ok) {
      if (response.status === 401) {
        dispatchUnauthorized(token, "/catalog/fitting-manufacturers/logo", response.status);
      }

      return {
        success: false,
        error: extractErrorMessage(payload),
        status: response.status,
      };
    }

    return payload;
  } catch (error) {
    return {
      success: false,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
      status: 0,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function uploadMaterialManufacturerLogo(token, file, timeoutMs = 30000) {
  if (!file) {
    return {
      success: false,
      status: 0,
      error: "File is required",
    };
  }

  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/catalog/material-manufacturers/logo`, {
      method: "POST",
      headers: authHeaders(token),
      body: formData,
      signal: controller.signal,
    });

    const responseText = await response.text();
    let payload = {};

    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch {
        payload = {
          success: false,
          error: responseText.trim().startsWith("<")
            ? `Server returned an HTML error page (HTTP ${response.status})`
            : `Server returned an invalid response (HTTP ${response.status})`,
        };
      }
    }

    if (!response.ok) {
      if (response.status === 401) {
        dispatchUnauthorized(token, "/catalog/material-manufacturers/logo", response.status);
      }

      return {
        success: false,
        error: extractErrorMessage(payload),
        status: response.status,
      };
    }

    return payload;
  } catch (error) {
    return {
      success: false,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
      status: 0,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function uploadMaterialCategoryImage(token, file, timeoutMs = 30000) {
  if (!file) {
    return {
      success: false,
      status: 0,
      error: "File is required",
    };
  }

  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/catalog/material-categories/image`, {
      method: "POST",
      headers: authHeaders(token),
      body: formData,
      signal: controller.signal,
    });

    const responseText = await response.text();
    let payload = {};

    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch {
        payload = {
          success: false,
          error: responseText.trim().startsWith("<")
            ? `Server returned an HTML error page (HTTP ${response.status})`
            : `Server returned an invalid response (HTTP ${response.status})`,
        };
      }
    }

    if (!response.ok) {
      if (response.status === 401) {
        dispatchUnauthorized(token, "/catalog/material-categories/image", response.status);
      }

      return {
        success: false,
        error: extractErrorMessage(payload),
        status: response.status,
      };
    }

    return payload;
  } catch (error) {
    return {
      success: false,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
      status: 0,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function uploadEdgeImage(token, file, timeoutMs = 30000) {
  if (!file) {
    return {
      success: false,
      status: 0,
      error: "File is required",
    };
  }

  const formData = new FormData();
  formData.append("file", file);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${API_BASE_URL}/catalog/edges/image`, {
      method: "POST",
      headers: authHeaders(token),
      body: formData,
      signal: controller.signal,
    });

    const responseText = await response.text();
    let payload = {};

    if (responseText) {
      try {
        payload = JSON.parse(responseText);
      } catch {
        payload = {
          success: false,
          error: responseText.trim().startsWith("<")
            ? `Server returned an HTML error page (HTTP ${response.status})`
            : `Server returned an invalid response (HTTP ${response.status})`,
        };
      }
    }

    if (!response.ok) {
      if (response.status === 401) {
        dispatchUnauthorized(token, "/catalog/edges/image", response.status);
      }

      return {
        success: false,
        error: extractErrorMessage(payload),
        status: response.status,
      };
    }

    return payload;
  } catch (error) {
    return {
      success: false,
      error:
        error?.name === "AbortError"
          ? `Request timed out after ${Math.round(timeoutMs / 1000)} seconds`
          : error?.message || "Network request failed",
      status: 0,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function login(email, password) {
  return request("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export async function getCurrentUser(token) {
  return request("/auth/me", {
    headers: authHeaders(token),
  });
}

export async function getSpecificationCatalog() {
  return request("/catalog/specification");
}

export async function getMaterialsCatalog(token, params = {}) {
  const searchParams = new URLSearchParams();

  if (params.search) {
    searchParams.set("search", params.search);
  }

  if (params.category) {
    searchParams.set("category", params.category);
  }

  if (params.city) {
    searchParams.set("city", params.city);
  }

  if (params.ownership_scope) {
    searchParams.set("ownership_scope", params.ownership_scope);
  }

  if (params.include_private_categories) {
    searchParams.set("include_private_categories", "true");
  }

  const query = searchParams.toString();

  return request(`/catalog/materials${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
    timeoutMs: 60000,
  });
}

export async function getEdgesCatalog(token, params = {}) {
  const searchParams = new URLSearchParams();

  if (params.search) {
    searchParams.set("search", params.search);
  }

  if (params.manufacturer_id) {
    searchParams.set("manufacturer_id", params.manufacturer_id);
  }

  if (params.supplier_id) {
    searchParams.set("supplier_id", params.supplier_id);
  }

  const query = searchParams.toString();

  return request(`/catalog/edges${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
    timeoutMs: 30000,
  });
}

export async function createEdgeCatalog(token, payload) {
  return request("/catalog/edges", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function previewEdgeCatalogSource(token, payload) {
  return request("/catalog/edges/source-preview", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function createEdgeCatalogFromSource(token, payload) {
  return request("/catalog/edges/source-create", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function getEdgeCatalogDetail(token, edgeId) {
  const normalizedEdgeId = String(edgeId || "").trim();

  if (!normalizedEdgeId) {
    return {
      success: false,
      status: 0,
      error: "Edge ID is required",
    };
  }

  return request(`/catalog/edges/${encodeURIComponent(normalizedEdgeId)}`, {
    headers: authHeaders(token),
    timeoutMs: 30000,
  });
}

export async function updateEdgeCatalog(token, edgeId, payload) {
  const normalizedEdgeId = String(edgeId || "").trim();

  if (!normalizedEdgeId) {
    return {
      success: false,
      status: 0,
      error: "Edge ID is required",
    };
  }

  return request(`/catalog/edges/${encodeURIComponent(normalizedEdgeId)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteEdgeCatalog(token, edgeId) {
  const normalizedEdgeId = String(edgeId || "").trim();

  if (!normalizedEdgeId) {
    return {
      success: false,
      status: 0,
      error: "Edge ID is required",
    };
  }

  return request(`/catalog/edges/${encodeURIComponent(normalizedEdgeId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function getFittingsCatalog(token, params = {}) {
  const searchParams = new URLSearchParams();

  if (params.search) {
    searchParams.set("search", params.search);
  }

  if (params.city) {
    searchParams.set("city", params.city);
  }

  if (params.fitting_group) {
    searchParams.set("fitting_group", params.fitting_group);
  }

  if (params.fitting_type) {
    searchParams.set("fitting_type", params.fitting_type);
  }

  if (params.ownership_scope) {
    searchParams.set("ownership_scope", params.ownership_scope);
  }

  const query = searchParams.toString();

  return request(`/catalog/fittings${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getFittingDetails(token, itemId) {
  const normalizedItemId = String(itemId || "").trim();

  if (!normalizedItemId) {
    return {
      success: false,
      error: "Fitting item ID is required",
      status: 0,
    };
  }

  return request(`/catalog/fittings/${encodeURIComponent(normalizedItemId)}`, {
    headers: authHeaders(token),
  });
}

export async function createFitting(token, payload) {
  return request("/catalog/fittings", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function previewFittingSource(token, payload) {
  return request("/catalog/fittings/source-preview", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFitting(token, itemId, payload) {
  return request(`/catalog/fittings/${itemId}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function listFittingSuppliers(token, includeInactive = false) {
  const searchParams = new URLSearchParams();

  if (includeInactive) {
    searchParams.set("include_inactive", "true");
  }

  const query = searchParams.toString();

  return request(`/catalog/suppliers${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function createFittingSupplier(token, payload) {
  return request("/catalog/suppliers", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingSupplier(token, supplierId, payload) {
  const normalizedSupplierId = String(supplierId || "").trim();

  if (!normalizedSupplierId) {
    return {
      success: false,
      error: "Supplier ID is required",
      status: 0,
    };
  }

  return request(`/catalog/suppliers/${encodeURIComponent(normalizedSupplierId)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingSupplier(token, supplierId) {
  const normalizedSupplierId = String(supplierId || "").trim();

  if (!normalizedSupplierId) {
    return {
      success: false,
      error: "Supplier ID is required",
      status: 0,
    };
  }

  return request(`/catalog/suppliers/${encodeURIComponent(normalizedSupplierId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listFittingSupplierOffers(token, itemId) {
  return request(`/catalog/fittings/${encodeURIComponent(String(itemId || ""))}/supplier-offers`, {
    headers: authHeaders(token),
  });
}

export async function createFittingSupplierOffer(token, itemId, payload) {
  return request(`/catalog/fittings/${encodeURIComponent(String(itemId || ""))}/supplier-offers`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingSupplierOffer(token, itemId, offerId, payload) {
  return request(`/catalog/fittings/${encodeURIComponent(String(itemId || ""))}/supplier-offers/${encodeURIComponent(String(offerId || ""))}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFitting(token, itemId) {
  return request(`/catalog/fittings/${itemId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function deleteFittingProduct(token, itemId) {
  return request(`/catalog/fitting-products/${encodeURIComponent(String(itemId || ""))}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listFittingManufacturers(token, includeInactive = false) {
  const searchParams = new URLSearchParams();
  if (includeInactive) {
    searchParams.set("active_only", "false");
  }
  const query = searchParams.toString();
  return request(`/catalog/fitting-manufacturers${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getFittingManufacturer(token, itemId) {
  return request(`/catalog/fitting-manufacturers/${encodeURIComponent(String(itemId || ""))}`, {
    headers: authHeaders(token),
  });
}

export async function createFittingManufacturer(token, payload) {
  return request("/catalog/fitting-manufacturers", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingManufacturer(token, itemId, payload) {
  return request(`/catalog/fitting-manufacturers/${encodeURIComponent(String(itemId || ""))}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingManufacturer(token, itemId) {
  return request(`/catalog/fitting-manufacturers/${encodeURIComponent(String(itemId || ""))}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listFittingSeries(token, includeInactive = false) {
  const searchParams = new URLSearchParams();
  if (includeInactive) {
    searchParams.set("active_only", "false");
  }
  const query = searchParams.toString();
  return request(`/catalog/fitting-series${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getFittingSeries(token, itemId) {
  return request(`/catalog/fitting-series/${encodeURIComponent(String(itemId || ""))}`, {
    headers: authHeaders(token),
  });
}

export async function createFittingSeries(token, payload) {
  return request("/catalog/fitting-series", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingSeries(token, itemId, payload) {
  return request(`/catalog/fitting-series/${encodeURIComponent(String(itemId || ""))}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingSeries(token, itemId) {
  return request(`/catalog/fitting-series/${encodeURIComponent(String(itemId || ""))}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listFittingCategories(token, includeInactive = false) {
  const searchParams = new URLSearchParams();
  if (includeInactive) {
    searchParams.set("active_only", "false");
  }
  const query = searchParams.toString();
  return request(`/catalog/fitting-categories${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getFittingCategory(token, itemId) {
  return request(`/catalog/fitting-categories/${encodeURIComponent(String(itemId || ""))}`, {
    headers: authHeaders(token),
  });
}

export async function createFittingCategory(token, payload) {
  return request("/catalog/fitting-categories", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingCategory(token, itemId, payload) {
  return request(`/catalog/fitting-categories/${encodeURIComponent(String(itemId || ""))}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingCategory(token, itemId) {
  return request(`/catalog/fitting-categories/${encodeURIComponent(String(itemId || ""))}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listMaterialCategories(token, includeInactive = false, includePrivateCategories = false) {
  const searchParams = new URLSearchParams();
  if (includeInactive) {
    searchParams.set("active_only", "false");
  }
  if (includePrivateCategories) {
    searchParams.set("include_private_categories", "true");
  }
  const query = searchParams.toString();
  return request(`/catalog/material-categories${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getMaterialCategory(token, itemId) {
  return request(`/catalog/material-categories/${encodeURIComponent(String(itemId || ""))}`, {
    headers: authHeaders(token),
  });
}

export async function createMaterialCategory(token, payload) {
  return request("/catalog/material-categories", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateMaterialCategory(token, itemId, payload) {
  return request(`/catalog/material-categories/${encodeURIComponent(String(itemId || ""))}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteMaterialCategory(token, itemId) {
  return request(`/catalog/material-categories/${encodeURIComponent(String(itemId || ""))}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listMaterialManufacturers(token, includeInactive = false) {
  const searchParams = new URLSearchParams();
  if (includeInactive) {
    searchParams.set("active_only", "false");
  }
  const query = searchParams.toString();
  return request(`/catalog/material-manufacturers${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getMaterialManufacturer(token, itemId) {
  return request(`/catalog/material-manufacturers/${encodeURIComponent(String(itemId || ""))}`, {
    headers: authHeaders(token),
  });
}

export async function createMaterialManufacturer(token, payload) {
  return request("/catalog/material-manufacturers", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateMaterialManufacturer(token, itemId, payload) {
  return request(`/catalog/material-manufacturers/${encodeURIComponent(String(itemId || ""))}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteMaterialManufacturer(token, itemId) {
  return request(`/catalog/material-manufacturers/${encodeURIComponent(String(itemId || ""))}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listFittingProducts(token, params = {}) {
  const searchParams = new URLSearchParams();
  if (params.search) {
    searchParams.set("search", params.search);
  }
  if (params.manufacturer_id !== undefined && params.manufacturer_id !== null && `${params.manufacturer_id}`.trim()) {
    searchParams.set("manufacturer_id", params.manufacturer_id);
  }
  if (params.series_id !== undefined && params.series_id !== null && `${params.series_id}`.trim()) {
    searchParams.set("series_id", params.series_id);
  }
  if (params.category_id !== undefined && params.category_id !== null && `${params.category_id}`.trim()) {
    searchParams.set("category_id", params.category_id);
  }
  if (params.active_only === false) {
    searchParams.set("active_only", "false");
  }
  const query = searchParams.toString();
  return request(`/catalog/fitting-products${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getFittingProduct(token, itemId) {
  return request(`/catalog/fitting-products/${encodeURIComponent(String(itemId || ""))}`, {
    headers: authHeaders(token),
  });
}

export async function updateFittingProductTaxonomy(token, itemId, payload) {
  return request(`/catalog/fitting-products/${encodeURIComponent(String(itemId || ""))}/taxonomy`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function listFittingHoleTemplatesByFitting(token, fittingId) {
  return request(`/fitting-holes/fittings/${fittingId}/templates`, {
    headers: authHeaders(token),
  });
}

function normalizeMountingNodeBoolean(value) {
  if (typeof value === "boolean") {
    return value;
  }

  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  if (["1", "true", "yes", "on"].includes(normalized)) {
    return true;
  }

  if (["0", "false", "no", "off"].includes(normalized)) {
    return false;
  }

  return null;
}

export async function getMountingNodes(token, filters = {}) {
  const searchParams = new URLSearchParams();
  const normalizedSearch = String(filters.search || "").trim();
  const normalizedFittingId = String(filters.fitting_id || "").trim();
  const normalizedVariantKey = String(filters.mounting_variant_key || "").trim();
  const normalizedCategoryCode = String(filters.category_code || "").trim().toLowerCase();
  const normalizedIsActive = normalizeMountingNodeBoolean(filters.is_active);

  if (normalizedSearch) {
    searchParams.set("search", normalizedSearch);
  }

  if (normalizedFittingId) {
    searchParams.set("fitting_id", normalizedFittingId);
  }

  if (normalizedVariantKey) {
    searchParams.set("mounting_variant_key", normalizedVariantKey);
  }

  if (normalizedCategoryCode) {
    searchParams.set("category_code", normalizedCategoryCode);
  }

  if (normalizedIsActive !== null) {
    searchParams.set("is_active", normalizedIsActive ? "true" : "false");

    if (!normalizedIsActive) {
      searchParams.set("include_inactive", "true");
    }
  }

  const query = searchParams.toString();
  const result = await request(`/mounting-nodes${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });

  if (
    result.success &&
    normalizedIsActive === false &&
    Array.isArray(result.nodes)
  ) {
    return {
      ...result,
      nodes: result.nodes.filter((node) => node?.is_active === false),
    };
  }

  return result;
}

export async function getMountingNode(token, nodeId) {
  const normalizedNodeId = String(nodeId || "").trim();

  if (!normalizedNodeId) {
    return {
      success: false,
      error: "Mounting node ID is required",
      status: 0,
    };
  }

  return request(`/mounting-nodes/${encodeURIComponent(normalizedNodeId)}`, {
    headers: authHeaders(token),
  });
}

export async function getMountingNodeVersion(token, nodeId, versionId) {
  const normalizedNodeId = String(nodeId || "").trim();
  const normalizedVersionId = String(versionId || "").trim();

  if (!normalizedNodeId || !normalizedVersionId) {
    return {
      success: false,
      error: "Mounting node and version IDs are required",
      status: 0,
    };
  }

  return request(`/mounting-nodes/${encodeURIComponent(normalizedNodeId)}/versions/${encodeURIComponent(normalizedVersionId)}`, {
    headers: authHeaders(token),
  });
}

export async function createMountingNode(token, payload) {
  return request("/mounting-nodes", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateMountingNode(token, nodeId, payload) {
  const normalizedNodeId = String(nodeId || "").trim();

  if (!normalizedNodeId) {
    return {
      success: false,
      error: "Mounting node ID is required",
      status: 0,
    };
  }

  return request(`/mounting-nodes/${encodeURIComponent(normalizedNodeId)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteMountingNode(token, nodeId) {
  const normalizedNodeId = String(nodeId || "").trim();

  if (!normalizedNodeId) {
    return {
      success: false,
      error: "Mounting node ID is required",
      status: 0,
    };
  }

  return request(`/mounting-nodes/${encodeURIComponent(normalizedNodeId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listMountingSchemes(token, includeInactive = false) {
  const searchParams = new URLSearchParams();
  if (includeInactive) {
    searchParams.set("include_inactive", "true");
  }

  const query = searchParams.toString();

  return request(`/mounting-schemes${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getMountingScheme(token, schemeId) {
  const normalizedSchemeId = String(schemeId || "").trim();

  if (!normalizedSchemeId) {
    return {
      success: false,
      error: "Mounting scheme ID is required",
      status: 0,
    };
  }

  return request(`/mounting-schemes/${encodeURIComponent(normalizedSchemeId)}`, {
    headers: authHeaders(token),
  });
}

export async function createMountingScheme(token, payload) {
  return request("/mounting-schemes", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateMountingScheme(token, schemeId, payload) {
  const normalizedSchemeId = String(schemeId || "").trim();

  if (!normalizedSchemeId) {
    return {
      success: false,
      error: "Mounting scheme ID is required",
      status: 0,
    };
  }

  return request(`/mounting-schemes/${encodeURIComponent(normalizedSchemeId)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function listFittingHoleBundles(token) {
  return request("/fitting-holes/bundles", {
    headers: authHeaders(token),
  });
}

export async function getFittingHoleBundle(token, bundleKey) {
  return request(`/fitting-holes/bundles/${encodeURIComponent(bundleKey)}`, {
    headers: authHeaders(token),
  });
}

export async function updateFittingHoleBundle(token, bundleKey, payload) {
  return request(`/fitting-holes/bundles/${encodeURIComponent(bundleKey)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingHoleBundle(token, bundleKey) {
  return request(`/fitting-holes/bundles/${encodeURIComponent(bundleKey)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function createFittingHoleBundle(token, payload) {
  return request("/fitting-holes/bundles", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingHoleBundleMountingVariant(token, bundleKey, payload) {
  return request(`/fitting-holes/bundles/${encodeURIComponent(bundleKey)}/mounting-variant`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function getFittingHoleTemplate(token, templateId) {
  return request(`/fitting-holes/templates/${templateId}`, {
    headers: authHeaders(token),
  });
}

export async function listFittingHolePoints(token, templateId) {
  return request(`/fitting-holes/templates/${templateId}/points`, {
    headers: authHeaders(token),
  });
}

export async function getFittingHoleServicePreview(token, templateId) {
  return request(`/fitting-holes/templates/${templateId}/service-preview`, {
    headers: authHeaders(token),
  });
}

export async function getProcessingOperationsPreview(token, templateId) {
  return request(`/fitting-holes/templates/${templateId}/operations-preview`, {
    headers: authHeaders(token),
  });
}

export async function getProjectPartOperationsPreview(token, projectId, partIdentifier) {
  const normalizedProjectId = encodeURIComponent(String(projectId || "").trim());
  const normalizedPartIdentifier = encodeURIComponent(String(partIdentifier || "").trim());

  return request(`/processing/projects/${normalizedProjectId}/parts/${normalizedPartIdentifier}/operations-preview`, {
    headers: authHeaders(token),
  });
}

export async function getProcessingOperationTypes(token) {
  return request("/processing/operation-types", {
    headers: authHeaders(token),
  });
}

export async function listFittingHoleServiceRules(token) {
  return request("/fitting-holes/service-rules", {
    headers: authHeaders(token),
  });
}

export async function createFittingHoleServiceRule(token, payload) {
  return request("/fitting-holes/service-rules", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingHoleServiceRule(token, ruleId, payload) {
  return request(`/fitting-holes/service-rules/${ruleId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingHoleServiceRule(token, ruleId) {
  return request(`/fitting-holes/service-rules/${ruleId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listServiceDrillingRules(token, params = {}) {
  const searchParams = new URLSearchParams();

  if (params.include_inactive) {
    searchParams.set("include_inactive", "true");
  }

  if (params.service_catalog_item_id) {
    searchParams.set("service_catalog_item_id", params.service_catalog_item_id);
  }

  const query = searchParams.toString();

  return request(`/service-drilling-rules${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function getServiceDrillingRule(token, ruleId) {
  return request(`/service-drilling-rules/${ruleId}`, {
    headers: authHeaders(token),
  });
}

export async function createServiceDrillingRule(token, payload) {
  return request("/service-drilling-rules", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateServiceDrillingRule(token, ruleId, payload) {
  return request(`/service-drilling-rules/${ruleId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteServiceDrillingRule(token, ruleId) {
  return request(`/service-drilling-rules/${ruleId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listAvailableViyarDrillingServices(token, params = {}) {
  const searchParams = new URLSearchParams();

  searchParams.set("category", params.category || "drilling");

  if (params.search) {
    searchParams.set("search", params.search);
  }

  const query = searchParams.toString();

  return request(`/service-drilling-rules/available-services${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function createFittingHoleTemplate(token, payload) {
  return request("/fitting-holes/templates", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingHoleTemplate(token, templateId, payload) {
  return request(`/fitting-holes/templates/${templateId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingHoleTemplate(token, templateId) {
  return request(`/fitting-holes/templates/${templateId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function createFittingHolePoint(token, templateId, payload) {
  return request(`/fitting-holes/templates/${templateId}/points`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateFittingHolePoint(token, pointId, payload) {
  return request(`/fitting-holes/points/${pointId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function deleteFittingHolePoint(token, pointId) {
  return request(`/fitting-holes/points/${pointId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function getCatalogAutoRefreshStatus(token) {
  return request("/catalog/auto-refresh/status", {
    headers: authHeaders(token),
  });
}

export async function getEntitlementFeatures(token, activeOnly = false) {
  const searchParams = new URLSearchParams();

  if (activeOnly) {
    searchParams.set("active_only", "true");
  }

  const query = searchParams.toString();

  return request(`/admin/entitlements/features${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
  });
}

export async function createEntitlementFeature(token, payload) {
  return request("/admin/entitlements/features", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateEntitlementFeature(token, featureId, payload) {
  return request(`/admin/entitlements/features/${featureId}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function getEntitlementMatrix(token) {
  return request("/admin/entitlements/matrix", {
    headers: authHeaders(token),
  });
}

export async function updateEntitlementMatrix(token, payload) {
  return request("/admin/entitlements/matrix", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function previewEntitlementRegistrySync(token) {
  return request("/admin/entitlements/registry-sync/preview", {
    headers: authHeaders(token),
  });
}

export async function applyEntitlementRegistrySync(token) {
  return request("/admin/entitlements/registry-sync/apply", {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function importMaterialFromViyar(
  token,
  article,
  category = "dsp",
  sourceUrl = "",
  forceRefresh = false,
) {
  return request("/catalog/materials/import-viyar", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      article,
      category,
      source_url: sourceUrl || null,
      force_refresh: Boolean(forceRefresh),
    }),
    timeoutMs: 120000,
    diagnosticLabel: "material-source-import",
  });
}

export async function refreshMaterialGallery(token, materialId) {
  const normalizedMaterialId = String(materialId || "").trim();

  if (!normalizedMaterialId) {
    return {
      success: false,
      status: 0,
      error: "Material ID is required",
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedMaterialId)}/images/refresh`, {
    method: "POST",
    headers: authHeaders(token),
    timeoutMs: 120000,
  });
}

export async function refreshMaterialRecommendedEdges(token, materialId) {
  const normalizedMaterialId = String(materialId || "").trim();

  if (!normalizedMaterialId) {
    return {
      success: false,
      status: 0,
      error: "Material ID is required",
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedMaterialId)}/recommended-edges/refresh`, {
    method: "POST",
    headers: authHeaders(token),
    timeoutMs: 120000,
  });
}

export async function createMaterial(token, payload) {
  return request("/catalog/materials", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    timeoutMs: 120000,
    diagnosticLabel: "material-source-import",
  });
}

export async function updateMaterial(token, article, payload) {
  return request(`/catalog/materials/${encodeURIComponent(article)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    timeoutMs: 120000,
  });
}

export async function getMaterialImportJob(token, jobId) {
  return request(`/catalog/materials/import-jobs/${jobId}`, {
    headers: authHeaders(token),
  });
}

export async function getMaterialDetails(token, article, city = "") {
  const searchParams = new URLSearchParams();

  if (city) {
    searchParams.set("city", city);
  }

  const query = searchParams.toString();

  return request(`/catalog/materials/${encodeURIComponent(article)}${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
    timeoutMs: 60000,
  });
}

export async function listMaterialSupplierOffers(token, article) {
  const normalizedArticle = String(article || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      error: "Material article is required",
      status: 0,
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedArticle)}/supplier-offers`, {
    headers: authHeaders(token),
    timeoutMs: 30000,
  });
}

export async function createMaterialSupplierOffer(token, article, payload) {
  const normalizedArticle = String(article || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      error: "Material article is required",
      status: 0,
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedArticle)}/supplier-offers`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    timeoutMs: 30000,
  });
}

export async function attachMaterialSupplierOfferFromSource(token, article, sourceUrl) {
  const normalizedArticle = String(article || "").trim();
  const normalizedSourceUrl = String(sourceUrl || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      error: "Material article is required",
      status: 0,
    };
  }

  if (!normalizedSourceUrl) {
    return {
      success: false,
      error: "Source URL is required",
      status: 0,
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedArticle)}/supplier-offers/from-source`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      source_url: normalizedSourceUrl,
    }),
    timeoutMs: 30000,
  });
}

export async function updateMaterialSupplierOffer(token, offerId, payload) {
  const normalizedOfferId = String(offerId || "").trim();

  if (!normalizedOfferId) {
    return {
      success: false,
      error: "Offer ID is required",
      status: 0,
    };
  }

  return request(`/catalog/material-supplier-offers/${encodeURIComponent(normalizedOfferId)}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    timeoutMs: 30000,
  });
}

export async function deleteMaterialSupplierOffer(token, offerId) {
  const normalizedOfferId = String(offerId || "").trim();

  if (!normalizedOfferId) {
    return {
      success: false,
      error: "Offer ID is required",
      status: 0,
    };
  }

  return request(`/catalog/material-supplier-offers/${encodeURIComponent(normalizedOfferId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
    timeoutMs: 30000,
  });
}

export async function getMaterialOwners(token, article) {
  const normalizedArticle = String(article || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      error: "Material article is required",
      status: 0,
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedArticle)}/owners`, {
    headers: authHeaders(token),
    timeoutMs: 30000,
  });
}

export async function attachMaterialEdge(token, article, payload) {
  return request(`/catalog/materials/${encodeURIComponent(article)}/edges`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    timeoutMs: 120000,
  });
}

export async function listMaterialCanonicalEdges(token, article) {
  const normalizedArticle = String(article || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      error: "Material article is required",
      status: 0,
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedArticle)}/canonical-edges`, {
    headers: authHeaders(token),
    timeoutMs: 30000,
  });
}

export async function attachMaterialCanonicalEdge(token, article, edgeId) {
  const normalizedArticle = String(article || "").trim();
  const normalizedEdgeId = String(edgeId || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      error: "Material article is required",
      status: 0,
    };
  }

  if (!normalizedEdgeId) {
    return {
      success: false,
      error: "Edge ID is required",
      status: 0,
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedArticle)}/canonical-edges`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      edge_id: Number(normalizedEdgeId),
    }),
    timeoutMs: 30000,
  });
}

export async function deleteMaterialCanonicalEdge(token, article, edgeId) {
  const normalizedArticle = String(article || "").trim();
  const normalizedEdgeId = String(edgeId || "").trim();

  if (!normalizedArticle) {
    return {
      success: false,
      error: "Material article is required",
      status: 0,
    };
  }

  if (!normalizedEdgeId) {
    return {
      success: false,
      error: "Edge ID is required",
      status: 0,
    };
  }

  return request(`/catalog/materials/${encodeURIComponent(normalizedArticle)}/canonical-edges/${encodeURIComponent(normalizedEdgeId)}`, {
    method: "DELETE",
    headers: authHeaders(token),
    timeoutMs: 30000,
  });
}

export async function deleteMaterial(token, article) {
  return request(`/catalog/materials/${encodeURIComponent(article)}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listCatalogItems(token) {
  return request("/catalog/items?include_inactive=true", {
    headers: authHeaders(token),
  });
}

export async function getViyarServicesTree(token) {
  return request("/catalog/viyar-services/tree", {
    headers: authHeaders(token),
  });
}

export async function importViyarServices(token) {
  return request("/catalog/viyar-services/import", {
    method: "POST",
    headers: authHeaders(token),
    timeoutMs: 180000,
  });
}

export async function updateViyarService(token, itemId, payload) {
  return request(`/catalog/viyar-services/${itemId}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function syncViyarServicePrices(token) {
  return request("/catalog/viyar-services/sync-prices", {
    method: "POST",
    headers: authHeaders(token),
    timeoutMs: 180000,
  });
}

export async function getManualServicesTree(token) {
  return request("/catalog/manual-services/tree?include_inactive=true", {
    headers: authHeaders(token),
  });
}

export async function createManualService(token, payload) {
  return request("/catalog/manual-services", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function updateManualService(token, itemId, payload) {
  return request(`/catalog/manual-services/${itemId}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function createCatalogItem(token, category, value, sortOrder) {
  return request("/catalog/items", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      category,
      value,
      sort_order: Number(sortOrder),
    }),
  });
}

export async function updateCatalogItem(token, itemId, value, sortOrder) {
  return request(`/catalog/items/${itemId}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({
      value,
      sort_order: Number(sortOrder),
    }),
  });
}

export async function updateCatalogItemActive(token, itemId, isActive) {
  return request(`/catalog/items/${itemId}/active`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({
      is_active: isActive,
    }),
  });
}

export async function changeOwnPassword(token, currentPassword, newPassword) {
  return request("/auth/me/password", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

export async function updateMyProfile(token, payload) {
  return request("/auth/me/profile", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
}

export async function createMyEmailChangeRequest(token, newEmail) {
  return request("/auth/me/email-change-request", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      new_email: newEmail,
    }),
  });
}

export async function listUserChangeRequests(token, status = "pending") {
  const params = new URLSearchParams();
  if (status) {
    params.set("status", status);
  }
  return request(`/auth/change-requests?${params.toString()}`, {
    headers: authHeaders(token),
  });
}

export async function reviewUserChangeRequest(token, requestId, status) {
  return request(`/auth/change-requests/${requestId}/review`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      status,
    }),
  });
}

export async function getMyViyarAuthStatus(token) {
  return request("/auth/me/viyar", {
    headers: authHeaders(token),
  });
}

export async function updateMyViyarAuth(token, email, password) {
  return request("/auth/me/viyar", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({
      email,
      password,
    }),
  });
}

export async function refreshMyViyarSession(token) {
  return request("/auth/me/viyar/session", {
    method: "POST",
    headers: authHeaders(token),
    timeoutMs: 45000,
  });
}

export async function listProjects(token, limit, offset, filters = {}) {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });

  Object.entries(filters).forEach(([key, value]) => {
    if (value !== "" && value !== null && value !== undefined) {
      params.set(key, String(value));
    }
  });

  return request(`/project?${params.toString()}`, {
    headers: authHeaders(token),
  });
}

export async function getProjectQuota(token) {
  return request("/project/quota", {
    headers: authHeaders(token),
  });
}

export async function generateProject(token, project) {
  return request("/project/generate", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(project),
  });
}

export async function scanProjectFile(token, file) {
  let contentBase64 = "";

  try {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(file);
    });
    contentBase64 = dataUrl.split(",")[1] || "";
  } catch (error) {
    return {
      success: false,
      error: error?.message || "Unable to read file",
      status: 0,
    };
  }

  return request("/project/scan", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      filename: file.name,
      content_base64: contentBase64,
    }),
  });
}

export async function listProjectScans(token, limit = 5) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));

  return request(`/project/scans?${params.toString()}`, {
    headers: authHeaders(token),
  });
}

export async function confirmProjectScan(token, scanId, confirmedProjectId = "") {
  return request(`/project/scans/${encodeURIComponent(scanId)}/confirm`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      confirmed_project_id: confirmedProjectId || null,
    }),
  });
}

export async function getProject(token, projectId) {
  return request(`/project/${projectId}`, {
    headers: authHeaders(token),
  });
}

export async function getProjectHistory(token, projectId) {
  return request(`/project/${projectId}/history`, {
    headers: authHeaders(token),
  });
}

export async function getProjectCutting(token, projectId) {
  return request(`/project/${projectId}/cutting`, {
    headers: authHeaders(token),
  });
}

export async function getProjectPartDetail(token, projectId, partCode) {
  return request(`/project/${projectId}/production/parts/${partCode}`, {
    headers: authHeaders(token),
  });
}

export async function updateProjectPartEdges(token, projectId, partCode, edges) {
  return request(`/project/${projectId}/production/parts/${partCode}/edges`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(edges),
  });
}

export async function updateProjectPartMachining(token, projectId, partCode, machining) {
  return request(`/project/${projectId}/production/parts/${partCode}/machining`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(machining),
  });
}

export async function updateProject(token, projectId, project) {
  return request(`/project/${projectId}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(project),
  });
}

export async function rollbackProject(token, projectId, versionId) {
  return request(`/project/${projectId}/rollback/${versionId}`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function deleteProject(token, projectId) {
  return request(`/project/${projectId}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function listUsers(token, limit, offset) {
  return request(`/auth/users?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(token),
  });
}

export async function getUserDetails(token, userId) {
  return request(`/auth/users/${userId}`, {
    headers: authHeaders(token),
  });
}

export async function createUser(token, email, password, role) {
  return request("/auth/users", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({
      email,
      password,
      role,
    }),
  });
}

export async function updateUserRole(token, userId, role) {
  return request(`/auth/users/${userId}/role`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({
      role,
    }),
  });
}

export async function updateUserActive(token, userId, isActive) {
  return request(`/auth/users/${userId}/active`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({
      is_active: isActive,
    }),
  });
}

export async function resetUserPassword(token, userId, password) {
  return request(`/auth/users/${userId}/password`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({
      password,
    }),
  });
}

export async function listAuditLogs(token, limit, offset) {
  return request(`/audit/logs?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(token),
  });
}
