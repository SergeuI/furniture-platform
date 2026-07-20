const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || (
    import.meta.env.DEV ? "http://127.0.0.1:8000" : "/api"
  )
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

  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    return {
      success: false,
      error: error?.message || "Network request failed",
      status: 0,
    };
  }

  let payload = {};

  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  if (!response.ok) {
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

export async function startRegistration(payload) {
  return request("/auth/registration/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function confirmRegistration(payload) {
  return request("/auth/registration/confirm", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getRegistrationTelegramStatus(payload) {
  return request("/auth/registration/telegram/status", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function requestPasswordReset(email) {
  return request("/auth/password-reset-request", {
    method: "POST",
    body: JSON.stringify({
      email,
    }),
  });
}

export async function getPublicOverview() {
  return request("/auth/public-overview");
}

export async function getCurrentUser(token) {
  return request("/auth/me", {
    headers: authHeaders(token),
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

export async function getSpecificationCatalog() {
  return request("/catalog/specification");
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

export async function getProjectBom(token, projectId) {
  return request(`/project/${projectId}/bom`, {
    headers: authHeaders(token),
  });
}

export async function getProjectCutting(token, projectId) {
  return request(`/project/${projectId}/cutting`, {
    headers: authHeaders(token),
  });
}

export async function getCuttingExportFormats(token, projectId) {
  return request(`/project/${projectId}/exports/cutting`, {
    headers: authHeaders(token),
  });
}

export async function getCuttingJsonExport(token, projectId) {
  return request(`/project/${projectId}/exports/cutting/json`, {
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
