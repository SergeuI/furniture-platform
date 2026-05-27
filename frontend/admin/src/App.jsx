import {
  ChevronLeft,
  ChevronRight,
  History,
  LogOut,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  X,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  deleteProject,
  getCurrentUser,
  getProject,
  getProjectHistory,
  listProjects,
  login,
  rollbackProject,
  updateProject,
} from "./api";

const TOKEN_STORAGE_KEY = "furniture_admin_token";
const PAGE_SIZE = 20;

function buildProjectPayload(form) {
  return {
    dimensions: {
      width: Number(form.width),
      height: Number(form.height),
      depth: Number(form.depth),
    },
    sections: {
      count: Number(form.sections),
      config: [],
    },
    drawers: {
      config: form.drawers
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean)
        .map(Number),
    },
    materials: {
      facade: null,
      inside: null,
    },
    fittings: {
      slide_type: null,
      bottom_type: null,
    },
  };
}

function projectToForm(project) {
  return {
    width: project?.width || "",
    height: project?.height || "",
    depth: project?.depth || "",
    sections: project?.sections || "",
    drawers: Array.isArray(project?.drawers) ? project.drawers.join(", ") : "",
  };
}

function formatDrawers(drawers) {
  if (!Array.isArray(drawers) || drawers.length === 0) {
    return "None";
  }

  return drawers.join(", ");
}

function formatDateTime(value) {
  if (!value) {
    return "Not set";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not set";
  }

  return date.toLocaleString();
}

