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
  createCatalogItem,
  createUser,
  deleteProject,
  generateProject,
  getCurrentUser,
  getProject,
  getProjectCutting,
  getProjectHistory,
  getProjectPartDetail,
  getSpecificationCatalog,
  listAuditLogs,
  listCatalogItems,
  listUsers,
  listProjects,
  login,
  rollbackProject,
  resetUserPassword,
  updateCatalogItem,
  updateCatalogItemActive,
  updateProject,
  updateUserActive,
  updateUserRole,
} from "./api";

const TOKEN_STORAGE_KEY = "furniture_admin_token";
const LANGUAGE_STORAGE_KEY = "furniture_admin_language";
const PAGE_SIZE = 20;
const DEFAULT_PROJECT_FORM = {
  projectName: "",
  projectType: "dresser",
  clientName: "",
  roomName: "",
  width: 1000,
  height: 800,
  depth: 500,
  sections: 2,
  drawers: "1, 2",
  facadeMaterial: "",
  insideMaterial: "",
  edgeBanding: "",
  materialThickness: 18,
  slideType: "tandem",
  bottomType: "hdf",
  handleType: "",
  handlePosition: "",
  notes: "",
};
const DEFAULT_PROJECT_FILTERS = {
  search: "",
  project_type: "",
  slide_type: "",
  bottom_type: "",
  width_min: "",
  width_max: "",
  height_min: "",
  height_max: "",
  only_mine: false,
};
const DEFAULT_SPECIFICATION_CATALOG = {
  project_types: [
    "dresser",
    "wardrobe",
    "cabinet",
    "kitchen",
    "drawer_unit",
  ],
  slide_types: [
    "tandem",
    "movento",
    "telescopic",
  ],
  bottom_types: [
    "hdf",
    "hdf_3",
    "dsp",
    "dsp_18",
  ],
  material_thicknesses: [
    16,
    18,
    19,
  ],
  edge_bandings: [
    "abs_0_5",
    "abs_1",
    "abs_2",
    "pvc_0_5",
    "pvc_1",
    "pvc_2",
  ],
  handle_positions: [
    "top",
    "center",
    "bottom",
    "left",
    "right",
    "integrated",
  ],
};
const CATALOG_CATEGORIES = [
  "project_type",
  "slide_type",
  "bottom_type",
  "material_thickness",
  "edge_banding",
  "handle_position",
];

