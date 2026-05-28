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

export async function getProjectHistory(token, projectId) {
  return request(`/project/${projectId}/history`, {
    headers: authHeaders(token),
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