export default function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) || "",
  );
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [projects, setProjects] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selectedProject, setSelectedProject] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [form, setForm] = useState(projectToForm(null));
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);

  const canGoBack = offset > 0;
  const canGoForward = offset + PAGE_SIZE < total;

  const selectedProjectId = selectedProject?.id || "";

  const pageLabel = useMemo(() => {
    if (total === 0) {
      return "0 of 0";
    }

    return `${offset + 1}-${Math.min(offset + PAGE_SIZE, total)} of ${total}`;
  }, [offset, total]);

  async function loadUser(activeToken) {
    const result = await getCurrentUser(activeToken);

    if (!result.success) {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      setToken("");
      setUser(null);
      return;
    }

    setUser(result.user);
  }

  async function loadProjects(activeToken = token, nextOffset = offset) {
    if (!activeToken) {
      return;
    }

    setLoading(true);
    const result = await listProjects(activeToken, PAGE_SIZE, nextOffset);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || "Unable to load projects");
      return;
    }

    setProjects(result.projects);
    setTotal(result.total);
    setOffset(result.offset);
  }

  async function loadProject(projectId) {
    const [projectResult, historyResult] = await Promise.all([
      getProject(projectId),
      getProjectHistory(projectId),
    ]);

    if (!projectResult.success) {
      setStatus(projectResult.error || "Project not found");
      return;
    }

    setSelectedProject(projectResult.project);
    setForm(projectToForm(projectResult.project));
    setHistoryItems(historyResult.success ? historyResult.versions : []);
  }

  async function handleLogin(event) {
    event.preventDefault();
    setLoading(true);
    const result = await login(email, password);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || "Login failed");
      return;
    }

    localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setToken(result.access_token);
    setUser(result.user);
    setStatus("");
    await loadProjects(result.access_token, 0);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken("");
    setUser(null);
    setProjects([]);
    setSelectedProject(null);
    setHistoryItems([]);
    setStatus("");
  }

  async function handleUpdate(event) {
    event.preventDefault();

    if (!selectedProjectId) {
      return;
    }

    setLoading(true);
    const result = await updateProject(
      token,
      selectedProjectId,
      buildProjectPayload(form),
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || "Update failed");
      return;
    }

    setStatus("Project updated");
    await loadProject(selectedProjectId);
    await loadProjects(token, offset);
  }

  function openRollbackConfirm(version) {
    setConfirmAction({
      type: "rollback",
      title: "Rollback project",
      message: `Rollback project ${selectedProjectId} to ${version.width} x ${version.height} x ${version.depth}?`,
      confirmLabel: "Rollback",
      targetId: version.id,
    });
  }

  function openDeleteConfirm() {
    if (!selectedProjectId) {
      return;
    }

    setConfirmAction({
      type: "delete",
      title: "Delete project",
      message: `Delete project ${selectedProjectId}?`,
      confirmLabel: "Delete",
      targetId: selectedProjectId,
    });
  }

  function closeConfirm() {
    setConfirmAction(null);
  }

  async function confirmSelectedAction() {
    if (!confirmAction) {
      return;
    }

    if (confirmAction.type === "rollback") {
      await handleRollback(confirmAction.targetId);
      return;
    }

    if (confirmAction.type === "delete") {
      await handleDelete();
    }
  }

  async function handleRollback(versionId) {
    if (!selectedProjectId) {
      return;
    }

    setLoading(true);
    const result = await rollbackProject(token, selectedProjectId, versionId);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || "Rollback failed");
      return;
    }

    setStatus("Project rolled back");
    closeConfirm();
    await loadProject(selectedProjectId);
    await loadProjects(token, offset);
  }

  async function handleDelete() {
    if (!selectedProjectId) {
      return;
    }

    setLoading(true);
    const result = await deleteProject(token, selectedProjectId);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || "Delete failed");
      return;
    }

    setStatus("Project deleted");
    closeConfirm();
    setSelectedProject(null);
    setHistoryItems([]);
    await loadProjects(token, offset);
  }

  useEffect(() => {
    if (!token) {
      return;
    }

    loadUser(token);
    loadProjects(token, 0);
  }, [token]);

  if (!token || !user) {
    return (
      <main className="auth-screen">
        <form className="login-panel" onSubmit={handleLogin}>
          <div>
            <p className="eyebrow">Furniture Platform</p>
            <h1>Admin</h1>
          </div>

          <label>
            Email
            <input
              autoComplete="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>

          <label>
            Password
            <input
              autoComplete="current-password"
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              required
              type="password"
              value={password}
            />
          </label>

          {status ? <p className="status error">{status}</p> : null}

          <button className="primary-button" disabled={loading} type="submit">
            <Search size={18} />
            Sign in
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="eyebrow">Furniture Platform</p>
          <h1>Admin</h1>
        </div>

        <div className="user-block">
          <span>{user.email}</span>
          <strong>{user.role}</strong>
        </div>

        <button className="ghost-button" onClick={handleLogout} type="button">
          <LogOut size={18} />
          Logout
        </button>
      </aside>

      <section className="workspace">
        <header className="toolbar">
          <div>
            <h2>Projects</h2>
            <p>{pageLabel}</p>
          </div>

          <div className="toolbar-actions">
            <button
              aria-label="Previous page"
              className="icon-button"
              disabled={!canGoBack || loading}
              onClick={() => loadProjects(token, Math.max(0, offset - PAGE_SIZE))}
              type="button"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              aria-label="Next page"
              className="icon-button"
              disabled={!canGoForward || loading}
              onClick={() => loadProjects(token, offset + PAGE_SIZE)}
              type="button"
            >
              <ChevronRight size={18} />
            </button>
            <button
              aria-label="Refresh projects"
              className="icon-button"
              disabled={loading}
              onClick={() => loadProjects(token, offset)}
              type="button"
            >
              <RefreshCw size={18} />
            </button>
          </div>
        </header>

        {status ? <p className="status">{status}</p> : null}

        <div className="content-grid">
          <section className="table-panel">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Size</th>
                  <th>Sections</th>
                  <th>Drawers</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr
                    className={project.id === selectedProjectId ? "selected" : ""}
                    key={project.id}
                    onClick={() => loadProject(project.id)}
                  >
                    <td>{project.id}</td>
                    <td>
                      {project.width} x {project.height} x {project.depth}
                    </td>
                    <td>{project.sections}</td>
                    <td>{formatDrawers(project.drawers)}</td>
                    <td>{formatDateTime(project.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="detail-panel">
            {selectedProject ? (
              <>
                <div className="detail-header">
                  <div>
                    <p className="eyebrow">Selected project</p>
                    <h2>{selectedProject.id}</h2>
                    <div className="meta-grid">
                      <span>Created: {formatDateTime(selectedProject.created_at)}</span>
                      <span>Updated: {formatDateTime(selectedProject.updated_at)}</span>
                    </div>
                  </div>
                  <button
                    className="danger-button"
                    disabled={loading}
                    onClick={openDeleteConfirm}
                    type="button"
                  >
                    <Trash2 size={18} />
                    Delete
                  </button>
                </div>

                <form className="edit-grid" onSubmit={handleUpdate}>
                  <label>
                    Width
                    <input
                      min="1"
                      onChange={(event) =>
                        setForm({ ...form, width: event.target.value })
                      }
                      required
                      type="number"
                      value={form.width}
                    />
                  </label>
                  <label>
                    Height
                    <input
                      min="1"
                      onChange={(event) =>
                        setForm({ ...form, height: event.target.value })
                      }
                      required
                      type="number"
                      value={form.height}
                    />
                  </label>
                  <label>
                    Depth
                    <input
                      min="1"
                      onChange={(event) =>
                        setForm({ ...form, depth: event.target.value })
                      }
                      required
                      type="number"
                      value={form.depth}
                    />
                  </label>
                  <label>
                    Sections
                    <input
                      min="1"
                      onChange={(event) =>
                        setForm({ ...form, sections: event.target.value })
                      }
                      required
                      type="number"
                      value={form.sections}
                    />
                  </label>
                  <label className="wide-field">
                    Drawers
                    <input
                      onChange={(event) =>
                        setForm({ ...form, drawers: event.target.value })
                      }
                      placeholder="1, 2, 3"
                      type="text"
                      value={form.drawers}
                    />
                  </label>
                  <button
                    className="primary-button wide-button"
                    disabled={loading}
                    type="submit"
                  >
                    <Save size={18} />
                    Save
                  </button>
                </form>

                <div className="history-header">
                  <History size={18} />
                  <h3>History</h3>
                </div>
                <div className="history-list">
                  {historyItems.map((item) => (
                    <article className="history-item" key={item.id}>
                      <div>
                        <strong>{item.id}</strong>
                        <span>
                          {item.width} x {item.height} x {item.depth}
                        </span>
                        <span>{formatDateTime(item.created_at)}</span>
                      </div>
                      <button
                        className="ghost-button"
                        disabled={loading}
                        onClick={() => openRollbackConfirm(item)}
                        type="button"
                      >
                        <RotateCcw size={16} />
                        Rollback
                      </button>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <Search size={22} />
                <p>Select a project</p>
              </div>
            )}
          </section>
        </div>
      </section>

      {confirmAction ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          role="dialog"
        >
          <section className="confirm-modal">
            <header className="confirm-header">
              <h2>{confirmAction.title}</h2>
              <button
                aria-label="Close confirmation"
                className="icon-button"
                disabled={loading}
                onClick={closeConfirm}
                type="button"
              >
                <X size={18} />
              </button>
            </header>
            <p>{confirmAction.message}</p>
            <div className="confirm-actions">
              <button
                className="ghost-button"
                disabled={loading}
                onClick={closeConfirm}
                type="button"
              >
                Cancel
              </button>
              <button
                className={
                  confirmAction.type === "delete"
                    ? "danger-button"
                    : "primary-button"
                }
                disabled={loading}
                onClick={confirmSelectedAction}
                type="button"
              >
                {confirmAction.confirmLabel}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