const TRANSLATIONS = {
  en: {
    access: "Access",
    action: "Action",
    active: "Active",
    actor: "Actor",
    admin: "Admin",
    all: "All",
    applyFilters: "Apply",
    audit: "Audit",
    catalog: "Catalog",
    catalogCategory: "Category",
    catalogItemCreated: "Catalog item created",
    catalogItemUpdated: "Catalog item updated",
    catalogItemValue: "Value",
    catalogSortOrder: "Order",
    catalogStatusUpdated: "Catalog status updated",
    cancel: "Cancel",
    changePassword: "Change password",
    create: "Create",
    createProject: "Create project",
    createUser: "Create user",
    created: "Created",
    createdBy: "Created by",
    currentPassword: "Current password",
    cuttingArea: "Area, m2",
    cuttingEdge: "Edge, m",
    cuttingExportCode: "Code",
    cuttingGrain: "Grain",
    cuttingLength: "Length",
    cuttingSize: "Size",
    cuttingSummary: "Summary",
    bottomType: "Bottom type",
    bottom_type: "Bottom type",
    cabinet: "Cabinet",
    center: "Center",
    client: "Client",
    delete: "Delete",
    deleteFailed: "Delete failed",
    deleteProject: "Delete project",
    deleteProjectConfirm: "Delete project",
    deleteRestricted: "Only admins can delete projects",
    depth: "Depth",
    details: "Details",
    dresser: "Dresser",
    drawers: "Drawers",
    drawerUnit: "Drawer unit",
    edgeBanding: "Edge banding",
    email: "Email",
    enabled: "Enabled",
    entity: "Entity",
    edge_banding: "Edge banding",
    facadeMaterial: "Facade material",
    furniturePlatform: "Furniture Platform",
    handlePosition: "Handle position",
    handle_position: "Handle position",
    handleType: "Handle type",
    height: "Height",
    heightMax: "Height max",
    heightMin: "Height min",
    history: "History",
    insideMaterial: "Inside material",
    inactive: "Inactive",
    integrated: "Integrated",
    kitchen: "Kitchen",
    left: "Left",
    invalidCurrentPassword: "Invalid current password",
    loginFailed: "Login failed",
    logout: "Logout",
    noDetails: "No details",
    noCuttingItems: "No cutting items yet.",
    newPassword: "New password",
    notSet: "Not set",
    materialThickness: "Thickness",
    material_thickness: "Thickness",
    notes: "Notes",
    of: "of",
    onlyMine: "Only mine",
    password: "Password",
    passwordChanged: "Password changed",
    passwordMustBeLong: "Password must be at least 8 characters",
    passwordReset: "Password reset",
    projectDeleted: "Project deleted",
    projectDeleteRestricted: "You do not have permission to delete this project",
    projectEditRestricted: "You do not have permission to edit this project",
    projectCreated: "Project created",
    projectName: "Project name",
    projectNotFound: "Project not found",
    projectRolledBack: "Project rolled back",
    projectRollbackRestricted: "You do not have permission to roll back this project",
    projectUpdated: "Project updated",
    projects: "Projects",
    projectType: "Project type",
    project_type: "Project type",
    production: "Production",
    productionCutting: "Cutting list",
    productionGrooves: "Grooves",
    productionHoles: "Holes",
    productionPartViewer: "Part map",
    productionQuarters: "Quarters",
    readOnlyProject: "Read-only project",
    readOnlyProjectDescription: "You can view this project, but cannot edit it.",
    reset: "Reset",
    right: "Right",
    role: "Role",
    rollback: "Rollback",
    rollbackFailed: "Rollback failed",
    rollbackProject: "Rollback project",
    room: "Room",
    save: "Save",
    searchProjects: "Search projects",
    sections: "Sections",
    selectProject: "Select a project",
    selectedProject: "Selected project",
    side: "Side",
    slideType: "Slide type",
    slide_type: "Slide type",
    signIn: "Sign in",
    size: "Size",
    specification: "Specification",
    status: "Status",
    time: "Time",
    top: "Top",
    to: "to",
    unableToChangePassword: "Unable to change password",
    unableToCreateProject: "Unable to create project",
    unableToCreateUser: "Unable to create user",
    unableToLoadCutting: "Unable to load cutting list",
    unableToLoadPart: "Unable to load part map",
    unableToLoadCatalog: "Unable to load catalog",
    unableToSaveCatalogItem: "Unable to save catalog item",
    unableToUpdateCatalogStatus: "Unable to update catalog status",
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
    widthMax: "Width max",
    widthMin: "Width min",
    wardrobe: "Wardrobe",
  },
  uk: {
    access: "Доступ",
    action: "Дія",
    active: "Активний",
    actor: "Користувач",
    admin: "Адмін",
    all: "Всі",
    applyFilters: "Застосувати",
    audit: "Аудит",
    catalog: "Довідники",
    catalogCategory: "Категорія",
    catalogItemCreated: "Значення довідника створено",
    catalogItemUpdated: "Значення довідника оновлено",
    catalogItemValue: "Значення",
    catalogSortOrder: "Порядок",
    catalogStatusUpdated: "Статус довідника оновлено",
    cancel: "Скасувати",
    changePassword: "Змінити пароль",
    create: "Створити",
    createProject: "Створити проект",
    createUser: "Створити користувача",
    created: "Створено",
    createdBy: "Створив",
    currentPassword: "Поточний пароль",
    cuttingArea: "Площа, м2",
    cuttingEdge: "Крайка, м",
    cuttingExportCode: "Код",
    cuttingGrain: "Волокно",
    cuttingLength: "Довжина",
    cuttingSize: "Розмір",
    cuttingSummary: "Підсумок",
    bottomType: "Тип дна",
    bottom_type: "Тип дна",
    cabinet: "Тумба",
    center: "По центру",
    client: "Клієнт",
    delete: "Видалити",
    deleteFailed: "Не вдалося видалити",
    deleteProject: "Видалити проект",
    deleteProjectConfirm: "Видалити проект",
    deleteRestricted: "Видаляти проекти може тільки адміністратор",
    depth: "Глибина",
    details: "Деталі",
    dresser: "Комод",
    drawers: "Шухляди",
    drawerUnit: "Блок шухляд",
    edgeBanding: "Крайка",
    email: "Email",
    enabled: "Увімкнено",
    entity: "Сутність",
    edge_banding: "Крайка",
    facadeMaterial: "Матеріал фасаду",
    furniturePlatform: "Furniture Platform",
    handlePosition: "Позиція ручки",
    handle_position: "Позиція ручки",
    handleType: "Тип ручки",
    height: "Висота",
    heightMax: "Висота до",
    heightMin: "Висота від",
    history: "Історія",
    insideMaterial: "Матеріал корпусу",
    inactive: "Неактивний",
    integrated: "Інтегрована",
    kitchen: "Кухня",
    left: "Зліва",
    invalidCurrentPassword: "Невірний поточний пароль",
    loginFailed: "Не вдалося увійти",
    logout: "Вийти",
    noDetails: "Без деталей",
    noCuttingItems: "Карта розкрою ще порожня.",
    newPassword: "Новий пароль",
    notSet: "Не вказано",
    materialThickness: "Товщина",
    material_thickness: "Товщина",
    notes: "Нотатки",
    of: "з",
    onlyMine: "Тільки мої",
    password: "Пароль",
    passwordChanged: "Пароль змінено",
    passwordMustBeLong: "Пароль має містити мінімум 8 символів",
    passwordReset: "Пароль скинуто",
    projectDeleted: "Проект видалено",
    projectDeleteRestricted: "У вас немає прав для видалення цього проекту",
    projectEditRestricted: "У вас немає прав для редагування цього проекту",
    projectCreated: "Проект створено",
    projectName: "Назва проекту",
    projectNotFound: "Проект не знайдено",
    projectRolledBack: "Проект відновлено",
    projectRollbackRestricted: "У вас немає прав для відновлення цього проекту",
    projectUpdated: "Проект оновлено",
    projects: "Проекти",
    projectType: "Тип проекту",
    project_type: "Тип проекту",
    production: "Виробництво",
    productionCutting: "Карта розкрою",
    productionGrooves: "Пази",
    productionHoles: "Отвори",
    productionPartViewer: "Карта деталі",
    productionQuarters: "Чверті",
    readOnlyProject: "Проект лише для перегляду",
    readOnlyProjectDescription: "Ви можете переглядати цей проект, але не можете його редагувати.",
    reset: "Скинути",
    right: "Справа",
    role: "Роль",
    rollback: "Відновити",
    rollbackFailed: "Не вдалося відновити",
    rollbackProject: "Відновити проект",
    room: "Кімната",
    save: "Зберегти",
    searchProjects: "Пошук проектів",
    sections: "Секції",
    selectProject: "Виберіть проект",
    selectedProject: "Вибраний проект",
    side: "Сторона",
    slideType: "Тип направляючих",
    slide_type: "Тип направляючих",
    signIn: "Увійти",
    size: "Розмір",
    specification: "Специфікація",
    status: "Статус",
    time: "Час",
    top: "Зверху",
    to: "до",
    unableToChangePassword: "Не вдалося змінити пароль",
    unableToCreateProject: "Не вдалося створити проект",
    unableToCreateUser: "Не вдалося створити користувача",
    unableToLoadCutting: "Не вдалося завантажити карту розкрою",
    unableToLoadPart: "Не вдалося завантажити карту деталі",
    unableToLoadCatalog: "Не вдалося завантажити довідники",
    unableToSaveCatalogItem: "Не вдалося зберегти значення довідника",
    unableToUpdateCatalogStatus: "Не вдалося оновити статус довідника",
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
    widthMax: "Ширина до",
    widthMin: "Ширина від",
    wardrobe: "Шафа",
  },
};

