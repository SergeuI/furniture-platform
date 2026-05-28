import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Eye,
  LogOut,
  Plus,
  RefreshCw,
  Save,
  Search,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  generateProject,
  getCurrentUser,
  getProject,
  getProjectBom,
  getProjectCutting,
  getSpecificationCatalog,
  listProjects,
  login,
} from "./api";

const TOKEN_STORAGE_KEY = "furniture_app_token";
const LANGUAGE_STORAGE_KEY = "furniture_app_language";
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
  only_mine: false,
};

const DEFAULT_SPECIFICATION_CATALOG = {
  project_types: ["dresser", "wardrobe", "cabinet", "kitchen", "drawer_unit"],
  slide_types: ["tandem", "movento", "telescopic"],
  bottom_types: ["hdf", "hdf_3", "dsp", "dsp_18"],
  material_thicknesses: [16, 18, 19],
  edge_bandings: ["abs_0_5", "abs_1", "abs_2", "pvc_0_5", "pvc_1", "pvc_2"],
  handle_positions: ["top", "center", "bottom", "left", "right", "integrated"],
};

const TRANSLATIONS = {
  en: {
    all: "All",
    app: "App",
    bottomType: "Bottom type",
    bomCategory: "Category",
    bomEdgeBanding: "Edge",
    bomMaterial: "Material",
    bomNotes: "Notes",
    bomPartName: "Part",
    bomQuantity: "Qty",
    bomThickness: "Thickness",
    cabinet: "Cabinet",
    center: "Center",
    client: "Client",
    createProject: "Create project",
    created: "Created",
    cuttingArea: "Area, m2",
    cuttingEdge: "Edge, m",
    cuttingExportCode: "Code",
    cuttingGrain: "Grain",
    cuttingLength: "Cut, m",
    cuttingSize: "Size",
    cuttingSummary: "Summary",
    depth: "Depth",
    dresser: "Dresser",
    drawers: "Drawers",
    drawerUnit: "Drawer unit",
    edgeBanding: "Edge banding",
    email: "Email",
    facadeMaterial: "Facade material",
    furniturePlatform: "Furniture Platform",
    fittings: "Fittings",
    general: "General",
    handlePosition: "Handle position",
    handleType: "Handle type",
    height: "Height",
    insideMaterial: "Inside material",
    integrated: "Integrated",
    kitchen: "Kitchen",
    left: "Left",
    loginFailed: "Login failed",
    logout: "Logout",
    materialThickness: "Thickness",
    materials: "Materials",
    newProject: "New project",
    noBomItems: "No BOM items yet.",
    noCuttingItems: "No cutting items yet.",
    notes: "Notes",
    notSet: "Not set",
    of: "of",
    onlyMine: "Only mine",
    password: "Password",
    projectCreated: "Project created",
    projectDetails: "Project details",
    projectName: "Project name",
    projects: "Projects",
    projectType: "Project type",
    production: "Production",
    productionBom: "BOM preview",
    productionCutting: "Cutting list preview",
    productionDrilling: "Drilling preview",
    productionPlaceholder: "Production outputs will appear here after cutting and drilling APIs are connected.",
    right: "Right",
    room: "Room",
    saveProject: "Save project",
    searchProjects: "Search projects",
    sections: "Sections",
    selectProject: "Select a project",
    signIn: "Sign in",
    slideType: "Slide type",
    top: "Top",
    unableToCreateProject: "Unable to create project",
    unableToLoadBom: "Unable to load BOM",
    unableToLoadCutting: "Unable to load cutting list",
    unableToLoadProjects: "Unable to load projects",
    updated: "Updated",
    validation: "Validation",
    validationReady: "Project data passed API validation and catalog checks.",
    view: "View",
    wardrobe: "Wardrobe",
    width: "Width",
  },
  uk: {
    all: "Всі",
    app: "Застосунок",
    bottomType: "Тип дна",
    bomCategory: "Категорія",
    bomEdgeBanding: "Крайка",
    bomMaterial: "Матеріал",
    bomNotes: "Нотатки",
    bomPartName: "Деталь",
    bomQuantity: "К-сть",
    bomThickness: "Товщина",
    cabinet: "Тумба",
    center: "По центру",
    client: "Клієнт",
    createProject: "Створити проект",
    created: "Створено",
    cuttingArea: "Площа, м2",
    cuttingEdge: "Крайка, м",
    cuttingExportCode: "Код",
    cuttingGrain: "Волокно",
    cuttingLength: "Різ, м",
    cuttingSize: "Розмір",
    cuttingSummary: "Підсумок",
    depth: "Глибина",
    dresser: "Комод",
    drawers: "Шухляди",
    drawerUnit: "Блок шухляд",
    edgeBanding: "Крайка",
    email: "Email",
    facadeMaterial: "Матеріал фасаду",
    furniturePlatform: "Furniture Platform",
    fittings: "Фурнітура",
    general: "Загальне",
    handlePosition: "Позиція ручки",
    handleType: "Тип ручки",
    height: "Висота",
    insideMaterial: "Матеріал корпусу",
    integrated: "Інтегрована",
    kitchen: "Кухня",
    left: "Зліва",
    loginFailed: "Не вдалося увійти",
    logout: "Вийти",
    materialThickness: "Товщина",
    materials: "Матеріали",
    newProject: "Новий проект",
    noBomItems: "BOM ще порожній.",
    noCuttingItems: "Карта розкрою ще порожня.",
    notes: "Нотатки",
    notSet: "Не вказано",
    of: "з",
    onlyMine: "Тільки мої",
    password: "Пароль",
    projectCreated: "Проект створено",
    projectDetails: "Деталі проекту",
    projectName: "Назва проекту",
    projects: "Проекти",
    projectType: "Тип проекту",
    production: "Виробництво",
    productionBom: "BOM перегляд",
    productionCutting: "Карта розкрою",
    productionDrilling: "Свердління",
    productionPlaceholder: "Виробничі результати зʼявляться тут після підключення розкрою і свердління.",
    right: "Справа",
    room: "Кімната",
    saveProject: "Зберегти проект",
    searchProjects: "Пошук проектів",
    sections: "Секції",
    selectProject: "Виберіть проект",
    signIn: "Увійти",
    slideType: "Тип направляючих",
    top: "Зверху",
    unableToCreateProject: "Не вдалося створити проект",
    unableToLoadBom: "Не вдалося завантажити BOM",
    unableToLoadCutting: "Не вдалося завантажити карту розкрою",
    unableToLoadProjects: "Не вдалося завантажити проекти",
    updated: "Оновлено",
    validation: "Валідація",
    validationReady: "Дані проекту пройшли API-валідацію і перевірку довідників.",
    view: "Перегляд",
    wardrobe: "Шафа",
    width: "Ширина",
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
      slide_type: form.slideType || null,
      bottom_type: form.bottomType || null,
      handle_type: form.handleType || null,
      handle_position: form.handlePosition || null,
    },
  };
}

