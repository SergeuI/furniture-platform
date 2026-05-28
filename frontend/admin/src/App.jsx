import {
  ChevronLeft,
  ChevronRight,
  History,
  LogOut,
  Plus,
  RefreshCw,
  RotateCcw,
  Save,
  Search,
  X,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  changeOwnPassword,
  createUser,
  deleteProject,
  generateProject,
  getCurrentUser,
  getProject,
  getProjectHistory,
  listAuditLogs,
  listUsers,
  listProjects,
  login,
  rollbackProject,
  resetUserPassword,
  updateProject,
  updateUserActive,
  updateUserRole,
} from "./api";

const TOKEN_STORAGE_KEY = "furniture_admin_token";
const LANGUAGE_STORAGE_KEY = "furniture_admin_language";
const PAGE_SIZE = 20;
const DEFAULT_PROJECT_FORM = {
  width: 1000,
  height: 800,
  depth: 500,
  sections: 2,
  drawers: "1, 2",
};

const TRANSLATIONS = {
  en: {
    access: "Access",
    action: "Action",
    active: "Active",
    actor: "Actor",
    admin: "Admin",
    audit: "Audit",
    cancel: "Cancel",
    changePassword: "Change password",
    createProject: "Create project",
    createUser: "Create user",
    created: "Created",
    createdBy: "Created by",
    currentPassword: "Current password",
    delete: "Delete",
    deleteFailed: "Delete failed",
    deleteProject: "Delete project",
    deleteProjectConfirm: "Delete project",
    deleteRestricted: "Only admins can delete projects",
    depth: "Depth",
    details: "Details",
    drawers: "Drawers",
    email: "Email",
    enabled: "Enabled",
    entity: "Entity",
    furniturePlatform: "Furniture Platform",
    height: "Height",
    history: "History",
    inactive: "Inactive",
    invalidCurrentPassword: "Invalid current password",
    loginFailed: "Login failed",
    logout: "Logout",
    noDetails: "No details",
    newPassword: "New password",
    notSet: "Not set",
    of: "of",
    password: "Password",
    passwordChanged: "Password changed",
    passwordMustBeLong: "Password must be at least 8 characters",
    passwordReset: "Password reset",
    projectDeleted: "Project deleted",
    projectDeleteRestricted: "You do not have permission to delete this project",
    projectEditRestricted: "You do not have permission to edit this project",
    projectCreated: "Project created",
    projectNotFound: "Project not found",
    projectRolledBack: "Project rolled back",
    projectRollbackRestricted: "You do not have permission to roll back this project",
    projectUpdated: "Project updated",
    projects: "Projects",
    readOnlyProject: "Read-only project",
    readOnlyProjectDescription: "You can view this project, but cannot edit it.",
    reset: "Reset",
    role: "Role",
    rollback: "Rollback",
    rollbackFailed: "Rollback failed",
    rollbackProject: "Rollback project",
    save: "Save",
    sections: "Sections",
    selectProject: "Select a project",
    selectedProject: "Selected project",
    signIn: "Sign in",
    size: "Size",
    status: "Status",
    time: "Time",
    to: "to",
    unableToChangePassword: "Unable to change password",
    unableToCreateProject: "Unable to create project",
    unableToCreateUser: "Unable to create user",
    unableToLoadAuditLogs: "Unable to load audit logs",
    unableToLoadProjects: "Unable to load projects",
    unableToLoadUsers: "Unable to load users",
    unableToResetPassword: "Unable to reset password",
    unableToUpdateUserAccess: "Unable to update user access",
    unableToUpdateUserRole: "Unable to update user role",
    updateFailed: "Update failed",
    updated: "Updated",
    updatedBy: "Updated by",
    userAccessUpdated: "User access updated",
    userCreated: "User created",
    userRoleUpdated: "User role updated",
    users: "Users",
    width: "Width",
  },
  uk: {
    access: "Доступ",
    action: "Дія",
    active: "Активний",
    actor: "Користувач",
    admin: "Адмін",
    audit: "Аудит",
    cancel: "Скасувати",
    changePassword: "Змінити пароль",
    createProject: "Створити проект",
    createUser: "Створити користувача",
    created: "Створено",
    createdBy: "Створив",
    currentPassword: "Поточний пароль",
    delete: "Видалити",
    deleteFailed: "Не вдалося видалити",
    deleteProject: "Видалити проект",
    deleteProjectConfirm: "Видалити проект",
    deleteRestricted: "Видаляти проекти може тільки адміністратор",
    depth: "Глибина",
    details: "Деталі",
    drawers: "Шухляди",
    email: "Email",
    enabled: "Увімкнено",
    entity: "Сутність",
    furniturePlatform: "Furniture Platform",
    height: "Висота",
    history: "Історія",
    inactive: "Неактивний",
    invalidCurrentPassword: "Невірний поточний пароль",
    loginFailed: "Не вдалося увійти",
    logout: "Вийти",
    noDetails: "Без деталей",
    newPassword: "Новий пароль",
    notSet: "Не вказано",
    of: "з",
    password: "Пароль",
    passwordChanged: "Пароль змінено",
    passwordMustBeLong: "Пароль має містити мінімум 8 символів",
    passwordReset: "Пароль скинуто",
    projectDeleted: "Проект видалено",
    projectDeleteRestricted: "У вас немає прав для видалення цього проекту",
    projectEditRestricted: "У вас немає прав для редагування цього проекту",
    projectCreated: "Проект створено",
    projectNotFound: "Проект не знайдено",
    projectRolledBack: "Проект відновлено",
    projectRollbackRestricted: "У вас немає прав для відновлення цього проекту",
    projectUpdated: "Проект оновлено",
    projects: "Проекти",
    readOnlyProject: "Проект лише для перегляду",
    readOnlyProjectDescription: "Ви можете переглядати цей проект, але не можете його редагувати.",
    reset: "Скинути",
    role: "Роль",
    rollback: "Відновити",
    rollbackFailed: "Не вдалося відновити",
    rollbackProject: "Відновити проект",
    save: "Зберегти",
    sections: "Секції",
    selectProject: "Виберіть проект",
    selectedProject: "Вибраний проект",
    signIn: "Увійти",
    size: "Розмір",
    status: "Статус",
    time: "Час",
    to: "до",
    unableToChangePassword: "Не вдалося змінити пароль",
    unableToCreateProject: "Не вдалося створити проект",
    unableToCreateUser: "Не вдалося створити користувача",
    unableToLoadAuditLogs: "Не вдалося завантажити аудит",
    unableToLoadProjects: "Не вдалося завантажити проекти",
    unableToLoadUsers: "Не вдалося завантажити користувачів",
    unableToResetPassword: "Не вдалося скинути пароль",
    unableToUpdateUserAccess: "Не вдалося оновити доступ користувача",
    unableToUpdateUserRole: "Не вдалося оновити роль користувача",
    updateFailed: "Не вдалося оновити",
    updated: "Оновлено",
    updatedBy: "Оновив",
    userAccessUpdated: "Доступ користувача оновлено",
    userCreated: "Користувача створено",
    userRoleUpdated: "Роль користувача оновлено",
    users: "Користувачі",
    width: "Ширина",
  },
};

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
      slide_type: "tandem",
      bottom_type: "hdf",
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

