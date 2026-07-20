import {
  ArrowRight,
  BadgeCheck,
  Bot,
  Boxes,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  CircleAlert,
  Cpu,
  Database,
  ExternalLink,
  Layers3,
  LayoutDashboard,
  Menu,
  Package2,
  PlayCircle,
  RotateCcw,
  Download,
  Eye,
  Info,
  LogOut,
  Rocket,
  Plus,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
  Sparkles,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { Component, Fragment, Suspense, lazy, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import {
  buildTrialCountdown,
  formatTrialCountdown,
  getSubscriptionLabel,
} from "../../shared/trialStatus.js";

import {
  confirmRegistration,
  changeOwnPassword,
  confirmProjectScan,
  createMyEmailChangeRequest,
  getRegistrationTelegramStatus,
  generateProject,
  getPublicOverview,
  getCuttingExportFormats,
  getCuttingJsonExport,
  getCurrentUser,
  getProject,
  getProjectBom,
  getProjectCutting,
  getProjectPartDetail,
  getSpecificationCatalog,
  listProjectScans,
  listProjects,
  login,
  requestPasswordReset,
  scanProjectFile,
  startRegistration,
  updateMyProfile,
  updateProjectPartEdges,
  updateProjectPartMachining,
} from "./api";
const PartThreeViewer = lazy(() => import("./components/PartThreeViewer"));
const ProjectThreeViewer = lazy(() => import("./components/ProjectThreeViewer"));


const TOKEN_STORAGE_KEY = "furniture_app_token";
const LANGUAGE_STORAGE_KEY = "furniture_app_language";
const PAGE_SIZE = 20;
const ADMIN_BASE_URL = import.meta.env.VITE_ADMIN_BASE_URL || (
  import.meta.env.DEV ? "http://127.0.0.1:5173" : "/admin/"
);
const TELEGRAM_BOT_URL =
  import.meta.env.VITE_TELEGRAM_BOT_URL || "https://t.me/Mebli_calculator_bot";
const YOUTUBE_CHANNEL_URL = import.meta.env.VITE_YOUTUBE_CHANNEL_URL || "https://www.youtube.com/";
const ADMIN_TOKEN_HASH_KEY = "mproject_token";
const ADMIN_LOGOUT_HASH_KEY = "mproject_logout";
const REGISTRATION_PASSWORD_MIN_LENGTH = 8;
const REGISTRATION_EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const REGISTRATION_PHONE_PATTERN = /^\+\d{8,15}$/;


function normalizeRegistrationPhoneInput(value) {
  return String(value || "").replace(/[\s().-]+/g, "").trim();
}


function isValidRegistrationEmail(value) {
  return REGISTRATION_EMAIL_PATTERN.test(String(value || "").trim());
}


function isValidRegistrationPassword(value) {
  return String(value || "").length >= REGISTRATION_PASSWORD_MIN_LENGTH;
}


function isValidRegistrationPhone(value) {
  return REGISTRATION_PHONE_PATTERN.test(normalizeRegistrationPhoneInput(value));
}


function maskRegistrationPhone(value) {
  const normalized = normalizeRegistrationPhoneInput(value);
  if (!normalized) {
    return "";
  }

  if (normalized.length <= 5) {
    return normalized;
  }

  const visiblePrefix = normalized.slice(0, 4);
  const visibleSuffix = normalized.slice(-3);
  const hiddenCount = Math.max(normalized.length - visiblePrefix.length - visibleSuffix.length, 0);

  return `${visiblePrefix}${"•".repeat(hiddenCount)}${visibleSuffix}`;
}


function normalizeRegistrationCodeInput(value) {
  return String(value || "").replace(/\D+/g, "").slice(0, 6);
}


function formatRegistrationCodeDisplay(value) {
  const normalized = normalizeRegistrationCodeInput(value);
  if (normalized.length <= 3) {
    return normalized;
  }

  return `${normalized.slice(0, 3)} ${normalized.slice(3)}`;
}

const TARIFF_CONTENT = {
  uk: {
    eyebrow: "Тарифи MP Furniture Calculator",
    title: "Оберіть формат роботи",
    description:
      "Почніть безкоштовно, перевірте AI у Trial або підключіть інструменти для щоденної роботи й виробництва.",
    recommended: "Рекомендований",
    comparisonTitle: "Детальне порівняння",
    comparisonDescription: "Усі ключові можливості та ліміти в одній таблиці.",
    feature: "Можливість",
    included: "Доступно",
    unavailable: "Недоступно",
    plans: [
      {
        id: "trial",
        name: "Trial",
        price: "Безкоштовно",
        period: "14 днів або 20 AI-операцій",
        audience: "Для знайомства з повною системою",
        summary: "Тимчасовий повний доступ, щоб спроєктувати реальний виріб і перевірити автоматизацію.",
        cta: "Спробувати Trial",
      },
      {
        id: "free",
        name: "Free",
        price: "0 грн",
        period: "Безстроково",
        audience: "Для базових прорахунків",
        summary: "Ручне проєктування, креслення та кошторис для невеликої кількості активних проєктів.",
        cta: "Почати безкоштовно",
      },
      {
        id: "pro",
        name: "PRO",
        price: "999 грн",
        period: "на місяць",
        audience: "Для конструкторів і майстрів",
        summary: "AI-розпізнавання, автоматичний розкрій, виробничі експорти та більше робочих проєктів.",
        cta: "Обрати PRO",
        recommended: true,
      },
      {
        id: "business",
        name: "Business",
        price: "2 999 грн",
        period: "на місяць",
        audience: "Для меблевих виробництв",
        summary: "Безлімітна автоматизація, командна робота, власні бази, API та персональна підтримка.",
        cta: "Обрати Business",
      },
    ],
    groups: [
      {
        title: "Проєктування меблів",
        rows: [
          ["Створення меблів", true, true, true, true],
          ["Прорахунок вартості", true, true, true, true],
          ["Креслення та специфікація деталей", true, true, true, true],
          ["Крайка, присадки та фурнітура", true, true, true, true],
          ["Кількість проєктів", "Безліміт", "3", "20", "Безліміт"],
          ["Історія проєктів", "Безліміт", "30 днів", "Безліміт", "Безліміт"],
          ["Збереження шаблонів", true, false, true, true],
          ["Клонування проєктів", true, false, true, true],
        ],
      },
      {
        title: "AI та автоматизація",
        rows: [
          ["Аналіз PDF-проєктів", "У межах Trial", false, "20/міс", "Безліміт"],
          ["Розпізнавання ескізів і фото", "У межах Trial", false, "20/міс", "Безліміт"],
          ["AI-генерація меблів", "У межах Trial", false, "20/міс", "Безліміт"],
          ["Автопідбір матеріалів і фурнітури", "У межах Trial", false, "20/міс", "Безліміт"],
          ["AI-консультант", "У межах Trial", "10/міс", "100/міс", "Безліміт"],
        ],
      },
      {
        title: "Виробництво та експорт",
        rows: [
          ["Автоматичний розкрій", "У межах Trial", false, "20/міс", "Безліміт"],
          ["Експорт Viyar і Kronas", "У межах Trial", false, "20/міс", "Безліміт"],
          ["Excel і PDF-звіти", "У межах Trial", "1/міс", "20/міс", "Безліміт"],
          ["CSV-експорт", "У межах Trial", false, "20/міс", "Безліміт"],
        ],
      },
      {
        title: "Команда та власні налаштування",
        rows: [
          ["Співробітники", "До 10 у Trial", false, false, "До 10"],
          ["Ролі та загальна база проєктів", true, false, false, true],
          ["Статистика компанії та API", true, false, false, true],
          ["Власна база й ціни матеріалів", true, false, false, true],
          ["Власні ціни робіт і націнки", true, false, false, true],
          ["Власні шаблони компанії", true, false, false, true],
        ],
      },
      {
        title: "Доступ і підтримка",
        rows: [
          ["Telegram-бот", true, true, true, true],
          ["Веб-система", true, true, true, true],
          ["Пріоритетна підтримка", true, false, true, true],
          ["Персональний менеджер", false, false, false, true],
        ],
      },
    ],
  },
  en: {
    eyebrow: "MP Furniture Calculator plans",
    title: "Choose how you want to work",
    description:
      "Start free, evaluate AI with Trial, or unlock daily production and team workflows.",
    recommended: "Recommended",
    comparisonTitle: "Detailed comparison",
    comparisonDescription: "All major capabilities and limits in one table.",
    feature: "Capability",
    included: "Included",
    unavailable: "Unavailable",
    plans: [
      { id: "trial", name: "Trial", price: "Free", period: "7 days or 20 AI operations", audience: "Evaluate the full system", summary: "Temporary full access for a real project and automation test.", cta: "Try Trial" },
      { id: "free", name: "Free", price: "UAH 0", period: "No time limit", audience: "Basic calculations", summary: "Manual design, drawings, and estimates for a small project list.", cta: "Start free" },
      { id: "pro", name: "PRO", price: "UAH 999", period: "per month", audience: "Designers and makers", summary: "AI recognition, automatic cutting, production exports, and more active projects.", cta: "Choose PRO", recommended: true },
      { id: "business", name: "Business", price: "UAH 2,999", period: "per month", audience: "Furniture production teams", summary: "Unlimited automation, team workflows, own databases, API, and personal support.", cta: "Choose Business" },
    ],
    groups: [
      { title: "Furniture design", rows: [["Furniture design", true, true, true, true], ["Cost calculation", true, true, true, true], ["Part drawings and specification", true, true, true, true], ["Edging, drilling, and fittings", true, true, true, true], ["Projects", "Unlimited", "3", "20", "Unlimited"], ["Project history", "Unlimited", "30 days", "Unlimited", "Unlimited"], ["Save templates", true, false, true, true], ["Clone projects", true, false, true, true]] },
      { title: "AI and automation", rows: [["PDF project analysis", "Trial quota", false, "20/mo", "Unlimited"], ["Sketch and photo recognition", "Trial quota", false, "20/mo", "Unlimited"], ["AI furniture generation", "Trial quota", false, "20/mo", "Unlimited"], ["Automatic materials and fittings", "Trial quota", false, "20/mo", "Unlimited"], ["AI assistant", "Trial quota", "10/mo", "100/mo", "Unlimited"]] },
      { title: "Production and export", rows: [["Automatic cutting", "Trial quota", false, "20/mo", "Unlimited"], ["Viyar and Kronas export", "Trial quota", false, "20/mo", "Unlimited"], ["Excel and PDF reports", "Trial quota", "1/mo", "20/mo", "Unlimited"], ["CSV export", "Trial quota", false, "20/mo", "Unlimited"]] },
      { title: "Team and own settings", rows: [["Team members", "Up to 10 in Trial", false, false, "Up to 10"], ["Roles and shared projects", true, false, false, true], ["Company statistics and API", true, false, false, true], ["Own material database and prices", true, false, false, true], ["Own work prices and margins", true, false, false, true], ["Company templates", true, false, false, true]] },
      { title: "Access and support", rows: [["Telegram bot", true, true, true, true], ["Web system", true, true, true, true], ["Priority support", true, false, true, true], ["Personal manager", false, false, false, true]] },
    ],
  },
};

function TariffValue({ value, labels }) {
  if (value === true) {
    return <CheckCircle2 aria-label={labels.included} className="tariff-value-icon included" size={19} />;
  }
  if (value === false) {
    return <span aria-label={labels.unavailable} className="tariff-value-empty">—</span>;
  }
  return <span className="tariff-value-text">{value}</span>;
}

function buildAdminUrl(baseUrl, activeToken) {
  try {
    const url = new URL(baseUrl, window.location.origin);
    const hashParams = new URLSearchParams(url.hash.replace(/^#/, ""));
    if (activeToken) {
      hashParams.set(ADMIN_TOKEN_HASH_KEY, activeToken);
      hashParams.delete(ADMIN_LOGOUT_HASH_KEY);
    } else {
      hashParams.delete(ADMIN_TOKEN_HASH_KEY);
      hashParams.set(ADMIN_LOGOUT_HASH_KEY, "1");
    }
    url.hash = hashParams.toString();
    return url.toString();
  } catch {
    const separator = String(baseUrl).includes("#") ? "&" : "#";
    return activeToken
      ? `${baseUrl}${separator}${ADMIN_TOKEN_HASH_KEY}=${encodeURIComponent(activeToken)}`
      : `${baseUrl}${separator}${ADMIN_LOGOUT_HASH_KEY}=1`;
  }
}

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
  project_types: [
    "dresser",
    "wardrobe",
    "cabinet",
    "kitchen",
    "wall_unit",
    "bathroom_vanity",
    "bathroom_shelf",
  ],
  slide_types: ["tandem", "movento", "telescopic"],
  bottom_types: ["hdf", "hdf_3", "dsp", "dsp_18"],
  material_thicknesses: [16, 18, 19],
  edge_bandings: ["abs_0_5", "abs_1", "abs_2", "pvc_0_5", "pvc_1", "pvc_2"],
  handle_positions: ["top", "center", "bottom", "left", "right", "integrated"],
};

const PROJECT_TYPE_OPTIONS = DEFAULT_SPECIFICATION_CATALOG.project_types;

function normalizeProjectTypes(projectTypes) {
  const allowed = new Set(PROJECT_TYPE_OPTIONS);
  const incoming = Array.isArray(projectTypes)
    ? projectTypes.filter((item) => allowed.has(item))
    : [];
  return [...new Set([...PROJECT_TYPE_OPTIONS, ...incoming])];
}

const PROJECT_TEMPLATE_PRESETS = [
  {
    descriptionKey: "projectTemplateDresserDescription",
    fields: {
      projectType: "dresser",
      width: 1000,
      height: 800,
      depth: 500,
      sections: 2,
      drawers: "1, 2",
      materialThickness: 18,
      slideType: "tandem",
      bottomType: "hdf",
    },
    image: "/static/project-start/dresser.jpg",
    titleKey: "projectTemplateDresserTitle",
    visual: "dresser",
  },
  {
    descriptionKey: "projectTemplateWardrobeDescription",
    fields: {
      projectType: "wardrobe",
      width: 1200,
      height: 2200,
      depth: 600,
      sections: 3,
      drawers: "1",
      materialThickness: 18,
      slideType: "tandem",
      bottomType: "dsp_18",
    },
    image: "/static/project-start/wardrobe.jpg",
    titleKey: "projectTemplateWardrobeTitle",
    visual: "wardrobe",
  },
  {
    descriptionKey: "projectTemplateCabinetDescription",
    fields: {
      projectType: "cabinet",
      width: 600,
      height: 720,
      depth: 450,
      sections: 1,
      drawers: "",
      materialThickness: 18,
      slideType: "telescopic",
      bottomType: "hdf",
    },
    image: "/static/project-start/cabinet.jpg",
    titleKey: "projectTemplateCabinetTitle",
    visual: "cabinet",
  },
  {
    descriptionKey: "projectTemplateKitchenDescription",
    fields: {
      projectType: "kitchen",
      width: 2400,
      height: 850,
      depth: 600,
      sections: 4,
      drawers: "2, 3",
      materialThickness: 18,
      slideType: "tandem",
      bottomType: "dsp_18",
    },
    image: "/static/project-start/hero-scene.png",
    titleKey: "projectTemplateKitchenTitle",
    visual: "kitchen",
  },
  {
    descriptionKey: "projectTemplateWallUnitDescription",
    fields: {
      projectType: "wall_unit",
      width: 2200,
      height: 1800,
      depth: 450,
      sections: 3,
      drawers: "1",
      materialThickness: 18,
      slideType: "telescopic",
      bottomType: "dsp_18",
    },
    image: "/static/project-start/hero-scene.png",
    titleKey: "projectTemplateWallUnitTitle",
    visual: "wall-unit",
  },
  {
    descriptionKey: "projectTemplateBathroomVanityDescription",
    fields: {
      projectType: "bathroom_vanity",
      width: 800,
      height: 650,
      depth: 460,
      sections: 2,
      drawers: "1, 2",
      materialThickness: 18,
      slideType: "tandem",
      bottomType: "dsp_18",
    },
    image: "/static/project-start/dresser.jpg",
    titleKey: "projectTemplateBathroomVanityTitle",
    visual: "bathroom-vanity",
  },
  {
    descriptionKey: "projectTemplateBathroomShelfDescription",
    fields: {
      projectType: "bathroom_shelf",
      width: 600,
      height: 900,
      depth: 250,
      sections: 3,
      drawers: "",
      materialThickness: 18,
      slideType: "telescopic",
      bottomType: "dsp_18",
    },
    image: "/static/project-start/wardrobe.jpg",
    titleKey: "projectTemplateBathroomShelfTitle",
    visual: "bathroom-shelf",
  },
];

class ProductionViewerBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { errorMessage: "", hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    this.setState({
      errorMessage: error?.message || "Unknown production viewer error",
    });
  }

  componentDidUpdate(prevProps) {
    if (
      prevProps.selectedPartCode !== this.props.selectedPartCode ||
      prevProps.itemCount !== this.props.itemCount
    ) {
      if (this.state.hasError) {
        this.setState({ errorMessage: "", hasError: false });
      }
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="project-three-viewer-error">
          <strong>{this.props.t?.productionAssembly3d || "3D assembly"}</strong>
          <span>{this.props.t?.productionAssemblyHint || "3D preview is temporarily unavailable."}</span>
          {this.state.errorMessage ? <code>{this.state.errorMessage}</code> : null}
        </div>
      );
    }

    return this.props.children;
  }
}

function PublicStatCard({ icon: Icon, label, value }) {
  return (
    <article className="public-stat-card">
      <span className="public-stat-icon">
        <Icon size={18} />
      </span>
      <strong>{value}</strong>
      <span>{label}</span>
    </article>
  );
}

const TRANSLATIONS = {
  en: {
    all: "All",
    app: "Web system",
    brandTagline: "Furniture production platform",
    bottomType: "Bottom type",
    bottom: "Bottom",
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
    detailViewer: "Detail viewer",
    dresser: "Dresser",
    drawers: "Drawers",
    drawerUnit: "Drawer unit",
    edgeBanding: "Edge banding",
    edgeEditor: "Edge processing",
    edgeEditorDescription: "Edit edge banding for the selected production part.",
    edgeSaved: "Part edges updated",
    email: "Email",
    machiningAddGroove: "Add groove",
    machiningAddHole: "Add hole",
    machiningAddQuarter: "Add quarter",
    machiningEditor: "Machining editor",
    machiningSaved: "Part machining updated",
    exportDownloadJson: "Download JSON",
    exportFormats: "Export formats",
    exportPlanned: "Planned",
    exportReady: "Ready",
    facadeMaterial: "Facade material",
    furniturePlatform: "MProject.furniture",
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
    loginOrEmail: "Login or email",
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
    productionGrooves: "Grooves",
    productionHoles: "Holes",
    productionPartBack: "Back to production",
    productionPartWorkspace: "Detail workspace",
    productionQuarters: "Quarters",
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
    unableToLoadExports: "Unable to load exports",
    unableToLoadPart: "Unable to load part detail",
    unableToSaveEdges: "Unable to save part edges",
    unableToSaveMachining: "Unable to save part machining",
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
    app: "Веб-система",
    brandTagline: "Професійне рішення для меблевого виробництва",
    bottomType: "Тип дна",
    bottom: "Низ",
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
    detailViewer: "Карта деталі",
    dresser: "Комод",
    drawers: "Шухляди",
    drawerUnit: "Блок шухляд",
    edgeBanding: "Крайка",
    edgeEditor: "Обробка торців",
    edgeEditorDescription: "Редагування крайки для вибраної виробничої деталі.",
    edgeSaved: "Крайку деталі оновлено",
    email: "Email",
    machiningAddGroove: "Додати паз",
    machiningAddHole: "Додати отвір",
    machiningAddQuarter: "Додати чверть",
    machiningEditor: "Редактор обробки",
    machiningSaved: "Обробку деталі оновлено",
    exportDownloadJson: "Завантажити JSON",
    exportFormats: "Формати експорту",
    exportPlanned: "Заплановано",
    exportReady: "Готово",
    facadeMaterial: "Матеріал фасаду",
    furniturePlatform: "MProject.furniture",
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
    loginOrEmail: "\u041b\u043e\u0433\u0456\u043d \u0430\u0431\u043e email",
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
    productionGrooves: "Пази",
    productionHoles: "Отвори",
    productionPartBack: "Назад до виробництва",
    productionPartWorkspace: "Робоче місце деталі",
    productionQuarters: "Чверті",
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
    unableToLoadExports: "Не вдалося завантажити експорти",
    unableToLoadPart: "Не вдалося завантажити карту деталі",
    unableToSaveEdges: "Не вдалося зберегти крайку деталі",
    unableToSaveMachining: "Не вдалося зберегти обробку деталі",
    unableToLoadProjects: "Не вдалося завантажити проекти",
    updated: "Оновлено",
    validation: "Валідація",
    validationReady: "Дані проекту пройшли API-валідацію і перевірку довідників.",
    view: "Перегляд",
    wardrobe: "Шафа",
    width: "Ширина",
  },
};

Object.assign(TRANSLATIONS.en, {
  registrationBack: "Back",
  registrationCode: "Verification code",
  registrationCodeAutofilled: "Local test code created and inserted automatically",
  registrationCodeCopied: "Confirmation code copied",
  registrationCodeCreated: "Code created. Continue with confirmation.",
  registrationCodeHint: "Enter the 6-digit code.",
  registrationCompleteFree: "Registration complete. Active plan: Free.",
  registrationCompleteTrial: "Registration complete. Full access activated for 7 days.",
  registrationContinue: "Continue",
  registrationEmailInvalid: "Enter a valid email address.",
  registrationLocalCodeHint: "This block is available only in local test mode.",
  registrationLocalCodeTitle: "Local test code",
  registrationName: "Name",
  registrationPasswordTooShort: "Password must be at least 8 characters long.",
  registrationPhone: "Phone number",
  registrationPhoneInvalid: "Enter a phone number in international format, for example +380XXXXXXXXX.",
  registrationRequestCode: "Get code",
  registrationTelegramConfirm: "Confirm via Telegram",
  registrationTelegramCreated: "Telegram confirmation link created. Open Telegram to continue.",
  registrationTelegramDescription: "Open Telegram and confirm the phone number with the button below.",
  registrationTelegramExpired: "Telegram confirmation expired. Start registration again.",
  registrationTelegramInstruction: "Confirm your phone number through Telegram to finish registration.",
  registrationTelegramOpen: "Open Telegram",
  registrationTelegramTitle: "Telegram confirmation",
  registrationTelegramWaiting: "Waiting for Telegram confirmation...",
  registrationStepOne: "Step 1 of 3",
  registrationStepTwo: "Step 2 of 3",
  registrationStepThree: "Step 3 of 3",
  registrationUseLocalCode: "Use code",
  registrationVerifyPhone: "Verify code",
});

Object.assign(TRANSLATIONS.uk, {
  registrationBack: "Назад",
  registrationCode: "Код підтвердження",
  registrationCodeAutofilled: "Локальний тестовий код створено та підставлено автоматично",
  registrationCodeCopied: "Код підтвердження скопійовано",
  registrationCodeCreated: "Код створено. Переходьте до підтвердження.",
  registrationCodeHint: "Введіть 6-значний код.",
  registrationCompleteFree: "Реєстрацію завершено. Активовано тариф Free.",
  registrationCompleteTrial: "Реєстрацію завершено. Повний доступ активовано на 7 днів.",
  registrationContinue: "Продовжити",
  registrationEmailInvalid: "Введіть коректний email.",
  registrationLocalCodeHint: "Цей блок доступний тільки в локальному тестовому режимі.",
  registrationLocalCodeTitle: "Локальний тестовий код",
  registrationName: "Ім'я",
  registrationPasswordTooShort: "Пароль має містити щонайменше 8 символів.",
  registrationPhone: "Номер телефону",
  registrationPhoneInvalid: "Введіть номер у міжнародному форматі, наприклад +380XXXXXXXXX.",
  registrationRequestCode: "Отримати код",
  registrationTelegramConfirm: "Підтвердити через Telegram",
  registrationTelegramCreated: "Додано посилання для підтвердження через Telegram. Відкрийте Telegram, щоб продовжити.",
  registrationTelegramDescription: "Відкрийте Telegram і підтвердьте номер телефону кнопкою нижче.",
  registrationTelegramExpired: "Підтвердження Telegram застаріло. Започніть реєстрацію знову.",
  registrationTelegramInstruction: "Підтвердіть номер через Telegram, щоб завершити реєстрацію.",
  registrationTelegramOpen: "Відкрити Telegram",
  registrationTelegramTitle: "Підтвердження через Telegram",
  registrationTelegramWaiting: "Чекаємо підтвердження в Telegram...",
  registrationStepOne: "Крок 1 з 3",
  registrationStepTwo: "Крок 2 з 3",
  registrationStepThree: "Крок 3 з 3",
  registrationUseLocalCode: "Підставити код",
  registrationVerifyPhone: "Підтвердити код",
});

Object.assign(TRANSLATIONS.en, {
  clearEdge: "Clear edge",
  edgeBandingInvalid: "Select a value from the edge banding catalog",
  edgeSelectSide: "Select a side on the scheme or in the quick selector.",
  edgeSelectedSide: "Selected side",
  edgeThicknessInvalid: "Edge thickness could not be determined",
  preview2d: "2D карта",
  preview3d: "3D панель",
  rotateLeft: "Вліво",
  rotateRight: "Вправо",
  resetView: "Скинути",
  preview3dHint: "3D перегляд для візуальної оцінки. Для точного редагування крайки й координат обробки використовуйте режим 2D.",
});

Object.assign(TRANSLATIONS.en, {
  assemblyAssembled: "Assembled",
  assemblyClearSelection: "Clear selection",
  assemblyExploded: "Exploded",
  assemblyFocusSelected: "Focus selected",
  assemblyGroupBack: "Back panel",
  assemblyGroupCarcass: "Carcass",
  assemblyGroupDrawers: "Drawers",
  assemblyGroupFacades: "Facades",
  assemblyGroupOther: "Other panels",
  assemblyLayerGrooves: "Grooves",
  assemblyLayerHoles: "Holes",
  assemblyLayerQuarters: "Quarters",
  assemblyModeSolid: "Solid",
  assemblyModeTransparent: "Transparent + holes",
  assemblyOpenWorkspace: "Open detail workspace",
  assemblyResetCamera: "Reset camera",
  assemblyShowAll: "Show all",
  assemblyShowFull: "Show full assembly",
  preview2d: "2D map",
  preview3d: "3D panel",
  preview3dHint:
    "3D preview for visual inspection. Use 2D mode for precise edge editing and machining coordinates.",
  preview3dInteractiveHint: "LMB rotate, RMB move, wheel zoom.",
  productionAssembly3d: "3D assembly",
  productionAssemblyHint:
    "This 3D assembly is based on the cutting map. Click a panel to open its detail workspace.",
  resetView: "Reset",
  rotateLeft: "Left",
  rotateRight: "Right",
});

Object.assign(TRANSLATIONS.uk, {
  preview3dInteractiveHint: "Перетягуйте для обертання. Колесо миші або жест масштабування змінює зум. У 3D моделі показані крайка, отвори, пази та чверті.",
  productionAssembly3d: "3D збірка",
  productionAssemblyHint: "Ця 3D збірка побудована на основі карти розкрою. Натисніть на панель, щоб відкрити її робоче місце деталі.",
  assemblyAssembled: "Зібрано",
  assemblyExploded: "Рознесено",
  assemblyShowAll: "Показати все",
  assemblyGroupCarcass: "Корпус",
  assemblyGroupFacades: "Фасади",
  assemblyGroupDrawers: "Шухляди",
  assemblyGroupBack: "Задня стінка",
  assemblyGroupOther: "Інші панелі",
});

Object.assign(TRANSLATIONS.uk, {
  preview3dInteractiveHint: "Перетягуйте для обертання. Колесо миші або жест масштабування змінює зум. У 3D моделі показані крайка, отвори, пази та чверті.",
  productionAssembly3d: "3D збірка",
  productionAssemblyHint: "Ця 3D збірка побудована на основі карти розкрою. Натисніть на панель, щоб відкрити її робоче місце деталі.",
  assemblyAssembled: "Зібрано",
  assemblyExploded: "Рознесено",
  assemblyShowAll: "Показати все",
  assemblyGroupCarcass: "Корпус",
  assemblyGroupFacades: "Фасади",
  assemblyGroupDrawers: "Шухляди",
  assemblyGroupBack: "Задня стінка",
  assemblyGroupOther: "Інші панелі",
});

Object.assign(TRANSLATIONS.en, {
  assemblyClearSelection: "Clear selection",
  assemblyFocusSelected: "Focus selected",
  assemblyLayerGrooves: "Grooves",
  assemblyLayerHoles: "Holes",
  assemblyLayerQuarters: "Quarters",
  assemblyModeSolid: "Solid",
  assemblyModeTransparent: "Transparent + holes",
  assemblyOpenWorkspace: "Open detail workspace",
  assemblyResetCamera: "Reset camera",
  assemblyShowFull: "Show full assembly",
  hideProjectOverview: "Hide project overview",
  showProjectOverview: "Show project overview",
});

Object.assign(TRANSLATIONS.uk, {
  assemblyClearSelection: "\u041e\u0447\u0438\u0441\u0442\u0438\u0442\u0438 \u0432\u0438\u0431\u0456\u0440",
  assemblyFocusSelected: "\u0424\u043e\u043a\u0443\u0441 \u043d\u0430 \u0434\u0435\u0442\u0430\u043b\u0456",
  assemblyLayerGrooves: "\u041f\u0430\u0437\u0438",
  assemblyLayerHoles: "\u041e\u0442\u0432\u043e\u0440\u0438",
  assemblyLayerQuarters: "\u0427\u0432\u0435\u0440\u0442\u0456",
  assemblyModeSolid: "\u0421\u0443\u0446\u0456\u043b\u044c\u043d\u0430",
  assemblyModeTransparent: "\u041d\u0430\u043f\u0456\u0432\u043f\u0440\u043e\u0437\u043e\u0440\u043e + \u043e\u0442\u0432\u043e\u0440\u0438",
  assemblyOpenWorkspace: "\u0412\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u043a\u0430\u0440\u0442\u0443 \u0434\u0435\u0442\u0430\u043b\u0456",
  assemblyResetCamera: "\u0421\u043a\u0438\u043d\u0443\u0442\u0438 \u043a\u0430\u043c\u0435\u0440\u0443",
  assemblyShowFull: "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u0438 \u0432\u0441\u044e \u0437\u0431\u0456\u0440\u043a\u0443",
  hideProjectOverview: "\u0421\u0445\u043e\u0432\u0430\u0442\u0438 \u0434\u0430\u043d\u0456 \u043f\u0440\u043e\u0435\u043a\u0442\u0443",
  showProjectOverview: "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u0438 \u0434\u0430\u043d\u0456 \u043f\u0440\u043e\u0435\u043a\u0442\u0443",
});

Object.assign(TRANSLATIONS.en, {
  changePassword: "Change password",
  currentPassword: "Current password",
  emailChangeRequested: "Email change request created",
  myData: "My data",
  newEmail: "New email",
  newPassword: "New password",
  passwordChanged: "Password changed",
  phone: "Phone",
  profileUpdated: "Profile updated",
  requestEmailChange: "Request email change",
  role: "Role",
  saveProfile: "Save profile",
  settings: "Settings",
  unableToChangePassword: "Unable to change password",
  unableToRequestEmailChange: "Unable to request email change",
  unableToUpdateProfile: "Unable to update profile",
  username: "Username",
});

Object.assign(TRANSLATIONS.uk, {
  changePassword: "\u0417\u043c\u0456\u043d\u0438\u0442\u0438 \u043f\u0430\u0440\u043e\u043b\u044c",
  currentPassword: "\u041f\u043e\u0442\u043e\u0447\u043d\u0438\u0439 \u043f\u0430\u0440\u043e\u043b\u044c",
  emailChangeRequested: "\u0417\u0430\u043f\u0438\u0442 \u043d\u0430 \u0437\u043c\u0456\u043d\u0443 email \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043e",
  myData: "\u041c\u043e\u0457 \u0434\u0430\u043d\u0456",
  newEmail: "\u041d\u043e\u0432\u0438\u0439 email",
  newPassword: "\u041d\u043e\u0432\u0438\u0439 \u043f\u0430\u0440\u043e\u043b\u044c",
  passwordChanged: "\u041f\u0430\u0440\u043e\u043b\u044c \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
  phone: "\u0422\u0435\u043b\u0435\u0444\u043e\u043d",
  profileUpdated: "\u041f\u0440\u043e\u0444\u0456\u043b\u044c \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
  requestEmailChange: "\u0417\u0430\u043f\u0438\u0442\u0438 \u0437\u043c\u0456\u043d\u0443 email",
  role: "\u0420\u043e\u043b\u044c",
  saveProfile: "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u043f\u0440\u043e\u0444\u0456\u043b\u044c",
  settings: "\u041d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f",
  unableToChangePassword: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0437\u043c\u0456\u043d\u0438\u0442\u0438 \u043f\u0430\u0440\u043e\u043b\u044c",
  unableToRequestEmailChange: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0441\u0442\u0432\u043e\u0440\u0438\u0442\u0438 \u0437\u0430\u043f\u0438\u0442 \u043d\u0430 \u0437\u043c\u0456\u043d\u0443 email",
  unableToUpdateProfile: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u043e\u043d\u043e\u0432\u0438\u0442\u0438 \u043f\u0440\u043e\u0444\u0456\u043b\u044c",
  username: "\u041b\u043e\u0433\u0456\u043d",
});

Object.assign(TRANSLATIONS.en, {
  adminPortal: "Admin portal",
  authLoginTab: "Login",
  authRegisterTab: "Register",
  confirmPassword: "Confirm password",
  landingExperienceTitle: "One ecosystem for website, web system, bot, and calculator",
  landingExperienceDescription: "Start from the public website, compare access, then move into the web workspace or Telegram bot.",
  landingHeroBulletCatalogs: "Catalogs of materials, fittings, edging, and services",
  landingHeroBulletProduction: "Project preparation for production and cutting",
  landingHeroBulletAutomation: "Telegram access, admin control, and shared product data",
  landingHeroRegistrationBadge: "Open registration",
  landingAdminHint: "Admin opens in a new tab. Access is available after login or registration.",
  landingAuthDescription: "Use your account to open the calculator workspace, projects, and profile settings.",
  landingAuthTitle: "Account access",
  landingBotCardTitle: "Telegram bot",
  landingBotCardDescription: "Quick access to profile data, fitting picks, and helper actions in chat.",
  landingBotCta: "Open bot",
  landingCapabilitiesDescription: "One platform for calculation, production prep, catalogs, and guided work in chat.",
  landingCapabilitiesTitle: "Platform capabilities",
  landingCatalogsCardTitle: "Catalogs and references",
  landingCatalogsCardDescription: "Materials, fittings, edging, services, and system values in one structure.",
  landingDashboardCardTitle: "Admin and control",
  landingDashboardCardDescription: "Users, roles, catalogs, personal prices, and product data in one admin area.",
  landingHeroDescription:
    "Online calculator for furniture makers and workshops. Accurate estimates, materials, edging, fittings, and production data in a few clicks.",
  landingHeroTitle: "Calculate. Design.",
  landingHeroAccent: "Build.",
  landingHeroFeatureProjects: "Project calculation",
  landingHeroFeatureMaterials: "Materials and cutting",
  landingHeroFeatureEdges: "Edging and fittings",
  landingHeroFeatureEstimate: "Estimate and export",
  landingHeroViewCapabilities: "View capabilities",
  landingOpenAdmin: "Open admin",
  landingOpenApp: "Open web system",
  landingOpenYoutube: "Video guides",
  landingPackagesDescription: "Choose access depth depending on your workflow: review, work, or full commercial use.",
  landingPackagesTitle: "Packages and access",
  landingPricingGuestFeatures: "Basic free mode for stable furniture calculation through ready-made templates.",
  landingPricingGuestTitle: "Free",
  landingPricingProFeatures: "Premium mode for PDF design-project analysis, BOM generation, exports, and extended reports.",
  landingPricingProTitle: "Premium",
  landingPricingUserFeatures: "PRO mode for photo or sketch upload, OCR size recognition, and automatic parameter filling.",
  landingPricingUserTitle: "PRO",
  landingPublicStatsDescription: "Live numbers from the current product database.",
  landingPublicStatsTitle: "Platform scale",
  landingRegisterAction: "Create account",
  landingRegistrationSuccess: "Account created. You are now signed in.",
  landingSiteCardDescription: "Open website entry, review packages, instructions, and platform updates.",
  landingSiteCardTitle: "Website",
  landingStartCta: "Launch calculator",
  landingStatsFittings: "Fittings",
  landingStatsMaterials: "Materials",
  landingStatsProjects: "Projects",
  landingStatsUsers: "Users",
  landingStatusRegistrationOpen: "Registration is open",
  landingStatusRegistrationRestricted: "Registration is limited",
  landingYoutubeCardTitle: "YouTube channel",
  landingYoutubeCardDescription: "Video instructions, onboarding flows, and practical walkthroughs for daily work.",
  landingAppCardTitle: "Web system",
  landingAppCardDescription: "Create projects, prepare production data, and work with materials and fittings in the browser.",
  passwordResetRequest: "Forgot or change password?",
  passwordResetRequestDescription: "Enter your account email. If it exists, the administrator will receive a password reset request.",
  passwordResetRequestFailed: "Unable to create password reset request",
  passwordResetRequestSent: "Password reset request sent. The administrator will review it.",
  passwordResetSubmit: "Send request",
  showPassword: "Show password",
  aiScanTitle: "AI recognition",
  aiScanDescription: "Upload a photo, sketch, or PDF. The system will try to find furniture type and dimensions, then you confirm the fields.",
  aiScanUpload: "Analyze file",
  aiScanApply: "Apply to form",
  aiScanFound: "Preliminary result",
  aiScanHistory: "Recent recognition drafts",
  aiScanRawText: "OCR text",
  aiScanNeedsConfirmation: "Needs confirmation",
  aiScanProOnly: "AI recognition is available for PRO and admin accounts.",
  aiScanConfirmed: "Recognition confirmed",
  aiScanUnsupported: "Recognition failed",
  projectStartManualTitle: "Manual calculation",
  projectStartManualDescription: "Free start: enter dimensions and specification fields yourself.",
  projectStartAiTitle: "PRO AI scan",
  projectStartAiDescription: "Upload a sketch, photo, or PDF and confirm the detected project data.",
  projectStartFreeBadge: "Free",
  projectStartProBadge: "PRO / Premium",
  projectSpecificationTitle: "Project specification",
  passwordsDoNotMatch: "Passwords do not match",
  registrationFailed: "Registration failed",
});

Object.assign(TRANSLATIONS.uk, {
  adminPortal: "Адмінка",
  authLoginTab: "Вхід",
  authRegisterTab: "Реєстрація",
  confirmPassword: "Підтвердіть пароль",
  landingExperienceTitle: "Єдина екосистема: сайт, веб-система, бот і калькулятор",
  landingExperienceDescription: "Початок із відкритого сайту, далі вибір доступу та перехід у веб-кабінет або Telegram-бот.",
  landingHeroBulletCatalogs: "Каталоги матеріалів, фурнітури, крайки та послуг",
  landingHeroBulletProduction: "Підготовка проєктів до виробництва та розкрою",
  landingHeroBulletAutomation: "Telegram-доступ, контроль через адмінку та спільні дані продукту",
  landingHeroRegistrationBadge: "Реєстрація відкрита",
  landingAdminHint: "Адмінка відкривається в новій вкладці. Доступ до неї лише після входу або реєстрації.",
  landingAuthDescription: "Увійдіть у свій акаунт, щоб відкрити калькулятор, проєкти та власні налаштування.",
  landingAuthTitle: "Доступ до акаунта",
  landingBotCardTitle: "Telegram бот",
  landingBotCardDescription: "Швидкий доступ до профілю, підбору фурнітури та допоміжних дій у чаті.",
  landingBotCta: "Відкрити бота",
  landingCapabilitiesDescription: "Єдина платформа для прорахунку, підготовки виробництва, довідників та роботи через чат.",
  landingCapabilitiesTitle: "Можливості платформи",
  landingCatalogsCardTitle: "Каталоги та довідники",
  landingCatalogsCardDescription: "Матеріали, фурнітура, крайка, послуги та системні значення в одній структурі.",
  landingDashboardCardTitle: "Адмінка та контроль",
  landingDashboardCardDescription: "Користувачі, ролі, каталоги, персональні ціни та керування даними продукту.",
  landingHeroDescription:
    "Онлайн калькулятор для меблевих виробників та майстрів. Точні прорахунки, матеріали, крайка, фурнітура та кошторис за кілька кліків.",
  landingHeroTitle: "Рахуй. Проєктуй.",
  landingHeroAccent: "Створюй.",
  landingHeroFeatureProjects: "Розрахунок проєктів",
  landingHeroFeatureMaterials: "Матеріали та розкрій",
  landingHeroFeatureEdges: "Крайка та фурнітура",
  landingHeroFeatureEstimate: "Кошторис та експорт",
  landingHeroViewCapabilities: "Дивитись можливості",
  landingOpenAdmin: "Відкрити адмінку",
  landingOpenApp: "Відкрити веб-систему",
  landingOpenYoutube: "Відео інструкції",
  landingPackagesDescription: "Оберіть рівень доступу під свій сценарій: ознайомлення, робота або повний комерційний режим.",
  landingPackagesTitle: "Пакети та доступ",
  landingPricingGuestFeatures: "Базовий безкоштовний режим для стабільного прорахунку меблів через готові шаблони.",
  landingPricingGuestTitle: "Безкоштовний",
  landingPricingProFeatures: "Premium режим для аналізу PDF дизайн-проєктів, BOM, експортів і розширених звітів.",
  landingPricingProTitle: "Premium",
  landingPricingUserFeatures: "PRO режим для завантаження фото або ескізу, OCR-розпізнавання розмірів і автозаповнення параметрів.",
  landingPricingUserTitle: "PRO",
  landingPublicStatsDescription: "Живі цифри з поточної бази продукту.",
  landingPublicStatsTitle: "Масштаб платформи",
  landingRegisterAction: "Створити акаунт",
  landingRegistrationSuccess: "Акаунт створено. Ви вже увійшли в систему.",
  landingSiteCardDescription: "Відкритий сайт-вхід з описом пакетів, інструкцій та оновлень платформи.",
  landingSiteCardTitle: "Сайт",
  landingStartCta: "Запустити калькулятор",
  landingStatsFittings: "Фурнітура",
  landingStatsMaterials: "Матеріали",
  landingStatsProjects: "Проєкти",
  landingStatsUsers: "Користувачі",
  landingStatusRegistrationOpen: "Реєстрація відкрита",
  landingStatusRegistrationRestricted: "Реєстрація обмежена",
  landingYoutubeCardTitle: "YouTube канал",
  landingYoutubeCardDescription: "Відеоінструкції, сценарії старту та практичні приклади щоденної роботи.",
  landingAppCardTitle: "Веб-система",
  landingAppCardDescription: "Створення проєктів, підготовка виробництва та робота з матеріалами й фурнітурою в браузері.",
  passwordsDoNotMatch: "Паролі не співпадають",
  registrationFailed: "Не вдалося зареєструватися",
});

Object.assign(TRANSLATIONS.en, {
  landingPricingGuestList:
    "Manual furniture type selection|Width, height, depth, and construction parameters|Basic estimate from furniture templates",
  landingPricingUserList:
    "Upload photo, screenshot, or hand sketch|OCR recognition of dimensions|Automatic draft filling before confirmation",
  landingPricingProList:
    "PDF design-project analysis|Several furniture items from one PDF|BOM generation, exports, and extended reports",
  landingProSpotlightTitle: "Why PRO is the working tier",
  landingProSpotlightDescription:
    "PRO is built for teams and makers who work in the calculator every day and want their own commercial logic inside the product.",
  landingProSpotlightPointOne: "Own materials and fittings for calculation",
  landingProSpotlightPointTwo: "Deeper catalog control and personal data workflows",
  landingProSpotlightPointThree:
    "Better fit for real production and estimate preparation",
});

Object.assign(TRANSLATIONS.uk, {
  landingPricingGuestList:
    "Ручний вибір типу меблів|Ширина, висота, глибина та параметри конструкції|Базовий кошторис по шаблонах меблів",
  landingPricingUserList:
    "Завантаження фото, скріншоту або ескізу|OCR-розпізнавання розмірів|Автозаповнення чернетки перед підтвердженням",
  landingPricingProList:
    "Аналіз PDF дизайн-проєкту|Пошук декількох виробів в одному PDF|BOM, експорти та розширені звіти",
  landingProSpotlightTitle: "Чому PRO і Premium прискорюють роботу",
  landingProSpotlightDescription:
    "PRO закриває швидкий старт по фото або ескізу, а Premium потрібен там, де треба розбирати повні PDF-проєкти й готувати розширені звіти.",
  landingProSpotlightPointOne: "AI-розпізнавання фото, скріншотів та ескізів",
  landingProSpotlightPointTwo:
    "Автозаповнення параметрів перед підтвердженням",
  landingProSpotlightPointThree:
    "PDF, BOM, експорти та виробничі звіти у Premium",
});

Object.assign(TRANSLATIONS.en, {
  landingWorkflowTitle: "How the product works",
  landingWorkflowDescription:
    "A clear entry path for new users and a structured workflow for teams already inside the product.",
  landingWorkflowStepOneTitle: "Visit the public website",
  landingWorkflowStepOneDescription:
    "Review capabilities, compare packages, and understand what the ecosystem includes.",
  landingWorkflowStepTwoTitle: "Create an account",
  landingWorkflowStepTwoDescription:
    "Open access to the calculator workspace, profile settings, and shared product data.",
  landingWorkflowStepThreeTitle: "Work in catalogs and projects",
  landingWorkflowStepThreeDescription:
    "Prepare materials, fittings, services, and production-ready project structures.",
  landingWorkflowStepFourTitle: "Move to production flow",
  landingWorkflowStepFourDescription:
    "Use the web system, admin area, and bot as one connected working flow.",
  landingModulesTitle: "Connected product modules",
  landingModulesDescription:
    "Every surface solves its own task, but the data model stays unified across the whole product.",
  landingModuleSiteTitle: "Public website",
  landingModuleSiteDescription:
    "Open presentation layer with entry points, package logic, and onboarding information.",
  landingModuleAdminTitle: "Admin control",
  landingModuleAdminDescription:
    "Users, roles, shared catalogs, and system-level product configuration.",
  landingModuleAppTitle: "Web calculation system",
  landingModuleAppDescription:
    "Projects, materials, fittings, production preparation, and estimate logic inside the browser.",
  landingModuleBotTitle: "Telegram access",
  landingModuleBotDescription:
    "Fast actions, guided interaction, and profile-related work inside chat.",
  landingFooterTitle: "MProject.furniture",
  landingFooterDescription:
    "A furniture calculation and production platform built around shared catalogs, project data, and practical daily workflows.",
  landingFooterCaption: "Website, web system, admin, and bot working as one product.",
});

Object.assign(TRANSLATIONS.uk, {
  landingWorkflowTitle: "\u042f\u043a \u043f\u0440\u0430\u0446\u044e\u0454 \u043f\u0440\u043e\u0434\u0443\u043a\u0442",
  landingWorkflowDescription:
    "\u0417\u0440\u043e\u0437\u0443\u043c\u0456\u043b\u0438\u0439 \u0441\u0446\u0435\u043d\u0430\u0440\u0456\u0439 \u0441\u0442\u0430\u0440\u0442\u0443 \u0434\u043b\u044f \u043d\u043e\u0432\u0438\u0445 \u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456\u0432 \u0456 \u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u043d\u0438\u0439 \u0440\u043e\u0431\u043e\u0447\u0438\u0439 \u0446\u0438\u043a\u043b \u0434\u043b\u044f \u043a\u043e\u043c\u0430\u043d\u0434.",
  landingWorkflowStepOneTitle: "\u0412\u0456\u0434\u0432\u0456\u0434\u0430\u0442\u0438 \u0432\u0456\u0434\u043a\u0440\u0438\u0442\u0438\u0439 \u0441\u0430\u0439\u0442",
  landingWorkflowStepOneDescription:
    "\u041f\u0435\u0440\u0435\u0433\u043b\u044f\u043d\u0443\u0442\u0438 \u043c\u043e\u0436\u043b\u0438\u0432\u043e\u0441\u0442\u0456, \u043f\u043e\u0440\u0456\u0432\u043d\u044f\u0442\u0438 \u043f\u0430\u043a\u0435\u0442\u0438 \u0442\u0430 \u0437\u0440\u043e\u0437\u0443\u043c\u0456\u0442\u0438, \u0449\u043e \u0432\u0445\u043e\u0434\u0438\u0442\u044c \u0432 \u0435\u043a\u043e\u0441\u0438\u0441\u0442\u0435\u043c\u0443.",
  landingWorkflowStepTwoTitle: "\u0421\u0442\u0432\u043e\u0440\u0438\u0442\u0438 \u0430\u043a\u0430\u0443\u043d\u0442",
  landingWorkflowStepTwoDescription:
    "\u0412\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u0434\u043e\u0441\u0442\u0443\u043f \u0434\u043e \u043a\u0430\u043b\u044c\u043a\u0443\u043b\u044f\u0442\u043e\u0440\u0430, \u043f\u0440\u043e\u0444\u0456\u043b\u044e \u0442\u0430 \u0441\u043f\u0456\u043b\u044c\u043d\u0438\u0445 \u0434\u0430\u043d\u0438\u0445 \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u0443.",
  landingWorkflowStepThreeTitle: "\u041f\u0440\u0430\u0446\u044e\u0432\u0430\u0442\u0438 \u0437 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0430\u043c\u0438 \u0442\u0430 \u043f\u0440\u043e\u0454\u043a\u0442\u0430\u043c\u0438",
  landingWorkflowStepThreeDescription:
    "\u0413\u043e\u0442\u0443\u0432\u0430\u0442\u0438 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0438, \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443, \u043f\u043e\u0441\u043b\u0443\u0433\u0438 \u0442\u0430 \u0432\u0438\u0440\u043e\u0431\u043d\u0438\u0447\u0456 \u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u0438 \u043f\u0440\u043e\u0454\u043a\u0442\u0443.",
  landingWorkflowStepFourTitle: "\u041f\u0435\u0440\u0435\u0439\u0442\u0438 \u0434\u043e \u0432\u0438\u0440\u043e\u0431\u043d\u0438\u0447\u043e\u0433\u043e \u0446\u0438\u043a\u043b\u0443",
  landingWorkflowStepFourDescription:
    "\u0412\u0438\u043a\u043e\u0440\u0438\u0441\u0442\u043e\u0432\u0443\u0432\u0430\u0442\u0438 \u0432\u0435\u0431-\u0441\u0438\u0441\u0442\u0435\u043c\u0443, \u0430\u0434\u043c\u0456\u043d\u043a\u0443 \u0442\u0430 \u0431\u043e\u0442\u0430 \u044f\u043a \u0454\u0434\u0438\u043d\u0438\u0439 \u0440\u043e\u0431\u043e\u0447\u0438\u0439 \u0446\u0438\u043a\u043b.",
  landingModulesTitle: "\u041f\u043e\u0432'\u044f\u0437\u0430\u043d\u0456 \u043c\u043e\u0434\u0443\u043b\u0456 \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u0443",
  landingModulesDescription:
    "\u041a\u043e\u0436\u0435\u043d \u0456\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441 \u043c\u0430\u0454 \u0441\u0432\u043e\u0454 \u0437\u0430\u0432\u0434\u0430\u043d\u043d\u044f, \u0430\u043b\u0435 \u0434\u0430\u043d\u0456 \u0442\u0440\u0438\u043c\u0430\u044e\u0442\u044c\u0441\u044f \u0432 \u0454\u0434\u0438\u043d\u0456\u0439 \u043b\u043e\u0433\u0456\u0446\u0456 \u043f\u043e \u0432\u0441\u044c\u043e\u043c\u0443 \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u0443.",
  landingModuleSiteTitle: "\u0412\u0456\u0434\u043a\u0440\u0438\u0442\u0438\u0439 \u0441\u0430\u0439\u0442",
  landingModuleSiteDescription:
    "\u041f\u0443\u0431\u043b\u0456\u0447\u043d\u0438\u0439 \u0432\u0445\u0456\u0434, \u043f\u0430\u043a\u0435\u0442\u0438, \u043f\u043e\u044f\u0441\u043d\u0435\u043d\u043d\u044f \u043c\u043e\u0436\u043b\u0438\u0432\u043e\u0441\u0442\u0435\u0439 \u0442\u0430 \u043e\u043d\u0431\u043e\u0440\u0434\u0438\u043d\u0433.",
  landingModuleAdminTitle: "\u0410\u0434\u043c\u0456\u043d\u043a\u0430",
  landingModuleAdminDescription:
    "\u041a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456, \u0440\u043e\u043b\u0456, \u0441\u043f\u0456\u043b\u044c\u043d\u0456 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0438 \u0442\u0430 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u0435 \u043d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u0443.",
  landingModuleAppTitle: "\u0412\u0435\u0431-\u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443",
  landingModuleAppDescription:
    "\u041f\u0440\u043e\u0454\u043a\u0442\u0438, \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0438, \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430, \u043f\u0456\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 \u0434\u043e \u0432\u0438\u0440\u043e\u0431\u043d\u0438\u0446\u0442\u0432\u0430 \u0442\u0430 \u043b\u043e\u0433\u0456\u043a\u0430 \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443.",
  landingModuleBotTitle: "Telegram \u0431\u043e\u0442",
  landingModuleBotDescription:
    "\u0428\u0432\u0438\u0434\u043a\u0456 \u0434\u0456\u0457, \u043f\u0456\u0434\u043a\u0430\u0437\u043a\u0438 \u0442\u0430 \u0434\u043e\u0441\u0442\u0443\u043f \u0434\u043e \u0434\u0430\u043d\u0438\u0445 \u043f\u0440\u043e\u0434\u0443\u043a\u0442\u0443 \u043f\u0440\u044f\u043c\u043e \u0432 \u0447\u0430\u0442\u0456.",
  landingFooterTitle: "MProject.furniture",
  landingFooterDescription:
    "\u041f\u043b\u0430\u0442\u0444\u043e\u0440\u043c\u0430 \u0434\u043b\u044f \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443 \u043c\u0435\u0431\u043b\u0456\u0432 \u0442\u0430 \u043f\u0456\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0438 \u0432\u0438\u0440\u043e\u0431\u043d\u0438\u0446\u0442\u0432\u0430 \u043d\u0430 \u043e\u0441\u043d\u043e\u0432\u0456 \u0441\u043f\u0456\u043b\u044c\u043d\u0438\u0445 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0456\u0432, \u043f\u0440\u043e\u0454\u043a\u0442\u043d\u0438\u0445 \u0434\u0430\u043d\u0438\u0445 \u0442\u0430 \u0440\u043e\u0431\u043e\u0447\u0438\u0445 \u0441\u0446\u0435\u043d\u0430\u0440\u0456\u0457\u0432.",
  landingFooterCaption: "\u0421\u0430\u0439\u0442, \u0432\u0435\u0431-\u0441\u0438\u0441\u0442\u0435\u043c\u0430, \u0430\u0434\u043c\u0456\u043d\u043a\u0430 \u0442\u0430 \u0431\u043e\u0442 \u043f\u0440\u0430\u0446\u044e\u044e\u0442\u044c \u044f\u043a \u043e\u0434\u0438\u043d \u043f\u0440\u043e\u0434\u0443\u043a\u0442.",
});

Object.assign(TRANSLATIONS.uk, {
  passwordResetRequest: "\u041d\u0430\u0433\u0430\u0434\u0430\u0442\u0438 \u0430\u0431\u043e \u0437\u043c\u0456\u043d\u0438\u0442\u0438 \u043f\u0430\u0440\u043e\u043b\u044c?",
  passwordResetRequestDescription:
    "\u0412\u0432\u0435\u0434\u0456\u0442\u044c email \u0430\u043a\u0430\u0443\u043d\u0442\u0430. \u042f\u043a\u0449\u043e \u0432\u0456\u043d \u0454 \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0456, \u0430\u0434\u043c\u0456\u043d\u0456\u0441\u0442\u0440\u0430\u0442\u043e\u0440 \u043e\u0442\u0440\u0438\u043c\u0430\u0454 \u0437\u0430\u044f\u0432\u043a\u0443 \u043d\u0430 \u0437\u043c\u0456\u043d\u0443 \u043f\u0430\u0440\u043e\u043b\u044f.",
  passwordResetRequestFailed: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0441\u0442\u0432\u043e\u0440\u0438\u0442\u0438 \u0437\u0430\u044f\u0432\u043a\u0443 \u043d\u0430 \u0437\u043c\u0456\u043d\u0443 \u043f\u0430\u0440\u043e\u043b\u044f",
  passwordResetRequestSent: "\u0417\u0430\u044f\u0432\u043a\u0443 \u043d\u0430 \u0437\u043c\u0456\u043d\u0443 \u043f\u0430\u0440\u043e\u043b\u044f \u0432\u0456\u0434\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u043e \u0430\u0434\u043c\u0456\u043d\u0456\u0441\u0442\u0440\u0430\u0442\u043e\u0440\u0443.",
  passwordResetSubmit: "\u0412\u0456\u0434\u043f\u0440\u0430\u0432\u0438\u0442\u0438 \u0437\u0430\u044f\u0432\u043a\u0443",
  showPassword: "\u041f\u043e\u043a\u0430\u0437\u0430\u0442\u0438 \u043f\u0430\u0440\u043e\u043b\u044c",
  aiScanTitle: "AI-\u0440\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f",
  aiScanDescription:
    "\u0417\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0442\u0435 \u0444\u043e\u0442\u043e, \u0435\u0441\u043a\u0456\u0437 \u0430\u0431\u043e PDF. \u0421\u0438\u0441\u0442\u0435\u043c\u0430 \u0441\u043f\u0440\u043e\u0431\u0443\u0454 \u0437\u043d\u0430\u0439\u0442\u0438 \u0442\u0438\u043f \u043c\u0435\u0431\u043b\u0456\u0432 \u0456 \u0440\u043e\u0437\u043c\u0456\u0440\u0438, \u0430 \u0432\u0438 \u043f\u0456\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u0435 \u043f\u043e\u043b\u044f.",
  aiScanUpload: "\u041f\u0440\u043e\u0430\u043d\u0430\u043b\u0456\u0437\u0443\u0432\u0430\u0442\u0438 \u0444\u0430\u0439\u043b",
  aiScanApply: "\u0417\u0430\u0441\u0442\u043e\u0441\u0443\u0432\u0430\u0442\u0438 \u0434\u043e \u0444\u043e\u0440\u043c\u0438",
  aiScanFound: "\u041f\u043e\u043f\u0435\u0440\u0435\u0434\u043d\u0456\u0439 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442",
  aiScanHistory: "\u041e\u0441\u0442\u0430\u043d\u043d\u0456 \u0447\u0435\u0440\u043d\u0435\u0442\u043a\u0438 \u0440\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u044c",
  aiScanRawText: "OCR-\u0442\u0435\u043a\u0441\u0442",
  aiScanNeedsConfirmation: "\u041f\u043e\u0442\u0440\u0456\u0431\u043d\u0435 \u043f\u0456\u0434\u0442\u0432\u0435\u0440\u0434\u0436\u0435\u043d\u043d\u044f",
  aiScanProOnly: "AI-\u0440\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0435 \u0434\u043b\u044f PRO \u0442\u0430 \u0430\u0434\u043c\u0456\u043d\u0430.",
  aiScanConfirmed: "\u0420\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f \u043f\u0456\u0434\u0442\u0432\u0435\u0440\u0434\u0436\u0435\u043d\u043e",
  aiScanUnsupported: "\u0420\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f \u043d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f",
  projectStartManualTitle: "\u0420\u0443\u0447\u043d\u0438\u0439 \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043e\u043a",
  projectStartManualDescription:
    "\u0411\u0435\u0437\u043a\u043e\u0448\u0442\u043e\u0432\u043d\u0438\u0439 \u0441\u0442\u0430\u0440\u0442: \u0432\u0432\u0435\u0434\u0456\u0442\u044c \u0440\u043e\u0437\u043c\u0456\u0440\u0438 \u0442\u0430 \u043f\u043e\u043b\u044f \u0441\u043f\u0435\u0446\u0438\u0444\u0456\u043a\u0430\u0446\u0456\u0457 \u0432\u0440\u0443\u0447\u043d\u0443.",
  projectStartAiTitle: "PRO AI-\u0441\u043a\u0430\u043d",
  projectStartAiDescription:
    "\u0417\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0442\u0435 \u0435\u0441\u043a\u0456\u0437, \u0444\u043e\u0442\u043e \u0430\u0431\u043e PDF \u0456 \u043f\u0456\u0434\u0442\u0432\u0435\u0440\u0434\u0456\u0442\u044c \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u0456 \u0434\u0430\u043d\u0456 \u043f\u0440\u043e\u0435\u043a\u0442\u0443.",
  projectStartFreeBadge: "\u0411\u0435\u0437\u043a\u043e\u0448\u0442\u043e\u0432\u043d\u043e",
  projectStartProBadge: "PRO / Premium",
  projectSpecificationTitle: "\u0421\u043f\u0435\u0446\u0438\u0444\u0456\u043a\u0430\u0446\u0456\u044f \u043f\u0440\u043e\u0435\u043a\u0442\u0443",
  projectStartTitle: "\u041f\u043e\u0447\u0430\u0442\u043e\u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0443",
  projectStartDescription:
    "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0441\u0446\u0435\u043d\u0430\u0440\u0456\u0439: \u0448\u0430\u0431\u043b\u043e\u043d, PRO-\u0441\u043a\u0430\u043d \u0430\u0431\u043e \u0440\u043e\u0437\u0448\u0438\u0440\u0435\u043d\u0438\u0439 Premium-\u0441\u0442\u0430\u0440\u0442.",
  projectTemplateApplied: "\u0428\u0430\u0431\u043b\u043e\u043d \u0437\u0430\u0441\u0442\u043e\u0441\u043e\u0432\u0430\u043d\u043e \u0434\u043e \u0444\u043e\u0440\u043c\u0438",
  projectTemplateCabinetDescription: "\u041a\u043e\u043c\u043f\u0430\u043a\u0442\u043d\u0430 \u0442\u0443\u043c\u0431\u0430 \u0434\u043b\u044f \u0448\u0432\u0438\u0434\u043a\u043e\u0433\u043e \u0440\u0443\u0447\u043d\u043e\u0433\u043e \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443.",
  projectTemplateCabinetTitle: "\u0422\u0443\u043c\u0431\u0430",
  projectTemplateDrawerUnitDescription: "\u0411\u043b\u043e\u043a \u0448\u0443\u0445\u043b\u044f\u0434 \u0437 \u0431\u0430\u0437\u043e\u0432\u0438\u043c\u0438 \u043d\u0430\u043f\u0440\u0430\u0432\u043b\u044f\u044e\u0447\u0438\u043c\u0438.",
  projectTemplateDrawerUnitTitle: "\u0411\u043b\u043e\u043a \u0448\u0443\u0445\u043b\u044f\u0434",
  projectTemplateDresserDescription: "\u041a\u043e\u043c\u043e\u0434 \u0437 \u0441\u0435\u043a\u0446\u0456\u044f\u043c\u0438 \u0442\u0430 \u0448\u0443\u0445\u043b\u044f\u0434\u0430\u043c\u0438 \u0437\u0430 \u0431\u0430\u0437\u043e\u0432\u0438\u043c \u0441\u0446\u0435\u043d\u0430\u0440\u0456\u0454\u043c.",
  projectTemplateDresserTitle: "\u041a\u043e\u043c\u043e\u0434",
  projectTemplateWardrobeDescription: "\u0412\u0438\u0441\u043e\u043a\u0430 \u0448\u0430\u0444\u0430 \u0437 \u0441\u0435\u043a\u0446\u0456\u044f\u043c\u0438 \u0442\u0430 \u043e\u0434\u043d\u0456\u0454\u044e \u0448\u0443\u0445\u043b\u044f\u0434\u043e\u044e.",
  projectTemplateWardrobeTitle: "\u0428\u0430\u0444\u0430",
  projectStartPremiumBadge: "Premium",
  projectStartPremiumDescription:
    "\u041c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u0438\u0439 \u0441\u0442\u0430\u0440\u0442: \u0448\u0430\u0431\u043b\u043e\u043d\u0438, \u0441\u043a\u0430\u043d, PDF \u0442\u0430 \u043c\u0430\u0439\u0431\u0443\u0442\u043d\u0456 \u043f\u0430\u043a\u0435\u0442\u043d\u0456 \u0456\u043c\u043f\u043e\u0440\u0442\u0438.",
  projectStartPremiumOnly: "Premium-\u0441\u0442\u0430\u0440\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0438\u0439 \u0434\u043b\u044f Premium \u0442\u0430 \u0430\u0434\u043c\u0456\u043d\u0430.",
  projectStartPremiumTitle: "Premium \u0441\u0442\u0430\u0440\u0442",
  projectPremiumOpenUpload: "\u0412\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0435\u043d\u043d\u044f",
  projectPremiumOptionBatch: "\u041f\u0430\u043a\u0435\u0442\u043d\u0438\u0439 \u0441\u0442\u0430\u0440\u0442",
  projectPremiumOptionBatchDescription:
    "\u041c\u0456\u0441\u0446\u0435 \u0434\u043b\u044f \u043c\u0430\u0439\u0431\u0443\u0442\u043d\u044c\u043e\u0433\u043e \u0456\u043c\u043f\u043e\u0440\u0442\u0443 \u043d\u0430\u0431\u043e\u0440\u0443 \u0432\u0438\u0440\u043e\u0431\u0456\u0432.",
  projectPremiumOptionRecognition: "\u0424\u0430\u0439\u043b \u0430\u0431\u043e \u0435\u0441\u043a\u0456\u0437",
  projectPremiumOptionRecognitionDescription:
    "\u0424\u043e\u0442\u043e, \u043c\u0430\u043b\u044e\u043d\u043e\u043a \u0430\u0431\u043e PDF \u0434\u043b\u044f \u043f\u0435\u0440\u0432\u0438\u043d\u043d\u043e\u0433\u043e \u0440\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f.",
  projectPremiumOptionTemplates: "\u0420\u043e\u0437\u0443\u043c\u043d\u0456 \u0448\u0430\u0431\u043b\u043e\u043d\u0438",
  projectPremiumOptionTemplatesDescription:
    "\u0428\u0432\u0438\u0434\u043a\u0438\u0439 \u0432\u0438\u0431\u0456\u0440 \u043a\u043e\u043d\u0441\u0442\u0440\u0443\u043a\u0446\u0456\u0439 \u0437 \u0431\u0430\u0437\u043e\u0432\u0438\u043c\u0438 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u0430\u043c\u0438.",
});

Object.assign(TRANSLATIONS.en, {
  projectPremiumOpenUpload: "Open upload",
  projectPremiumOptionBatch: "Batch start",
  projectPremiumOptionBatchDescription: "Reserved for future import of several products at once.",
  projectPremiumOptionRecognition: "File or sketch",
  projectPremiumOptionRecognitionDescription: "Photo, drawing, or PDF for initial recognition.",
  projectPremiumOptionTemplates: "Smart templates",
  projectPremiumOptionTemplatesDescription: "Fast construction presets with base parameters.",
  projectStartDescription: "Choose a start scenario: template, PRO scan, or extended Premium start.",
  projectStartPremiumBadge: "Premium",
  projectStartPremiumDescription: "Maximum start with templates, scan, PDF, and future batch imports.",
  projectStartPremiumOnly: "Premium start is available for Premium users and admins.",
  projectStartPremiumTitle: "Premium start",
  projectStartTitle: "Project start",
  projectTemplateApplied: "Template applied to the form",
  projectTemplateCabinetDescription: "Compact cabinet for quick manual calculation.",
  projectTemplateCabinetTitle: "Cabinet",
  projectTemplateDrawerUnitDescription: "Drawer unit with base slide settings.",
  projectTemplateDrawerUnitTitle: "Drawer unit",
  projectTemplateDresserDescription: "Dresser with sections and drawers by a base scenario.",
  projectTemplateDresserTitle: "Dresser",
  projectTemplateWardrobeDescription: "Tall wardrobe with sections and one drawer.",
  projectTemplateWardrobeTitle: "Wardrobe",
});

Object.assign(TRANSLATIONS.en, {
  bathroom_shelf: "Bathroom shelf",
  bathroom_vanity: "Bathroom vanity",
  wall_unit: "Wall unit",
  projectStartPremiumBadge: "Business",
  projectStartPremiumDescription:
    "Business start: templates, scan, PDF, and extended import scenarios for larger workflows.",
  projectStartPremiumOnly: "Business start is available for Premium users and admins.",
  projectStartPremiumTitle: "Business start",
  projectTemplateBathroomShelfDescription: "Compact bathroom shelf with shallow depth and vertical storage.",
  projectTemplateBathroomShelfTitle: "Bathroom shelf",
  projectTemplateBathroomVanityDescription: "Vanity unit for a bathroom with a cabinet body and front.",
  projectTemplateBathroomVanityTitle: "Bathroom vanity",
  projectTemplateKitchenDescription: "Base kitchen module with countertop depth and working height.",
  projectTemplateKitchenTitle: "Kitchen",
  projectTemplateWallUnitDescription: "Living-room wall unit with wide body and storage zones.",
  projectTemplateWallUnitTitle: "Wall unit",
});

Object.assign(TRANSLATIONS.uk, {
  bathroom_shelf: "Санвузлова полка",
  bathroom_vanity: "Санвузлова тумба",
  wall_unit: "Стінка",
  projectStartPremiumBadge: "Business",
  projectStartPremiumDescription:
    "Business-старт: шаблони, скан, PDF та розширені сценарії імпорту для більших робочих процесів.",
  projectStartPremiumOnly: "Business-старт доступний для Premium-користувачів та адміна.",
  projectStartPremiumTitle: "Business старт",
  projectTemplateBathroomShelfDescription: "Компактна санвузлова полка з малою глибиною та вертикальним зберіганням.",
  projectTemplateBathroomShelfTitle: "Санвузлова полка",
  projectTemplateBathroomVanityDescription: "Тумба для санвузла з корпусом, фасадом і базовими параметрами.",
  projectTemplateBathroomVanityTitle: "Санвузлова тумба",
  projectTemplateKitchenDescription: "Базовий кухонний модуль з робочою висотою та глибиною стільниці.",
  projectTemplateKitchenTitle: "Кухня",
  projectTemplateWallUnitDescription: "Стінка для кімнати з широким корпусом і зонами зберігання.",
  projectTemplateWallUnitTitle: "Стінка",
});

Object.assign(TRANSLATIONS.en, {
  landingProductTitle: "One system for sales, design, and production",
  landingProductDescription:
    "The product is structured as a shared operating environment instead of disconnected tools.",
  landingProductCardOneTitle: "Telegram bot",
  landingProductCardOneDescription:
    "Fast guided input for dimensions, materials, drawers, fittings, and profile data.",
  landingProductCardTwoTitle: "Web workspace",
  landingProductCardTwoDescription:
    "Projects, catalogs, production prep, and material logic in one practical interface.",
  landingProductCardThreeTitle: "Backend and shared data",
  landingProductCardThreeDescription:
    "Unified roles, catalogs, counts, and future-ready integration points for scaling.",
  landingVisualTitle: "Design language and technical identity",
  landingVisualDescription:
    "A darker premium shell, precise information blocks, and a calm technical rhythm closer to modern product sites.",
  landingVisualCaptionOne: "Graphite product shell",
  landingVisualCaptionTwo: "Green system accent",
  landingVisualCaptionThree: "Catalog-first interface",
});

Object.assign(TRANSLATIONS.uk, {
  landingProductTitle: "\u0404\u0434\u0438\u043d\u0430 \u0441\u0438\u0441\u0442\u0435\u043c\u0430 \u0434\u043b\u044f \u043f\u0440\u043e\u0434\u0430\u0436\u0443, \u043a\u043e\u043d\u0441\u0442\u0440\u0443\u043a\u0442\u043e\u0440\u0430 \u0456 \u0432\u0438\u0440\u043e\u0431\u043d\u0438\u0446\u0442\u0432\u0430",
  landingProductDescription:
    "\u041f\u0440\u043e\u0434\u0443\u043a\u0442 \u043f\u043e\u0431\u0443\u0434\u043e\u0432\u0430\u043d\u0438\u0439 \u044f\u043a \u0441\u043f\u0456\u043b\u044c\u043d\u0435 \u0440\u043e\u0431\u043e\u0447\u0435 \u0441\u0435\u0440\u0435\u0434\u043e\u0432\u0438\u0449\u0435, \u0430 \u043d\u0435 \u044f\u043a \u043d\u0430\u0431\u0456\u0440 \u0440\u043e\u0437\u0456\u0440\u0432\u0430\u043d\u0438\u0445 \u0456\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u0456\u0432.",
  landingProductCardOneTitle: "Telegram \u0431\u043e\u0442",
  landingProductCardOneDescription:
    "\u0428\u0432\u0438\u0434\u043a\u0438\u0439 \u0441\u0446\u0435\u043d\u0430\u0440\u0456\u0439 \u0432\u0432\u043e\u0434\u0443 \u0433\u0430\u0431\u0430\u0440\u0438\u0442\u0456\u0432, \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0456\u0432, \u0448\u0443\u0445\u043b\u044f\u0434 \u0442\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438.",
  landingProductCardTwoTitle: "\u0412\u0435\u0431-\u0441\u0438\u0441\u0442\u0435\u043c\u0430",
  landingProductCardTwoDescription:
    "\u041f\u0440\u043e\u0454\u043a\u0442\u0438, \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0438, \u043f\u0456\u0434\u0433\u043e\u0442\u043e\u0432\u043a\u0430 \u0432\u0438\u0440\u043e\u0431\u043d\u0438\u0446\u0442\u0432\u0430 \u0442\u0430 \u043b\u043e\u0433\u0456\u043a\u0430 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0456\u0432 \u0432 \u043e\u0434\u043d\u043e\u043c\u0443 \u0456\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441\u0456.",
  landingProductCardThreeTitle: "Backend \u0456 \u0441\u043f\u0456\u043b\u044c\u043d\u0456 \u0434\u0430\u043d\u0456",
  landingProductCardThreeDescription:
    "\u0404\u0434\u0438\u043d\u0456 \u0440\u043e\u043b\u0456, \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0438, \u043b\u0456\u0447\u0438\u043b\u044c\u043d\u0438\u043a\u0438 \u0442\u0430 \u0442\u043e\u0447\u043a\u0438 \u0456\u043d\u0442\u0435\u0433\u0440\u0430\u0446\u0456\u0439 \u0434\u043b\u044f \u043f\u043e\u0434\u0430\u043b\u044c\u0448\u043e\u0433\u043e \u043c\u0430\u0441\u0448\u0442\u0430\u0431\u0443.",
  landingVisualTitle: "\u0412\u0456\u0437\u0443\u0430\u043b\u044c\u043d\u0430 \u043c\u043e\u0432\u0430 \u0442\u0430 \u0442\u0435\u0445\u043d\u0456\u0447\u043d\u0430 \u0456\u0434\u0435\u043d\u0442\u0438\u043a\u0430",
  landingVisualDescription:
    "\u0422\u0435\u043c\u043d\u0438\u0439 premium-\u043a\u0430\u0440\u043a\u0430\u0441, \u0442\u043e\u0447\u043d\u0456 \u0456\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0456\u0439\u043d\u0456 \u0431\u043b\u043e\u043a\u0438 \u0442\u0430 \u0441\u043f\u043e\u043a\u0456\u0439\u043d\u0438\u0439 \u0442\u0435\u0445\u043d\u0456\u0447\u043d\u0438\u0439 \u0440\u0438\u0442\u043c \u0443 \u0441\u0442\u0438\u043b\u0456 \u0441\u0443\u0447\u0430\u0441\u043d\u0438\u0445 product-site.",
  landingVisualCaptionOne: "\u0413\u0440\u0430\u0444\u0456\u0442\u043e\u0432\u0430 \u043e\u0431\u043e\u043b\u043e\u043d\u043a\u0430",
  landingVisualCaptionTwo: "\u0417\u0435\u043b\u0435\u043d\u0438\u0439 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u0438\u0439 \u0430\u043a\u0446\u0435\u043d\u0442",
  landingVisualCaptionThree: "\u041a\u0430\u0442\u0430\u043b\u043e\u0436\u043d\u0430 \u043b\u043e\u0433\u0456\u043a\u0430 \u0456\u043d\u0442\u0435\u0440\u0444\u0435\u0439\u0441\u0443",
});

function buildProjectPayload(form) {
  const normalizeText = (value) => {
    const trimmed = String(value || "").trim();
    return trimmed || null;
  };

  const drawerConfig = String(form.drawers || "")
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);

  return {
    metadata: {
      name: normalizeText(form.projectName),
      type: normalizeText(form.projectType),
      client: normalizeText(form.clientName),
      room: normalizeText(form.roomName),
      notes: normalizeText(form.notes),
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
      config: drawerConfig,
    },
    materials: {
      facade: normalizeText(form.facadeMaterial),
      inside: normalizeText(form.insideMaterial),
      edge_banding: normalizeText(form.edgeBanding),
      thickness: form.materialThickness ? Number(form.materialThickness) : null,
    },
    fittings: {
      slide_type: normalizeText(form.slideType),
      bottom_type: normalizeText(form.bottomType),
      handle_type: normalizeText(form.handleType),
      handle_position: normalizeText(form.handlePosition),
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

const EDGE_SIDES = ["top", "right", "bottom", "left"];

function getEdgeValue(part, side) {
  return part?.[`edge_${side}`] || "";
}

function getEdgeThickness(material) {
  if (!material || material === "not_set") {
    return null;
  }

  const normalized = String(material).replace(",", ".").replaceAll("_", ".");
  const match = normalized.match(/(\d+(?:\.\d+)?)/);

  if (!match) {
    return null;
  }

  const value = Number(match[1]);
  return Number.isFinite(value) ? value : null;
}

function getEdgeColor(material) {
  const thickness = getEdgeThickness(material);

  if (thickness === null) {
    return "#f47b20";
  }

  if (thickness <= 0.6) {
    return "#078000";
  }

  if (thickness <= 0.8) {
    return "#ff7300";
  }

  if (thickness <= 1) {
    return "#b7dce8";
  }

  if (thickness < 2) {
    return "#0b1cff";
  }

  return "#7a0b80";
}

function getEdgeLabel(side, t) {
  return t[side] || side;
}

function validateEdgeValue(value, edgeBandings, t) {
  if (!value) {
    return "";
  }

  if (!edgeBandings.includes(value)) {
    return t.edgeBandingInvalid;
  }

  if (getEdgeThickness(value) === null) {
    return t.edgeThicknessInvalid;
  }

  return "";
}

function validatePartEdges(part, edgeBandings, t) {
  for (const side of EDGE_SIDES) {
    const value = getEdgeValue(part, side);
    const error = validateEdgeValue(value, edgeBandings, t);

    if (error) {
      return `${getEdgeLabel(side, t)}: ${error}`;
    }
  }

  return "";
}

function PartPreview({ detail, onSelectEdge, selectedEdgeSide, t }) {
  if (!detail?.part) {
    return null;
  }

  const { part } = detail;
  const [previewMode, setPreviewMode] = useState("3d");
  const [rotation, setRotation] = useState(28);
  const viewWidth = 720;
  const viewHeight = 450;
  const marginX = 112;
  const marginTop = 84;
  const marginBottom = 118;
  const scale = Math.min(
    (viewWidth - marginX * 2) / part.width,
    (viewHeight - marginTop - marginBottom) / part.height,
  );
  const width = part.width * scale;
  const height = part.height * scale;
  const x = (viewWidth - width) / 2;
  const y = marginTop + (viewHeight - marginTop - marginBottom - height) / 2;
  const edgeStripSize = 18;
  const edgeGap = 12;
  const legendY = viewHeight - 38;

  function pxX(value) {
    return x + value * scale;
  }

  function pxY(value) {
    return y + height - value * scale;
  }

  function clampRotation(nextRotation) {
    return Math.max(-60, Math.min(60, nextRotation));
  }

  function getEdgeRect(side) {
    if (side === "top") {
      return {
        height: edgeStripSize,
        width,
        x,
        y: y - edgeGap - edgeStripSize,
      };
    }

    if (side === "bottom") {
      return {
        height: edgeStripSize,
        width,
        x,
        y: y + height + edgeGap,
      };
    }

    if (side === "left") {
      return {
        height,
        width: edgeStripSize,
        x: x - edgeGap - edgeStripSize,
        y,
      };
    }

    return {
      height,
      width: edgeStripSize,
      x: x + width + edgeGap,
      y,
    };
  }

  function edgeStrip(side, material) {
    const rect = getEdgeRect(side);
    const hasMaterial = Boolean(material && material !== "not_set");
    const isSelected = selectedEdgeSide === side;

    return (
      <g key={side}>
        {hasMaterial ? (
          <rect
            className="part-edge-strip"
            fill={getEdgeColor(material)}
            {...rect}
          />
        ) : (
          <rect className="part-edge-guide" {...rect} />
        )}
        <rect
          aria-label={`${t.edgeSelectedSide}: ${getEdgeLabel(side, t)}`}
          className={`part-edge-hitbox${isSelected ? " selected" : ""}`}
          fill="transparent"
          onClick={() => onSelectEdge?.(side)}
          role={onSelectEdge ? "button" : undefined}
          stroke="transparent"
          tabIndex={onSelectEdge ? 0 : undefined}
          {...rect}
        />
      </g>
    );
  }

  function pointsToString(points) {
    return points.map((point) => point.join(",")).join(" ");
  }

  function render3dFace() {
    const faceWidth = Math.min(300, viewWidth - 260);
    const faceHeight = Math.min(220, viewHeight - 190);
    const faceX = (viewWidth - faceWidth) / 2 - 12;
    const faceY = 112;
    const depthOffset = 56;
    const angle = (rotation * Math.PI) / 180;
    const dx = Math.sin(angle) * depthOffset;
    const dy = Math.cos(angle) * depthOffset * 0.52;
    const topLeft = [faceX, faceY];
    const topRight = [faceX + faceWidth, faceY];
    const bottomLeft = [faceX, faceY + faceHeight];
    const bottomRight = [faceX + faceWidth, faceY + faceHeight];
    const backTopLeft = [faceX + dx, faceY - dy];
    const backTopRight = [faceX + faceWidth + dx, faceY - dy];
    const backBottomLeft = [faceX + dx, faceY + faceHeight - dy];
    const backBottomRight = [faceX + faceWidth + dx, faceY + faceHeight - dy];

    function edgeBand(side, color) {
      if (!color) {
        return null;
      }

      const bandStyle = {
        fill: color,
        stroke: "rgba(13, 20, 26, 0.75)",
        strokeWidth: 1,
      };

      if (side === "top") {
        return (
          <polygon
            {...bandStyle}
            key={side}
            points={pointsToString([topLeft, topRight, backTopRight, backTopLeft])}
          />
        );
      }

      if (side === "bottom") {
        return (
          <polygon
            {...bandStyle}
            key={side}
            opacity="0.92"
            points={pointsToString([bottomLeft, bottomRight, backBottomRight, backBottomLeft])}
          />
        );
      }

      if (side === "left") {
        return (
          <polygon
            {...bandStyle}
            key={side}
            opacity="0.96"
            points={pointsToString([topLeft, bottomLeft, backBottomLeft, backTopLeft])}
          />
        );
      }

      return (
        <polygon
          {...bandStyle}
          key={side}
          opacity="0.96"
          points={pointsToString([topRight, bottomRight, backBottomRight, backTopRight])}
        />
      );
    }

    return (
      <>
        <defs>
          <linearGradient id="panel-front-gradient-app" x1="0%" x2="0%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#fbfdfe" />
            <stop offset="100%" stopColor="#d8e2e8" />
          </linearGradient>
          <linearGradient id="panel-top-gradient-app" x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#f7fbfd" />
            <stop offset="100%" stopColor="#bcc8d1" />
          </linearGradient>
          <linearGradient id="panel-side-gradient-app" x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#cbd6de" />
            <stop offset="100%" stopColor="#a8b6bf" />
          </linearGradient>
          <filter id="panel-shadow-app" colorInterpolationFilters="sRGB" height="160%" width="160%" x="-30%" y="-30%">
            <feDropShadow dx="0" dy="10" floodColor="rgba(13,20,26,0.18)" stdDeviation="10" />
          </filter>
        </defs>
        <ellipse className="part-3d-shadow" cx={viewWidth / 2} cy={faceY + faceHeight + 56} rx={faceWidth * 0.42} ry="24" />
        <g filter="url(#panel-shadow-app)">
          <polygon
            className="part-3d-face part-3d-top"
            fill="url(#panel-top-gradient-app)"
            points={pointsToString([topLeft, topRight, backTopRight, backTopLeft])}
          />
          {dx >= 0 ? (
            <polygon
              className="part-3d-face part-3d-side"
              fill="url(#panel-side-gradient-app)"
              points={pointsToString([topRight, bottomRight, backBottomRight, backTopRight])}
            />
          ) : (
            <polygon
              className="part-3d-face part-3d-side"
              fill="url(#panel-side-gradient-app)"
              points={pointsToString([topLeft, bottomLeft, backBottomLeft, backTopLeft])}
            />
          )}
          <rect
            className="part-board"
            fill="url(#panel-front-gradient-app)"
            height={faceHeight}
            rx="2"
            width={faceWidth}
            x={faceX}
            y={faceY}
          />
          {edgeBand("top", getEdgeColor(part.edge_top))}
          {edgeBand("bottom", getEdgeColor(part.edge_bottom))}
          {edgeBand("left", getEdgeColor(part.edge_left))}
          {edgeBand("right", getEdgeColor(part.edge_right))}
        </g>
        <text className="part-3d-dimension width" textAnchor="middle" x={viewWidth / 2} y={74}>
          {part.width}
        </text>
        <text
          className="part-3d-dimension height"
          textAnchor="middle"
          transform={`translate(${faceX + faceWidth + 92} ${faceY + faceHeight / 2}) rotate(-90)`}
        >
          {part.height}
        </text>
        <text className="part-3d-meta" textAnchor="middle" x={viewWidth / 2} y={viewHeight - 42}>
          {part.part_name} ? {part.width} x {part.height} x {part.thickness}
        </text>
        <text className="part-3d-note" textAnchor="middle" x={viewWidth / 2} y={viewHeight - 18}>
          {t.preview3dHint}
        </text>
      </>
    );
  }

  function render2dPreview() {
    return (
      <>
        <defs>
          <marker id="dimension-arrow" markerHeight="10" markerWidth="10" orient="auto" refX="9" refY="5">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#111827" />
          </marker>
          <marker id="dimension-arrow-start" markerHeight="10" markerWidth="10" orient="auto-start-reverse" refX="1" refY="5">
            <path d="M 10 0 L 0 5 L 10 10 z" fill="#111827" />
          </marker>
          <marker id="axis-arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4">
            <path d="M 0 0 L 8 4 L 0 8 z" fill="#7f8790" />
          </marker>
        </defs>
        {edgeStrip("top", part.edge_top)}
        {edgeStrip("bottom", part.edge_bottom)}
        {edgeStrip("left", part.edge_left)}
        {edgeStrip("right", part.edge_right)}
        <rect className="part-board" height={height} width={width} x={x} y={y} />
        <line
          className="dimension-line"
          markerEnd="url(#dimension-arrow)"
          markerStart="url(#dimension-arrow-start)"
          x1={x}
          x2={x + width}
          y1={y - 38}
          y2={y - 38}
        />
        <line className="dimension-line" x1={x} x2={x} y1={y - 42} y2={y - 12} />
        <line className="dimension-line" x1={x + width} x2={x + width} y1={y - 42} y2={y - 12} />
        <text className="dimension-text" textAnchor="middle" x={viewWidth / 2} y={y - 48}>
          {part.width}
        </text>
        <line
          className="dimension-line"
          markerEnd="url(#dimension-arrow)"
          markerStart="url(#dimension-arrow-start)"
          x1={x + width + 46}
          x2={x + width + 46}
          y1={y}
          y2={y + height}
        />
        <line className="dimension-line" x1={x + width + 16} x2={x + width + 44} y1={y} y2={y} />
        <line className="dimension-line" x1={x + width + 16} x2={x + width + 44} y1={y + height} y2={y + height} />
        <text
          className="dimension-text rotated"
          textAnchor="middle"
          transform={`translate(${x + width + 78} ${y + height / 2}) rotate(-90)`}
        >
          {part.height}
        </text>
        <g className="grain-direction" transform={`translate(${x + width / 2 - 18} ${y + height / 2 - 12})`}>
          <line x1="0" x2="36" y1="0" y2="0" />
          <line x1="0" x2="36" y1="10" y2="10" />
          <line x1="0" x2="36" y1="20" y2="20" />
        </g>
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
        <g className="coordinate-axis" transform={`translate(${x - 78} ${y + height + 82})`}>
          <line markerEnd="url(#axis-arrow)" x1="0" x2="96" y1="0" y2="0" />
          <line markerEnd="url(#axis-arrow)" x1="0" x2="0" y1="0" y2="-96" />
          <text x="104" y="9">X</text>
          <text x="8" y="-104">Y</text>
        </g>
        <g className="part-legend" transform={`translate(34 ${legendY})`}>
          <rect className="legend-swatch" fill="#078000" height="18" width="22" x="0" y="-14" />
          <text x="30" y="0">≤ 0.6 мм</text>
          <rect className="legend-swatch" fill="#ff7300" height="18" width="22" x="98" y="-14" />
          <text x="128" y="0">≤ 0.8 мм</text>
          <rect className="legend-swatch" fill="#b7dce8" height="18" width="22" x="196" y="-14" />
          <text x="226" y="0">≤ 1.0 мм</text>
          <rect className="legend-swatch" fill="#0b1cff" height="18" width="22" x="294" y="-14" />
          <text x="324" y="0">&lt; 2.0 мм</text>
          <rect className="legend-swatch" fill="#7a0b80" height="18" width="22" x="392" y="-14" />
          <text x="422" y="0">= 2.0 мм</text>
          <rect className="legend-swatch" fill="#f3b300" height="18" width="22" x="490" y="-14" />
          <line className="legend-facade-line" x1="490" x2="512" y1="-5" y2="-5" />
          <text x="520" y="0">з фаскою 45</text>
          <g className="legend-grain" transform="translate(615 -11)">
            <line x1="0" x2="24" y1="0" y2="0" />
            <line x1="0" x2="24" y1="7" y2="7" />
            <line x1="0" x2="24" y1="14" y2="14" />
          </g>
        </g>
      </>
    );
  }

  return (    <div className="part-preview-shell">
      <div className="part-preview-toolbar">
        <div className="preview-mode-toggle">
          <button
            className={previewMode === "2d" ? "active" : ""}
            onClick={() => setPreviewMode("2d")}
            type="button"
          >
            {t.preview2d}
          </button>
          <button
            className={previewMode === "3d" ? "active" : ""}
            onClick={() => setPreviewMode("3d")}
            type="button"
          >
            {t.preview3d}
          </button>
        </div>
        {previewMode === "3d" ? (
          <div className="preview-rotation-controls">
            <button onClick={() => setRotation((value) => clampRotation(value - 12))} type="button">
              <ChevronLeft size={16} />
              {t.rotateLeft}
            </button>
            <button onClick={() => setRotation((value) => clampRotation(value + 12))} type="button">
              {t.rotateRight}
              <ChevronRight size={16} />
            </button>
            <button onClick={() => setRotation(28)} type="button">
              <RotateCcw size={16} />
              {t.resetView}
            </button>
          </div>
        ) : null}
      </div>
      {previewMode === "3d" ? (
        <Suspense fallback={<div className="part-three-viewer part-three-viewer-loading">Loading 3D viewer...</div>}>
          <PartThreeViewer
            detail={detail}
            onSelectEdge={onSelectEdge}
            rotation={rotation}
            selectedEdgeSide={selectedEdgeSide}
            t={t}
          />
        </Suspense>
      ) : (
        <svg className="part-preview" role="img" viewBox={`0 0 ${viewWidth} ${viewHeight}`}>
          {render2dPreview()}
        </svg>
      )}
    </div>  );
}

function PartEdgeEditor({
  detail,
  disabled,
  edgeBandings,
  loading,
  onChange,
  onSelectSide,
  onSave,
  selectedEdgeSide,
  t,
}) {
  if (!detail?.part) {
    return null;
  }
  const selectedValue = selectedEdgeSide
    ? getEdgeValue(detail.part, selectedEdgeSide)
    : "";
  const validationMessage = selectedEdgeSide
    ? validateEdgeValue(selectedValue, edgeBandings, t)
    : "";

  return (
    <section className="edge-editor-panel">
      <div className="edge-editor-header">
        <strong>{t.edgeEditor}</strong>
        <span>{t.edgeEditorDescription}</span>
      </div>
      <div className="edge-quick-editor">
        <div className="edge-side-pills">
          {EDGE_SIDES.map((side) => (
            <button
              className={selectedEdgeSide === side ? "active" : ""}
              disabled={disabled || loading}
              key={side}
              onClick={() => onSelectSide(side)}
              type="button"
            >
              {getEdgeLabel(side, t)}
            </button>
          ))}
        </div>
        {selectedEdgeSide ? (
          <div className="edge-quick-row">
            <strong>{t.edgeSelectedSide}: {getEdgeLabel(selectedEdgeSide, t)}</strong>
            <div className="edge-quick-actions">
              <select
                disabled={disabled || loading}
                onChange={(event) => onChange(selectedEdgeSide, event.target.value)}
                value={selectedValue}
              >
                <option value="">{t.notSet}</option>
                {edgeBandings.map((edgeBanding) => (
                  <option key={edgeBanding} value={edgeBanding}>
                    {edgeBanding}
                  </option>
                ))}
              </select>
              <button
                className="ghost-button"
                disabled={disabled || loading}
                onClick={() => onChange(selectedEdgeSide, "")}
                type="button"
              >
                {t.clearEdge}
              </button>
            </div>
          </div>
        ) : (
          <p className="edge-helper-text">{t.edgeSelectSide}</p>
        )}
        {validationMessage ? (
          <p className="edge-validation-message">{validationMessage}</p>
        ) : null}
      </div>
      <div className="edge-editor-grid">
        {EDGE_SIDES.map((side) => (
          <label
            className={`edge-editor-row${selectedEdgeSide === side ? " active" : ""}`}
            key={side}
            onClick={() => onSelectSide(side)}
          >
            <span className={`edge-side-icon ${side}`} aria-hidden="true" />
            <span>{getEdgeLabel(side, t)}</span>
            <select
              disabled={disabled || loading}
              onClick={() => onSelectSide(side)}
              onChange={(event) => onChange(side, event.target.value)}
              value={getEdgeValue(detail.part, side)}
            >
              <option value="">{t.notSet}</option>
              {edgeBandings.map((edgeBanding) => (
                <option key={edgeBanding} value={edgeBanding}>
                  {edgeBanding}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <button
        className="primary-button wide-button"
        disabled={disabled || loading}
        onClick={onSave}
        type="button"
      >
        <Save size={18} />
        {t.saveProject}
      </button>
    </section>
  );
}

function PartMachiningEditor({
  detail,
  disabled,
  loading,
  onAdd,
  onChange,
  onRemove,
  onSave,
  t,
}) {
  if (!detail?.part) {
    return null;
  }

  function renderRows(kind, rows, fields) {
    return (
      <section>
        <div className="machining-editor-heading">
          <h4>
            {kind === "holes" ? t.productionHoles : kind === "grooves" ? t.productionGrooves : t.productionQuarters} {rows.length}
          </h4>
          <button
            className="ghost-button compact-button"
            disabled={disabled || loading}
            onClick={() => onAdd(kind)}
            type="button"
          >
            <Plus size={14} />
            {kind === "holes" ? t.machiningAddHole : kind === "grooves" ? t.machiningAddGroove : t.machiningAddQuarter}
          </button>
        </div>
        <table className="machining-editor-table">
          <thead>
            <tr>
              <th>#</th>
              {fields.map((field) => (
                <th key={field}>{field.toUpperCase()}</th>
              ))}
              <th>{t.action || ""}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${kind}-${index}`}>
                <td>{index + 1}</td>
                {fields.map((field) => (
                  <td key={field}>
                    <input
                      disabled={disabled || loading}
                      onChange={(event) => onChange(kind, index, field, event.target.value)}
                      type={["side", "origin", "type"].includes(field) ? "text" : "number"}
                      value={row[field] ?? ""}
                    />
                  </td>
                ))}
                <td>
                  <button
                    className="icon-button danger-icon"
                    disabled={disabled || loading}
                    onClick={() => onRemove(kind, index)}
                    type="button"
                  >
                    x
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    );
  }

  return (
    <section className="machining-editor-panel">
      <div className="edge-editor-header">
        <strong>{t.machiningEditor}</strong>
        <span>{t.detailViewer}</span>
      </div>
      {renderRows("holes", detail.holes, ["side", "x", "y", "diameter", "depth", "type"])}
      {renderRows("grooves", detail.grooves, ["side", "x", "y", "length", "width", "depth", "type"])}
      {renderRows("quarters", detail.quarters, ["side", "x", "y", "length", "width", "depth", "radius", "type"])}
      <button
        className="primary-button wide-button"
        disabled={disabled || loading}
        onClick={onSave}
        type="button"
      >
        <Save size={18} />
        {t.saveProject}
      </button>
    </section>
  );
}

function PartDetailWorkspace({
  canEdit,
  detail,
  edgeBandings,
  loading,
  onAddMachining,
  onBack,
  onEdgeChange,
  onEdgeSelect,
  onMachiningChange,
  onRemoveMachining,
  onSaveEdges,
  onSaveMachining,
  selectedEdgeSide,
  t,
}) {
  if (!detail?.part) {
    return null;
  }

  return (
    <section className="part-workspace">
      <div className="part-workspace-header">
        <div>
          <p className="eyebrow">{t.productionPartWorkspace}</p>
          <h3>{detail.part.part_name}</h3>
          <strong className="part-title">
            {detail.part.export_code} / {detail.part.width} x {detail.part.height} x {detail.part.thickness}
          </strong>
        </div>
        <button className="ghost-button" onClick={onBack} type="button">
          <ChevronLeft size={18} />
          {t.productionPartBack}
        </button>
      </div>

      <div className="part-workspace-grid">
        <div className="part-workspace-preview">
          <PartPreview
            detail={detail}
            onSelectEdge={onEdgeSelect}
            selectedEdgeSide={selectedEdgeSide}
            t={t}
          />
        </div>
        <div className="part-workspace-side">
          <PartEdgeEditor
            detail={detail}
            disabled={!canEdit}
            edgeBandings={edgeBandings}
            loading={loading}
            onChange={onEdgeChange}
            onSelectSide={onEdgeSelect}
            onSave={onSaveEdges}
            selectedEdgeSide={selectedEdgeSide}
            t={t}
          />
          <div className="part-operation-tables">
            <section>
              <h4>{t.productionHoles} {detail.holes.length}</h4>
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{t.bomCategory}</th>
                    <th>X</th>
                    <th>Y</th>
                    <th>{t.bomThickness}</th>
                    <th>D</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.holes.map((hole) => (
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
              <h4>{t.productionGrooves} {detail.grooves.length}</h4>
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{t.bomCategory}</th>
                    <th>X</th>
                    <th>Y</th>
                    <th>{t.cuttingLength}</th>
                    <th>{t.bomThickness}</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.grooves.map((groove) => (
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
              <h4>{t.productionQuarters} {detail.quarters.length}</h4>
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{t.bomCategory}</th>
                    <th>{t.cuttingLength}</th>
                    <th>{t.cuttingSize}</th>
                    <th>{t.bomThickness}</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.quarters.map((quarter) => (
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
        </div>
      </div>

      <PartMachiningEditor
        detail={detail}
        disabled={!canEdit}
        loading={loading}
        onAdd={onAddMachining}
        onChange={onMachiningChange}
        onRemove={onRemoveMachining}
        onSave={onSaveMachining}
        t={t}
      />
    </section>
  );
}

export default function App() {
  useLayoutEffect(() => {
    const previousScrollRestoration = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    window.scrollTo(0, 0);
    const frameId = window.requestAnimationFrame(() => window.scrollTo(0, 0));

    return () => {
      window.cancelAnimationFrame(frameId);
      window.history.scrollRestoration = previousScrollRestoration;
    };
  }, []);

  const [language, setLanguage] = useState(
    () => localStorage.getItem(LANGUAGE_STORAGE_KEY) || "uk",
  );
  const [token, setToken] = useState(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) || "",
  );
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authMode, setAuthMode] = useState("login");
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [publicProfileMenuOpen, setPublicProfileMenuOpen] = useState(false);
  const [trialClockNow, setTrialClockNow] = useState(() => Date.now());
  const trialRefreshTriggeredRef = useRef(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [showOwnCurrentPassword, setShowOwnCurrentPassword] = useState(false);
  const [showOwnNewPassword, setShowOwnNewPassword] = useState(false);
  const [resetPasswordEmail, setResetPasswordEmail] = useState("");
  const [registrationStep, setRegistrationStep] = useState(1);
  const [registrationChallengeId, setRegistrationChallengeId] = useState(null);
  const [registrationTelegramStatusToken, setRegistrationTelegramStatusToken] = useState("");
  const [registrationTelegramConfirmationUrl, setRegistrationTelegramConfirmationUrl] = useState("");
  const [registrationTelegramWaiting, setRegistrationTelegramWaiting] = useState(false);
  const [registrationTelegramStartedAt, setRegistrationTelegramStartedAt] = useState(0);
  const [registerForm, setRegisterForm] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    phone: "",
    confirmationCode: "",
  });
  const [registrationStartResponse, setRegistrationStartResponse] = useState(null);
  const [publicOverview, setPublicOverview] = useState({
    registration_enabled: true,
    stats: {
      projects_total: 0,
      materials_total: 0,
      fittings_total: 0,
      users_total: 0,
    },
  });
  const [ownProfileForm, setOwnProfileForm] = useState({
    username: "",
    phone: "",
    city: "",
  });
  const [emailChangeForm, setEmailChangeForm] = useState({
    newEmail: "",
  });
  const [ownPasswordForm, setOwnPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
  });
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [bomItems, setBomItems] = useState([]);
  const [cuttingItems, setCuttingItems] = useState([]);
  const [cuttingAssembly, setCuttingAssembly] = useState({});
  const [cuttingSummary, setCuttingSummary] = useState(null);
  const [cuttingExportFormats, setCuttingExportFormats] = useState([]);
  const [cuttingJsonExport, setCuttingJsonExport] = useState(null);
  const [selectedPartDetail, setSelectedPartDetail] = useState(null);
  const [selectedCuttingPartCode, setSelectedCuttingPartCode] = useState(null);
  const [hoveredCuttingPartCode, setHoveredCuttingPartCode] = useState(null);
  const [collapsedCuttingGroups, setCollapsedCuttingGroups] = useState({});
  const [cuttingSearch, setCuttingSearch] = useState("");
  const [selectedEdgeSide, setSelectedEdgeSide] = useState(null);
  const [projectForm, setProjectForm] = useState(DEFAULT_PROJECT_FORM);
  const [projectStartMode, setProjectStartMode] = useState("templates");
  const [aiScanFile, setAiScanFile] = useState(null);
  const [aiScanResult, setAiScanResult] = useState(null);
  const [aiScanSession, setAiScanSession] = useState(null);
  const [aiScanHistory, setAiScanHistory] = useState([]);
  const [projectFilters, setProjectFilters] = useState(DEFAULT_PROJECT_FILTERS);
  const [specificationCatalog, setSpecificationCatalog] = useState(
    DEFAULT_SPECIFICATION_CATALOG,
  );
  const [activeView, setActiveView] = useState("projects");
  const [activeProjectTab, setActiveProjectTab] = useState("general");
  const [projectOverviewOpen, setProjectOverviewOpen] = useState(false);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [status, setStatusState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(
    () => (typeof window !== "undefined" ? window.matchMedia("(min-width: 981px)").matches : true),
  );
  const sidebarTouchState = useRef({
    active: false,
    startX: 0,
    startY: 0,
    endX: 0,
    endY: 0,
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const mediaQuery = window.matchMedia("(min-width: 981px)");
    const syncSidebarState = () => setIsSidebarOpen(mediaQuery.matches);

    syncSidebarState();

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", syncSidebarState);
      return () => mediaQuery.removeEventListener("change", syncSidebarState);
    }

    mediaQuery.addListener(syncSidebarState);
    return () => mediaQuery.removeListener(syncSidebarState);
  }, []);

  const t = TRANSLATIONS[language] || TRANSLATIONS.en;
  const tariffContent = TARIFF_CONTENT[language] || TARIFF_CONTENT.en;
  const canUseAiScan = user?.role === "admin" || user?.role === "premium" || user?.role === "pro";
  const canUsePremiumStart = user?.role === "admin" || user?.role === "premium";
  const userLoginName = user?.username || user?.email?.split("@")[0] || "";
  const userTierLabel = getSubscriptionLabel(user, language);
  const userCityLabel = user?.city || t.notSet;
  const trialCountdown = useMemo(
    () => buildTrialCountdown(user, trialClockNow),
    [trialClockNow, user],
  );
  const trialMessage = useMemo(
    () => formatTrialCountdown(trialCountdown, language),
    [language, trialCountdown],
  );

  useEffect(() => {
    if (!trialCountdown || trialCountdown.state !== "active") {
      return undefined;
    }

    setTrialClockNow(Date.now());
    const timerId = window.setInterval(() => {
      setTrialClockNow(Date.now());
    }, 60000);

    return () => window.clearInterval(timerId);
  }, [trialCountdown]);

  useEffect(() => {
    trialRefreshTriggeredRef.current = false;
  }, [user?.id, user?.effective_plan, user?.trial_ends_at]);

  useEffect(() => {
    if (
      !token ||
      !trialCountdown ||
      trialCountdown.state !== "expired" ||
      trialRefreshTriggeredRef.current
    ) {
      return undefined;
    }

    trialRefreshTriggeredRef.current = true;
    loadUser(token);
    return undefined;
  }, [token, trialCountdown, user?.effective_plan, user?.trial_ends_at]);

  useEffect(() => {
    if (
      !registrationTelegramWaiting ||
      !registrationTelegramStatusToken ||
      !registrationTelegramConfirmationUrl
    ) {
      return undefined;
    }

    let cancelled = false;
    const startedAt = registrationTelegramStartedAt || Date.now();
    const timeoutMs = 10 * 60 * 1000;

    const pollTelegramStatus = async () => {
      if (cancelled) {
        return;
      }

      if (Date.now() - startedAt >= timeoutMs) {
        setStatus({ message: t.registrationTelegramExpired, tone: "error" });
        resetRegistrationFlow(registerForm.email.trim());
        return;
      }

      const result = await getRegistrationTelegramStatus({
        status_token: registrationTelegramStatusToken,
      });

      if (cancelled) {
        return;
      }

      if (!result.success) {
        if (result.error === "Registration status not found") {
          setStatus({ message: t.registrationTelegramExpired, tone: "error" });
          resetRegistrationFlow(registerForm.email.trim());
        }
        return;
      }

      if (result.registration_status === "active" || result.challenge_status === "consumed") {
        finishRegistrationSuccess(result);
        return;
      }

      if (result.challenge_status === "expired" || result.challenge_status === "blocked") {
        setStatus({
          message: result.challenge_status === "expired"
            ? t.registrationTelegramExpired
            : t.registrationFailed,
          tone: "error",
        });
        resetRegistrationFlow(registerForm.email.trim());
      }
    };

    pollTelegramStatus();
    const timerId = window.setInterval(pollTelegramStatus, 2500);

    return () => {
      cancelled = true;
      window.clearInterval(timerId);
    };
  }, [
    finishRegistrationSuccess,
    registrationTelegramConfirmationUrl,
    registrationTelegramStartedAt,
    registrationTelegramStatusToken,
    registrationTelegramWaiting,
    registerForm.email,
    t,
  ]);

  function closeSidebarOnMobile() {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 980px)").matches) {
      setIsSidebarOpen(false);
    }
  }

  function handleSidebarTouchStart(event) {
    if (typeof window === "undefined" || event.touches.length !== 1) {
      return;
    }

    const target = event.target;
    if (target.closest("button, a, input, select, textarea, label")) {
      return;
    }

    const touch = event.touches[0];
    const isMobileViewport = window.matchMedia("(max-width: 980px)").matches;
    const edgeGestureAllowed = isSidebarOpen || touch.clientX <= 28;

    if (!isMobileViewport || !edgeGestureAllowed) {
      return;
    }

    sidebarTouchState.current = {
      active: true,
      startX: touch.clientX,
      startY: touch.clientY,
      endX: touch.clientX,
      endY: touch.clientY,
    };
  }

  function handleSidebarTouchMove(event) {
    if (!sidebarTouchState.current.active || event.touches.length !== 1) {
      return;
    }

    const touch = event.touches[0];
    sidebarTouchState.current.endX = touch.clientX;
    sidebarTouchState.current.endY = touch.clientY;
  }

  function finishSidebarGesture() {
    if (!sidebarTouchState.current.active) {
      return;
    }

    const deltaX = sidebarTouchState.current.endX - sidebarTouchState.current.startX;
    const deltaY = sidebarTouchState.current.endY - sidebarTouchState.current.startY;

    if (Math.abs(deltaX) > 48 && Math.abs(deltaX) > Math.abs(deltaY) * 1.2) {
      setIsSidebarOpen(deltaX > 0);
    }

    sidebarTouchState.current = {
      active: false,
      startX: 0,
      startY: 0,
      endX: 0,
      endY: 0,
    };
  }
  const inferStatusTone = useCallback((message) => {
    const normalizedMessage = String(message || "").toLowerCase();

    if (!normalizedMessage) {
      return "info";
    }

    if (
      /unable|failed|invalid|error|restricted|not found|�� �������|�������|����������|��������|�� ��������/.test(normalizedMessage)
    ) {
      return "error";
    }

    if (
      /saved|updated|created|connected|queued|synced|deleted|confirmed|requested|loaded from cache|applied|success|working|������|����|�����|������|����|�������|�����|������|������|����|�������/.test(normalizedMessage)
    ) {
      return "success";
    }

    return "info";
  }, []);
  const normalizeStatusPayload = useCallback(
    (value, previous = null) => {
      if (!value) {
        return null;
      }

      if (typeof value === "function") {
        const resolved = value(previous?.message || "");
        return normalizeStatusPayload(resolved, previous);
      }

      if (typeof value === "string") {
        const message = value.trim();
        return message ? { message, tone: inferStatusTone(message) } : null;
      }

      if (typeof value === "object") {
        const message = String(value.message || "").trim();
        if (!message) {
          return null;
        }

        return {
          message,
          tone: value.tone || inferStatusTone(message),
        };
      }

      return null;
    },
    [inferStatusTone],
  );
  const setStatus = useCallback((value) => {
    setStatusState((current) => normalizeStatusPayload(value, current));
  }, [normalizeStatusPayload]);
  const statusTone = status?.tone || "info";
  const statusMessage = status?.message || "";
  const StatusIcon =
    statusTone === "error" ? CircleAlert : statusTone === "success" ? CheckCircle2 : Info;
  const publicProfileMenuRef = useRef(null);
  const adminUrl = buildAdminUrl(ADMIN_BASE_URL, token);
  const canGoBack = offset > 0;
  const canGoForward = offset + PAGE_SIZE < total;
  const statusNotice = statusMessage ? (
    <button
      className="status-overlay"
      onClick={() => setStatus("")}
      type="button"
    >
      <span
        className={`status-toast ${statusTone}`}
        onClick={(event) => event.stopPropagation()}
        role="status"
      >
        <span className={`status-toast-icon ${statusTone}`}>
          <StatusIcon size={18} />
        </span>
        <span className="status-toast-copy">{statusMessage}</span>
        <span
          aria-label={t.close}
          className="status-toast-close"
          onClick={() => setStatus("")}
          role="button"
          tabIndex={0}
        >
          <X size={16} />
        </span>
      </span>
    </button>
  ) : null;
  const effectiveSelectedPartCode =
    selectedCuttingPartCode || selectedPartDetail?.part?.export_code || "";
  const hasProfileChanges =
    (ownProfileForm.username || "") !== (user?.username || "") ||
    (ownProfileForm.phone || "") !== (user?.phone || "") ||
    (ownProfileForm.city || "") !== (user?.city || "");
  const filteredCuttingItems = useMemo(() => {
    const normalizedQuery = cuttingSearch.trim().toLowerCase();

    if (!normalizedQuery) {
      return cuttingItems;
    }

    return cuttingItems.filter((item) =>
      String(item.part_name || "").toLowerCase().includes(normalizedQuery),
    );
  }, [cuttingItems, cuttingSearch]);
  const expandedCuttingItems = useMemo(
    () =>
      filteredCuttingItems.flatMap((item) => {
        const quantity = Math.max(Number(item.quantity) || 1, 1);

        return Array.from({ length: quantity }, (_, index) => ({
          ...item,
          row_key: `${item.export_code}-${index + 1}`,
          row_title:
            quantity > 1
              ? `${item.part_name} #${index + 1}`
              : item.part_name,
        }));
      }),
    [filteredCuttingItems],
  );
  const groupedCuttingItems = useMemo(() => {
    const groups = new Map();

    expandedCuttingItems.forEach((item) => {
      const materialName = item.material || t.notSet;

      if (!groups.has(materialName)) {
        groups.set(materialName, []);
      }

      groups.get(materialName).push(item);
    });

    return Array.from(groups.entries());
  }, [expandedCuttingItems, t]);
  const selectedCuttingItem = useMemo(
    () =>
      effectiveSelectedPartCode
        ? cuttingItems.find((item) => item.export_code === effectiveSelectedPartCode) || null
        : null,
    [cuttingItems, effectiveSelectedPartCode],
  );

  useEffect(() => {
    setProjectOverviewOpen(false);
  }, [selectedProject?.id]);
  useEffect(() => {
    setCollapsedCuttingGroups({});
  }, [selectedProject?.id]);
  useEffect(() => {
    setCuttingSearch("");
  }, [selectedProject?.id]);
  useEffect(() => {
    if (!effectiveSelectedPartCode || activeProjectTab !== "production") {
      return;
    }

    const row = document.querySelector(
      `[data-export-code="${effectiveSelectedPartCode}"]`,
    );

    if (row && typeof row.scrollIntoView === "function") {
      row.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [activeProjectTab, effectiveSelectedPartCode]);

  function toggleCuttingGroup(materialName) {
    setCollapsedCuttingGroups((current) => ({
      ...current,
      [materialName]: !current[materialName],
    }));
  }

  function collapseAllCuttingGroups() {
    setCollapsedCuttingGroups(
      groupedCuttingItems.reduce((accumulator, [materialName]) => {
        accumulator[materialName] = true;
        return accumulator;
      }, {}),
    );
  }

  function expandAllCuttingGroups() {
    setCollapsedCuttingGroups({});
  }

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

  function resetRegistrationFlow(prefillEmail = "") {
    setRegistrationStep(1);
    setRegistrationStartResponse(null);
    setRegistrationChallengeId(null);
    setRegistrationTelegramStatusToken("");
    setRegistrationTelegramConfirmationUrl("");
    setRegistrationTelegramWaiting(false);
    setRegistrationTelegramStartedAt(0);
    setRegisterForm({
      name: "",
      email: prefillEmail,
      password: "",
      confirmPassword: "",
      phone: "",
      confirmationCode: "",
    });
    setShowRegisterPassword(false);
  }

  function finishRegistrationSuccess(result) {
    const nextEmail = registerForm.email.trim();
    resetRegistrationFlow(nextEmail);
    setEmail(nextEmail);
    setPassword("");
    setAuthMode("login");
    setStatus({
      message: result.trial_granted
        ? t.registrationCompleteTrial
        : t.registrationCompleteFree,
      tone: "success",
    });
  }

  async function copyRegistrationCode(code) {
    const text = String(code || "").trim();
    if (!text || !navigator?.clipboard?.writeText) {
      return false;
    }

    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  }

  function scrollToAuthPanel() {
    setAuthModalOpen(true);
  }

  async function loadPublicOverview() {
    const result = await getPublicOverview();
    if (!result.success) {
      return;
    }

    setPublicOverview({
      registration_enabled: Boolean(result.registration_enabled),
      stats: {
        projects_total: Number(result.stats?.projects_total || 0),
        materials_total: Number(result.stats?.materials_total || 0),
        fittings_total: Number(result.stats?.fittings_total || 0),
        users_total: Number(result.stats?.users_total || 0),
      },
    });
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
    setOwnProfileForm({
      username: result.user?.username || "",
      phone: result.user?.phone || "",
      city: result.user?.city || "",
    });
  }

  async function loadSpecificationCatalog() {
    const result = await getSpecificationCatalog();

    if (!result.success) {
      return;
    }

    setSpecificationCatalog({
      project_types: normalizeProjectTypes(result.project_types),
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
    const [
      result,
      bomResult,
      cuttingResult,
      exportFormatsResult,
      jsonExportResult,
    ] = await Promise.all([
      getProject(token, projectId),
      getProjectBom(token, projectId),
      getProjectCutting(token, projectId),
      getCuttingExportFormats(token, projectId),
      getCuttingJsonExport(token, projectId),
    ]);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadProjects);
      return;
    }

    setSelectedProject(result.project);
    setBomItems(bomResult.success ? bomResult.items : []);
    setCuttingItems(cuttingResult.success ? cuttingResult.items : []);
    setCuttingAssembly(cuttingResult.success ? cuttingResult.assembly || {} : {});
    setCuttingSummary(cuttingResult.success ? cuttingResult.summary : null);
    setSelectedPartDetail(null);
    setSelectedEdgeSide(null);
    setCuttingExportFormats(
      exportFormatsResult.success ? exportFormatsResult.formats : [],
    );
    setCuttingJsonExport(jsonExportResult.success ? jsonExportResult.export : null);
    if (!bomResult.success) {
      setStatus(bomResult.error || t.unableToLoadBom);
    } else if (!cuttingResult.success) {
      setStatus(cuttingResult.error || t.unableToLoadCutting);
    } else if (!exportFormatsResult.success || !jsonExportResult.success) {
      setStatus(
        exportFormatsResult.error ||
          jsonExportResult.error ||
          t.unableToLoadExports,
      );
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
      setStatus({ message: result.error || t.loginFailed, tone: "error" });
      return;
    }

    localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    setToken(result.access_token);
    setUser(result.user);
    setAuthModalOpen(false);
    setPublicProfileMenuOpen(false);
    setWorkspaceOpen(false);
    setStatus("");
  }

  async function handleRegister(event) {
    event.preventDefault();

    if (registrationStep === 1) {
      if (!isValidRegistrationEmail(registerForm.email)) {
        setStatus({ message: t.registrationEmailInvalid, tone: "error" });
        return;
      }

      if (!isValidRegistrationPassword(registerForm.password)) {
        setStatus({ message: t.registrationPasswordTooShort, tone: "error" });
        return;
      }

      if (registerForm.password !== registerForm.confirmPassword) {
        setStatus({ message: t.passwordsDoNotMatch, tone: "error" });
        return;
      }

      setRegistrationStep(2);
      setStatus("");
      return;
    }

    if (registrationStep === 2) {
      if (!isValidRegistrationPhone(registerForm.phone)) {
        setStatus({ message: t.registrationPhoneInvalid, tone: "error" });
        return;
      }

      setLoading(true);
      const result = await startRegistration({
        name: registerForm.name.trim(),
        email: registerForm.email.trim(),
        password: registerForm.password,
        phone: registerForm.phone.trim(),
      });
      setLoading(false);

      if (!result.success) {
        setStatus({ message: result.error || t.registrationFailed, tone: "error" });
        return;
      }

      setRegistrationStartResponse(result);
      setRegistrationChallengeId(result.challenge_id || null);
      setRegistrationTelegramStatusToken(result.telegram_status_token || "");
      setRegistrationTelegramConfirmationUrl(result.telegram_confirmation_url || "");
      setRegistrationTelegramWaiting(false);
      setRegistrationTelegramStartedAt(0);
      setRegisterForm((current) => ({
        ...current,
        confirmationCode: result.debug_verification_code || "",
      }));
      setRegistrationStep(3);
      setStatus(
        result.debug_verification_code
          ? { message: t.registrationCodeAutofilled, tone: "success" }
          : result.telegram_confirmation_url
            ? { message: t.registrationTelegramCreated, tone: "info" }
            : { message: t.registrationCodeCreated, tone: "info" },
      );
      return;
    }

    if (registrationStep === 3) {
      if (registrationTelegramConfirmationUrl) {
        if (!registrationTelegramWaiting) {
          setRegistrationTelegramWaiting(true);
          setRegistrationTelegramStartedAt(Date.now());
          window.open(
            registrationTelegramConfirmationUrl,
            "_blank",
            "noopener,noreferrer",
          );
        }
        setStatus({ message: t.registrationTelegramWaiting, tone: "info" });
        return;
      }

      const confirmationCode = normalizeRegistrationCodeInput(registerForm.confirmationCode);
      if (!confirmationCode) {
        setStatus({ message: t.registrationCodeHint, tone: "error" });
        return;
      }

      if (!registrationChallengeId) {
        setStatus({ message: t.registrationFailed, tone: "error" });
        return;
      }

      setLoading(true);
      const result = await confirmRegistration({
        challenge_id: registrationChallengeId,
        code: confirmationCode,
      });
      setLoading(false);

      if (!result.success) {
        setStatus({ message: result.error || t.registrationFailed, tone: "error" });
        if (
          result.error === "Challenge expired" ||
          result.error === "Challenge not found" ||
          result.error === "Challenge is consumed" ||
          result.error === "Challenge is blocked" ||
          result.error === "User not found" ||
          result.error === "User registration is not pending"
        ) {
          resetRegistrationFlow(registerForm.email.trim());
        }
        return;
      }

      finishRegistrationSuccess(result);
    }
  }

  async function handlePasswordResetRequest(event) {
    event.preventDefault();
    setLoading(true);
    const result = await requestPasswordReset(resetPasswordEmail || email);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.passwordResetRequestFailed, tone: "error" });
      return;
    }

    setStatus({ message: t.passwordResetRequestSent, tone: "success" });
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken("");
    setUser(null);
    setAuthModalOpen(false);
    setPasswordModalOpen(false);
    setPublicProfileMenuOpen(false);
    setWorkspaceOpen(false);
    setEmail("");
    setPassword("");
    setOwnProfileForm({
      username: "",
      phone: "",
      city: "",
    });
    setEmailChangeForm({
      newEmail: "",
    });
    setOwnPasswordForm({
      currentPassword: "",
      newPassword: "",
    });
    setShowOwnCurrentPassword(false);
    setShowOwnNewPassword(false);
    resetRegistrationFlow();
    setProjects([]);
    setSelectedProject(null);
    setBomItems([]);
    setCuttingItems([]);
    setCuttingAssembly({});
    setCuttingSummary(null);
    setCuttingExportFormats([]);
    setCuttingJsonExport(null);
    setSelectedPartDetail(null);
    setSelectedCuttingPartCode(null);
    setSelectedEdgeSide(null);
    setActiveProjectTab("general");
    setStatus("");
  }

  async function handleOwnProfileSave(event) {
    event.preventDefault();

    const trimmedUsername = ownProfileForm.username.trim();
    const trimmedPhone = ownProfileForm.phone.trim();
    const trimmedCity = ownProfileForm.city.trim();

    setLoading(true);
    const result = await updateMyProfile(token, {
      username: trimmedUsername || null,
      phone: trimmedPhone || null,
      city: trimmedCity || null,
    });
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToUpdateProfile, tone: "error" });
      return;
    }

    setUser(result.user);
    setOwnProfileForm({
      username: result.user?.username || "",
      phone: result.user?.phone || "",
      city: result.user?.city || "",
    });
    setStatus({ message: t.profileUpdated, tone: "success" });
  }

  async function handleOwnEmailChangeRequest(event) {
    event.preventDefault();

    setLoading(true);
    const result = await createMyEmailChangeRequest(
      token,
      emailChangeForm.newEmail.trim(),
    );
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToRequestEmailChange, tone: "error" });
      return;
    }

    setEmailChangeForm({ newEmail: "" });
    setStatus({ message: t.emailChangeRequested, tone: "success" });
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
      setStatus({ message: result.error || t.unableToChangePassword, tone: "error" });
      return;
    }

    setOwnPasswordForm({
      currentPassword: "",
      newPassword: "",
    });
    setShowOwnCurrentPassword(false);
    setShowOwnNewPassword(false);
    setPasswordModalOpen(false);
    setStatus({ message: t.passwordChanged, tone: "success" });
  }

  async function handlePreviewCuttingPart(partCode) {
    setSelectedCuttingPartCode(partCode);
    setStatus("");

    if (!selectedProjectId || !partCode) {
      return;
    }

    const result = await getProjectPartDetail(token, selectedProjectId, partCode);

    if (!result.success) {
      return;
    }

    setSelectedPartDetail(result);
    setSelectedEdgeSide(null);
  }

  async function handleSelectCuttingPart(partCode = selectedCuttingPartCode) {
    if (!selectedProject) {
      return;
    }

    if (!partCode) {
      return;
    }

    const result = await getProjectPartDetail(
      token,
      selectedProject.id,
      partCode,
    );

    if (!result.success) {
      setStatus(result.error || t.unableToLoadPart);
      return;
    }

    setSelectedCuttingPartCode(partCode);
    setSelectedPartDetail(result);
    setSelectedEdgeSide(null);
    setActiveProjectTab("partDetail");
    setStatus("");
  }

  function handleClearCuttingPartSelection() {
    setSelectedCuttingPartCode(null);
    setHoveredCuttingPartCode(null);
    setStatus("");
  }

  function handlePartEdgeChange(side, value) {
    setSelectedPartDetail((current) => {
      if (!current?.part) {
        return current;
      }

      return {
        ...current,
        part: {
          ...current.part,
          [`edge_${side}`]: value || null,
        },
      };
    });
  }

  async function handleSavePartEdges() {
    if (!selectedProject?.id || !selectedPartDetail?.part) {
      return;
    }

    setLoading(true);
    const result = await updateProjectPartEdges(
      token,
      selectedProject.id,
      selectedPartDetail.part.export_code,
      {
        top: selectedPartDetail.part.edge_top || null,
        bottom: selectedPartDetail.part.edge_bottom || null,
        left: selectedPartDetail.part.edge_left || null,
        right: selectedPartDetail.part.edge_right || null,
      },
    );

    const [
      cuttingResult,
      jsonExportResult,
    ] = await Promise.all([
      getProjectCutting(token, selectedProject.id),
      getCuttingJsonExport(token, selectedProject.id),
    ]);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveEdges);
      return;
    }

    setSelectedPartDetail(result);
    if (cuttingResult.success) {
      setCuttingItems(cuttingResult.items || []);
      setCuttingAssembly(cuttingResult.assembly || {});
      setCuttingSummary(cuttingResult.summary || null);
    }
    if (jsonExportResult.success) {
      setCuttingJsonExport(jsonExportResult.export || null);
    }
    setStatus(t.edgeSaved);
  }

  function createMachiningRow(kind) {
    const nextNumber = (selectedPartDetail?.[kind]?.length || 0) + 1;

    if (kind === "holes") {
      return {
        number: nextNumber,
        side: "front",
        origin: "left_bottom",
        x: 0,
        y: 0,
        z: 0,
        diameter: 5,
        depth: selectedPartDetail?.part?.thickness || 18,
        type: "manual",
      };
    }

    if (kind === "grooves") {
      return {
        number: nextNumber,
        side: "front",
        origin: "left_bottom",
        x: 0,
        y: 0,
        depth: 8,
        width: 4,
        length: selectedPartDetail?.part?.width || 0,
        type: "manual",
      };
    }

    return {
      number: nextNumber,
      side: "bottom",
      origin: "left_bottom",
      x: 0,
      y: 0,
      depth: 2,
      width: 12,
      length: selectedPartDetail?.part?.width || 0,
      radius: 0,
      type: "manual",
    };
  }

  function handleAddMachiningRow(kind) {
    setSelectedPartDetail((current) => ({
      ...current,
      [kind]: [
        ...(current?.[kind] || []),
        createMachiningRow(kind),
      ],
    }));
  }

  function handleMachiningChange(kind, index, field, value) {
    setSelectedPartDetail((current) => ({
      ...current,
      [kind]: (current?.[kind] || []).map((row, rowIndex) => (
        rowIndex === index
          ? {
              ...row,
              [field]: ["side", "origin", "type"].includes(field) ? value : Number(value),
            }
          : row
      )),
    }));
  }

  function handleRemoveMachiningRow(kind, index) {
    setSelectedPartDetail((current) => ({
      ...current,
      [kind]: (current?.[kind] || [])
        .filter((_, rowIndex) => rowIndex !== index)
        .map((row, rowIndex) => ({
          ...row,
          number: rowIndex + 1,
        })),
    }));
  }

  async function handleSavePartMachining() {
    if (!selectedProject?.id || !selectedPartDetail?.part) {
      return;
    }

    setLoading(true);
    const result = await updateProjectPartMachining(
      token,
      selectedProject.id,
      selectedPartDetail.part.export_code,
      {
        holes: selectedPartDetail.holes || [],
        grooves: selectedPartDetail.grooves || [],
        quarters: selectedPartDetail.quarters || [],
      },
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveMachining);
      return;
    }

    setSelectedPartDetail(result);
    setStatus(t.machiningSaved);
  }

  function handleDownloadCuttingJson() {
    if (!selectedProject || !cuttingJsonExport) {
      return;
    }

    const blob = new Blob(
      [
        JSON.stringify(
          cuttingJsonExport,
          null,
          2,
        ),
      ],
      {
        type: "application/json",
      },
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedProject.id}-cutting.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function handleApplyFilters(event) {
    event.preventDefault();
    await loadProjects(token, 0, projectFilters);
  }

  async function loadAiScanHistory(activeToken = token) {
    if (!activeToken || !canUseAiScan) {
      setAiScanHistory([]);
      return;
    }

    const result = await listProjectScans(activeToken, 5);

    if (!result.success) {
      return;
    }

    setAiScanHistory(result.items || []);
  }

  async function handleScanProjectFile(event) {
    event.preventDefault();

    if (!canUseAiScan) {
      setStatus({ message: t.aiScanProOnly, tone: "info" });
      return;
    }

    if (!aiScanFile) {
      setStatus({ message: t.aiScanUnsupported, tone: "error" });
      return;
    }

    setLoading(true);
    const result = await scanProjectFile(
      token,
      aiScanFile,
    );
    setLoading(false);

    if (!result.success) {
      setAiScanResult(null);
      setAiScanSession(null);
      setStatus({ message: result.error || t.aiScanUnsupported, tone: "error" });
      return;
    }

    setAiScanResult(result.scan?.project_data || null);
    setAiScanSession(result.scan_session || null);
    await loadAiScanHistory(token);
    setStatus({ message: t.aiScanNeedsConfirmation, tone: "info" });
  }

  async function handleApplyAiScanResult() {
    if (!aiScanResult) {
      return;
    }

    const defaults = aiScanResult.form_defaults || {};
    const detectedProjectType = defaults.projectType || aiScanResult.type;
    const nextProjectType = specificationCatalog.project_types.includes(detectedProjectType)
      ? detectedProjectType
      : projectForm.projectType;
    const scanNotes = defaults.notes || aiScanResult.raw_text || "";

    setProjectForm({
      ...projectForm,
      projectName: projectForm.projectName || defaults.projectName || projectForm.projectName,
      projectType: nextProjectType,
      width: defaults.width || aiScanResult.width || projectForm.width,
      height: defaults.height || aiScanResult.height || projectForm.height,
      depth: defaults.depth || aiScanResult.depth || projectForm.depth,
      notes: [
        projectForm.notes,
        scanNotes ? `${t.aiScanRawText}: ${scanNotes}` : "",
      ]
        .filter(Boolean)
        .join(" | "),
    });

    if (aiScanSession?.id) {
      const result = await confirmProjectScan(token, aiScanSession.id);

      if (result.success) {
        setAiScanSession(result.scan_session || aiScanSession);
        await loadAiScanHistory(token);
      }
    }

    setStatus({ message: t.aiScanConfirmed, tone: "success" });
  }

  function handleApplyProjectTemplate(template) {
    setProjectStartMode("templates");
    setProjectForm((current) => ({
      ...current,
      ...template.fields,
      projectName:
        current.projectName || t[template.titleKey] || current.projectName,
      notes: current.notes || t[template.descriptionKey] || current.notes,
    }));
    setStatus({ message: t.projectTemplateApplied, tone: "success" });
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
            setStatus({
        message: result.errors?.join(", ") || result.error || t.unableToCreateProject,
        tone: "error",
      });
      return;
    }

    const projectId = result.result?.project_id;

    if (projectId && aiScanSession?.id) {
      const confirmResult = await confirmProjectScan(token, aiScanSession.id, projectId);

      if (confirmResult.success) {
        setAiScanSession(confirmResult.scan_session || aiScanSession);
        await loadAiScanHistory(token);
      }
    }

    setProjectForm(DEFAULT_PROJECT_FORM);
    setAiScanFile(null);
    setAiScanResult(null);
    setAiScanSession(null);
    setStatus({ message: t.projectCreated, tone: "success" });
    setActiveView("projects");
    await loadProjects(token, 0);

    if (projectId) {
      await loadProject(projectId);
    }
  }

  useEffect(() => {
    if (!token) {
      loadPublicOverview();
    }
  }, [token]);

  useEffect(() => {
    if (!token) {
      return;
    }

    loadUser(token);
    loadSpecificationCatalog();
    loadProjects(token, 0);
  }, [token]);

  useEffect(() => {
    if (!token || !canUseAiScan || activeView !== "create") {
      return;
    }

    loadAiScanHistory(token);
  }, [token, canUseAiScan, activeView]);

  useEffect(() => {
    if (!publicProfileMenuOpen) {
      return undefined;
    }

    function handlePointerDown(event) {
      if (!publicProfileMenuRef.current?.contains(event.target)) {
        setPublicProfileMenuOpen(false);
      }
    }

    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setPublicProfileMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [publicProfileMenuOpen]);

  useEffect(() => {
    if (
      (projectStartMode === "ai" && !canUseAiScan) ||
      (projectStartMode === "premium" && !canUsePremiumStart)
    ) {
      setProjectStartMode("templates");
    }
  }, [projectStartMode, canUseAiScan, canUsePremiumStart]);

  if (!workspaceOpen || !token || !user) {
    return (
      <main className="public-site-shell">
        {statusNotice}
        <header className="public-site-header">
          <div className="public-site-brand">
            <img
              alt={t.furniturePlatform}
              className="brand-logo brand-logo-mpfc"
              src="/brand/logo-mpfc.png"
            />
            <div className="public-site-brand-copy">
              <p>{t.brandTagline}</p>
              <strong>{t.furniturePlatform}</strong>
            </div>
          </div>

          <div className="public-site-actions">
            <nav className="public-site-nav" aria-label="Public navigation">
              <a href="#workflow">{t.landingWorkflowTitle}</a>
              <a href="#capabilities">{t.landingCapabilitiesTitle}</a>
              <a href="#packages">{t.landingPackagesTitle}</a>
              <a href={adminUrl} rel="noreferrer noopener" target="_blank">
                {t.adminPortal}
              </a>
            </nav>
            {user ? (
              <div className="public-user-menu" ref={publicProfileMenuRef}>
                <button
                  className="public-user-chip"
                  onClick={() => setPublicProfileMenuOpen((current) => !current)}
                  type="button"
                >
                  <span>{userLoginName}</span>
                  <strong>{userTierLabel}</strong>
                </button>
                {publicProfileMenuOpen ? (
                  <div className="public-user-dropdown">
                    <div className="public-user-dropdown-summary">
                      <span className="public-user-dropdown-login">{userLoginName}</span>
                      <div className="public-user-dropdown-meta">
                        <strong>{userTierLabel}</strong>
                        <span>{userCityLabel}</span>
                      </div>
                    </div>
                    <a href={adminUrl} rel="noreferrer noopener" target="_blank">
                      <ShieldCheck size={16} />
                      {t.landingOpenAdmin}
                    </a>
                    <button
                      onClick={() => {
                        setOwnPasswordForm({
                          currentPassword: "",
                          newPassword: "",
                        });
                        setShowOwnCurrentPassword(false);
                        setShowOwnNewPassword(false);
                        setPasswordModalOpen(true);
                        setPublicProfileMenuOpen(false);
                      }}
                      type="button"
                    >
                      <Eye size={16} />
                      {t.changePassword}
                    </button>
                    <button onClick={handleLogout} type="button">
                      <LogOut size={16} />
                      {t.logout}
                    </button>
                  </div>
                ) : null}
              </div>
            ) : null}
            <div className="public-header-side">
              {!user ? (
                <button
                  className="primary-button public-header-login-button"
                  onClick={() => {
                    setAuthMode("login");
                    setStatus("");
                    setAuthModalOpen(true);
                  }}
                  type="button"
                >
                  <Search size={18} />
                  {t.signIn}
                </button>
              ) : null}
            </div>
          </div>
        </header>

        <section className="public-hero">
          <div className="public-hero-copy">
            <div className="public-hero-topline">
              <span className="public-kicker">{t.brandTagline}</span>
              <span className="public-hero-badge">{t.landingHeroRegistrationBadge}</span>
            </div>
            <h1>
              <span>{t.landingHeroTitle}</span>
              <span className="public-hero-title-accent">{t.landingHeroAccent}</span>
            </h1>
            <p>{t.landingHeroDescription}</p>

            <div className="public-hero-feature-grid">
              <article className="public-hero-feature-card">
                <Boxes size={26} />
                <span>{t.landingHeroFeatureProjects}</span>
              </article>
              <article className="public-hero-feature-card">
                <Layers3 size={26} />
                <span>{t.landingHeroFeatureMaterials}</span>
              </article>
              <article className="public-hero-feature-card">
                <Package2 size={26} />
                <span>{t.landingHeroFeatureEdges}</span>
              </article>
              <article className="public-hero-feature-card">
                <ClipboardList size={26} />
                <span>{t.landingHeroFeatureEstimate}</span>
              </article>
            </div>

            <div className="public-hero-actions">
              {user ? (
                <a
                  className="primary-button public-link-button"
                  href={adminUrl}
                  rel="noreferrer noopener"
                  target="_blank"
                >
                  <ExternalLink size={18} />
                  {t.landingOpenAdmin}
                </a>
              ) : (
                <button
                  className="primary-button"
                  onClick={() => {
                    setAuthMode("login");
                    setStatus("");
                    setAuthModalOpen(true);
                  }}
                  type="button"
                >
                  <Rocket size={18} />
                  {t.landingStartCta}
                </button>
              )}
              <a
                className="ghost-button public-link-button"
                href="#capabilities"
              >
                <ArrowRight size={18} />
                {t.landingHeroViewCapabilities}
              </a>
            </div>
          </div>

          <div className="public-hero-showcase">
            <div className="public-preview-trust public-hero-trust">
              <span>Web</span>
              <span>Bot</span>
              <span>BOM</span>
              <span>AI OCR</span>
            </div>
            <div className="public-hero-image-shell">
              <img alt="" src="/brand/hero-calculator-visual.png" />
            </div>
          </div>
        </section>

        <section className="public-section public-section-light">
          <div className="section-heading">
            <h2>{t.landingProductTitle}</h2>
            <p>{t.landingProductDescription}</p>
          </div>
          <div className="public-product-grid">
            <article className="public-product-card">
              <span className="public-product-index">01</span>
              <h3>{t.landingProductCardOneTitle}</h3>
              <p>{t.landingProductCardOneDescription}</p>
            </article>
            <article className="public-product-card">
              <span className="public-product-index">02</span>
              <h3>{t.landingProductCardTwoTitle}</h3>
              <p>{t.landingProductCardTwoDescription}</p>
            </article>
            <article className="public-product-card">
              <span className="public-product-index">03</span>
              <h3>{t.landingProductCardThreeTitle}</h3>
              <p>{t.landingProductCardThreeDescription}</p>
            </article>
          </div>
        </section>

        <section className="public-section public-section-technical">
          <div className="section-heading">
            <h2>{t.landingModulesTitle}</h2>
            <p>{t.landingModulesDescription}</p>
          </div>
          <div className="public-module-grid">
            <article className="public-module-card">
              <div className="public-module-icon">
                <Layers3 size={18} />
              </div>
              <div className="public-module-copy">
                <strong>{t.landingModuleSiteTitle}</strong>
                <p>{t.landingModuleSiteDescription}</p>
              </div>
            </article>
            <article className="public-module-card">
              <div className="public-module-icon">
                <Database size={18} />
              </div>
              <div className="public-module-copy">
                <strong>{t.landingModuleAdminTitle}</strong>
                <p>{t.landingModuleAdminDescription}</p>
              </div>
            </article>
            <article className="public-module-card">
              <div className="public-module-icon">
                <Bot size={18} />
              </div>
              <div className="public-module-copy">
                <strong>{t.landingModuleBotTitle}</strong>
                <p>{t.landingModuleBotDescription}</p>
              </div>
            </article>
          </div>
        </section>

        <section className="public-section" id="workflow">
          <div className="section-heading">
            <h2>{t.landingWorkflowTitle}</h2>
            <p>{t.landingWorkflowDescription}</p>
          </div>
          <div className="public-workflow-grid">
            <article className="public-workflow-step">
              <span className="public-workflow-number">01</span>
              <strong>{t.landingWorkflowStepOneTitle}</strong>
              <p>{t.landingWorkflowStepOneDescription}</p>
              <ArrowRight size={16} />
            </article>
            <article className="public-workflow-step">
              <span className="public-workflow-number">02</span>
              <strong>{t.landingWorkflowStepTwoTitle}</strong>
              <p>{t.landingWorkflowStepTwoDescription}</p>
              <ArrowRight size={16} />
            </article>
            <article className="public-workflow-step">
              <span className="public-workflow-number">03</span>
              <strong>{t.landingWorkflowStepThreeTitle}</strong>
              <p>{t.landingWorkflowStepThreeDescription}</p>
              <ArrowRight size={16} />
            </article>
            <article className="public-workflow-step">
              <span className="public-workflow-number">04</span>
              <strong>{t.landingWorkflowStepFourTitle}</strong>
              <p>{t.landingWorkflowStepFourDescription}</p>
              <BadgeCheck size={16} />
            </article>
          </div>
        </section>

        <section className="public-section">
          <div className="section-heading">
            <h2>{t.landingPublicStatsTitle}</h2>
            <p>{t.landingPublicStatsDescription}</p>
          </div>
          <div className="public-stats-grid">
            <PublicStatCard
              icon={Boxes}
              label={t.landingStatsMaterials}
              value={publicOverview.stats.materials_total}
            />
            <PublicStatCard
              icon={Package2}
              label={t.landingStatsFittings}
              value={publicOverview.stats.fittings_total}
            />
            <PublicStatCard
              icon={ClipboardList}
              label={t.landingStatsProjects}
              value={publicOverview.stats.projects_total}
            />
            <PublicStatCard
              icon={Users}
              label={t.landingStatsUsers}
              value={publicOverview.stats.users_total}
            />
          </div>
        </section>

        <section className="public-section" id="capabilities">
          <div className="section-heading">
            <h2>{t.landingCapabilitiesTitle}</h2>
            <p>{t.landingCapabilitiesDescription}</p>
          </div>
          <div className="public-feature-grid">
            <article className="public-feature-card">
              <LayoutDashboard size={20} />
              <h3>{t.landingDashboardCardTitle}</h3>
              <p>{t.landingDashboardCardDescription}</p>
            </article>
            <article className="public-feature-card">
              <Boxes size={20} />
              <h3>{t.landingCatalogsCardTitle}</h3>
              <p>{t.landingCatalogsCardDescription}</p>
            </article>
            <article className="public-feature-card">
              <Bot size={20} />
              <h3>{t.landingBotCardTitle}</h3>
              <p>{t.landingBotCardDescription}</p>
            </article>
            <article className="public-feature-card">
              <PlayCircle size={20} />
              <h3>{t.landingYoutubeCardTitle}</h3>
              <p>{t.landingYoutubeCardDescription}</p>
            </article>
          </div>
        </section>

        <section className="public-section" id="packages">
          <div className="section-heading pricing-heading">
            <span className="pricing-eyebrow">{tariffContent.eyebrow}</span>
            <h2>{tariffContent.title}</h2>
            <p>{tariffContent.description}</p>
          </div>
          <div className="pricing-plan-grid">
            {tariffContent.plans.map((plan, planIndex) => {
              const PlanIcon = [Sparkles, Package2, Rocket, Users][planIndex];
              return (
                <article
                  className={`pricing-plan-card pricing-plan-${plan.id}${plan.recommended ? " recommended" : ""}`}
                  key={plan.id}
                >
                  {plan.recommended ? (
                    <span className="pricing-recommended">{tariffContent.recommended}</span>
                  ) : null}
                  <div className="pricing-plan-topline">
                    <span className="pricing-plan-icon"><PlanIcon size={20} /></span>
                    <span className="pricing-plan-name">{plan.name}</span>
                  </div>
                  <div className="pricing-plan-price">
                    <strong>{plan.price}</strong>
                    <span>{plan.period}</span>
                  </div>
                  <strong className="pricing-plan-audience">{plan.audience}</strong>
                  <p>{plan.summary}</p>
                  <button
                    className={`pricing-plan-action${plan.recommended ? " primary" : ""}`}
                    onClick={() => {
                      if (token) {
                        window.open(adminUrl, "_blank", "noopener,noreferrer");
                        return;
                      }
                      resetRegistrationFlow(email.trim());
                      setAuthMode("register");
                      setAuthModalOpen(true);
                    }}
                    type="button"
                  >
                    {plan.cta}
                    <ArrowRight size={16} />
                  </button>
                </article>
              );
            })}
          </div>

          <div className="pricing-comparison">
            <div className="pricing-comparison-heading">
              <div>
                <h3>{tariffContent.comparisonTitle}</h3>
                <p>{tariffContent.comparisonDescription}</p>
              </div>
              <span>{tariffContent.plans.length} {language === "uk" ? "тарифи" : "plans"}</span>
            </div>
            <div className="pricing-table-scroll">
              <table className="pricing-table">
                <thead>
                  <tr>
                    <th>{tariffContent.feature}</th>
                    {tariffContent.plans.map((plan) => (
                      <th className={plan.recommended ? "recommended" : ""} key={plan.id}>
                        <span>{plan.name}</span>
                        <small>{plan.price}</small>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tariffContent.groups.map((group) => (
                    <Fragment key={group.title}>
                      <tr className="pricing-group-row">
                        <th colSpan={5}>{group.title}</th>
                      </tr>
                      {group.rows.map(([feature, ...values]) => (
                        <tr key={`${group.title}-${feature}`}>
                          <th>{feature}</th>
                          {values.map((value, valueIndex) => (
                            <td
                              className={tariffContent.plans[valueIndex]?.recommended ? "recommended" : ""}
                              key={`${feature}-${tariffContent.plans[valueIndex]?.id}`}
                            >
                              <TariffValue labels={tariffContent} value={value} />
                            </td>
                          ))}
                        </tr>
                      ))}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section className="public-section public-section-accent">
          <div className="public-pro-spotlight">
            <div className="section-heading">
              <h2>{t.landingProSpotlightTitle}</h2>
              <p>{t.landingProSpotlightDescription}</p>
            </div>
            <div className="public-pro-grid">
              <article className="public-pro-point">
                <BadgeCheck size={18} />
                <span>{t.landingProSpotlightPointOne}</span>
              </article>
              <article className="public-pro-point">
                <BadgeCheck size={18} />
                <span>{t.landingProSpotlightPointTwo}</span>
              </article>
              <article className="public-pro-point">
                <BadgeCheck size={18} />
                <span>{t.landingProSpotlightPointThree}</span>
              </article>
            </div>
          </div>
        </section>

        <section className="public-section" id="entry">
          <div className="section-heading">
            <h2>{t.general}</h2>
            <p>{t.landingStatusRegistrationOpen}</p>
          </div>
          <div className="public-entry-grid">
            <article className="public-entry-card">
              <Sparkles size={18} />
              <h3>{t.landingSiteCardTitle}</h3>
              <p>{t.landingSiteCardDescription}</p>
            </article>
            <article className="public-entry-card">
              <ShieldCheck size={18} />
              <h3>{t.adminPortal}</h3>
              <p>{t.landingAdminHint}</p>
              <a
                className="ghost-button public-link-button"
                href={adminUrl}
                rel="noreferrer noopener"
                target="_blank"
              >
                <ExternalLink size={16} />
                {t.landingOpenAdmin}
              </a>
            </article>
            <article className="public-entry-card">
              <Bot size={18} />
              <h3>{t.landingBotCardTitle}</h3>
              <p>{t.landingBotCardDescription}</p>
              <a
                className="ghost-button public-link-button"
                href={TELEGRAM_BOT_URL}
                rel="noreferrer noopener"
                target="_blank"
              >
                <ExternalLink size={16} />
                {t.landingBotCta}
              </a>
            </article>
            <article className="public-entry-card">
              <PlayCircle size={18} />
              <h3>{t.landingYoutubeCardTitle}</h3>
              <p>{t.landingYoutubeCardDescription}</p>
              <a
                className="ghost-button public-link-button"
                href={YOUTUBE_CHANNEL_URL}
                rel="noreferrer noopener"
                target="_blank"
              >
                <ExternalLink size={16} />
                {t.landingOpenYoutube}
              </a>
            </article>
          </div>
        </section>

        <footer className="public-site-footer">
          <div className="public-site-footer-brand">
            <img
              alt={t.furniturePlatform}
              className="brand-logo brand-logo-mpfc"
              src="/brand/logo-mpfc.png"
            />
            <div>
              <strong>{t.landingFooterTitle}</strong>
              <p>{t.landingFooterDescription}</p>
            </div>
          </div>
          <div className="public-site-footer-meta">
            <span>{t.landingFooterCaption}</span>
            <div className="public-site-footer-links">
              <a href="#workflow">{t.landingWorkflowTitle}</a>
              <a href="#capabilities">{t.landingCapabilitiesTitle}</a>
              <a href="#packages">{t.landingPackagesTitle}</a>
            </div>
            <div className="public-language-switch public-footer-language-switch" role="group" aria-label="Language switcher">
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
          </div>
        </footer>
        {authModalOpen ? (
          <div
            className="public-auth-modal"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                resetRegistrationFlow();
                setAuthModalOpen(false);
              }
            }}
            role="presentation"
          >
            <aside className="public-auth-card public-auth-card-modal" id="public-auth-panel">
              <button
                aria-label="Close"
                className="public-auth-close"
                onClick={() => {
                  resetRegistrationFlow();
                  setAuthModalOpen(false);
                }}
                type="button"
              >
                <X size={18} />
              </button>
              <div className="public-auth-card-header">
                <h2>{t.landingAuthTitle}</h2>
                <p>{t.landingAuthDescription}</p>
              </div>

              <div className="public-auth-tabs">
                <button
                  className={authMode === "login" ? "active" : ""}
                  onClick={() => {
                    setStatus("");
                    setAuthMode("login");
                    resetRegistrationFlow();
                  }}
                  type="button"
                >
                  {t.authLoginTab}
                </button>
                <button
                  className={authMode === "register" ? "active" : ""}
                  onClick={() => {
                    setStatus("");
                    setAuthMode("register");
                    resetRegistrationFlow(email.trim());
                  }}
                  type="button"
                >
                  {t.authRegisterTab}
                </button>
              </div>

              {authMode === "login" ? (
                <form className="login-panel public-login-panel" onSubmit={handleLogin}>
                  <label>
                    {t.loginOrEmail}
                    <input
                      autoComplete="username"
                      onChange={(event) => setEmail(event.target.value)}
                      required
                      type="text"
                      value={email}
                    />
                  </label>

                  <label>
                    {t.password}
                    <span className="public-password-field">
                      <input
                        autoComplete="current-password"
                        minLength={8}
                        onChange={(event) => setPassword(event.target.value)}
                        required
                        type={showLoginPassword ? "text" : "password"}
                        value={password}
                      />
                      <button
                        aria-label={t.showPassword}
                        className="public-password-toggle"
                        onClick={() => setShowLoginPassword((current) => !current)}
                        type="button"
                      >
                        <Eye size={17} />
                      </button>
                    </span>
                  </label>

                  <button className="primary-button" disabled={loading} type="submit">
                    <Search size={18} />
                    {t.signIn}
                  </button>
                  <div className="public-auth-secondary-actions">
                    <button
                      className="public-auth-text-button"
                      onClick={() => {
                        setStatus("");
                        setResetPasswordEmail(email);
                        setAuthMode("forgot");
                      }}
                      type="button"
                    >
                      {t.passwordResetRequest}
                    </button>
                  </div>
                  <p className="public-auth-hint">{t.landingAdminHint}</p>
                </form>
              ) : authMode === "register" ? (
                <form className="login-panel public-login-panel" onSubmit={handleRegister}>
                  <div className="public-auth-step-indicator">
                    <span>
                      {registrationStep === 1
                        ? t.registrationStepOne
                        : registrationStep === 2
                          ? t.registrationStepTwo
                          : t.registrationStepThree}
                    </span>
                  </div>

                  {registrationStep === 1 ? (
                    <>
                      <label>
                        {t.registrationName}
                        <input
                          autoComplete="name"
                          onChange={(event) =>
                            setRegisterForm((current) => ({
                              ...current,
                              name: event.target.value,
                            }))
                          }
                          required
                          type="text"
                          value={registerForm.name}
                        />
                      </label>

                      <label>
                        {t.email}
                        <input
                          autoComplete="email"
                          onChange={(event) =>
                            setRegisterForm((current) => ({
                              ...current,
                              email: event.target.value,
                            }))
                          }
                          required
                          type="email"
                          value={registerForm.email}
                        />
                      </label>

                      <label>
                        {t.password}
                        <span className="public-password-field">
                          <input
                            autoComplete="new-password"
                            minLength={8}
                            onChange={(event) =>
                              setRegisterForm((current) => ({
                                ...current,
                                password: event.target.value,
                              }))
                            }
                            required
                            type={showRegisterPassword ? "text" : "password"}
                            value={registerForm.password}
                          />
                          <button
                            aria-label={t.showPassword}
                            className="public-password-toggle"
                            onClick={() => setShowRegisterPassword((current) => !current)}
                            type="button"
                          >
                            <Eye size={17} />
                          </button>
                        </span>
                      </label>

                      <label>
                        {t.confirmPassword}
                        <input
                          autoComplete="new-password"
                          minLength={8}
                          onChange={(event) =>
                            setRegisterForm((current) => ({
                              ...current,
                              confirmPassword: event.target.value,
                            }))
                          }
                          required
                          type={showRegisterPassword ? "text" : "password"}
                          value={registerForm.confirmPassword}
                        />
                      </label>
                    </>
                  ) : registrationStep === 2 ? (
                    <>
                      <p className="public-auth-step-copy" hidden={Boolean(registrationTelegramConfirmationUrl)}>
                        {language === "uk"
                          ? "Номер потрібен для захисту пробного періоду та відновлення доступу."
                          : "The phone number is needed to protect the trial period and restore access."}
                      </p>

                      <label>
                        {t.registrationPhone}
                        <input
                          autoComplete="tel"
                          inputMode="tel"
                          onChange={(event) =>
                            setRegisterForm((current) => ({
                              ...current,
                              phone: event.target.value,
                            }))
                          }
                          placeholder="+380XXXXXXXXX"
                          required
                          type="tel"
                          value={registerForm.phone}
                        />
                      </label>
                    </>
                  ) : (
                    <>
                      <p className="public-auth-step-copy" hidden={Boolean(registrationTelegramConfirmationUrl)}>
                        {language === "uk"
                          ? `Підтвердіть номер ${maskRegistrationPhone(registerForm.phone)}.`
                          : `Confirm ${maskRegistrationPhone(registerForm.phone)}.`}
                      </p>

                      {registrationTelegramConfirmationUrl ? (
                        <p className="public-auth-step-copy">{t.registrationTelegramInstruction}</p>
                      ) : null}

                      {registrationTelegramConfirmationUrl ? (
                        <div className="public-local-code-box" hidden={Boolean(registrationTelegramConfirmationUrl)}>
                          <div className="public-local-code-copy">
                            <strong>{t.registrationTelegramTitle}</strong>
                            <p>
                              {registrationTelegramWaiting
                                ? t.registrationTelegramWaiting
                                : t.registrationTelegramDescription}
                            </p>
                          </div>
                          <div className="public-auth-secondary-actions">
                            <button
                              className="primary-button"
                              onClick={() => {
                                setRegistrationTelegramWaiting(true);
                                setRegistrationTelegramStartedAt(Date.now());
                                window.open(
                                  registrationTelegramConfirmationUrl,
                                  "_blank",
                                  "noopener,noreferrer",
                                );
                                setStatus({ message: t.registrationTelegramWaiting, tone: "info" });
                              }}
                              type="button"
                            >
                              <BadgeCheck size={18} />
                              {t.registrationTelegramConfirm}
                            </button>
                            <button
                              className="public-auth-text-button"
                              onClick={() => {
                                window.open(
                                  registrationTelegramConfirmationUrl,
                                  "_blank",
                                  "noopener,noreferrer",
                                );
                              }}
                              type="button"
                            >
                              {t.registrationTelegramOpen}
                            </button>
                          </div>
                        </div>
                      ) : null}

                      <label hidden={Boolean(registrationTelegramConfirmationUrl)}>
                        {t.registrationCode}
                        <input
                          autoComplete="one-time-code"
                          inputMode="numeric"
                          maxLength={6}
                          pattern="[0-9]*"
                          onChange={(event) =>
                            setRegisterForm((current) => ({
                              ...current,
                              confirmationCode: normalizeRegistrationCodeInput(event.target.value),
                            }))
                          }
                          required
                          type="text"
                          value={registerForm.confirmationCode}
                        />
                      </label>

                      {registrationStartResponse?.debug_verification_code ? (
                        <div className="public-local-code-box">
                          <div className="public-local-code-copy">
                            <strong>{t.registrationLocalCodeTitle}</strong>
                            <p>{t.registrationLocalCodeHint}</p>
                          </div>
                          <code className="public-local-code-value">
                            {formatRegistrationCodeDisplay(registrationStartResponse.debug_verification_code)}
                          </code>
                          <div className="public-auth-secondary-actions">
                            <button
                              className="public-auth-text-button"
                              onClick={async () => {
                                const copied = await copyRegistrationCode(
                                  registrationStartResponse.debug_verification_code,
                                );
                                setStatus({
                                  message: copied
                                    ? t.registrationCodeCopied
                                    : t.registrationFailed,
                                  tone: copied ? "success" : "error",
                                });
                              }}
                              type="button"
                            >
                              {language === "uk" ? "Скопіювати код" : "Copy code"}
                            </button>
                            <button
                              className="public-auth-text-button"
                              onClick={() => {
                                setRegisterForm((current) => ({
                                  ...current,
                                  confirmationCode: normalizeRegistrationCodeInput(
                                    registrationStartResponse.debug_verification_code || "",
                                  ),
                                }));
                                setStatus({ message: t.registrationCodeAutofilled, tone: "success" });
                              }}
                              type="button"
                            >
                              {t.registrationUseLocalCode}
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="public-auth-step-copy">{t.registrationCodeCreated}</p>
                      )}
                    </>
                  )}

                  <div className="public-auth-secondary-actions">
                    {registrationStep > 1 ? (
                      <button
                        className="public-auth-text-button"
                        onClick={() => {
                          setStatus("");
                          setRegistrationStep((current) => Math.max(current - 1, 1));
                        }}
                        type="button"
                      >
                        {t.registrationBack}
                      </button>
                    ) : null}
                    <button className="primary-button" disabled={loading} type="submit">
                      {registrationStep === 1 ? (
                        <>
                          <ArrowRight size={18} />
                          {t.registrationContinue}
                        </>
                      ) : registrationStep === 2 ? (
                        <>
                          <UserPlus size={18} />
                          {t.registrationRequestCode}
                        </>
                      ) : (
                        <>
                          <BadgeCheck size={18} />
                          {registrationTelegramConfirmationUrl
                            ? t.registrationTelegramConfirm
                            : t.registrationVerifyPhone}
                        </>
                      )}
                    </button>
                  </div>
                </form>
              ) : (
                <form className="login-panel public-login-panel" onSubmit={handlePasswordResetRequest}>
                  <p className="public-auth-reset-copy">{t.passwordResetRequestDescription}</p>

                  <label>
                    {t.email}
                    <input
                      autoComplete="email"
                      onChange={(event) => setResetPasswordEmail(event.target.value)}
                      required
                      type="email"
                      value={resetPasswordEmail}
                    />
                  </label>

                  <button className="primary-button" disabled={loading} type="submit">
                    <Search size={18} />
                    {t.passwordResetSubmit}
                  </button>

                  <button
                    className="public-auth-text-button public-auth-back-button"
                    onClick={() => {
                      setStatus("");
                      setAuthMode("login");
                    }}
                    type="button"
                  >
                    {t.authLoginTab}
                  </button>
                </form>
              )}
            </aside>
          </div>
        ) : null}
        {passwordModalOpen && user ? (
          <div
            className="public-auth-modal"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setPasswordModalOpen(false);
              }
            }}
            role="presentation"
          >
            <aside className="public-auth-card public-auth-card-modal public-password-modal">
              <button
                aria-label={t.close}
                className="public-auth-close"
                onClick={() => setPasswordModalOpen(false)}
                type="button"
              >
                <X size={18} />
              </button>
              <div className="public-auth-card-header">
                <h2>{t.changePassword}</h2>
                <p>{userLoginName}</p>
              </div>
              <form className="login-panel public-login-panel" onSubmit={handleOwnPasswordChange}>
                <label>
                  {t.currentPassword}
                  <span className="public-password-field">
                    <input
                      autoComplete="current-password"
                      minLength={8}
                      onChange={(event) =>
                        setOwnPasswordForm((current) => ({
                          ...current,
                          currentPassword: event.target.value,
                        }))
                      }
                      placeholder={t.currentPassword}
                      required
                      type={showOwnCurrentPassword ? "text" : "password"}
                      value={ownPasswordForm.currentPassword}
                    />
                    <button
                      aria-label={t.showPassword}
                      className="public-password-toggle"
                      onClick={() => setShowOwnCurrentPassword((current) => !current)}
                      type="button"
                    >
                      <Eye size={17} />
                    </button>
                  </span>
                </label>
                <label>
                  {t.newPassword}
                  <span className="public-password-field">
                    <input
                      autoComplete="new-password"
                      minLength={8}
                      onChange={(event) =>
                        setOwnPasswordForm((current) => ({
                          ...current,
                          newPassword: event.target.value,
                        }))
                      }
                      placeholder={t.newPassword}
                      required
                      type={showOwnNewPassword ? "text" : "password"}
                      value={ownPasswordForm.newPassword}
                    />
                    <button
                      aria-label={t.showPassword}
                      className="public-password-toggle"
                      onClick={() => setShowOwnNewPassword((current) => !current)}
                      type="button"
                    >
                      <Eye size={17} />
                    </button>
                  </span>
                </label>
                <div className="public-password-modal-actions">
                  <button
                    className="ghost-button"
                    onClick={() => setPasswordModalOpen(false)}
                    type="button"
                  >
                    {t.close}
                  </button>
                  <button className="primary-button" disabled={loading} type="submit">
                    <Save size={18} />
                    {t.changePassword}
                  </button>
                </div>
              </form>
            </aside>
          </div>
        ) : null}
      </main>
    );
  }

  return (
    <main
      className="app-shell"
      onTouchCancel={finishSidebarGesture}
      onTouchEnd={finishSidebarGesture}
      onTouchMove={handleSidebarTouchMove}
      onTouchStart={handleSidebarTouchStart}
    >
      {statusNotice}
      {isSidebarOpen ? (
        <div
          className="sidebar-backdrop"
          onClick={() => setIsSidebarOpen(false)}
          role="presentation"
        />
      ) : null}
      <aside className={`sidebar${isSidebarOpen ? " open" : ""}`}>
        <button
          aria-label="Close menu"
          className="sidebar-close-button"
          onClick={() => setIsSidebarOpen(false)}
          type="button"
        >
          <X size={18} />
        </button>
        <div className="brand-block brand-lockup">
          <img alt="" className="brand-mark" src="/brand/mp-symbol-reference.jpg" />
          <div className="brand-copy">
            <p className="eyebrow">{t.furniturePlatform}</p>
            <h1>{t.app}</h1>
          </div>
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
          <span>{userLoginName}</span>
          <strong>{userTierLabel}</strong>
        </div>

        {trialCountdown ? (
          <div
            className={`trial-status${trialCountdown.state === "expired" ? " expired" : ""}`}
            role="status"
          >
            <div className="trial-status-heading">
              {trialCountdown.state === "expired" ? (
                <CircleAlert aria-hidden="true" size={16} />
              ) : (
                <BadgeCheck aria-hidden="true" size={16} />
              )}
              <strong>{language === "uk" ? "Пробний доступ" : "Trial access"}</strong>
            </div>
            <p>{trialMessage}</p>
            {trialCountdown.state === "active" ? (
              <small className="trial-status-note">
                {language === "uk" ? "Після завершення: Free" : "After trial: Free"}
              </small>
            ) : null}
          </div>
        ) : null}

        <nav className="nav-tabs" aria-label="Application sections">
          <button
            className={activeView === "projects" ? "active" : ""}
            onClick={() => {
              setActiveView("projects");
              closeSidebarOnMobile();
            }}
            type="button"
          >
            <ClipboardList size={18} />
            {t.projects}
          </button>
          <button
            className={activeView === "create" ? "active" : ""}
            onClick={() => {
              setActiveView("create");
              closeSidebarOnMobile();
            }}
            type="button"
          >
            <Plus size={18} />
            {t.newProject}
          </button>
          <button
            className={activeView === "details" ? "active" : ""}
            disabled={!selectedProject}
            onClick={() => {
              setActiveView("details");
              closeSidebarOnMobile();
            }}
            type="button"
          >
            <Eye size={18} />
            {t.view}
          </button>
          <button
            className={activeView === "settings" ? "active" : ""}
            onClick={() => {
              setActiveView("settings");
              closeSidebarOnMobile();
            }}
            type="button"
          >
            <Info size={18} />
            {t.settings}
          </button>
        </nav>

        <button
          className="ghost-button logout-button"
          onClick={() => {
            closeSidebarOnMobile();
            handleLogout();
          }}
          type="button"
        >
          <LogOut size={18} />
          {t.logout}
        </button>
      </aside>

      <section className="workspace">
        <header className={`toolbar${activeView === "details" ? " project-toolbar" : ""}`}>
          <div className="toolbar-heading">
            <button
              aria-label="Open menu"
              className="sidebar-toggle-button"
              onClick={() => setIsSidebarOpen(true)}
              type="button"
            >
              <Menu size={18} />
            </button>
            <h2>
              {activeView === "create"
                ? t.createProject
                : activeView === "details"
                  ? t.projectDetails
                  : activeView === "settings"
                    ? t.settings
                  : t.projects}
            </h2>
            {activeView === "details" && selectedProject ? (
              <div className="toolbar-project-meta">
                <span>{selectedProject.project_name || t.newProject}</span>
                <button
                  aria-label={t.showProjectOverview}
                  className="ghost-button compact-button detail-info-button"
                  disabled={loading}
                  onClick={() => setProjectOverviewOpen(true)}
                  title={t.showProjectOverview}
                  type="button"
                >
                  <Info size={16} />
                </button>
              </div>
            ) : (
              <p>
                {activeView === "projects" ? pageLabel : t.furniturePlatform}
              </p>
            )}
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
            ) : activeView === "details" && selectedProject ? (
              <div className="toolbar-project-controls">
                <div className="detail-tabs toolbar-project-tabs" role="tablist">
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
                  {selectedPartDetail ? (
                    <button
                      className={activeProjectTab === "partDetail" ? "active" : ""}
                      onClick={() => setActiveProjectTab("partDetail")}
                      type="button"
                    >
                      {t.detailViewer}
                    </button>
                  ) : null}
                  <button
                    className={activeProjectTab === "validation" ? "active" : ""}
                    onClick={() => setActiveProjectTab("validation")}
                    type="button"
                  >
                    {t.validation}
                  </button>
                </div>
                <button
                  className="ghost-button"
                  onClick={() => setActiveView("projects")}
                  type="button"
                >
                  <ChevronLeft size={18} />
                  {t.projects}
                </button>
              </div>
            ) : null}
          </div>
        </header>

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
            <div className="project-start-shell">
              <div className="project-start-heading">
                <div>
                  <strong>{t.projectStartTitle}</strong>
                  <span>{t.projectStartDescription}</span>
                </div>
                <span className="project-start-current-tier">
                  {userTierLabel}
                </span>
              </div>
              <div className="project-start-grid">
                <article className="project-start-card free">
                  <div className="project-start-card-head">
                    <span className="project-start-icon">
                      <ClipboardList size={22} />
                    </span>
                    <div>
                      <strong>{t.projectStartManualTitle}</strong>
                      <small>{t.projectStartManualDescription}</small>
                    </div>
                    <em>{t.projectStartFreeBadge}</em>
                  </div>
                  <div className="project-template-scroll">
                    <div className="project-template-grid">
                      {PROJECT_TEMPLATE_PRESETS.map((template) => (
                        <button
                          className="project-template-card"
                          key={template.titleKey}
                          onClick={() => handleApplyProjectTemplate(template)}
                          type="button"
                        >
                          <span className={`project-template-visual ${template.visual}`}>
                            <img alt={t[template.titleKey]} src={template.image} />
                          </span>
                          <span>
                            <strong>{t[template.titleKey]}</strong>
                            <small>{t[template.descriptionKey]}</small>
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </article>
                <button
                  className={`project-start-card action ${projectStartMode === "ai" ? "active" : ""} ${!canUseAiScan ? "locked" : ""}`}
                  onClick={() => {
                    if (!canUseAiScan) {
                      setStatus({ message: t.aiScanProOnly, tone: "info" });
                      return;
                    }

                    setProjectStartMode("ai");
                  }}
                  type="button"
                >
                  <span className="project-start-action-visual pro-scan" aria-hidden="true">
                    <img alt="" src="/static/project-start/hero-scene.png" />
                  </span>
                  <span className="project-start-icon pro">
                    <Sparkles size={22} />
                  </span>
                  <strong>{t.projectStartAiTitle}</strong>
                  <small>{t.projectStartAiDescription}</small>
                  <em>{t.projectStartProBadge}</em>
                </button>
                <button
                  className={`project-start-card action premium ${projectStartMode === "premium" ? "active" : ""} ${!canUsePremiumStart ? "locked" : ""}`}
                  onClick={() => {
                    if (!canUsePremiumStart) {
                      setStatus({ message: t.projectStartPremiumOnly, tone: "info" });
                      return;
                    }

                    setProjectStartMode("premium");
                  }}
                  type="button"
                >
                  <span className="project-start-action-visual premium-power" aria-hidden="true">
                    <img alt="" src="/static/project-start/hero-scene.png" />
                  </span>
                  <span className="project-start-icon premium">
                    <Rocket size={22} />
                  </span>
                  <strong>{t.projectStartPremiumTitle}</strong>
                  <small>{t.projectStartPremiumDescription}</small>
                  <em>{t.projectStartPremiumBadge}</em>
                </button>
              </div>
            </div>

            {projectStartMode === "premium" && canUsePremiumStart ? (
              <div className="premium-start-panel">
                <article>
                  <Layers3 size={20} />
                  <strong>{t.projectPremiumOptionTemplates}</strong>
                  <span>{t.projectPremiumOptionTemplatesDescription}</span>
                </article>
                <article>
                  <Cpu size={20} />
                  <strong>{t.projectPremiumOptionRecognition}</strong>
                  <span>{t.projectPremiumOptionRecognitionDescription}</span>
                </article>
                <article>
                  <Boxes size={20} />
                  <strong>{t.projectPremiumOptionBatch}</strong>
                  <span>{t.projectPremiumOptionBatchDescription}</span>
                </article>
                <button
                  className="secondary-button"
                  onClick={() => setProjectStartMode("ai")}
                  type="button"
                >
                  <Search size={18} />
                  {t.projectPremiumOpenUpload}
                </button>
              </div>
            ) : null}

            {projectStartMode === "ai" ? (
              <div className="ai-scan-panel">
                <div className="ai-scan-copy">
                  <h3>{t.aiScanTitle}</h3>
                  <p>{t.aiScanDescription}</p>
                  {!canUseAiScan ? <p className="ai-scan-lock">{t.aiScanProOnly}</p> : null}
                </div>
                <form className="ai-scan-form" onSubmit={handleScanProjectFile}>
                  <input
                    accept=".jpg,.jpeg,.png,.pdf"
                    disabled={!canUseAiScan}
                    onChange={(event) => {
                      setAiScanFile(event.target.files?.[0] || null);
                      setAiScanResult(null);
                    }}
                    type="file"
                  />
                  <button
                    className="secondary-button"
                    disabled={loading || !aiScanFile || !canUseAiScan}
                    type="submit"
                  >
                    <Search size={18} />
                    {t.aiScanUpload}
                  </button>
                </form>
                {aiScanResult ? (
                  <div className="ai-scan-result">
                    <div>
                      <span>{t.aiScanFound}</span>
                      <strong>{formatCatalogLabel(aiScanResult.type, t)}</strong>
                    </div>
                    <div>
                      <span>{t.width} x {t.height} x {t.depth}</span>
                      <strong>
                        {aiScanResult.width} x {aiScanResult.height} x {aiScanResult.depth}
                      </strong>
                    </div>
                    <div>
                      <span>{t.aiScanNeedsConfirmation}</span>
                      <strong>{Math.round((aiScanResult.confidence || 0) * 100)}%</strong>
                    </div>
                    <button className="primary-button" onClick={handleApplyAiScanResult} type="button">
                      <BadgeCheck size={18} />
                      {t.aiScanApply}
                    </button>
                    {aiScanResult.raw_text ? (
                      <p className="ai-scan-raw">
                        <strong>{t.aiScanRawText}:</strong> {aiScanResult.raw_text}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {canUseAiScan && aiScanHistory.length ? (
                  <div className="ai-scan-history">
                    <h4>{t.aiScanHistory}</h4>
                    <div className="ai-scan-history-list">
                      {aiScanHistory.map((scan) => {
                        const scanData = scan.project_data || {};
                        return (
                          <div className="ai-scan-history-item" key={scan.id}>
                            <div>
                              <strong>{formatCatalogLabel(scanData.type || scan.detected_type, t)}</strong>
                              <span>
                                {scanData.width || "-"} x {scanData.height || "-"} x {scanData.depth || "-"}
                              </span>
                            </div>
                            <span className={`ai-scan-status ${scan.status}`}>
                              {scan.status}
                            </span>
                            <span>{formatDateTime(scan.updated_at, t)}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="project-form-caption">
              <strong>{t.projectSpecificationTitle}</strong>
              <span>
                {projectStartMode === "ai"
                  ? t.aiScanApply
                  : projectStartMode === "premium"
                    ? t.projectStartPremiumDescription
                    : t.projectStartManualDescription}
              </span>
            </div>
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
        ) : activeView === "settings" ? (
          <section className="settings-panel full-panel">
            <div className="settings-grid">
              <article className="settings-card">
                <div className="settings-card-header">
                  <h3>{t.myData}</h3>
                </div>
                <form className="settings-password-form" onSubmit={handleOwnProfileSave}>
                  <div className="settings-info-grid">
                    <label>
                      {t.email}
                      <input disabled readOnly type="text" value={user.email} />
                    </label>
                    <label>
                      {t.role}
                      <input disabled readOnly type="text" value={user.role} />
                    </label>
                    <label>
                      {t.username}
                      <input
                        onChange={(event) =>
                          setOwnProfileForm({
                            ...ownProfileForm,
                            username: event.target.value,
                          })
                        }
                        required
                        type="text"
                        value={ownProfileForm.username}
                      />
                    </label>
                    <label>
                      {t.phone}
                      <input
                        onChange={(event) =>
                          setOwnProfileForm({
                            ...ownProfileForm,
                            phone: event.target.value,
                          })
                        }
                        type="text"
                        value={ownProfileForm.phone}
                      />
                    </label>
                    <label>
                      {language === "uk" ? "Місто" : "City"}
                      <select
                        onChange={(event) =>
                          setOwnProfileForm({
                            ...ownProfileForm,
                            city: event.target.value,
                          })
                        }
                        value={ownProfileForm.city}
                      >
                        <option value="">{t.notSet}</option>
                        {[
                          ["kyiv", "Київ", "Kyiv"],
                          ["lviv", "Львів", "Lviv"],
                          ["odessa", "Одеса", "Odesa"],
                          ["dnipro", "Дніпро", "Dnipro"],
                          ["kharkiv", "Харків", "Kharkiv"],
                          ["khmelnytskyi", "Хмельницький", "Khmelnytskyi"],
                          ["rivne", "Рівне", "Rivne"],
                        ].map(([value, ukLabel, enLabel]) => (
                          <option key={value} value={value}>
                            {language === "uk" ? ukLabel : enLabel}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="settings-actions">
                    <button className="ghost-button" disabled={loading || !hasProfileChanges} type="submit">
                      {t.saveProfile}
                    </button>
                  </div>
                </form>
                <form className="settings-password-form settings-subform" onSubmit={handleOwnEmailChangeRequest}>
                  <label>
                    {t.newEmail}
                    <input
                      autoComplete="email"
                      onChange={(event) =>
                        setEmailChangeForm({
                          newEmail: event.target.value,
                        })
                      }
                      placeholder={t.newEmail}
                      required
                      type="email"
                      value={emailChangeForm.newEmail}
                    />
                  </label>
                  <div className="settings-actions">
                    <button className="ghost-button" disabled={loading || !emailChangeForm.newEmail.trim()} type="submit">
                      {t.requestEmailChange}
                    </button>
                  </div>
                </form>
              </article>

              <article className="settings-card">
                <div className="settings-card-header">
                  <h3>{t.password}</h3>
                </div>
                <form className="settings-password-form" onSubmit={handleOwnPasswordChange}>
                  <label>
                    {t.currentPassword}
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
                  </label>
                  <label>
                    {t.newPassword}
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
                  </label>
                  <div className="settings-actions">
                    <button className="ghost-button" disabled={loading} type="submit">
                      {t.changePassword}
                    </button>
                  </div>
                </form>
              </article>
            </div>
          </section>
        ) : (
          <section className="detail-panel">
            {selectedProject ? (
              <>
                {projectOverviewOpen ? (
                  <div
                    aria-modal="true"
                    className="modal-backdrop"
                    onClick={() => setProjectOverviewOpen(false)}
                    role="dialog"
                  >
                    <section
                      className="confirm-modal project-info-modal"
                      onClick={(event) => event.stopPropagation()}
                    >
                      <header className="confirm-header">
                        <div>
                          <strong>{t.projectDetails}</strong>
                          <p>{selectedProject.project_name || t.newProject}</p>
                        </div>
                        <button
                          aria-label={t.hideProjectOverview}
                          className="ghost-button compact-button detail-info-button"
                          onClick={() => setProjectOverviewOpen(false)}
                          type="button"
                        >
                          <X size={16} />
                        </button>
                      </header>
                      <div className="project-info-grid">
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
                        <span>{t.notes}</span>
                        <strong>{selectedProject.notes || t.notSet}</strong>
                      </div>
                    </section>
                  </div>
                ) : null}

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
                    <section className="wide-production-section production-assembly-workspace">
                      <article className="production-card production-card-sticky">
                        <h3>{t.productionAssembly3d}</h3>
                        {selectedCuttingItem ? (
                          <div className="production-selected-part-summary">
                            <strong>{selectedCuttingItem.part_name}</strong>
                            <span>
                              {selectedCuttingItem.width} x {selectedCuttingItem.height} x {selectedCuttingItem.thickness || 18}
                            </span>
                            <span>{selectedCuttingItem.material || t.notSet}</span>
                          </div>
                        ) : null}
                        {cuttingItems.length > 0 ? (
                          <ProductionViewerBoundary
                            itemCount={cuttingItems.length}
                            selectedPartCode={effectiveSelectedPartCode}
                            t={t}
                          >
                            <Suspense fallback={<div className="part-three-viewer part-three-viewer-loading">Loading 3D assembly...</div>}>
                              <ProjectThreeViewer
                                hoveredPartCode={hoveredCuttingPartCode}
                                items={cuttingItems}
                                onClearSelection={handleClearCuttingPartSelection}
                                onHoverPartChange={setHoveredCuttingPartCode}
                              onOpenPart={handleSelectCuttingPart}
                              onSelectPart={handlePreviewCuttingPart}
                              projectMeta={{
                                cuttingAssembly: cuttingAssembly || {},
                                assemblyLayout: selectedProject?.assembly_layout || {},
                                drawers: selectedProject?.drawers || [],
                                projectType: selectedProject?.project_type || "dresser",
                                sections: selectedProject?.sections || 1,
                              }}
                                selectedPartDetail={selectedPartDetail}
                                selectedPartCode={effectiveSelectedPartCode}
                                t={t}
                              />
                            </Suspense>
                          </ProductionViewerBoundary>
                        ) : (
                          <p>{t.noCuttingItems}</p>
                        )}
                      </article>
                      <article className="production-card production-parts-list-card">
                        <h3>{t.productionCutting}</h3>
                        {cuttingSummary ? (
                          <div className="summary-row">
                            <span>{t.cuttingSummary}</span>
                            <strong>
                              {expandedCuttingItems.length} {language === "uk" ? "шт" : "pcs"} / {cuttingSummary.total_area_m2} {t.cuttingArea}
                            </strong>
                          </div>
                        ) : null}
                        <label className="production-parts-search">
                          <span>{t.search}</span>
                          <input
                            onChange={(event) => setCuttingSearch(event.target.value)}
                            placeholder={t.search}
                            type="text"
                            value={cuttingSearch}
                          />
                        </label>
                        {groupedCuttingItems.length > 0 ? (
                          <div className="production-parts-search-actions">
                            <button onClick={collapseAllCuttingGroups} type="button">
                              {language === "uk" ? "Згорнути все" : "Collapse all"}
                            </button>
                            <button onClick={expandAllCuttingGroups} type="button">
                              {language === "uk" ? "Розгорнути все" : "Expand all"}
                            </button>
                          </div>
                        ) : null}
                        {cuttingItems.length > 0 ? (
                          <div className="production-parts-groups">
                            {groupedCuttingItems.map(([materialName, materialItems]) => (
                              <section className="production-parts-group" key={materialName}>
                                <button
                                  className={`production-parts-group-head${collapsedCuttingGroups[materialName] ? " collapsed" : ""}`}
                                  onClick={() => toggleCuttingGroup(materialName)}
                                  type="button"
                                >
                                  <h5>{materialName}</h5>
                                  <span className="production-parts-group-meta">
                                    <span className="production-parts-group-count">{materialItems.length}</span>
                                    <span className="production-parts-group-caret" aria-hidden="true">
                                      {collapsedCuttingGroups[materialName] ? "+" : "-"}
                                    </span>
                                  </span>
                                </button>
                                {!collapsedCuttingGroups[materialName] ? (
                                <table className="cutting-table production-parts-table">
                                  <thead>
                                    <tr>
                                      <th className="production-parts-number-cell">№</th>
                                      <th>{t.details}</th>
                                      <th>{t.cuttingSize}</th>
                                      <th>{t.bomThickness}</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {materialItems.map((item, index) => {
                                      const isSelected =
                                        selectedPartDetail?.part?.export_code === item.export_code ||
                                        selectedCuttingPartCode === item.export_code;
                                      const isHovered = hoveredCuttingPartCode === item.export_code;

                                      return (
                                        <tr
                                          className={`${isSelected ? "selected" : ""}${isHovered ? " hovered" : ""}`}
                                          data-export-code={item.export_code}
                                          key={item.row_key}
                                          onClick={() => handlePreviewCuttingPart(item.export_code)}
                                          onMouseEnter={() => setHoveredCuttingPartCode(item.export_code)}
                                          onMouseLeave={() => setHoveredCuttingPartCode(null)}
                                        >
                                          <td className="production-parts-number-cell">{index + 1}</td>
                                          <td>{item.row_title}</td>
                                          <td>{item.width} x {item.height}</td>
                                          <td>{item.thickness || 18}</td>
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </table>
                                ) : null}
                              </section>
                            ))}
                          </div>
                        ) : (
                          <p>{t.noCuttingItems}</p>
                        )}
                      </article>
                    </section>
                    <article>
                      <h3>{t.productionDrilling}</h3>
                      <p>{t.productionPlaceholder}</p>
                    </article>
                    <article className="wide-production-section">
                      <h3>{t.exportFormats}</h3>
                      <div className="export-actions">
                        {cuttingExportFormats.map((format) => (
                          <button
                            className={
                              format.status === "available"
                                ? "primary-button"
                                : "ghost-button"
                            }
                            disabled={
                              format.status !== "available" ||
                              format.format !== "json"
                            }
                            key={format.format}
                            onClick={
                              format.format === "json"
                                ? handleDownloadCuttingJson
                                : undefined
                            }
                            type="button"
                          >
                            {format.format === "json" ? <Download size={18} /> : null}
                            {format.label}
                            <span>
                              {format.status === "available"
                                ? t.exportReady
                                : t.exportPlanned}
                            </span>
                          </button>
                        ))}
                      </div>
                    </article>
                  </div>
                ) : null}

                {activeProjectTab === "partDetail" && selectedPartDetail ? (
                  <PartDetailWorkspace
                    canEdit={Boolean(user)}
                    detail={selectedPartDetail}
                    edgeBandings={specificationCatalog.edge_bandings}
                    loading={loading}
                    onAddMachining={handleAddMachiningRow}
                    onBack={() => setActiveProjectTab("production")}
                    onEdgeChange={handlePartEdgeChange}
                    onEdgeSelect={setSelectedEdgeSide}
                    onMachiningChange={handleMachiningChange}
                    onRemoveMachining={handleRemoveMachiningRow}
                    onSaveEdges={handleSavePartEdges}
                    onSaveMachining={handleSavePartMachining}
                    selectedEdgeSide={selectedEdgeSide}
                    t={t}
                  />
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
