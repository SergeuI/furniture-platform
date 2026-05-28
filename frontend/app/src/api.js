const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
);

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const payload = await response.json();

  if (!response.ok) {
    return {
      success: false,
      error: payload.detail?.error || payload.error || "Request failed",
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