function formatDrawers(drawers, t) {
  if (!Array.isArray(drawers) || drawers.length === 0) {
    return t.notSet;
  }

  return drawers.join(", ");
}

function formatDateTime(value, t) {
  if (!value) {
    return t.notSet;
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return t.notSet;
  }

  return date.toLocaleString();
}

function formatAuditDetails(details, t) {
  if (!details || Object.keys(details).length === 0) {
    return t.noDetails;
  }

  return JSON.stringify(details);
}

function formatUserId(value, t) {
  if (!value) {
    return t.notSet;
  }

  return value;
}

function canEditProject(project, user) {
  if (!project || !user) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  if (user.role === "manager") {
    return project.created_by_user_id === user.id;
  }

  return false;
}

function canDeleteProject(user) {
  return user?.role === "admin";
}

function canRollbackProject(user) {
  return user?.role === "admin";
}

function canCreateProject(user) {
  return user?.role === "admin" || user?.role === "manager";
}

export default function App() {
  const [language, setLanguage] = useState(
    () => localStorage.getItem(LANGUAGE_STORAGE_KEY) || "en",
  );
  const [token, setToken] = useState(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) || "",
  );
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [ownPasswordForm, setOwnPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
  });
  const [newUserForm, setNewUserForm] = useState({
    email: "",
    password: "",
    role: "manager",
  });
  const [newProjectForm, setNewProjectForm] = useState(DEFAULT_PROJECT_FORM);
  const [resetPasswordForms, setResetPasswordForms] = useState({});
  const [projects, setProjects] = useState([]);
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [usersTotal, setUsersTotal] = useState(0);
  const [auditTotal, setAuditTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [usersOffset, setUsersOffset] = useState(0);
  const [auditOffset, setAuditOffset] = useState(0);
  const [selectedProject, setSelectedProject] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [form, setForm] = useState(projectToForm(null));
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [activeView, setActiveView] = useState("projects");

  const t = TRANSLATIONS[language] || TRANSLATIONS.en;

  const canGoBack = offset > 0;
  const canGoForward = offset + PAGE_SIZE < total;
  const canUsersGoBack = usersOffset > 0;
  const canUsersGoForward = usersOffset + PAGE_SIZE < usersTotal;
  const canAuditGoBack = auditOffset > 0;
  const canAuditGoForward = auditOffset + PAGE_SIZE < auditTotal;

  const selectedProjectId = selectedProject?.id || "";
  const canEditSelectedProject = canEditProject(selectedProject, user);
  const canDeleteSelectedProject = canDeleteProject(user);
  const canRollbackSelectedProject = canRollbackProject(user);
  const canCreateNewProject = canCreateProject(user);

  const pageLabel = useMemo(() => {
    if (total === 0) {
      return "0 of 0";
    }

    return `${offset + 1}-${Math.min(offset + PAGE_SIZE, total)} ${t.of} ${total}`;
  }, [offset, total, t]);

  const usersPageLabel = useMemo(() => {
    if (usersTotal === 0) {
      return "0 of 0";
    }

    return `${usersOffset + 1}-${Math.min(
      usersOffset + PAGE_SIZE,
      usersTotal,
    )} ${t.of} ${usersTotal}`;
  }, [usersOffset, usersTotal, t]);

  const auditPageLabel = useMemo(() => {
    if (auditTotal === 0) {
      return "0 of 0";
    }

    return `${auditOffset + 1}-${Math.min(
      auditOffset + PAGE_SIZE,
      auditTotal,
    )} ${t.of} ${auditTotal}`;
  }, [auditOffset, auditTotal, t]);

  const activePageLabel = useMemo(() => {
    if (activeView === "projects") {
      return pageLabel;
    }

    if (activeView === "users") {
      return usersPageLabel;
    }

    return auditPageLabel;
  }, [activeView, auditPageLabel, pageLabel, usersPageLabel]);

  function changeLanguage(nextLanguage) {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
    setLanguage(nextLanguage);
  }

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
      setStatus(result.error || t.unableToLoadProjects);
      return;
    }

    setProjects(result.projects);
    setTotal(result.total);
    setOffset(result.offset);
  }

  async function loadUsers(activeToken = token, nextOffset = usersOffset) {
    if (!activeToken || user?.role !== "admin") {
      return;
    }

    setLoading(true);
    const result = await listUsers(activeToken, PAGE_SIZE, nextOffset);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadUsers);
      return;
    }

    setUsers(result.users);
    setUsersTotal(result.total);
    setUsersOffset(result.offset);
  }

  async function loadAuditLogs(activeToken = token, nextOffset = auditOffset) {
    if (!activeToken || user?.role !== "admin") {
      return;
    }

    setLoading(true);
    const result = await listAuditLogs(activeToken, PAGE_SIZE, nextOffset);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadAuditLogs);
      return;
    }

    setAuditLogs(result.audit_logs);
    setAuditTotal(result.total);
    setAuditOffset(result.offset);
  }

  async function loadProject(projectId) {
    const [projectResult, historyResult] = await Promise.all([
      getProject(token, projectId),
      getProjectHistory(token, projectId),
    ]);

    if (!projectResult.success) {
      setStatus(projectResult.error || t.projectNotFound);
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
      setStatus(result.error || t.loginFailed);
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
    setUsers([]);
    setAuditLogs([]);
    setResetPasswordForms({});
    setOwnPasswordForm({
      currentPassword: "",
      newPassword: "",
    });
    setSelectedProject(null);
    setHistoryItems([]);
    setStatus("");
  }

  async function switchView(view) {
    setActiveView(view);
    setStatus("");

    if (view === "projects") {
      await loadProjects(token, offset);
      return;
    }

    if (view === "users") {
      await loadUsers(token, usersOffset);
      return;
    }

    if (view === "audit") {
      await loadAuditLogs(token, auditOffset);
    }
  }

  async function handleUserRoleChange(targetUser, role) {
    setLoading(true);
    const result = await updateUserRole(token, targetUser.id, role);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToUpdateUserRole);
      return;
    }

    setStatus(t.userRoleUpdated);
    await loadUsers(token, usersOffset);
  }

  async function handleUserActiveChange(targetUser, isActive) {
    setLoading(true);
    const result = await updateUserActive(token, targetUser.id, isActive);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToUpdateUserAccess);
      return;
    }

    setStatus(t.userAccessUpdated);
    await loadUsers(token, usersOffset);
  }

  function setResetPasswordValue(userId, passwordValue) {
    setResetPasswordForms({
      ...resetPasswordForms,
      [userId]: passwordValue,
    });
  }

  async function handleOwnPasswordChange(event) {
    event.preventDefault();

    setLoading(true);
    const result = await changeOwnPassword(
      token,
      ownPasswordForm.currentPassword,
      ownPasswordForm.newPassword,
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToChangePassword);
      return;
    }

    setOwnPasswordForm({
      currentPassword: "",
      newPassword: "",
    });
    setStatus(t.passwordChanged);
  }

  async function handleResetPassword(targetUser) {
    const passwordValue = resetPasswordForms[targetUser.id] || "";

    if (passwordValue.length < 8) {
      setStatus(t.passwordMustBeLong);
      return;
    }

    setLoading(true);
    const result = await resetUserPassword(
      token,
      targetUser.id,
      passwordValue,
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToResetPassword);
      return;
    }

    setResetPasswordForms({
      ...resetPasswordForms,
      [targetUser.id]: "",
    });
    setStatus(t.passwordReset);
    await loadUsers(token, usersOffset);
  }

  async function handleCreateUser(event) {
    event.preventDefault();

    setLoading(true);
    const result = await createUser(
      token,
      newUserForm.email,
      newUserForm.password,
      newUserForm.role,
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToCreateUser);
      return;
    }

    setNewUserForm({
      email: "",
      password: "",
      role: "manager",
    });
    setStatus(t.userCreated);
    await loadUsers(token, 0);
  }

  async function handleCreateProject(event) {
    event.preventDefault();

    if (!canCreateNewProject) {
      return;
    }

    setLoading(true);
    const result = await generateProject(
      token,
      buildProjectPayload(newProjectForm),
    );
    setLoading(false);

    if (!result.success) {
      setStatus(
        result.errors?.join(", ") || result.error || t.unableToCreateProject,
      );
      return;
    }

    const projectId = result.result?.project_id;

    setNewProjectForm(DEFAULT_PROJECT_FORM);
    setStatus(t.projectCreated);
    await loadProjects(token, 0);

    if (projectId) {
      await loadProject(projectId);
    }
  }

  async function handleUpdate(event) {
    event.preventDefault();

    if (!selectedProjectId) {
      return;
    }

    if (!canEditSelectedProject) {
      setStatus(t.projectEditRestricted);
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
      setStatus(result.error || t.updateFailed);
      return;
    }

    setStatus(t.projectUpdated);
    await loadProject(selectedProjectId);
    await loadProjects(token, offset);
  }

  function openRollbackConfirm(version) {
    if (!canRollbackSelectedProject) {
      setStatus(t.projectRollbackRestricted);
      return;
    }

    setConfirmAction({
      type: "rollback",
      title: t.rollbackProject,
      message: `${t.rollbackProject} ${selectedProjectId} ${t.to} ${version.width} x ${version.height} x ${version.depth}?`,
      confirmLabel: t.rollback,
      targetId: version.id,
    });
  }

  function openDeleteConfirm() {
    if (!selectedProjectId) {
      return;
    }

    if (!canDeleteSelectedProject) {
      setStatus(t.projectDeleteRestricted);
      return;
    }

    setConfirmAction({
      type: "delete",
      title: t.deleteProject,
      message: `${t.deleteProjectConfirm} ${selectedProjectId}?`,
      confirmLabel: t.delete,
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

    if (!canRollbackSelectedProject) {
      setStatus(t.projectRollbackRestricted);
      return;
    }

    setLoading(true);
    const result = await rollbackProject(token, selectedProjectId, versionId);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.rollbackFailed);
      return;
    }

    setStatus(t.projectRolledBack);
    closeConfirm();
    await loadProject(selectedProjectId);
    await loadProjects(token, offset);
  }

  async function handleDelete() {
    if (!selectedProjectId) {
      return;
    }

    if (!canDeleteSelectedProject) {
      setStatus(t.projectDeleteRestricted);
      return;
    }

    setLoading(true);
    const result = await deleteProject(token, selectedProjectId);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.deleteFailed);
      return;
    }

    setStatus(t.projectDeleted);
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

  useEffect(() => {
    if (!token || user?.role !== "admin" || activeView !== "users") {
      return;
    }

    loadUsers(token, 0);
  }, [token, user, activeView]);

  useEffect(() => {
    if (!token || user?.role !== "admin" || activeView !== "audit") {
      return;
    }

    loadAuditLogs(token, 0);
  }, [token, user, activeView]);

  if (!token || !user) {
    return (
      <main className="auth-screen">
        <form className="login-panel" onSubmit={handleLogin}>
          <div>
            <p className="eyebrow">{t.furniturePlatform}</p>
            <h1>{t.admin}</h1>
          </div>

          <label>
            {t.email}
            <input
              autoComplete="email"
              onChange={(event) => setEmail(event.target.value)}
              required
              type="email"
              value={email}
            />
          </label>

          <label>
            {t.password}
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
            {t.signIn}
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="eyebrow">{t.furniturePlatform}</p>
          <h1>{t.admin}</h1>
        </div>

        <div className="language-switcher" aria-label="Language">
          <button
            className={language === "en" ? "active" : ""}
            onClick={() => changeLanguage("en")}
            type="button"
          >
            EN
          </button>
          <button
            className={language === "uk" ? "active" : ""}
            onClick={() => changeLanguage("uk")}
            type="button"
          >
            UA
          </button>
        </div>

        <div className="user-block">
          <span>{user.email}</span>
          <strong>{user.role}</strong>
        </div>

        <nav className="nav-tabs" aria-label="Admin sections">
          <button
            className={activeView === "projects" ? "active" : ""}
            onClick={() => switchView("projects")}
            type="button"
          >
            {t.projects}
          </button>
          {user.role === "admin" ? (
            <>
              <button
                className={activeView === "users" ? "active" : ""}
                onClick={() => switchView("users")}
                type="button"
              >
                {t.users}
              </button>
              <button
                className={activeView === "audit" ? "active" : ""}
                onClick={() => switchView("audit")}
                type="button"
              >
                {t.audit}
              </button>
            </>
          ) : null}
        </nav>

        <form className="password-panel" onSubmit={handleOwnPasswordChange}>
          <p className="eyebrow">{t.password}</p>
          <input
            autoComplete="current-password"
            minLength={8}
            onChange={(event) =>
              setOwnPasswordForm({
                ...ownPasswordForm,
                currentPassword: event.target.value,
              })
            }
            placeholder={t.currentPassword}
            required
            type="password"
            value={ownPasswordForm.currentPassword}
          />
          <input
            autoComplete="new-password"
            minLength={8}
            onChange={(event) =>
              setOwnPasswordForm({
                ...ownPasswordForm,
                newPassword: event.target.value,
              })
            }
            placeholder={t.newPassword}
            required
            type="password"
            value={ownPasswordForm.newPassword}
          />
          <button className="ghost-button" disabled={loading} type="submit">
            {t.changePassword}
          </button>
        </form>

        <button className="ghost-button" onClick={handleLogout} type="button">
          <LogOut size={18} />
          {t.logout}
        </button>
      </aside>

      <section className="workspace">
        <header className="toolbar">
          <div>
            <h2>
              {activeView === "projects"
                ? t.projects
                : activeView === "users"
                  ? t.users
                  : t.audit}
            </h2>
            <p>{activePageLabel}</p>
          </div>

          <div className="toolbar-actions">
            {activeView === "projects" ? (
              <>
                <button
                  aria-label="Previous page"
                  className="icon-button"
                  disabled={!canGoBack || loading}
                  onClick={() =>
                    loadProjects(token, Math.max(0, offset - PAGE_SIZE))
                  }
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
              </>
            ) : activeView === "users" ? (
              <>
                <button
                  aria-label="Previous users page"
                  className="icon-button"
                  disabled={!canUsersGoBack || loading}
                  onClick={() =>
                    loadUsers(token, Math.max(0, usersOffset - PAGE_SIZE))
                  }
                  type="button"
                >
                  <ChevronLeft size={18} />
                </button>
                <button
                  aria-label="Next users page"
                  className="icon-button"
                  disabled={!canUsersGoForward || loading}
                  onClick={() => loadUsers(token, usersOffset + PAGE_SIZE)}
                  type="button"
                >
                  <ChevronRight size={18} />
                </button>
                <button
                  aria-label="Refresh users"
                  className="icon-button"
                  disabled={loading}
                  onClick={() => loadUsers(token, usersOffset)}
                  type="button"
                >
                  <RefreshCw size={18} />
                </button>
              </>
            ) : (
              <>
                <button
                  aria-label="Previous audit page"
                  className="icon-button"
                  disabled={!canAuditGoBack || loading}
                  onClick={() =>
                    loadAuditLogs(token, Math.max(0, auditOffset - PAGE_SIZE))
                  }
                  type="button"
                >
                  <ChevronLeft size={18} />
                </button>
                <button
                  aria-label="Next audit page"
                  className="icon-button"
                  disabled={!canAuditGoForward || loading}
                  onClick={() => loadAuditLogs(token, auditOffset + PAGE_SIZE)}
                  type="button"
                >
                  <ChevronRight size={18} />
                </button>
                <button
                  aria-label="Refresh audit logs"
                  className="icon-button"
                  disabled={loading}
                  onClick={() => loadAuditLogs(token, auditOffset)}
                  type="button"
                >
                  <RefreshCw size={18} />
                </button>
              </>
            )}
          </div>
        </header>

        {status ? <p className="status">{status}</p> : null}

        {activeView === "projects" ? (
          <div className="content-grid">
          <section className="table-panel">
            {canCreateNewProject ? (
              <form
                className="create-project-form"
                onSubmit={handleCreateProject}
              >
                <label>
                  {t.width}
                  <input
                    min="1"
                    onChange={(event) =>
                      setNewProjectForm({
                        ...newProjectForm,
                        width: event.target.value,
                      })
                    }
                    required
                    type="number"
                    value={newProjectForm.width}
                  />
                </label>
                <label>
                  {t.height}
                  <input
                    min="1"
                    onChange={(event) =>
                      setNewProjectForm({
                        ...newProjectForm,
                        height: event.target.value,
                      })
                    }
                    required
                    type="number"
                    value={newProjectForm.height}
                  />
                </label>
                <label>
                  {t.depth}
                  <input
                    min="1"
                    onChange={(event) =>
                      setNewProjectForm({
                        ...newProjectForm,
                        depth: event.target.value,
                      })
                    }
                    required
                    type="number"
                    value={newProjectForm.depth}
                  />
                </label>
                <label>
                  {t.sections}
                  <input
                    min="1"
                    onChange={(event) =>
                      setNewProjectForm({
                        ...newProjectForm,
                        sections: event.target.value,
                      })
                    }
                    required
                    type="number"
                    value={newProjectForm.sections}
                  />
                </label>
                <label>
                  {t.drawers}
                  <input
                    onChange={(event) =>
                      setNewProjectForm({
                        ...newProjectForm,
                        drawers: event.target.value,
                      })
                    }
                    placeholder="1, 2"
                    type="text"
                    value={newProjectForm.drawers}
                  />
                </label>
                <button
                  className="primary-button create-project-button"
                  disabled={loading}
                  type="submit"
                >
                  <Plus size={18} />
                  {t.createProject}
                </button>
              </form>
            ) : null}
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t.size}</th>
                  <th>{t.sections}</th>
                  <th>{t.drawers}</th>
                  <th>{t.updated}</th>
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
                    <td>{formatDrawers(project.drawers, t)}</td>
                    <td>{formatDateTime(project.updated_at, t)}</td>
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
                    <p className="eyebrow">{t.selectedProject}</p>
                    <h2>{selectedProject.id}</h2>
                    <div className="meta-grid">
                      <span>{t.created}: {formatDateTime(selectedProject.created_at, t)}</span>
                      <span>{t.updated}: {formatDateTime(selectedProject.updated_at, t)}</span>
                      <span>
                        {t.createdBy}: {formatUserId(selectedProject.created_by_user_id, t)}
                      </span>
                      <span>
                        {t.updatedBy}: {formatUserId(selectedProject.updated_by_user_id, t)}
                      </span>
                    </div>
                  </div>
                  {canDeleteSelectedProject ? (
                    <button
                      className="danger-button"
                      disabled={loading}
                      onClick={openDeleteConfirm}
                      type="button"
                    >
                      <Trash2 size={18} />
                      {t.delete}
                    </button>
                  ) : null}
                </div>

                {!canEditSelectedProject ? (
                  <div className="readonly-note">
                    <strong>{t.readOnlyProject}</strong>
                    <span>{t.readOnlyProjectDescription}</span>
                  </div>
                ) : null}

                <form className="edit-grid" onSubmit={handleUpdate}>
                  <label>
                    {t.width}
                    <input
                      disabled={!canEditSelectedProject || loading}
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
                    {t.height}
                    <input
                      disabled={!canEditSelectedProject || loading}
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
                    {t.depth}
                    <input
                      disabled={!canEditSelectedProject || loading}
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
                    {t.sections}
                    <input
                      disabled={!canEditSelectedProject || loading}
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
                    {t.drawers}
                    <input
                      disabled={!canEditSelectedProject || loading}
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
                    disabled={!canEditSelectedProject || loading}
                    type="submit"
                  >
                    <Save size={18} />
                    {t.save}
                  </button>
                </form>

                <div className="history-header">
                  <History size={18} />
                  <h3>{t.history}</h3>
                </div>
                <div className="history-list">
                  {historyItems.map((item) => (
                    <article className="history-item" key={item.id}>
                      <div>
                        <strong>{item.id}</strong>
                        <span>
                          {item.width} x {item.height} x {item.depth}
                        </span>
                        <span>{formatDateTime(item.created_at, t)}</span>
                      </div>
                      {canRollbackSelectedProject ? (
                        <button
                          className="ghost-button"
                          disabled={loading}
                          onClick={() => openRollbackConfirm(item)}
                          type="button"
                        >
                          <RotateCcw size={16} />
                          {t.rollback}
                        </button>
                      ) : null}
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <Search size={22} />
                <p>{t.selectProject}</p>
              </div>
            )}
          </section>
        </div>
        ) : activeView === "users" ? (
          <section className="table-panel full-panel">
            <form className="create-user-form" onSubmit={handleCreateUser}>
              <label>
                {t.email}
                <input
                  autoComplete="email"
                  onChange={(event) =>
                    setNewUserForm({
                      ...newUserForm,
                      email: event.target.value,
                    })
                  }
                  required
                  type="email"
                  value={newUserForm.email}
                />
              </label>
              <label>
                {t.password}
                <input
                  autoComplete="new-password"
                  minLength={8}
                  onChange={(event) =>
                    setNewUserForm({
                      ...newUserForm,
                      password: event.target.value,
                    })
                  }
                  required
                  type="password"
                  value={newUserForm.password}
                />
              </label>
              <label>
                {t.role}
                <select
                  onChange={(event) =>
                    setNewUserForm({
                      ...newUserForm,
                      role: event.target.value,
                    })
                  }
                  value={newUserForm.role}
                >
                  <option value="admin">admin</option>
                  <option value="manager">manager</option>
                  <option value="viewer">viewer</option>
                </select>
              </label>
              <button
                className="primary-button create-user-button"
                disabled={loading}
                type="submit"
              >
                {t.createUser}
              </button>
            </form>
            <table>
              <thead>
                <tr>
                  <th>{t.email}</th>
                  <th>{t.role}</th>
                  <th>{t.status}</th>
                  <th>{t.access}</th>
                  <th>{t.password}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((targetUser) => (
                  <tr key={targetUser.id}>
                    <td>{targetUser.email}</td>
                    <td>
                      <select
                        disabled={loading || targetUser.id === user.id}
                        onChange={(event) =>
                          handleUserRoleChange(targetUser, event.target.value)
                        }
                        value={targetUser.role}
                      >
                        <option value="admin">admin</option>
                        <option value="manager">manager</option>
                        <option value="viewer">viewer</option>
                      </select>
                    </td>
                    <td>{targetUser.is_active ? t.active : t.inactive}</td>
                    <td>
                      <label className="toggle-label">
                        <input
                          checked={targetUser.is_active}
                          disabled={loading || targetUser.id === user.id}
                          onChange={(event) =>
                            handleUserActiveChange(
                              targetUser,
                              event.target.checked,
                            )
                          }
                          type="checkbox"
                        />
                        {t.enabled}
                      </label>
                    </td>
                    <td>
                      <div className="reset-password-cell">
                        <input
                          autoComplete="new-password"
                          disabled={loading || targetUser.id === user.id}
                          minLength={8}
                          onChange={(event) =>
                            setResetPasswordValue(
                              targetUser.id,
                              event.target.value,
                            )
                          }
                          placeholder={t.newPassword}
                          type="password"
                          value={resetPasswordForms[targetUser.id] || ""}
                        />
                        <button
                          className="ghost-button"
                          disabled={loading || targetUser.id === user.id}
                          onClick={() => handleResetPassword(targetUser)}
                          type="button"
                        >
                          {t.reset}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : (
          <section className="table-panel full-panel">
            <table>
              <thead>
                <tr>
                  <th>{t.time}</th>
                  <th>{t.actor}</th>
                  <th>{t.action}</th>
                  <th>{t.entity}</th>
                  <th>{t.details}</th>
                </tr>
              </thead>
              <tbody>
                {auditLogs.map((auditLog) => (
                  <tr key={auditLog.id}>
                    <td>{formatDateTime(auditLog.created_at, t)}</td>
                    <td>{auditLog.actor_email}</td>
                    <td>{auditLog.action}</td>
                    <td>
                      {auditLog.entity_type}: {auditLog.entity_id}
                    </td>
                    <td className="audit-details">
                      {formatAuditDetails(auditLog.details, t)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
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
                {t.cancel}
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
