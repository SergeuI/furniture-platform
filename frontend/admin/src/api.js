const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "" : "/api")
);

function extractErrorMessage(payload) {
  if (payload?.detail?.error) {
    return payload.detail.error;
  }

  if (Array.isArray(payload?.detail)) {
    return payload.detail
      .map((item) => item?.msg || item?.message || item?.error)
      .filter(Boolean)
      .join(", ");
  }

  return payload?.error || "Request failed";
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

  let response;
  let payload = {};

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
      signal: controller.signal,
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
  } catch (error) {
    clearTimeout(timeoutId);
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

  const query = searchParams.toString();

  return request(`/catalog/materials${query ? `?${query}` : ""}`, {
    headers: authHeaders(token),
    timeoutMs: 60000,
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

  const query = searchParams.toString();

  return request(`/catalog/fittings${query ? `?${query}` : ""}`, {
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

export async function updateFitting(token, itemId, payload) {
  return request(`/catalog/fittings/${itemId}`, {
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

export async function listFittingHoleTemplatesByFitting(token, fittingId) {
  return request(`/fitting-holes/fittings/${fittingId}/templates`, {
    headers: authHeaders(token),
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
  });
}

export async function createMaterial(token, payload) {
  return request("/catalog/materials", {
    method: "POST",
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

export async function attachMaterialEdge(token, article, payload) {
  return request(`/catalog/materials/${encodeURIComponent(article)}/edges`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
    timeoutMs: 120000,
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