function buildProjectPayload(form) {
  return {
    metadata: {
      name: form.projectName || null,
      type: form.projectType || null,
      client: form.clientName || null,
      room: form.roomName || null,
      notes: form.notes || null,
    },
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
      facade: form.facadeMaterial || null,
      inside: form.insideMaterial || null,
      edge_banding: form.edgeBanding || null,
      thickness: form.materialThickness ? Number(form.materialThickness) : null,
    },
    fittings: {
      slide_type: form.slideType || "tandem",
      bottom_type: form.bottomType || "hdf",
      handle_type: form.handleType || null,
      handle_position: form.handlePosition || null,
    },
  };
}

function projectToForm(project) {
  return {
    projectName: project?.project_name || "",
    projectType: project?.project_type || "dresser",
    clientName: project?.client_name || "",
    roomName: project?.room_name || "",
    width: project?.width || "",
    height: project?.height || "",
    depth: project?.depth || "",
    sections: project?.sections || "",
    drawers: Array.isArray(project?.drawers) ? project.drawers.join(", ") : "",
    facadeMaterial: project?.facade_material || "",
    insideMaterial: project?.inside_material || "",
    edgeBanding: project?.edge_banding || "",
    materialThickness: project?.material_thickness || 18,
    slideType: project?.slide_type || "tandem",
    bottomType: project?.bottom_type || "hdf",
    handleType: project?.handle_type || "",
    handlePosition: project?.handle_position || "",
    notes: project?.notes || "",
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

function formatCatalogLabel(value, t) {
  if (!value) {
    return t.notSet;
  }

  return t[value] || value;
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

function PartPreview({ detail }) {
  if (!detail?.part) {
    return null;
  }

  const { part } = detail;
  const viewWidth = 720;
  const viewHeight = 360;
  const margin = 58;
  const scale = Math.min(
    (viewWidth - margin * 2) / part.width,
    (viewHeight - margin * 2) / part.height,
  );
  const width = part.width * scale;
  const height = part.height * scale;
  const x = (viewWidth - width) / 2;
  const y = (viewHeight - height) / 2;

  function pxX(value) {
    return x + value * scale;
  }

  function pxY(value) {
    return y + height - value * scale;
  }

  function edgeLine(side, material) {
    if (!material || material === "not_set") {
      return null;
    }

    const props = {
      className: "part-edge",
      key: side,
    };

    if (side === "top") {
      return <line {...props} x1={x} x2={x + width} y1={y} y2={y} />;
    }

    if (side === "bottom") {
      return <line {...props} x1={x} x2={x + width} y1={y + height} y2={y + height} />;
    }

    if (side === "left") {
      return <line {...props} x1={x} x2={x} y1={y} y2={y + height} />;
    }

    return <line {...props} x1={x + width} x2={x + width} y1={y} y2={y + height} />;
  }

  return (
    <svg className="part-preview" role="img" viewBox={`0 0 ${viewWidth} ${viewHeight}`}>
      <rect className="part-board" height={height} width={width} x={x} y={y} />
      {edgeLine("top", part.edge_top)}
      {edgeLine("bottom", part.edge_bottom)}
      {edgeLine("left", part.edge_left)}
      {edgeLine("right", part.edge_right)}

      <line className="dimension-line" x1={x} x2={x + width} y1={y - 28} y2={y - 28} />
      <line className="dimension-line" x1={x} x2={x} y1={y - 42} y2={y - 12} />
      <line className="dimension-line" x1={x + width} x2={x + width} y1={y - 42} y2={y - 12} />
      <text className="dimension-text" textAnchor="middle" x={viewWidth / 2} y={y - 36}>
        {part.width}
      </text>

      <line className="dimension-line" x1={x + width + 30} x2={x + width + 30} y1={y} y2={y + height} />
      <line className="dimension-line" x1={x + width + 16} x2={x + width + 44} y1={y} y2={y} />
      <line className="dimension-line" x1={x + width + 16} x2={x + width + 44} y1={y + height} y2={y + height} />
      <text
        className="dimension-text rotated"
        textAnchor="middle"
        transform={`translate(${x + width + 62} ${viewHeight / 2}) rotate(-90)`}
      >
        {part.height}
      </text>

      {detail.holes.map((hole) => (
        <circle
          className="part-hole"
          cx={pxX(hole.x)}
          cy={pxY(hole.y)}
          key={`hole-${hole.number}`}
          r={Math.max(4, hole.diameter * 0.75)}
        />
      ))}

      {detail.grooves.map((groove) => (
        <rect
          className="part-groove"
          height={Math.max(3, groove.width * scale)}
          key={`groove-${groove.number}`}
          width={groove.length * scale}
          x={pxX(groove.x)}
          y={pxY(groove.y) - Math.max(3, groove.width * scale) / 2}
        />
      ))}
    </svg>
  );
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
  const [newCatalogItemForm, setNewCatalogItemForm] = useState({
    category: "project_type",
    value: "",
    sortOrder: 0,
  });
  const [newProjectForm, setNewProjectForm] = useState(DEFAULT_PROJECT_FORM);
  const [projectFilters, setProjectFilters] = useState(DEFAULT_PROJECT_FILTERS);
  const [resetPasswordForms, setResetPasswordForms] = useState({});
  const [projects, setProjects] = useState([]);
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [catalogItems, setCatalogItems] = useState([]);
  const [specificationCatalog, setSpecificationCatalog] = useState(
    DEFAULT_SPECIFICATION_CATALOG,
  );
  const [total, setTotal] = useState(0);
  const [usersTotal, setUsersTotal] = useState(0);
  const [auditTotal, setAuditTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [usersOffset, setUsersOffset] = useState(0);
  const [auditOffset, setAuditOffset] = useState(0);
  const [selectedProject, setSelectedProject] = useState(null);
  const [historyItems, setHistoryItems] = useState([]);
  const [cuttingItems, setCuttingItems] = useState([]);
  const [cuttingSummary, setCuttingSummary] = useState(null);
  const [selectedPartDetail, setSelectedPartDetail] = useState(null);
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

    if (activeView === "createProject") {
      return t.specification;
    }

    if (activeView === "users") {
      return usersPageLabel;
    }

    if (activeView === "catalog") {
      return `${catalogItems.length} ${t.of} ${catalogItems.length}`;
    }

    return auditPageLabel;
  }, [activeView, auditPageLabel, catalogItems.length, pageLabel, t, usersPageLabel]);

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

  async function loadProjects(
    activeToken = token,
    nextOffset = offset,
    filters = projectFilters,
  ) {
    if (!activeToken) {
      return;
    }

    setLoading(true);
    const result = await listProjects(
      activeToken,
      PAGE_SIZE,
      nextOffset,
      filters,
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadProjects);
      return;
    }

    setProjects(result.projects);
    setTotal(result.total);
    setOffset(result.offset);
  }

  async function loadSpecificationCatalog() {
    const result = await getSpecificationCatalog();

    if (!result.success) {
      return;
    }

    setSpecificationCatalog({
      project_types: result.project_types || DEFAULT_SPECIFICATION_CATALOG.project_types,
      slide_types: result.slide_types || DEFAULT_SPECIFICATION_CATALOG.slide_types,
      bottom_types: result.bottom_types || DEFAULT_SPECIFICATION_CATALOG.bottom_types,
      material_thicknesses:
        result.material_thicknesses ||
        DEFAULT_SPECIFICATION_CATALOG.material_thicknesses,
      edge_bandings: result.edge_bandings || DEFAULT_SPECIFICATION_CATALOG.edge_bandings,
      handle_positions:
        result.handle_positions || DEFAULT_SPECIFICATION_CATALOG.handle_positions,
    });
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

  async function loadCatalogItems(activeToken = token) {
    if (!activeToken || user?.role !== "admin") {
      return;
    }

    setLoading(true);
    const result = await listCatalogItems(activeToken);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadCatalog);
      return;
    }

    setCatalogItems(result.items);
  }

  async function loadProject(projectId) {
    const [projectResult, historyResult, cuttingResult] = await Promise.all([
      getProject(token, projectId),
      getProjectHistory(token, projectId),
      getProjectCutting(token, projectId),
    ]);

    if (!projectResult.success) {
      setStatus(projectResult.error || t.projectNotFound);
      return;
    }

    setSelectedProject(projectResult.project);
    setForm(projectToForm(projectResult.project));
    setHistoryItems(historyResult.success ? historyResult.versions : []);
    setCuttingItems(cuttingResult.success ? cuttingResult.items : []);
    setCuttingSummary(cuttingResult.success ? cuttingResult.summary : null);
    setSelectedPartDetail(null);

    if (!cuttingResult.success) {
      setStatus(cuttingResult.error || t.unableToLoadCutting);
    }
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
    await loadSpecificationCatalog();
    await loadProjects(result.access_token, 0);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken("");
    setUser(null);
    setProjects([]);
    setUsers([]);
    setAuditLogs([]);
    setCatalogItems([]);
    setResetPasswordForms({});
    setOwnPasswordForm({
      currentPassword: "",
      newPassword: "",
    });
    setSelectedProject(null);
    setHistoryItems([]);
    setCuttingItems([]);
    setCuttingSummary(null);
    setSelectedPartDetail(null);
    setStatus("");
  }

  async function handleSelectCuttingPart(partCode) {
    if (!selectedProjectId) {
      return;
    }

    const result = await getProjectPartDetail(token, selectedProjectId, partCode);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadPart);
      return;
    }

    setSelectedPartDetail(result);
    setStatus("");
  }

  async function switchView(view) {
    setActiveView(view);
    setStatus("");

    if (view === "projects") {
      await loadProjects(token, offset);
      return;
    }

    if (view === "createProject") {
      return;
    }

    if (view === "users") {
      await loadUsers(token, usersOffset);
      return;
    }

    if (view === "catalog") {
      await loadCatalogItems(token);
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

  async function handleCreateCatalogItem(event) {
    event.preventDefault();

    setLoading(true);
    const result = await createCatalogItem(
      token,
      newCatalogItemForm.category,
      newCatalogItemForm.value,
      newCatalogItemForm.sortOrder,
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveCatalogItem);
      return;
    }

    setNewCatalogItemForm({
      ...newCatalogItemForm,
      value: "",
      sortOrder: 0,
    });
    setStatus(t.catalogItemCreated);
    await loadCatalogItems(token);
    await loadSpecificationCatalog();
  }

  async function handleCatalogItemUpdate(item, value, sortOrder) {
    setLoading(true);
    const result = await updateCatalogItem(
      token,
      item.id,
      value,
      sortOrder,
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveCatalogItem);
      return;
    }

    setStatus(t.catalogItemUpdated);
    await loadCatalogItems(token);
    await loadSpecificationCatalog();
  }

  async function handleCatalogItemActiveChange(item, isActive) {
    setLoading(true);
    const result = await updateCatalogItemActive(
      token,
      item.id,
      isActive,
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToUpdateCatalogStatus);
      return;
    }

    setStatus(t.catalogStatusUpdated);
    await loadCatalogItems(token);
    await loadSpecificationCatalog();
  }

  async function handleApplyProjectFilters(event) {
    event.preventDefault();

    await loadProjects(token, 0, projectFilters);
  }

  async function handleResetProjectFilters() {
    setProjectFilters(DEFAULT_PROJECT_FILTERS);
    await loadProjects(token, 0, DEFAULT_PROJECT_FILTERS);
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
    setProjectFilters(DEFAULT_PROJECT_FILTERS);
    setStatus(t.projectCreated);
    setActiveView("projects");
    await loadProjects(token, 0, DEFAULT_PROJECT_FILTERS);

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
    setCuttingItems([]);
    setCuttingSummary(null);
    setSelectedPartDetail(null);
    await loadProjects(token, offset);
  }

  useEffect(() => {
    if (!token) {
      return;
    }

    loadUser(token);
    loadSpecificationCatalog();
    loadProjects(token, 0);
  }, [token]);

  useEffect(() => {
    function handleUnauthorized() {
      handleLogout();
      setStatus(t.loginFailed);
    }

    window.addEventListener("furniture-admin-unauthorized", handleUnauthorized);

    return () => {
      window.removeEventListener("furniture-admin-unauthorized", handleUnauthorized);
    };
  }, [t]);

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

  useEffect(() => {
    if (!token || user?.role !== "admin" || activeView !== "catalog") {
      return;
    }

    loadCatalogItems(token);
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
          {canCreateNewProject ? (
            <button
              className={activeView === "createProject" ? "active" : ""}
              onClick={() => switchView("createProject")}
              type="button"
            >
              {t.createProject}
            </button>
          ) : null}
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
                className={activeView === "catalog" ? "active" : ""}
                onClick={() => switchView("catalog")}
                type="button"
              >
                {t.catalog}
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
                : activeView === "createProject"
                  ? t.createProject
                : activeView === "users"
                  ? t.users
                : activeView === "catalog"
                  ? t.catalog
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
            ) : activeView === "catalog" ? (
              <button
                aria-label="Refresh catalog"
                className="icon-button"
                disabled={loading}
                onClick={() => loadCatalogItems(token)}
                type="button"
              >
                <RefreshCw size={18} />
              </button>
            ) : activeView === "audit" ? (
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
            ) : null}
          </div>
        </header>

        {status ? <p className="status">{status}</p> : null}

        {activeView === "projects" ? (
          <div className="content-grid">
          <section className="table-panel">
            <form
              className="project-filter-form"
              onSubmit={handleApplyProjectFilters}
            >
              <label>
                {t.searchProjects}
                <input
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      search: event.target.value,
                    })
                  }
                  type="search"
                  value={projectFilters.search}
                />
              </label>
              <label>
                {t.projectType}
                <select
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      project_type: event.target.value,
                    })
                  }
                  value={projectFilters.project_type}
                >
                  <option value="">{t.all}</option>
                  {specificationCatalog.project_types.map((projectType) => (
                    <option key={projectType} value={projectType}>
                      {formatCatalogLabel(projectType, t)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.slideType}
                <select
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      slide_type: event.target.value,
                    })
                  }
                  value={projectFilters.slide_type}
                >
                  <option value="">{t.all}</option>
                  {specificationCatalog.slide_types.map((slideType) => (
                    <option key={slideType} value={slideType}>
                      {slideType}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.bottomType}
                <select
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      bottom_type: event.target.value,
                    })
                  }
                  value={projectFilters.bottom_type}
                >
                  <option value="">{t.all}</option>
                  {specificationCatalog.bottom_types.map((bottomType) => (
                    <option key={bottomType} value={bottomType}>
                      {bottomType}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.widthMin}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      width_min: event.target.value,
                    })
                  }
                  type="number"
                  value={projectFilters.width_min}
                />
              </label>
              <label>
                {t.widthMax}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      width_max: event.target.value,
                    })
                  }
                  type="number"
                  value={projectFilters.width_max}
                />
              </label>
              <label>
                {t.heightMin}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      height_min: event.target.value,
                    })
                  }
                  type="number"
                  value={projectFilters.height_min}
                />
              </label>
              <label>
                {t.heightMax}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      height_max: event.target.value,
                    })
                  }
                  type="number"
                  value={projectFilters.height_max}
                />
              </label>
              <label className="toggle-label filter-toggle">
                <input
                  checked={projectFilters.only_mine}
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      only_mine: event.target.checked,
                    })
                  }
                  type="checkbox"
                />
                {t.onlyMine}
              </label>
              <button
                className="primary-button filter-button"
                disabled={loading}
                type="submit"
              >
                {t.applyFilters}
              </button>
              <button
                className="ghost-button filter-button"
                disabled={loading}
                onClick={handleResetProjectFilters}
                type="button"
              >
                {t.reset}
              </button>
            </form>
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t.projectType}</th>
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
                    <td>{project.project_type || t.notSet}</td>
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
                      <span>
                        {t.projectName}: {selectedProject.project_name || t.notSet}
                      </span>
                      <span>
                        {t.projectType}: {selectedProject.project_type || t.notSet}
                      </span>
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
                    {t.projectName}
                    <input
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, projectName: event.target.value })
                      }
                      type="text"
                      value={form.projectName}
                    />
                  </label>
                  <label>
                    {t.projectType}
                    <select
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, projectType: event.target.value })
                      }
                      value={form.projectType}
                    >
                      {specificationCatalog.project_types.map((projectType) => (
                        <option key={projectType} value={projectType}>
                          {formatCatalogLabel(projectType, t)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t.client}
                    <input
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, clientName: event.target.value })
                      }
                      type="text"
                      value={form.clientName}
                    />
                  </label>
                  <label>
                    {t.room}
                    <input
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, roomName: event.target.value })
                      }
                      type="text"
                      value={form.roomName}
                    />
                  </label>
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
                  <label>
                    {t.facadeMaterial}
                    <input
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, facadeMaterial: event.target.value })
                      }
                      type="text"
                      value={form.facadeMaterial}
                    />
                  </label>
                  <label>
                    {t.insideMaterial}
                    <input
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, insideMaterial: event.target.value })
                      }
                      type="text"
                      value={form.insideMaterial}
                    />
                  </label>
                  <label>
                    {t.edgeBanding}
                    <select
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, edgeBanding: event.target.value })
                      }
                      value={form.edgeBanding}
                    >
                      <option value="">{t.notSet}</option>
                      {specificationCatalog.edge_bandings.map((edgeBanding) => (
                        <option key={edgeBanding} value={edgeBanding}>
                          {edgeBanding}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t.materialThickness}
                    <select
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({
                          ...form,
                          materialThickness: event.target.value,
                        })
                      }
                      value={form.materialThickness}
                    >
                      {specificationCatalog.material_thicknesses.map(
                        (thickness) => (
                          <option key={thickness} value={thickness}>
                            {thickness}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <label>
                    {t.slideType}
                    <select
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, slideType: event.target.value })
                      }
                      value={form.slideType}
                    >
                      {specificationCatalog.slide_types.map((slideType) => (
                        <option key={slideType} value={slideType}>
                          {slideType}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t.bottomType}
                    <select
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, bottomType: event.target.value })
                      }
                      value={form.bottomType}
                    >
                      {specificationCatalog.bottom_types.map((bottomType) => (
                        <option key={bottomType} value={bottomType}>
                          {bottomType}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    {t.handleType}
                    <input
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, handleType: event.target.value })
                      }
                      type="text"
                      value={form.handleType}
                    />
                  </label>
                  <label>
                    {t.handlePosition}
                    <select
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, handlePosition: event.target.value })
                      }
                      value={form.handlePosition}
                    >
                      <option value="">{t.notSet}</option>
                      {specificationCatalog.handle_positions.map(
                        (handlePosition) => (
                          <option key={handlePosition} value={handlePosition}>
                            {formatCatalogLabel(handlePosition, t)}
                          </option>
                        ),
                      )}
                    </select>
                  </label>
                  <label className="wide-field">
                    {t.notes}
                    <input
                      disabled={!canEditSelectedProject || loading}
                      onChange={(event) =>
                        setForm({ ...form, notes: event.target.value })
                      }
                      type="text"
                      value={form.notes}
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

                <section className="production-section">
                  <div className="history-header production-header">
                    <h3>{t.production}</h3>
                  </div>

                  <article className="production-card">
                    <h4>{t.productionCutting}</h4>
                    {cuttingSummary ? (
                      <div className="summary-row">
                        <span>{t.cuttingSummary}</span>
                        <strong>
                          {cuttingSummary.total_parts} {t.details} / {cuttingSummary.total_area_m2} {t.cuttingArea} / {cuttingSummary.total_cut_length_m} {t.cuttingLength} / {cuttingSummary.total_edge_length_m} {t.cuttingEdge}
                        </strong>
                      </div>
                    ) : null}

                    {cuttingItems.length > 0 ? (
                      <table className="cutting-table">
                        <thead>
                          <tr>
                            <th>{t.cuttingExportCode}</th>
                            <th>{t.details}</th>
                            <th>{t.cuttingSize}</th>
                            <th>{t.cuttingGrain}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {cuttingItems.map((item) => (
                            <tr
                              className={
                                selectedPartDetail?.part?.export_code === item.export_code
                                  ? "selected"
                                  : ""
                              }
                              key={item.export_code}
                              onClick={() => handleSelectCuttingPart(item.export_code)}
                            >
                              <td>{item.export_code}</td>
                              <td>{item.part_name}</td>
                              <td>{item.width} x {item.height}</td>
                              <td>{item.grain_direction || t.notSet}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p>{t.noCuttingItems}</p>
                    )}
                  </article>

                  {selectedPartDetail ? (
                    <article className="production-card part-detail-panel">
                      <h4>{t.productionPartViewer}</h4>
                      <strong className="part-title">
                        {selectedPartDetail.part.export_code} / {selectedPartDetail.part.part_name}
                      </strong>
                      <PartPreview detail={selectedPartDetail} />

                      <div className="part-operation-tables">
                        <section>
                          <h5>{t.productionHoles} {selectedPartDetail.holes.length}</h5>
                          <table>
                            <thead>
                              <tr>
                                <th>#</th>
                                <th>{t.side}</th>
                                <th>X</th>
                                <th>Y</th>
                                <th>{t.depth}</th>
                                <th>D</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedPartDetail.holes.map((hole) => (
                                <tr key={hole.number}>
                                  <td>{hole.number}</td>
                                  <td>{hole.side}</td>
                                  <td>{hole.x}</td>
                                  <td>{hole.y}</td>
                                  <td>{hole.depth}</td>
                                  <td>{hole.diameter}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </section>

                        <section>
                          <h5>{t.productionGrooves} {selectedPartDetail.grooves.length}</h5>
                          <table>
                            <thead>
                              <tr>
                                <th>#</th>
                                <th>{t.side}</th>
                                <th>X</th>
                                <th>Y</th>
                                <th>{t.cuttingLength}</th>
                                <th>{t.depth}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedPartDetail.grooves.map((groove) => (
                                <tr key={groove.number}>
                                  <td>{groove.number}</td>
                                  <td>{groove.side}</td>
                                  <td>{groove.x}</td>
                                  <td>{groove.y}</td>
                                  <td>{groove.length}</td>
                                  <td>{groove.depth}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </section>

                        <section>
                          <h5>{t.productionQuarters} {selectedPartDetail.quarters.length}</h5>
                          <table>
                            <thead>
                              <tr>
                                <th>#</th>
                                <th>{t.side}</th>
                                <th>{t.cuttingLength}</th>
                                <th>{t.cuttingSize}</th>
                                <th>{t.depth}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {selectedPartDetail.quarters.map((quarter) => (
                                <tr key={quarter.number}>
                                  <td>{quarter.number}</td>
                                  <td>{quarter.side}</td>
                                  <td>{quarter.length}</td>
                                  <td>{quarter.width}</td>
                                  <td>{quarter.depth}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </section>
                      </div>
                    </article>
                  ) : null}
                </section>

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
        ) : activeView === "createProject" ? (
          <section className="table-panel full-panel create-project-panel">
            <form
              className="create-project-form standalone-create-project-form"
              onSubmit={handleCreateProject}
            >
              <label>
                {t.projectName}
                <input
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      projectName: event.target.value,
                    })
                  }
                  type="text"
                  value={newProjectForm.projectName}
                />
              </label>
              <label>
                {t.projectType}
                <select
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      projectType: event.target.value,
                    })
                  }
                  value={newProjectForm.projectType}
                >
                  {specificationCatalog.project_types.map((projectType) => (
                    <option key={projectType} value={projectType}>
                      {formatCatalogLabel(projectType, t)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.client}
                <input
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      clientName: event.target.value,
                    })
                  }
                  type="text"
                  value={newProjectForm.clientName}
                />
              </label>
              <label>
                {t.room}
                <input
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      roomName: event.target.value,
                    })
                  }
                  type="text"
                  value={newProjectForm.roomName}
                />
              </label>
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
              <label>
                {t.facadeMaterial}
                <input
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      facadeMaterial: event.target.value,
                    })
                  }
                  type="text"
                  value={newProjectForm.facadeMaterial}
                />
              </label>
              <label>
                {t.insideMaterial}
                <input
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      insideMaterial: event.target.value,
                    })
                  }
                  type="text"
                  value={newProjectForm.insideMaterial}
                />
              </label>
              <label>
                {t.edgeBanding}
                <select
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      edgeBanding: event.target.value,
                    })
                  }
                  value={newProjectForm.edgeBanding}
                >
                  <option value="">{t.notSet}</option>
                  {specificationCatalog.edge_bandings.map((edgeBanding) => (
                    <option key={edgeBanding} value={edgeBanding}>
                      {edgeBanding}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.materialThickness}
                <select
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      materialThickness: event.target.value,
                    })
                  }
                  value={newProjectForm.materialThickness}
                >
                  {specificationCatalog.material_thicknesses.map(
                    (thickness) => (
                      <option key={thickness} value={thickness}>
                        {thickness}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                {t.slideType}
                <select
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      slideType: event.target.value,
                    })
                  }
                  value={newProjectForm.slideType}
                >
                  {specificationCatalog.slide_types.map((slideType) => (
                    <option key={slideType} value={slideType}>
                      {slideType}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.bottomType}
                <select
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      bottomType: event.target.value,
                    })
                  }
                  value={newProjectForm.bottomType}
                >
                  {specificationCatalog.bottom_types.map((bottomType) => (
                    <option key={bottomType} value={bottomType}>
                      {bottomType}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.handleType}
                <input
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      handleType: event.target.value,
                    })
                  }
                  type="text"
                  value={newProjectForm.handleType}
                />
              </label>
              <label>
                {t.handlePosition}
                <select
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      handlePosition: event.target.value,
                    })
                  }
                  value={newProjectForm.handlePosition}
                >
                  <option value="">{t.notSet}</option>
                  {specificationCatalog.handle_positions.map(
                    (handlePosition) => (
                      <option key={handlePosition} value={handlePosition}>
                        {formatCatalogLabel(handlePosition, t)}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label className="wide-field">
                {t.notes}
                <input
                  onChange={(event) =>
                    setNewProjectForm({
                      ...newProjectForm,
                      notes: event.target.value,
                    })
                  }
                  type="text"
                  value={newProjectForm.notes}
                />
              </label>
              <button
                className="primary-button wide-button"
                disabled={loading}
                type="submit"
              >
                <Plus size={18} />
                {t.createProject}
              </button>
            </form>
          </section>
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
        ) : activeView === "catalog" ? (
          <section className="table-panel full-panel">
            <form className="catalog-form" onSubmit={handleCreateCatalogItem}>
              <label>
                {t.catalogCategory}
                <select
                  onChange={(event) =>
                    setNewCatalogItemForm({
                      ...newCatalogItemForm,
                      category: event.target.value,
                    })
                  }
                  value={newCatalogItemForm.category}
                >
                  {CATALOG_CATEGORIES.map((category) => (
                    <option key={category} value={category}>
                      {formatCatalogLabel(category, t)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.catalogItemValue}
                <input
                  onChange={(event) =>
                    setNewCatalogItemForm({
                      ...newCatalogItemForm,
                      value: event.target.value,
                    })
                  }
                  required
                  type="text"
                  value={newCatalogItemForm.value}
                />
              </label>
              <label>
                {t.catalogSortOrder}
                <input
                  onChange={(event) =>
                    setNewCatalogItemForm({
                      ...newCatalogItemForm,
                      sortOrder: event.target.value,
                    })
                  }
                  type="number"
                  value={newCatalogItemForm.sortOrder}
                />
              </label>
              <button
                className="primary-button"
                disabled={loading}
                type="submit"
              >
                <Plus size={18} />
                {t.create}
              </button>
            </form>
            <table>
              <thead>
                <tr>
                  <th>{t.catalogCategory}</th>
                  <th>{t.catalogItemValue}</th>
                  <th>{t.catalogSortOrder}</th>
                  <th>{t.status}</th>
                  <th>{t.action}</th>
                </tr>
              </thead>
              <tbody>
                {catalogItems.map((item) => (
                  <tr key={item.id}>
                    <td>{formatCatalogLabel(item.category, t)}</td>
                    <td>
                      <input
                        onChange={(event) =>
                          setCatalogItems(
                            catalogItems.map((catalogItem) =>
                              catalogItem.id === item.id
                                ? {
                                    ...catalogItem,
                                    value: event.target.value,
                                  }
                                : catalogItem,
                            ),
                          )
                        }
                        type="text"
                        value={item.value}
                      />
                    </td>
                    <td>
                      <input
                        onChange={(event) =>
                          setCatalogItems(
                            catalogItems.map((catalogItem) =>
                              catalogItem.id === item.id
                                ? {
                                    ...catalogItem,
                                    sort_order: event.target.value,
                                  }
                                : catalogItem,
                            ),
                          )
                        }
                        type="number"
                        value={item.sort_order}
                      />
                    </td>
                    <td>{item.is_active ? t.active : t.inactive}</td>
                    <td>
                      <div className="catalog-actions">
                        <label className="toggle-label">
                          <input
                            checked={item.is_active}
                            disabled={loading}
                            onChange={(event) =>
                              handleCatalogItemActiveChange(
                                item,
                                event.target.checked,
                              )
                            }
                            type="checkbox"
                          />
                          {t.enabled}
                        </label>
                        <button
                          className="ghost-button"
                          disabled={loading}
                          onClick={() =>
                            handleCatalogItemUpdate(
                              item,
                              item.value,
                              item.sort_order,
                            )
                          }
                          type="button"
                        >
                          <Save size={16} />
                          {t.save}
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