function formatCatalogLabel(value, t) {
  if (!value) {
    return t.notSet;
  }

  return t[value] || value;
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

function formatDrawers(drawers, t) {
  if (!Array.isArray(drawers) || drawers.length === 0) {
    return t.notSet;
  }

  return drawers.join(", ");
}

export default function App() {
  const [language, setLanguage] = useState(
    () => localStorage.getItem(LANGUAGE_STORAGE_KEY) || "uk",
  );
  const [token, setToken] = useState(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) || "",
  );
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [bomItems, setBomItems] = useState([]);
  const [cuttingItems, setCuttingItems] = useState([]);
  const [cuttingSummary, setCuttingSummary] = useState(null);
  const [projectForm, setProjectForm] = useState(DEFAULT_PROJECT_FORM);
  const [projectFilters, setProjectFilters] = useState(DEFAULT_PROJECT_FILTERS);
  const [specificationCatalog, setSpecificationCatalog] = useState(
    DEFAULT_SPECIFICATION_CATALOG,
  );
  const [activeView, setActiveView] = useState("projects");
  const [activeProjectTab, setActiveProjectTab] = useState("general");
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const t = TRANSLATIONS[language] || TRANSLATIONS.en;
  const canGoBack = offset > 0;
  const canGoForward = offset + PAGE_SIZE < total;

  const pageLabel = useMemo(() => {
    if (total === 0) {
      return "0 of 0";
    }

    return `${offset + 1}-${Math.min(offset + PAGE_SIZE, total)} ${t.of} ${total}`;
  }, [offset, total, t]);

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

  async function loadProject(projectId) {
    const [result, bomResult, cuttingResult] = await Promise.all([
      getProject(token, projectId),
      getProjectBom(token, projectId),
      getProjectCutting(token, projectId),
    ]);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadProjects);
      return;
    }

    setSelectedProject(result.project);
    setBomItems(bomResult.success ? bomResult.items : []);
    setCuttingItems(cuttingResult.success ? cuttingResult.items : []);
    setCuttingSummary(cuttingResult.success ? cuttingResult.summary : null);
    if (!bomResult.success) {
      setStatus(bomResult.error || t.unableToLoadBom);
    } else if (!cuttingResult.success) {
      setStatus(cuttingResult.error || t.unableToLoadCutting);
    } else {
      setStatus("");
    }
    setActiveProjectTab("general");
    setActiveView("details");
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
    setSelectedProject(null);
    setBomItems([]);
    setCuttingItems([]);
    setCuttingSummary(null);
    setActiveProjectTab("general");
    setStatus("");
  }

  async function handleApplyFilters(event) {
    event.preventDefault();
    await loadProjects(token, 0, projectFilters);
  }

  async function handleCreateProject(event) {
    event.preventDefault();
    setLoading(true);
    const result = await generateProject(
      token,
      buildProjectPayload(projectForm),
    );
    setLoading(false);

    if (!result.success) {
      setStatus(
        result.errors?.join(", ") || result.error || t.unableToCreateProject,
      );
      return;
    }

    const projectId = result.result?.project_id;
    setProjectForm(DEFAULT_PROJECT_FORM);
    setStatus(t.projectCreated);
    setActiveView("projects");
    await loadProjects(token, 0);

    if (projectId) {
      await loadProject(projectId);
    }
  }

  useEffect(() => {
    if (!token) {
      return;
    }

    loadUser(token);
    loadSpecificationCatalog();
    loadProjects(token, 0);
  }, [token]);

  if (!token || !user) {
    return (
      <main className="auth-screen">
        <form className="login-panel" onSubmit={handleLogin}>
          <div>
            <p className="eyebrow">{t.furniturePlatform}</p>
            <h1>{t.app}</h1>
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
          <h1>{t.app}</h1>
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

        <nav className="nav-tabs" aria-label="Application sections">
          <button
            className={activeView === "projects" ? "active" : ""}
            onClick={() => setActiveView("projects")}
            type="button"
          >
            <ClipboardList size={18} />
            {t.projects}
          </button>
          <button
            className={activeView === "create" ? "active" : ""}
            onClick={() => setActiveView("create")}
            type="button"
          >
            <Plus size={18} />
            {t.newProject}
          </button>
          <button
            className={activeView === "details" ? "active" : ""}
            disabled={!selectedProject}
            onClick={() => setActiveView("details")}
            type="button"
          >
            <Eye size={18} />
            {t.view}
          </button>
        </nav>

        <button className="ghost-button logout-button" onClick={handleLogout} type="button">
          <LogOut size={18} />
          {t.logout}
        </button>
      </aside>

      <section className="workspace">
        <header className="toolbar">
          <div>
            <h2>
              {activeView === "create"
                ? t.createProject
                : activeView === "details"
                  ? t.projectDetails
                  : t.projects}
            </h2>
            <p>{activeView === "projects" ? pageLabel : t.furniturePlatform}</p>
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
            ) : null}
          </div>
        </header>

        {status ? <p className="status">{status}</p> : null}

        {activeView === "projects" ? (
          <section className="table-panel">
            <form className="filter-form" onSubmit={handleApplyFilters}>
              <label>
                {t.searchProjects}
                <input
                  onChange={(event) =>
                    setProjectFilters({
                      ...projectFilters,
                      search: event.target.value,
                    })
                  }
                  type="text"
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
              <label className="toggle-label">
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
              <button className="primary-button filter-button" disabled={loading} type="submit">
                <Search size={18} />
                {t.searchProjects}
              </button>
            </form>

            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>{t.projectType}</th>
                  <th>{t.width} x {t.height} x {t.depth}</th>
                  <th>{t.drawers}</th>
                  <th>{t.updated}</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => (
                  <tr
                    className={selectedProject?.id === project.id ? "selected" : ""}
                    key={project.id}
                    onClick={() => loadProject(project.id)}
                  >
                    <td>{project.id}</td>
                    <td>{formatCatalogLabel(project.project_type, t)}</td>
                    <td>
                      {project.width} x {project.height} x {project.depth}
                    </td>
                    <td>{formatDrawers(project.drawers, t)}</td>
                    <td>{formatDateTime(project.updated_at, t)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : activeView === "create" ? (
          <section className="table-panel create-panel">
            <form className="project-form" onSubmit={handleCreateProject}>
              <label>
                {t.projectName}
                <input
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      projectName: event.target.value,
                    })
                  }
                  type="text"
                  value={projectForm.projectName}
                />
              </label>
              <label>
                {t.projectType}
                <select
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      projectType: event.target.value,
                    })
                  }
                  value={projectForm.projectType}
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
                    setProjectForm({
                      ...projectForm,
                      clientName: event.target.value,
                    })
                  }
                  type="text"
                  value={projectForm.clientName}
                />
              </label>
              <label>
                {t.room}
                <input
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      roomName: event.target.value,
                    })
                  }
                  type="text"
                  value={projectForm.roomName}
                />
              </label>
              <label>
                {t.width}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      width: event.target.value,
                    })
                  }
                  required
                  type="number"
                  value={projectForm.width}
                />
              </label>
              <label>
                {t.height}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      height: event.target.value,
                    })
                  }
                  required
                  type="number"
                  value={projectForm.height}
                />
              </label>
              <label>
                {t.depth}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      depth: event.target.value,
                    })
                  }
                  required
                  type="number"
                  value={projectForm.depth}
                />
              </label>
              <label>
                {t.sections}
                <input
                  min="1"
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      sections: event.target.value,
                    })
                  }
                  required
                  type="number"
                  value={projectForm.sections}
                />
              </label>
              <label>
                {t.drawers}
                <input
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      drawers: event.target.value,
                    })
                  }
                  placeholder="1, 2"
                  type="text"
                  value={projectForm.drawers}
                />
              </label>
              <label>
                {t.edgeBanding}
                <select
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      edgeBanding: event.target.value,
                    })
                  }
                  value={projectForm.edgeBanding}
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
                    setProjectForm({
                      ...projectForm,
                      materialThickness: event.target.value,
                    })
                  }
                  value={projectForm.materialThickness}
                >
                  {specificationCatalog.material_thicknesses.map((thickness) => (
                    <option key={thickness} value={thickness}>
                      {thickness}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.slideType}
                <select
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      slideType: event.target.value,
                    })
                  }
                  value={projectForm.slideType}
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
                    setProjectForm({
                      ...projectForm,
                      bottomType: event.target.value,
                    })
                  }
                  value={projectForm.bottomType}
                >
                  {specificationCatalog.bottom_types.map((bottomType) => (
                    <option key={bottomType} value={bottomType}>
                      {bottomType}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.handlePosition}
                <select
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      handlePosition: event.target.value,
                    })
                  }
                  value={projectForm.handlePosition}
                >
                  <option value="">{t.notSet}</option>
                  {specificationCatalog.handle_positions.map((handlePosition) => (
                    <option key={handlePosition} value={handlePosition}>
                      {formatCatalogLabel(handlePosition, t)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.facadeMaterial}
                <input
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      facadeMaterial: event.target.value,
                    })
                  }
                  type="text"
                  value={projectForm.facadeMaterial}
                />
              </label>
              <label>
                {t.insideMaterial}
                <input
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      insideMaterial: event.target.value,
                    })
                  }
                  type="text"
                  value={projectForm.insideMaterial}
                />
              </label>
              <label>
                {t.handleType}
                <input
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      handleType: event.target.value,
                    })
                  }
                  type="text"
                  value={projectForm.handleType}
                />
              </label>
              <label className="wide-field">
                {t.notes}
                <input
                  onChange={(event) =>
                    setProjectForm({
                      ...projectForm,
                      notes: event.target.value,
                    })
                  }
                  type="text"
                  value={projectForm.notes}
                />
              </label>
              <button className="primary-button wide-field" disabled={loading} type="submit">
                <Save size={18} />
                {t.saveProject}
              </button>
            </form>
          </section>
        ) : (
          <section className="detail-panel">
            {selectedProject ? (
              <>
                <header className="detail-header">
                  <div>
                    <p className="eyebrow">{t.projectDetails}</p>
                    <h2>{selectedProject.id}</h2>
                  </div>
                  <button
                    className="ghost-button"
                    onClick={() => setActiveView("projects")}
                    type="button"
                  >
                    {t.projects}
                  </button>
                </header>

                <div className="detail-tabs" role="tablist">
                  <button
                    className={activeProjectTab === "general" ? "active" : ""}
                    onClick={() => setActiveProjectTab("general")}
                    type="button"
                  >
                    {t.general}
                  </button>
                  <button
                    className={activeProjectTab === "materials" ? "active" : ""}
                    onClick={() => setActiveProjectTab("materials")}
                    type="button"
                  >
                    {t.materials}
                  </button>
                  <button
                    className={activeProjectTab === "fittings" ? "active" : ""}
                    onClick={() => setActiveProjectTab("fittings")}
                    type="button"
                  >
                    {t.fittings}
                  </button>
                  <button
                    className={activeProjectTab === "production" ? "active" : ""}
                    onClick={() => setActiveProjectTab("production")}
                    type="button"
                  >
                    {t.production}
                  </button>
                  <button
                    className={activeProjectTab === "validation" ? "active" : ""}
                    onClick={() => setActiveProjectTab("validation")}
                    type="button"
                  >
                    {t.validation}
                  </button>
                </div>

                {activeProjectTab === "general" ? (
                  <div className="detail-grid">
                    <span>{t.projectName}</span>
                    <strong>{selectedProject.project_name || t.notSet}</strong>
                    <span>{t.projectType}</span>
                    <strong>{formatCatalogLabel(selectedProject.project_type, t)}</strong>
                    <span>{t.client}</span>
                    <strong>{selectedProject.client_name || t.notSet}</strong>
                    <span>{t.room}</span>
                    <strong>{selectedProject.room_name || t.notSet}</strong>
                    <span>{t.width} x {t.height} x {t.depth}</span>
                    <strong>
                      {selectedProject.width} x {selectedProject.height} x {selectedProject.depth}
                    </strong>
                    <span>{t.sections}</span>
                    <strong>{selectedProject.sections}</strong>
                    <span>{t.drawers}</span>
                    <strong>{formatDrawers(selectedProject.drawers, t)}</strong>
                    <span>{t.created}</span>
                    <strong>{formatDateTime(selectedProject.created_at, t)}</strong>
                    <span>{t.updated}</span>
                    <strong>{formatDateTime(selectedProject.updated_at, t)}</strong>
                  </div>
                ) : null}

                {activeProjectTab === "materials" ? (
                  <div className="detail-grid">
                    <span>{t.facadeMaterial}</span>
                    <strong>{selectedProject.facade_material || t.notSet}</strong>
                    <span>{t.insideMaterial}</span>
                    <strong>{selectedProject.inside_material || t.notSet}</strong>
                    <span>{t.edgeBanding}</span>
                    <strong>{selectedProject.edge_banding || t.notSet}</strong>
                    <span>{t.materialThickness}</span>
                    <strong>{selectedProject.material_thickness || t.notSet}</strong>
                  </div>
                ) : null}

                {activeProjectTab === "fittings" ? (
                  <div className="detail-grid">
                    <span>{t.slideType}</span>
                    <strong>{selectedProject.slide_type || t.notSet}</strong>
                    <span>{t.bottomType}</span>
                    <strong>{selectedProject.bottom_type || t.notSet}</strong>
                    <span>{t.handleType}</span>
                    <strong>{selectedProject.handle_type || t.notSet}</strong>
                    <span>{t.handlePosition}</span>
                    <strong>{formatCatalogLabel(selectedProject.handle_position, t)}</strong>
                  </div>
                ) : null}

                {activeProjectTab === "production" ? (
                  <div className="production-grid">
                    <article className="wide-production-section">
                      <h3>{t.productionBom}</h3>
                      {bomItems.length > 0 ? (
                        <table className="bom-table">
                          <thead>
                            <tr>
                              <th>{t.bomPartName}</th>
                              <th>{t.bomCategory}</th>
                              <th>{t.bomQuantity}</th>
                              <th>{t.bomMaterial}</th>
                              <th>{t.bomThickness}</th>
                              <th>{t.bomEdgeBanding}</th>
                              <th>{t.bomNotes}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {bomItems.map((item) => (
                              <tr key={`${item.category}-${item.part_name}`}>
                                <td>{item.part_name}</td>
                                <td>{item.category}</td>
                                <td>{item.quantity}</td>
                                <td>{item.material || t.notSet}</td>
                                <td>{item.thickness || t.notSet}</td>
                                <td>{item.edge_banding || t.notSet}</td>
                                <td>{item.notes || t.notSet}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <p>{t.noBomItems}</p>
                      )}
                    </article>
                    <article className="wide-production-section">
                      <h3>{t.productionCutting}</h3>
                      {cuttingSummary ? (
                        <div className="summary-row">
                          <span>{t.cuttingSummary}</span>
                          <strong>
                            {cuttingSummary.total_parts} {t.bomQuantity} / {cuttingSummary.total_area_m2} {t.cuttingArea} / {cuttingSummary.total_cut_length_m} {t.cuttingLength} / {cuttingSummary.total_edge_length_m} {t.cuttingEdge}
                          </strong>
                        </div>
                      ) : null}
                      {cuttingItems.length > 0 ? (
                        <table className="cutting-table">
                          <thead>
                            <tr>
                              <th>{t.cuttingExportCode}</th>
                              <th>{t.bomPartName}</th>
                              <th>{t.cuttingSize}</th>
                              <th>{t.bomQuantity}</th>
                              <th>{t.bomMaterial}</th>
                              <th>{t.bomThickness}</th>
                              <th>{t.bomEdgeBanding}</th>
                              <th>{t.cuttingGrain}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {cuttingItems.map((item) => (
                              <tr key={item.export_code}>
                                <td>{item.export_code}</td>
                                <td>{item.part_name}</td>
                                <td>{item.width} x {item.height}</td>
                                <td>{item.quantity}</td>
                                <td>{item.material || t.notSet}</td>
                                <td>{item.thickness || t.notSet}</td>
                                <td>
                                  {[item.edge_top, item.edge_bottom, item.edge_left, item.edge_right]
                                    .filter(Boolean)
                                    .join(", ") || t.notSet}
                                </td>
                                <td>{item.grain_direction || t.notSet}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <p>{t.noCuttingItems}</p>
                      )}
                    </article>
                    <article>
                      <h3>{t.productionDrilling}</h3>
                      <p>{t.productionPlaceholder}</p>
                    </article>
                  </div>
                ) : null}

                {activeProjectTab === "validation" ? (
                  <div className="validation-panel">
                    <strong>{t.validationReady}</strong>
                    <span>{t.updated}: {formatDateTime(selectedProject.updated_at, t)}</span>
                  </div>
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                <Search size={22} />
                <p>{t.selectProject}</p>
              </div>
            )}
          </section>
        )}
      </section>
    </main>
  );
}
