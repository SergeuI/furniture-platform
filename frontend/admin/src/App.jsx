import {
  Blocks,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Drill,
  FileSliders,
  FolderTree,
  History,
  House,
  Info,
  LayoutGrid,
  MoreHorizontal,
  Package,
  CircleAlert,
  LogOut,
  Plus,
  RefreshCw,
  Pencil,
  RotateCcw,
  Save,
  Scissors,
  Search,
  Settings2,
  Eye,
  EyeOff,
  X,
  Trash2,
  Users,
  Wrench,
} from "lucide-react";
import { Component, Suspense, lazy, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import surfaceMountIcon from "./assets/hole-mounting/surface_mount.png";
import angledTwoPlanesIcon from "./assets/hole-mounting/angled_two_planes.png";
import faceToEdgeIcon from "./assets/hole-mounting/face_to_edge.png";
import edgeToEdgeIcon from "./assets/hole-mounting/edge_to_edge.png";
import drawerSlidesIcon from "./assets/hole-mounting/drawer_slides.png";

import {
  attachMaterialEdge,
  changeOwnPassword,
  createMaterial,
  createFitting,
  createFittingHoleTemplate,
  createFittingHolePoint,
  createManualService,
  createMyEmailChangeRequest,
  createCatalogItem,
  createUser,
  deleteFitting,
  deleteMaterial,
  deleteProject,
  generateProject,
  confirmProjectScan,
  getCatalogAutoRefreshStatus,
  getCurrentUser,
  getFittingHoleTemplate,
  getFittingsCatalog,
  getMaterialDetails,
  getMaterialImportJob,
  getMaterialsCatalog,
  getMyViyarAuthStatus,
  getManualServicesTree,
  getProject,
  getProjectCutting,
  getProjectHistory,
  getProjectPartDetail,
  getUserDetails,
  getSpecificationCatalog,
  getViyarServicesTree,
  importViyarServices,
  importMaterialFromViyar,
  listAuditLogs,
  listCatalogItems,
  listFittingHolePoints,
  listFittingHoleTemplatesByFitting,
  listProjectScans,
  listUsers,
  listUserChangeRequests,
  listProjects,
  login,
  reviewUserChangeRequest,
  rollbackProject,
  resetUserPassword,
  updateCatalogItem,
  updateFittingHoleTemplate,
  updateCatalogItemActive,
  updateFittingHolePoint,
  updateMyViyarAuth,
  updateManualService,
  updateProject,
  updateProjectPartEdges,
  updateProjectPartMachining,
  updateViyarService,
  syncViyarServicePrices,
  updateMyProfile,
  updateUserActive,
  updateUserRole,
  refreshMyViyarSession,
  scanProjectFile,
} from "./api";
const PartThreeViewer = lazy(() => import("./components/PartThreeViewer"));
const ProjectThreeViewer = lazy(() => import("./components/ProjectThreeViewer"));


const TOKEN_STORAGE_KEY = "furniture_admin_token";
const LANGUAGE_STORAGE_KEY = "furniture_admin_language";
const ACTIVE_VIEW_STORAGE_KEY = "furniture_admin_active_view";
const ACTIVE_PROJECT_ID_STORAGE_KEY = "furniture_admin_active_project_id";
const ACTIVE_PROJECT_TAB_STORAGE_KEY = "furniture_admin_active_project_tab";
const ADMIN_TOKEN_HASH_KEY = "mproject_token";
const ADMIN_LOGOUT_HASH_KEY = "mproject_logout";
const VIYAR_SERVICES_CACHE_PREFIX = "furniture_admin_viyar_services_cache";
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "" : "/api")
);
const ADMIN_ASSET_BASE_URL = import.meta.env.BASE_URL || "/";
const PAGE_SIZE = 20;

function buildAdminAssetUrl(path) {
  return `${ADMIN_ASSET_BASE_URL}${String(path || "").replace(/^\/+/, "")}`;
}

function consumeAdminTokenHandoff() {
  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const searchParams = new URLSearchParams(window.location.search);
  const shouldLogout =
    hashParams.get(ADMIN_LOGOUT_HASH_KEY) === "1" ||
    searchParams.get(ADMIN_LOGOUT_HASH_KEY) === "1";
  const handoffToken = (
    hashParams.get(ADMIN_TOKEN_HASH_KEY) ||
    searchParams.get(ADMIN_TOKEN_HASH_KEY) ||
    ""
  ).trim();

  if (shouldLogout && !handoffToken) {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.setItem(ACTIVE_VIEW_STORAGE_KEY, "home");
    localStorage.removeItem(ACTIVE_PROJECT_ID_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_TAB_STORAGE_KEY);
  }

  if (!handoffToken) {
    hashParams.delete(ADMIN_LOGOUT_HASH_KEY);
    searchParams.delete(ADMIN_LOGOUT_HASH_KEY);

    const cleanHash = hashParams.toString();
    const cleanSearch = searchParams.toString();
    const nextUrl = `${window.location.pathname}${cleanSearch ? `?${cleanSearch}` : ""}${cleanHash ? `#${cleanHash}` : ""}`;
    window.history.replaceState({}, document.title, nextUrl);

    return localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  }

  const previousToken = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  localStorage.setItem(TOKEN_STORAGE_KEY, handoffToken);

  if (handoffToken !== previousToken) {
    localStorage.setItem(ACTIVE_VIEW_STORAGE_KEY, "home");
    localStorage.removeItem(ACTIVE_PROJECT_ID_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_TAB_STORAGE_KEY);
  }

  hashParams.delete(ADMIN_TOKEN_HASH_KEY);
  hashParams.delete(ADMIN_LOGOUT_HASH_KEY);
  searchParams.delete(ADMIN_TOKEN_HASH_KEY);
  searchParams.delete(ADMIN_LOGOUT_HASH_KEY);

  const nextSearch = searchParams.toString();
  const nextHash = hashParams.toString();
  const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}${nextHash ? `#${nextHash}` : ""}`;
  window.history.replaceState(null, document.title, nextUrl);

  return handoffToken;
}
const DEFAULT_PROJECT_NAME = "Новий проект";
const DEFAULT_PROJECT_FORM = {
  projectName: DEFAULT_PROJECT_NAME,
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
  facadeEdgeBanding: "",
  insideEdgeBanding: "",
  facadeThickness: 18,
  insideThickness: 18,
  slideType: "tandem",
  bottomType: "hdf",
  handleType: "",
  handlePosition: "",
  notes: "",
};

const DRAWER_SLIDE_LENGTHS = [250, 300, 350, 400, 450, 500, 550, 600];

const PROJECT_DRAWER_TYPE_PRESETS = [
  {
    id: "drawer-type-dsp",
    image_url: "/static/project-drawers/drawer-dsp.jpg",
    pickerSubtitleUk: "Дно шухляди з ДСП 18 мм для більш жорсткої конструкції.",
    pickerSubtitleEn: "Drawer bottom made from 18 mm board for a more rigid build.",
    pickerTitleEn: "Drawer bottom DSP",
    pickerTitleUk: "Шухляда з ДСП",
    pickerValue: "dsp_18",
    search: "dsp dsp_18 drawer bottom board",
  },
  {
    id: "drawer-type-hdf",
    image_url: "/static/project-drawers/drawer-hdf.jpg",
    pickerSubtitleUk: "Класичне дно HDF / ДВП для легкої шухляди.",
    pickerSubtitleEn: "Classic HDF drawer bottom for a lighter drawer box.",
    pickerTitleEn: "Drawer bottom HDF",
    pickerTitleUk: "Шухляда з HDF",
    pickerValue: "hdf",
    search: "hdf hdf_3 drawer bottom fiberboard",
  },
];
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
    "wall_unit",
    "bathroom_vanity",
    "bathroom_shelf",
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
      facadeThickness: 18,
      insideThickness: 18,
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
      facadeThickness: 18,
      insideThickness: 18,
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
      facadeThickness: 18,
      insideThickness: 18,
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
      facadeThickness: 18,
      insideThickness: 18,
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
      facadeThickness: 18,
      insideThickness: 18,
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
      facadeThickness: 18,
      insideThickness: 18,
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
      facadeThickness: 18,
      insideThickness: 18,
      slideType: "telescopic",
      bottomType: "dsp_18",
    },
    image: "/static/project-start/wardrobe.jpg",
    titleKey: "projectTemplateBathroomShelfTitle",
    visual: "bathroom-shelf",
  },
];

const DEFAULT_CITY_OPTIONS = [
  "kyiv",
  "lviv",
  "odessa",
  "dnipro",
  "kharkiv",
  "khmelnytskyi",
  "rivne",
];

const MATERIAL_EDGE_SLOTS = [
  { key: "edge_04", label: "0,4 мм" },
  { key: "edge_08", label: "0,8 мм" },
  { key: "edge_1", label: "1 мм" },
  { key: "edge_1x43", label: "1х43 мм" },
  { key: "edge_2", label: "2 мм" },
  { key: "edge_2x43", label: "2х43 мм" },
];

const CATALOG_SERVICE_VIEWS = new Set([
  "catalogHub",
  "catalogViyar",
  "catalogManual",
  "catalogMaterials",
  "catalogFittings",
  "catalogHoles",
  "catalogFasteners",
  "catalogValues",
]);

const DEFAULT_FITTING_FORM = {
  article: "",
  city: "",
  code: "",
  fitting_group: "fittings",
  fitting_type: "drawer_slides",
  image_url: "",
  source_url: "",
  is_active: true,
  is_system: false,
  name: "",
  price: "",
  sort_order: 0,
  stock: "",
};

const DEFAULT_HOLE_TEMPLATE_FORM = {
  fitting_id: "",
  name: "",
  template_type: "manual",
  side: "left",
  coordinate_system: "2d",
  is_default: false,
  is_active: true,
  notes: "",
};

const DEFAULT_HOLE_POINT_FORM = {
  template_id: "",
  label: "",
  x_mm: "",
  y_mm: "",
  z_mm: "",
  diameter_mm: "",
  depth_mm: "",
  side: "front",
  operation: "drill",
  order_index: "0",
  quantity: "1",
  mirrored: false,
  notes: "",
};

function buildHolePointFormFromPoint(point) {
  return {
    template_id: String(point?.template_id ?? ""),
    label: String(point?.label ?? ""),
    x_mm: point?.x_mm ?? "",
    y_mm: point?.y_mm ?? "",
    z_mm: point?.z_mm ?? "",
    diameter_mm: point?.diameter_mm ?? "",
    depth_mm: point?.depth_mm ?? "",
    side: String(point?.side ?? "front"),
    operation: String(point?.operation ?? "drill"),
    order_index: point?.order_index ?? 0,
    quantity: point?.quantity ?? 1,
    mirrored: Boolean(point?.mirrored),
    notes: String(point?.notes ?? ""),
  };
}

function buildHoleTemplateFormFromTemplate(template) {
  return {
    fitting_id: String(template?.fitting_id ?? ""),
    name: String(template?.name ?? ""),
    template_type: String(template?.template_type ?? "manual"),
    side: String(template?.side ?? "left"),
    coordinate_system: String(template?.coordinate_system ?? "2d"),
    is_default: Boolean(template?.is_default),
    is_active: Boolean(template?.is_active ?? true),
    notes: String(template?.notes ?? ""),
  };
}

const HOLE_POINT_SIDE_OPTIONS = [
  { value: "front", labelKey: "holePointSideFront" },
  { value: "back", labelKey: "holePointSideBack" },
  { value: "left", labelKey: "holePointSideLeft" },
  { value: "right", labelKey: "holePointSideRight" },
  { value: "top", labelKey: "holePointSideTop" },
  { value: "bottom", labelKey: "holePointSideBottom" },
];

const HOLE_POINT_OPERATION_OPTIONS = [{ value: "drill", labelKey: "holePointOperationDrill" }];

const HOLE_POINT_SIDE_LABEL_KEYS = {
  front: "holePointSideFront",
  back: "holePointSideBack",
  left: "holePointSideLeft",
  right: "holePointSideRight",
  top: "holePointSideTop",
  bottom: "holePointSideBottom",
};

const HOLE_POINT_OPERATION_LABEL_KEYS = {
  drill: "holePointOperationDrill",
};

  const HOLE_TEMPLATE_TYPE_LABEL_KEYS = {
  manual: "holeTemplateTypeManual",
  auto: "holeTemplateTypeAuto",
};

const HOLE_TEMPLATE_COORDINATE_SYSTEM_LABEL_KEYS = {
  "2d": "holeTemplateCoordinateSystem2d",
  "3d": "holeTemplateCoordinateSystem3d",
};

function formatHolePointValue(value, labelKeys, t) {
  const rawValue = String(value || "").trim();

  if (!rawValue) {
    return "—";
  }

  const labelKey = labelKeys[rawValue];
  return labelKey ? t[labelKey] || rawValue : rawValue;
}

function formatHolePointSide(value, t) {
  return formatHolePointValue(value, HOLE_POINT_SIDE_LABEL_KEYS, t);
}

function formatHolePointOperation(value, t) {
  return formatHolePointValue(value, HOLE_POINT_OPERATION_LABEL_KEYS, t);
}

function formatHoleTemplateType(value, t) {
  return formatHolePointValue(value, HOLE_TEMPLATE_TYPE_LABEL_KEYS, t);
}

function formatHoleTemplateCoordinateSystem(value, t) {
  return formatHolePointValue(value, HOLE_TEMPLATE_COORDINATE_SYSTEM_LABEL_KEYS, t);
}

function detectFittingSourceSite(sourceUrl) {
  if (!sourceUrl) {
    return "manual";
  }

  const normalized = String(sourceUrl).trim().toLowerCase();

  if (!normalized) {
    return "manual";
  }

  if (normalized.includes("viyar")) {
    return "viyar";
  }

  if (normalized.includes("kronas")) {
    return "kronas";
  }

  if (normalized.includes("blum") || normalized.includes("mt")) {
    return "blum";
  }

  return "manual";
}

function compressImageFileToDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onerror = () => reject(new Error("Unable to read image"));
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => reject(new Error("Unable to open image"));
      image.onload = () => {
        const maxSize = 900;
        const scale = Math.min(maxSize / image.width, maxSize / image.height, 1);
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const context = canvas.getContext("2d");

        if (!context) {
          reject(new Error("Canvas is not supported"));
          return;
        }

        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL("image/jpeg", 0.82));
      };
      image.src = String(reader.result || "");
    };
    reader.readAsDataURL(file);
  });
}

function buildViyarServicesCacheKey(userId) {
  return `${VIYAR_SERVICES_CACHE_PREFIX}:${userId}`;
}

function readViyarServicesCache(userId) {
  if (!userId) {
    return null;
  }

  try {
    const rawValue = localStorage.getItem(buildViyarServicesCacheKey(userId));

    if (!rawValue) {
      return null;
    }

    const parsed = JSON.parse(rawValue);

    if (!Array.isArray(parsed?.items)) {
      return null;
    }

    return {
      items: parsed.items,
      priceSyncSummary: parsed.priceSyncSummary || null,
      source: parsed.source || "viyar",
      savedAt: parsed.savedAt || null,
    };
  } catch {
    return null;
  }
}

function writeViyarServicesCache(userId, payload) {
  if (!userId) {
    return;
  }

  try {
    localStorage.setItem(
      buildViyarServicesCacheKey(userId),
      JSON.stringify({
        items: Array.isArray(payload?.items) ? payload.items : [],
        priceSyncSummary: payload?.priceSyncSummary || null,
        source: payload?.source || "viyar",
        savedAt: new Date().toISOString(),
      }),
    );
  } catch {
    // Ignore cache write failures and keep runtime state working.
  }
}

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

function filterServiceCatalogTree(nodes, query) {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) {
    return nodes;
  }

  function filterNode(node) {
    const children = (node.children || [])
      .map(filterNode)
      .filter(Boolean);
    const haystack = [
      node.name,
      node.description,
      node.folder_path,
      node.slug,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    if (haystack.includes(normalizedQuery) || children.length) {
      return {
        ...node,
        children,
      };
    }

    return null;
  }

  return nodes.map(filterNode).filter(Boolean);
}

function collectServiceFolderCodes(nodes) {
  return nodes.flatMap((node) => {
    const nested = collectServiceFolderCodes(node.children || []);

    if (node.item_type === "folder") {
      return [node.external_code, ...nested];
    }

    return nested;
  });
}

function countServiceTreeItems(nodes) {
  return nodes.reduce((total, node) => {
    const own = node.item_type === "service" ? 1 : 0;
    return total + own + countServiceTreeItems(node.children || []);
  }, 0);
}

function flattenServiceTree(nodes) {
  return nodes.flatMap((node) => [
    node,
    ...flattenServiceTree(node.children || []),
  ]);
}

function formatDateTimeValue(value) {
  if (!value) {
    return "";
  }

  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }

  return parsed.toLocaleString("uk-UA");
}

function formatMetricValue(value) {
  if (value === null || value === undefined || value === "") {
    return "0";
  }

  const numericValue = Number(String(value).replace(",", "."));

  if (!Number.isFinite(numericValue)) {
    return String(value);
  }

  return Number.isInteger(numericValue)
    ? String(numericValue)
    : numericValue.toFixed(1).replace(/\.0$/, "");
}

function formatMaterialImportDiagnostic(value, limit = 280) {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();

  if (!normalized) {
    return "";
  }

  if (
    normalized.includes("libatk-1.0.so.0") ||
    normalized.includes("error while loading shared libraries")
  ) {
    return "На сервері відсутні системні залежності Playwright Chromium. Встановіть залежності браузера та повторіть імпорт.";
  }

  return normalized.length > limit
    ? `${normalized.slice(0, Math.max(0, limit - 3))}...`
    : normalized;
}

function isFastenerFitting(item) {
  if (item?.fitting_group) {
    return item.fitting_group === "fasteners";
  }

  const haystack = [
    item?.name,
    item?.article,
    item?.code,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return /(самор|стяж|конфирм|шуруп|гвинт|болт|гайк|дюб|метиз|screw|confirmat)/i.test(
    haystack,
  );
}

function normalizeCatalogView(view) {
  return view === "catalogFasteners" ? "catalogFittings" : view;
}

const FITTING_CATEGORY_VISUALS = {
  connectors_fasteners: {
    accent: "#f59e0b",
    icon: Blocks,
    image: "/static/fittings/connectors-fasteners.png",
  },
  drawer_slides: {
    accent: "#0f766e",
    icon: ChevronRight,
    image: "/static/fittings/drawer-slides.png",
  },
  handles_hooks: {
    accent: "#2563eb",
    icon: Wrench,
    image: "/static/fittings/handles-hooks.png",
  },
  profiles_gola: {
    accent: "#1f6b34",
    icon: LayoutGrid,
    image: "/static/fittings/profiles-gola.png",
  },
  plinth_vents: {
    accent: "#2f8ecb",
    icon: LayoutGrid,
    image: "/static/fittings/plinth-vents.png",
  },
  legs_wheels: {
    accent: "#8b5cf6",
    icon: LayoutGrid,
    image: "/static/fittings/legs-wheels.png",
  },
  locks_magnets: {
    accent: "#f97316",
    icon: Settings2,
    image: "/static/fittings/locks-magnets.png",
  },
  wardrobe_systems: {
    accent: "#14b8a6",
    icon: LayoutGrid,
    image: "/static/fittings/wardrobe-systems.png",
  },
  hinges: {
    accent: "#ec4899",
    icon: LayoutGrid,
    image: "/static/fittings/hinges.png",
  },
  bathroom: {
    accent: "#0ea5e9",
    icon: House,
    image: "/static/fittings/bathroom.png",
  },
  packaging: {
    accent: "#f97316",
    icon: Package,
    image: "/static/fittings/packaging.png",
  },
  bed_components: {
    accent: "#6366f1",
    icon: LayoutGrid,
    image: "/static/fittings/bed-components.png",
  },
  wardrobe_fillings: {
    accent: "#10b981",
    icon: LayoutGrid,
    image: "/static/fittings/wardrobe-fillings.png",
  },
  other_fittings: { accent: "#64748b", icon: Package },
  other_fasteners: { accent: "#92400e", icon: Blocks },
};

const CATALOG_TILE_VISUALS = {
  materials: {
    accent: "#2563eb",
    icon: LayoutGrid,
  },
  fittings: {
    accent: "#0f766e",
    icon: Wrench,
  },
  fasteners: {
    accent: "#f59e0b",
    icon: Blocks,
  },
  manual: {
    accent: "var(--brand-green)",
    icon: Wrench,
  },
  values: {
    accent: "#2f8ecb",
    icon: FileSliders,
  },
  viyar: {
    accent: "#1f6b34",
    icon: FolderTree,
  },
};

const HOME_QUICK_TILE_VISUALS = {
  materials: {
    accent: "#2563eb",
    icon: LayoutGrid,
  },
  fittings: {
    accent: "#0f766e",
    icon: Wrench,
  },
  fasteners: {
    accent: "#f59e0b",
    icon: Blocks,
  },
  services: {
    accent: "#1f6b34",
    icon: FolderTree,
  },
};

const VIYAR_FOLDER_TILE_VISUALS = {
  "viyar-folder-cutting": { accent: "#2f8ecb", icon: Scissors },
  "viyar-folder-drilling": { accent: "#14b8a6", icon: Drill },
  "viyar-folder-straight_edgebanding": { accent: "#3b82f6", icon: Blocks },
  "viyar-folder-milling": { accent: "#8b5cf6", icon: Settings2 },
  "viyar-folder-additional_services": { accent: "#f59e0b", icon: Wrench },
  "viyar-folder-curved_edgebanding": { accent: "#ec4899", icon: LayoutGrid },
  "viyar-folder-jointing": { accent: "#10b981", icon: Blocks },
  "viyar-folder-packing": { accent: "#f97316", icon: Package },
};

function updateServiceTreeNode(nodes, itemId, updater) {
  return nodes.map((node) => {
    if (node.id === itemId) {
      return updater(node);
    }

    if (node.children?.length) {
      return {
        ...node,
        children: updateServiceTreeNode(node.children, itemId, updater),
      };
    }

    return node;
  });
}

function ServiceCatalogTreeNode({
  collapsedFolders,
  level = 0,
  mutationLoading = false,
  node,
  loading = false,
  onSaveService,
  onServiceFieldChange,
  onToggleCollapse,
  searchQuery,
  t,
}) {
  const [isDescriptionOpen, setIsDescriptionOpen] = useState(false);
  const isFolder = node.item_type === "folder";
  const isCollapsed =
    isFolder &&
    !searchQuery.trim() &&
    Boolean(collapsedFolders[node.external_code]);
  const effectiveStatus = node.user_price_sync_status || node.price_sync_status;
  const effectiveSourceLabel =
    node.user_price_source_label || node.price_source_label;
  const hasVisiblePrice =
    node.user_price !== null &&
    node.user_price !== undefined;
  const nestedServiceCount = isFolder
    ? countServiceTreeItems(node.children || [])
    : 0;
  const rowPaddingLeft = isFolder
    ? `${level * 18}px`
    : `${Math.max(0, (level - 1) * 18)}px`;

  return (
    <li className={`service-tree-node ${isFolder ? "folder" : "service"}`}>
      <div
        data-folder-code={isFolder ? node.external_code : undefined}
        className={`service-tree-row${!isFolder ? " service-row" : ""}`}
        style={{ paddingLeft: rowPaddingLeft }}
      >
        {isFolder ? (
          <>
            <div className="service-tree-main">
              <button
                className="service-tree-collapse"
                onClick={() => onToggleCollapse(node.external_code)}
                type="button"
              >
                <ChevronRight
                  className={isCollapsed ? "" : "expanded"}
                  size={14}
                />
              </button>
              <span className={`service-tree-bullet ${isFolder ? "folder" : "service"}`} />
              <div className="service-tree-copy">
                <div className="service-tree-title-row">
                  <strong>{node.name}</strong>
                  {nestedServiceCount ? (
                    <span className="service-tree-folder-count">
                      {nestedServiceCount}
                    </span>
                  ) : null}
                </div>
                {node.description && isDescriptionOpen ? <span>{node.description}</span> : null}
              </div>
            </div>
            <div className="service-tree-meta">
              {node.description ? (
                <button
                  className="ghost-button compact-button service-tree-folder-action"
                  onClick={() => setIsDescriptionOpen((current) => !current)}
                  type="button"
                >
                  {isDescriptionOpen ? t.hideDescription : t.showDescription}
                </button>
              ) : null}
              <div className="service-tree-folder-meta">
                <span className="service-tree-badge subtle">{t.folder}</span>
              </div>
            </div>
          </>
        ) : (
          <div className="service-tree-service-line">
            <div className="service-tree-name-cell">
              <span className="service-tree-bullet service" />
              <strong>{node.name}</strong>
            </div>
            <label>
              <span>{t.viyarArticle}</span>
              <input
                disabled
                type="text"
                value={node.article || ""}
              />
            </label>
            <label>
              <span>{t.serviceUnit}</span>
              <input
                disabled={mutationLoading}
                onChange={(event) =>
                  onServiceFieldChange(node.id, "unit", event.target.value)
                }
                type="text"
                value={node.unit || ""}
              />
            </label>
            <label>
              <span>{t.basePrice}</span>
              <input
                disabled={mutationLoading}
                min="0"
                onChange={(event) =>
                  onServiceFieldChange(node.id, "base_price", event.target.value)
                }
                step="0.01"
                type="number"
                value={node.base_price ?? ""}
              />
            </label>
            <button
              className="ghost-button compact-button service-tree-inline-action"
              disabled={!node.description}
              onClick={() => setIsDescriptionOpen((current) => !current)}
              type="button"
            >
              {isDescriptionOpen ? t.hideDescription : t.showDescription}
            </button>
            <label className="toggle-label">
              <input
                checked={Boolean(node.is_calculable)}
                disabled={mutationLoading}
                onChange={(event) =>
                  onServiceFieldChange(node.id, "is_calculable", event.target.checked)
                }
                type="checkbox"
              />
              {t.viyarCalculable}
            </label>
            <label className="toggle-label">
              <input
                checked={Boolean(node.is_active)}
                disabled={mutationLoading}
                onChange={(event) =>
                  onServiceFieldChange(node.id, "is_active", event.target.checked)
                }
                type="checkbox"
              />
              {t.enabled}
            </label>
            <button
              className="ghost-button compact-button"
              disabled={mutationLoading}
              onClick={() => onSaveService(node)}
              type="button"
            >
              <Save size={16} />
              {t.save}
            </button>
          </div>
        )}
      </div>
      {node.description && isDescriptionOpen ? (
        <div
          className={`service-tree-description-panel${isFolder ? " folder-description-panel" : ""}`}
          style={{ marginLeft: `${Math.max(0, (level - 1) * 18) + (isFolder ? 18 : 32)}px` }}
        >
          <strong>{t.showDescription}</strong>
          <p>{node.description}</p>
        </div>
      ) : null}
      {node.children?.length && !isCollapsed ? (
        <ul className="service-tree-list">
          {node.children.map((child) => (
            <ServiceCatalogTreeNode
              collapsedFolders={collapsedFolders}
              key={child.external_code}
              level={level + 1}
              loading={loading}
              mutationLoading={mutationLoading}
              node={child}
              onSaveService={onSaveService}
              onServiceFieldChange={onServiceFieldChange}
              onToggleCollapse={onToggleCollapse}
              searchQuery={searchQuery}
              t={t}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

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
    myData: "My data",
    username: "Username",
    phone: "Phone",
    saveProfile: "Save profile",
    profileSaved: "Profile saved",
    requestEmailChange: "Request email change",
    newEmail: "New email",
    emailChangeRequested: "Email change request created",
    usernameChangeWeekly: "Username can be changed only once every 7 days",
    pendingRequests: "Pending requests",
    noPendingRequests: "No pending requests",
    changeType: "Change type",
    oldValue: "Current value",
    newValue: "Requested value",
    requestedAt: "Requested at",
    approve: "Approve",
    reject: "Reject",
    requestReviewed: "Request reviewed",
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
    clearEdge: "Clear edge",
    dataProject: "Project data",
    cuttingArea: "Area, m2",
    cuttingEdge: "Edge, m",
    cuttingExportCode: "Code",
    cuttingGrain: "Grain",
    cuttingLength: "Cut, m",
    cuttingSize: "Size",
    cuttingSummary: "Summary",
    bottomType: "Bottom type",
    bottom_type: "Bottom type",
    brandTagline: "Furniture production platform",
    bottom: "Bottom",
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
    edgeBandingInvalid: "Select a value from the edge banding catalog",
    edgeEditor: "Edge processing",
    edgeEditorDescription: "Edit edge banding for the selected production part.",
    edgeSaved: "Part edges updated",
    edgeSelectSide: "Select a side on the scheme or in the quick selector.",
    edgeSelectedSide: "Selected side",
    edgeThicknessInvalid: "Edge thickness could not be determined",
    email: "Email",
    machiningAddGroove: "Add groove",
    machiningAddHole: "Add hole",
    machiningAddQuarter: "Add quarter",
    machiningEditor: "Machining editor",
    machiningSaved: "Part machining updated",
    enabled: "Enabled",
    disabled: "Disabled",
    forCalculation: "For calculation",
    entity: "Entity",
    edge_banding: "Edge banding",
    facadeMaterial: "Facade material",
    furniturePlatform: "MProject.furniture",
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
    loginOrEmail: "Login or email",
    logout: "Logout",
    noDetails: "No details",
    noCuttingItems: "No cutting items yet.",
    newPassword: "New password",
    newProjectDefault: "New project",
    notSet: "Not set",
    materialThickness: "Thickness",
    material_thickness: "Thickness",
    notes: "Notes",
    of: "of",
    onlyMine: "Only mine",
    password: "Password",
    showPassword: "Show password",
    hidePassword: "Hide password",
    passwordChanged: "Password changed",
    passwordMustBeLong: "Password must be at least 8 characters",
    passwordReset: "Password reset",
    projectDeleted: "Project deleted",
    projectDeleteRestricted: "You do not have permission to delete this project",
    projectEditRestricted: "You do not have permission to edit this project",
    projectCreated: "Project created",
    projectName: "Project name",
    projectNotFound: "Project not found",
    projectDetails: "Project details",
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
    holePreviewCoordinates: "Coordinates",
    holePreviewDepth: "Depth",
    holePreviewDiameter: "Diameter",
    holePreviewEmpty: "No hole points added yet",
    holePreviewHelper: "Preview uses the saved point coordinates and a scaled working plane.",
    holePreviewOperation: "Operation",
    holePreviewSide: "Side",
    holePreviewTitle: "2D preview",
    holeTabDescription: "View hole templates and hole points for the selected fitting.",
    holeTabPreview: "2D preview",
    holeTabPoints: "Points",
    holeTabSearchPlaceholder: "Search services",
    holeTabTemplates: "Templates",
    holeTabTitle: "Holes",
    holeReadOnlyBadge: "Read-only",
    holePointsTitle: "Hole points",
    holeWorkspaceConnectionVariantTitle: "Connection variant",
    holeWorkspaceFittingInfoArticle: "Article",
    holeWorkspaceFittingInfoDescription: "Description",
    holeWorkspaceFittingInfoTitle: "Fitting info",
    holeWorkspaceNoImage: "No image",
    holeWorkspacePreview3dPlaceholder:
      "The 3D view of panels, faces and holes will be added here.",
    holeWorkspacePreview3dTitle: "3D preview",
    holeWorkspaceSelected: "Selected",
    holeWorkspaceVariantEdgeToFace: "Edge → face",
    holeWorkspaceVariantFaceToEdge: "Face → edge",
    holeWorkspaceVariantHorizontalToVertical: "Horizontal → vertical",
    holeWorkspaceVariantVerticalToHorizontal: "Vertical → horizontal",
    holePointAdd: "Add point",
    holePointCreateDescription: "Create a new hole point for the selected template.",
    holePointCreateFailed: "Unable to create hole point",
    holePointCreateSuccess: "Hole point created",
    holePointCreateTitle: "Add hole point",
    holePointDepth: "Depth, mm",
    holePointDiameter: "Diameter, mm",
    holePointDiameterInvalid: "Diameter must be a valid positive number",
    holePointDiameterRequired: "Diameter is required",
    holePointTypeAuto: "Auto",
    holePointTypeManual: "Manual",
    holePointAction: "Action",
    holePointLabel: "Label",
    holePointMirrored: "Mirrored",
    holePointNotes: "Notes",
    holePointNumericInvalid: "Enter valid numeric values",
    holePointEdit: "Edit",
    holePointEditDescription: "Update the selected hole point.",
    holePointEditFailed: "Unable to open hole point for editing",
    holePointEditTitle: "Edit hole point",
    holePointOperation: "Operation",
    holePointOperationDrill: "Drilling",
    holePointOrderIndex: "Order index",
    holePointOrderIndexInvalid: "Order index must be a whole number",
    holePointQuantity: "Quantity",
    holePointQuantityInvalid: "Quantity must be at least 1",
    holePointSelectionNo: "No",
    holePointSelectionYes: "Yes",
    holePointSaveChanges: "Save changes",
    holePointUpdateFailed: "Unable to update hole point",
    holePointUpdateSuccess: "Hole point updated",
    holePointSide: "Side",
    holePointSideBack: "Back face",
    holePointSideBottom: "Bottom edge",
    holePointSideFront: "Front face",
    holePointSideLeft: "Left edge",
    holePointSideRight: "Right edge",
    holePointSideTop: "Top edge",
    holePointTemplate: "Template",
    holePointTemplateRequired: "Select a template before creating a point",
    holeTemplateActive: "Active",
    holeTemplateCoordinateSystem: "System",
    holeTemplateCreateDescription: "Create a new template for the selected fitting.",
    holeTemplateCreateTitle: "Add template",
    holeTemplateEdit: "Edit",
    holeTemplateEditDescription: "Update the hole template for the selected fitting.",
    holeTemplateEditFailed: "Unable to open hole template for editing",
    holeTemplateEditTitle: "Edit hole template",
    holeTemplateCoordinateSystem2d: "2D",
    holeTemplateCoordinateSystem3d: "3D",
    holeTemplateDefault: "Default",
    holeTemplateFitting: "Fitting",
    holeTemplateFittingRequired: "Select a fitting before creating a template",
    holeTemplateFittingInfoArticle: "Article",
    holeTemplateFittingInfoDescription: "Description",
    holeTemplateFittingInfoImageAlt: "Fitting image",
    holeTemplateFittingInfoNoImage: "No image",
    holeTemplateFittingInfoTitle: "Fitting",
    holeTemplateMountingSchemePlaceholder: "Choose the board side used by this hole template.",
    holeTemplateMountingSchemeTitle: "Template side",
    holeTemplateConnectionVariantPlaceholder:
      "Fitting connection schemes will be added in the next step.",
    holeTemplateConnectionVariantTitle: "Connection variant",
    holeTemplateMountingSchemeLeftEdge: "Left edge",
    holeTemplateMountingSchemeRightEdge: "Right edge",
    holeTemplateMountingSchemeTop: "Top",
    holeTemplateMountingSchemeBottom: "Bottom",
    holeTemplateMountingSchemeSelected: "Selected",
    holeTemplateName: "Name",
    holeTemplateNameRequired: "Template name is required",
    holeTemplateNotes: "Notes",
    holeTemplateRefresh: "Refresh",
    holeTemplateSave: "Save",
    holeTemplateSaveChanges: "Save changes",
    holeTemplateSide: "Side",
    holeTemplateTitle: "Templates",
    holeTemplateType: "Type",
    holeTemplateUpdateFailed: "Unable to update hole template",
    holeTemplateUpdateSuccess: "Hole template updated",
    holeTemplateEmpty: "No templates added yet",
    holeTemplateSelectFitting: "Select fitting",
    holeTemplateSelectTemplate: "Select template",
    holeTemplateColumnId: "ID",
    holeTemplateColumnName: "Name",
    holeTemplateColumnType: "Type",
    holeTemplateColumnSide: "Side",
    holeTemplateColumnSystem: "System",
    holeTemplateColumnNotes: "Notes",
    holeTemplateColumnDefault: "Default",
    holeTemplateColumnActive: "Active",
    holeTemplateTypeAuto: "Auto",
    holeTemplateTypeManual: "Manual",
    holeTemplateTypeSelectAuto: "Auto",
    holeTemplateTypeSelectManual: "Manual",
    holePointColumnId: "ID",
    holePointColumnLabel: "Label",
    holePointColumnDepth: "Depth",
    holePointColumnSide: "Side",
    holePointColumnOperation: "Operation",
    holePointColumnOrder: "Order",
    holePointPreviewTitle: "2D preview",
    holePointPreviewHelper: "Preview uses the saved point coordinates and a scaled working plane.",
    holePointX: "X, mm",
    holePointY: "Y, mm",
    holePointZ: "Z, mm",
    productionPartBack: "Back to production",
    productionPartWorkspace: "Detail workspace",
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
    showProjectOverview: "Show project overview",
    side: "Side",
    slideType: "Slide type",
    hideProjectOverview: "Hide project overview",
    slide_type: "Slide type",
    signIn: "Sign in",
    settings: "Settings",
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
    unableToSaveEdges: "Unable to save part edges",
    unableToSaveMachining: "Unable to save part machining",
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
    myData: "\u041c\u043e\u0457 \u0434\u0430\u043d\u0456",
    username: "\u041b\u043e\u0433\u0456\u043d",
    phone: "\u0422\u0435\u043b\u0435\u0444\u043e\u043d",
    saveProfile: "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u043f\u0440\u043e\u0444\u0456\u043b\u044c",
    profileSaved: "\u041f\u0440\u043e\u0444\u0456\u043b\u044c \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e",
    requestEmailChange: "\u0417\u0430\u043f\u0438\u0442\u0438 \u0437\u043c\u0456\u043d\u0443 email",
    newEmail: "\u041d\u043e\u0432\u0430 \u043f\u043e\u0448\u0442\u0430",
    emailChangeRequested: "\u0417\u0430\u043f\u0438\u0442 \u043d\u0430 \u0437\u043c\u0456\u043d\u0443 email \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043e",
    usernameChangeWeekly: "\u041b\u043e\u0433\u0456\u043d \u043c\u043e\u0436\u043d\u0430 \u0437\u043c\u0456\u043d\u044e\u0432\u0430\u0442\u0438 \u043d\u0435 \u0447\u0430\u0441\u0442\u0456\u0448\u0435 \u043d\u0456\u0436 \u0440\u0430\u0437 \u043d\u0430 7 \u0434\u043d\u0456\u0432",
    pendingRequests: "\u0417\u0430\u043f\u0438\u0442\u0438 \u0432 \u043e\u0447\u0456\u043a\u0443\u0432\u0430\u043d\u043d\u0456",
    noPendingRequests: "\u041d\u0435\u043c\u0430\u0454 \u0437\u0430\u043f\u0438\u0442\u0456\u0432 \u0432 \u043e\u0447\u0456\u043a\u0443\u0432\u0430\u043d\u043d\u0456",
    changeType: "\u0422\u0438\u043f \u0437\u043c\u0456\u043d\u0438",
    oldValue: "\u041f\u043e\u0442\u043e\u0447\u043d\u0435 \u0437\u043d\u0430\u0447\u0435\u043d\u043d\u044f",
    newValue: "\u041d\u043e\u0432\u0435 \u0437\u043d\u0430\u0447\u0435\u043d\u043d\u044f",
    requestedAt: "\u0421\u0442\u0432\u043e\u0440\u0435\u043d\u043e",
    approve: "\u041f\u043e\u0433\u043e\u0434\u0438\u0442\u0438",
    reject: "\u0412\u0456\u0434\u0445\u0438\u043b\u0438\u0442\u0438",
    requestReviewed: "\u0417\u0430\u043f\u0438\u0442 \u043e\u043f\u0440\u0430\u0446\u044c\u043e\u0432\u0430\u043d\u043e",
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
    dataProject: "Дані проекту",
    cuttingArea: "Площа, м2",
    cuttingEdge: "Крайка, м",
    cuttingExportCode: "Код",
    cuttingGrain: "Волокно",
    cuttingLength: "Різ, м",
    cuttingSize: "Розмір",
    cuttingSummary: "Підсумок",
    bottomType: "Тип дна",
    bottom_type: "Тип дна",
    brandTagline: "Професійне рішення для меблевого виробництва",
    bottom: "Низ",
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
    edgeEditor: "Обробка торців",
    edgeEditorDescription: "Редагування крайки для вибраної виробничої деталі.",
    edgeSaved: "Крайку деталі оновлено",
    email: "Email",
    machiningAddGroove: "Додати паз",
    machiningAddHole: "Додати отвір",
    machiningAddQuarter: "Додати чверть",
    machiningEditor: "Редактор обробки",
    machiningSaved: "Обробку деталі оновлено",
    enabled: "Увімкнено",
    entity: "Сутність",
    edge_banding: "Крайка",
    facadeMaterial: "Матеріал фасаду",
    furniturePlatform: "MProject.furniture",
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
    loginOrEmail: "\u041b\u043e\u0433\u0456\u043d \u0430\u0431\u043e email",
    logout: "Вийти",
    noDetails: "Без деталей",
    noCuttingItems: "Карта розкрою ще порожня.",
    newPassword: "Новий пароль",
    newProjectDefault: "Новий проект",
    notSet: "Не вказано",
    materialThickness: "Товщина",
    material_thickness: "Товщина",
    notes: "Нотатки",
    of: "з",
    onlyMine: "Тільки мої",
    password: "Пароль",
    showPassword: "Показати пароль",
    hidePassword: "Сховати пароль",
    passwordChanged: "Пароль змінено",
    passwordMustBeLong: "Пароль має містити мінімум 8 символів",
    passwordReset: "Пароль скинуто",
    projectDeleted: "Проект видалено",
    projectDeleteRestricted: "У вас немає прав для видалення цього проекту",
    projectEditRestricted: "У вас немає прав для редагування цього проекту",
    projectCreated: "Проект створено",
    projectName: "Назва проекту",
    projectNotFound: "Проект не знайдено",
    projectDetails: "Деталі проекту",
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
    productionPartBack: "Назад до виробництва",
    productionPartWorkspace: "Робоче місце деталі",
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
    showProjectOverview: "Показати дані проекту",
    side: "Сторона",
    slideType: "Тип направляючих",
    hideProjectOverview: "Сховати дані проекту",
    slide_type: "Тип направляючих",
    signIn: "Увійти",
    settings: "\u041d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f",
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
    unableToSaveEdges: "Не вдалося зберегти крайку деталі",
    unableToSaveMachining: "Не вдалося зберегти обробку деталі",
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
  clearEdge: TRANSLATIONS.en.clearEdge || "Clear edge",
  edgeBandingInvalid:
    TRANSLATIONS.en.edgeBandingInvalid || "Select a value from the edge banding catalog",
  edgeSelectSide:
    TRANSLATIONS.en.edgeSelectSide || "Select a side on the scheme or in the quick selector.",
  edgeSelectedSide: TRANSLATIONS.en.edgeSelectedSide || "Selected side",
  edgeThicknessInvalid:
    TRANSLATIONS.en.edgeThicknessInvalid || "Edge thickness could not be determined",
  preview2d: TRANSLATIONS.en.preview2d || "2D map",
  preview3d: TRANSLATIONS.en.preview3d || "3D panel",
  preview3dInteractiveHint:
    TRANSLATIONS.en.preview3dInteractiveHint || "LMB rotate, RMB move, wheel zoom.",
  productionAssembly3d: TRANSLATIONS.en.productionAssembly3d || "3D assembly",
  productionAssemblyHint:
    TRANSLATIONS.en.productionAssemblyHint ||
    "This 3D assembly is based on the cutting map. Click a panel to open its detail workspace.",
  rotateLeft: TRANSLATIONS.en.rotateLeft || "Left",
  rotateRight: TRANSLATIONS.en.rotateRight || "Right",
  resetView: TRANSLATIONS.en.resetView || "Reset",
  preview3dHint:
    TRANSLATIONS.en.preview3dHint ||
    "3D preview for visual inspection. Use 2D mode for precise edge editing and machining coordinates.",
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
  holePreviewCoordinates: "\u041a\u043e\u043e\u0440\u0434\u0438\u043d\u0430\u0442\u0438",
  holePreviewDepth: "\u0413\u043b\u0438\u0431\u0438\u043d\u0430",
  holePreviewDiameter: "\u0414\u0456\u0430\u043c\u0435\u0442\u0440",
  holePreviewEmpty: "\u0422\u043e\u0447\u043a\u0438 \u043e\u0442\u0432\u043e\u0440\u0456\u0432 \u0449\u0435 \u043d\u0435 \u0434\u043e\u0434\u0430\u043d\u0456",
  holePreviewHelper: "\u041f\u0440\u0435\u0432'\u044e \u043f\u043e\u043a\u0430\u0437\u0443\u0454 \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u0456 \u043a\u043e\u043e\u0440\u0434\u0438\u043d\u0430\u0442\u0438 \u0442\u043e\u0447\u043e\u043a \u043d\u0430 \u043c\u0430\u0441\u0448\u0442\u0430\u0431\u043e\u0432\u0430\u043d\u0456\u0439 \u043f\u043b\u043e\u0449\u0438\u043d\u0456.",
  holePreviewOperation: "\u041e\u043f\u0435\u0440\u0430\u0446\u0456\u044f",
  holePreviewSide: "\u0421\u0442\u043e\u0440\u043e\u043d\u0430",
  holePreviewTitle: "2D перегляд",
  holeTabDescription: "\u041f\u0435\u0440\u0435\u0433\u043b\u044f\u0434 \u0448\u0430\u0431\u043b\u043e\u043d\u0456\u0432 \u0456 \u0442\u043e\u0447\u043e\u043a \u043e\u0442\u0432\u043e\u0440\u0456\u0432 \u0434\u043b\u044f \u0432\u0438\u0431\u0440\u0430\u043d\u043e\u0457 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438.",
  holeTabPreview: "2D \u043f\u0435\u0440\u0435\u0433\u043b\u044f\u0434",
  holeTabPoints: "\u0422\u043e\u0447\u043a\u0438",
  holeTabSearchPlaceholder: "\u041f\u043e\u0448\u0443\u043a \u043f\u043e\u0441\u043b\u0443\u0433",
  holeTabTemplates: "\u0428\u0430\u0431\u043b\u043e\u043d\u0438",
  holeTabTitle: "\u041e\u0442\u0432\u043e\u0440\u0438",
  holeReadOnlyBadge: "\u041b\u0456\u0448\u0435 \u043f\u0435\u0440\u0435\u0433\u043b\u044f\u0434",
  holePointsTitle: "\u0422\u043e\u0447\u043a\u0438 \u043e\u0442\u0432\u043e\u0440\u0456\u0432",
  holeWorkspaceConnectionVariantTitle: "\u0412\u0430\u0440\u0456\u0430\u043d\u0442 \u043a\u0440\u0456\u043f\u043b\u0435\u043d\u043d\u044f",
  holeWorkspaceFittingInfoArticle: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b",
  holeWorkspaceFittingInfoDescription: "\u041e\u043f\u0438\u0441",
  holeWorkspaceFittingInfoTitle: "\u0406\u043d\u0444\u043e\u0440\u043c\u0430\u0446\u0456\u044f \u043f\u0440\u043e \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443",
  holeWorkspaceNoImage: "\u0411\u0435\u0437 \u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u043d\u044f",
  holeWorkspacePreview3dPlaceholder:
    "\u0422\u0443\u0442 \u0431\u0443\u0434\u0435 3D \u043e\u0433\u043b\u044f\u0434 \u0434\u0435\u0442\u0430\u043b\u0435\u0439, \u043f\u043b\u043e\u0449\u0438\u043d \u0456 \u043e\u0442\u0432\u043e\u0440\u0456\u0432.",
  holeWorkspacePreview3dTitle: "3D \u043f\u0435\u0440\u0435\u0433\u043b\u044f\u0434",
  holeWorkspaceSelected: "\u041e\u0431\u0440\u0430\u043d\u043e",
  holeWorkspaceVariantEdgeToFace: "\u0422\u043e\u0440\u0435\u0446\u044c \u2192 \u043f\u043b\u043e\u0449\u0438\u043d\u0430",
  holeWorkspaceVariantFaceToEdge: "\u041f\u043b\u043e\u0449\u0438\u043d\u0430 \u2192 \u0442\u043e\u0440\u0435\u0446\u044c",
  holeWorkspaceVariantHorizontalToVertical: "\u0413\u043e\u0440\u0438\u0437\u043e\u043d\u0442\u0430\u043b\u044c \u2192 \u0432\u0435\u0440\u0442\u0438\u043a\u0430\u043b\u044c",
  holeWorkspaceVariantVerticalToHorizontal: "\u0412\u0435\u0440\u0442\u0438\u043a\u0430\u043b\u044c \u2192 \u0433\u043e\u0440\u0438\u0437\u043e\u043d\u0442\u0430\u043b\u044c",
  holePointAdd: "\u0414\u043e\u0434\u0430\u0442\u0438 \u0442\u043e\u0447\u043a\u0443",
  holePointCreateDescription: "\u0421\u0442\u0432\u043e\u0440\u0435\u043d\u043d\u044f \u043d\u043e\u0432\u043e\u0457 \u0442\u043e\u0447\u043a\u0438 \u0434\u043b\u044f \u0432\u0438\u0431\u0440\u0430\u043d\u043e\u0433\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443.",
  holePointCreateFailed: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0441\u0442\u0432\u043e\u0440\u0438\u0442\u0438 \u0442\u043e\u0447\u043a\u0443 \u043e\u0442\u0432\u043e\u0440\u0443",
  holePointCreateSuccess: "\u0422\u043e\u0447\u043a\u0443 \u043e\u0442\u0432\u043e\u0440\u0443 \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043e",
  holePointCreateTitle: "\u0414\u043e\u0434\u0430\u0442\u0438 \u0442\u043e\u0447\u043a\u0443 \u043e\u0442\u0432\u043e\u0440\u0443",
  holePointDepth: "\u0413\u043b\u0438\u0431\u0438\u043d\u0430, \u043c\u043c",
  holePointDiameter: "\u0414\u0456\u0430\u043c\u0435\u0442\u0440, \u043c\u043c",
  holePointDiameterInvalid: "\u0414\u0456\u0430\u043c\u0435\u0442\u0440 \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 \u0434\u0456\u0439\u0441\u043d\u0438\u043c \u0434\u043e\u0434\u0430\u0442\u043d\u0438\u043c \u0447\u0438\u0441\u043b\u043e\u043c",
  holePointDiameterRequired: "\u0414\u0456\u0430\u043c\u0435\u0442\u0440 \u043e\u0431\u043e\u0432'\u044f\u0437\u043a\u043e\u0432\u0438\u0439",
  holePointTypeAuto: "Auto",
  holePointTypeManual: "Manual",
  holePointAction: "\u0414\u0456\u044f",
  holePointLabel: "\u041c\u0456\u0442\u043a\u0430",
  holePointMirrored: "\u0414\u0443\u0431\u043b\u044c\u043e\u0432\u0430\u043d\u0430",
  holePointNotes: "\u041f\u0440\u0438\u043c\u0456\u0442\u043a\u0438",
  holePointNumericInvalid: "\u0412\u0432\u0435\u0434\u0456\u0442\u044c \u043a\u043e\u0440\u0435\u043a\u0442\u043d\u0456 \u0447\u0438\u0441\u043b\u043e\u0432\u0456 \u0437\u043d\u0430\u0447\u0435\u043d\u043d\u044f",
  holePointEdit: "\u0420\u0435\u0434\u0430\u0433\u0443\u0432\u0430\u0442\u0438",
  holePointEditDescription: "\u041e\u043d\u043e\u0432\u0456\u0442\u044c \u0432\u0438\u0431\u0440\u0430\u043d\u0443 \u0442\u043e\u0447\u043a\u0443 \u043e\u0442\u0432\u043e\u0440\u0443.",
  holePointEditFailed: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0432\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u0442\u043e\u0447\u043a\u0443 \u0434\u043b\u044f \u0440\u0435\u0434\u0430\u0433\u0443\u0432\u0430\u043d\u043d\u044f",
  holePointEditTitle: "\u0420\u0435\u0434\u0430\u0433\u0443\u0432\u0430\u0442\u0438 \u0442\u043e\u0447\u043a\u0443 \u043e\u0442\u0432\u043e\u0440\u0443",
  holePointOperation: "\u041e\u043f\u0435\u0440\u0430\u0446\u0456\u044f",
  holePointOperationDrill: "\u0421\u0432\u0435\u0440\u0434\u043b\u0456\u043d\u043d\u044f",
  holePointOrderIndex: "\u041f\u043e\u0440\u044f\u0434\u043e\u043a",
  holePointOrderIndexInvalid: "\u041f\u043e\u0440\u044f\u0434\u043e\u043a \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 \u0446\u0456\u043b\u0438\u043c \u0447\u0438\u0441\u043b\u043e\u043c",
  holePointQuantity: "\u041a\u0456\u043b\u044c\u043a\u0456\u0441\u0442\u044c",
  holePointQuantityInvalid: "\u041a\u0456\u043b\u044c\u043a\u0456\u0441\u0442\u044c \u043c\u0430\u0454 \u0431\u0443\u0442\u0438 \u0449\u043e\u043d\u0430\u0439\u043c\u0435\u043d\u0448\u0435 1",
  holePointSelectionNo: "\u041d\u0456",
  holePointSelectionYes: "\u0422\u0430\u043a",
  holePointSaveChanges: "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u0437\u043c\u0456\u043d\u0438",
  holePointUpdateFailed: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u043e\u043d\u043e\u0432\u0438\u0442\u0438 \u0442\u043e\u0447\u043a\u0443 \u043e\u0442\u0432\u043e\u0440\u0443",
  holePointUpdateSuccess: "\u0422\u043e\u0447\u043a\u0443 \u043e\u0442\u0432\u043e\u0440\u0443 \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
  holePointSide: "\u0421\u0442\u043e\u0440\u043e\u043d\u0430",
  holePointSideBack: "\u0417\u0430\u0434\u043d\u044f \u043f\u043b\u043e\u0449\u0438\u043d\u0430",
  holePointSideBottom: "\u041d\u0438\u0436\u043d\u0456\u0439 \u0442\u043e\u0440\u0435\u0446\u044c",
  holePointSideFront: "\u0424\u0430\u0441\u0430\u0434 / \u043f\u0435\u0440\u0435\u0434\u043d\u044f \u043f\u043b\u043e\u0449\u0438\u043d\u0430",
  holePointSideLeft: "\u041b\u0456\u0432\u0438\u0439 \u0442\u043e\u0440\u0435\u0446\u044c",
  holePointSideRight: "\u041f\u0440\u0430\u0432\u0438\u0439 \u0442\u043e\u0440\u0435\u0446\u044c",
  holePointSideTop: "\u0412\u0435\u0440\u0445\u043d\u0456\u0439 \u0442\u043e\u0440\u0435\u0446\u044c",
  holePointTemplate: "\u0428\u0430\u0431\u043b\u043e\u043d",
  holePointTemplateRequired: "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0448\u0430\u0431\u043b\u043e\u043d \u043f\u0435\u0440\u0435\u0434 \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043d\u044f\u043c \u0442\u043e\u0447\u043a\u0438",
  holeTemplateActive: "\u0410\u043a\u0442\u0438\u0432\u043d\u0438\u0439",
  holeTemplateCoordinateSystem: "\u0421\u0438\u0441\u0442\u0435\u043c\u0430",
  holeTemplateCreateDescription: "\u0421\u0442\u0432\u043e\u0440\u0435\u043d\u043d\u044f \u043d\u043e\u0432\u043e\u0433\u043e \u0448\u0430\u0431\u043b\u043e\u043d\u0443 \u0434\u043b\u044f \u0432\u0438\u0431\u0440\u0430\u043d\u043e\u0457 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438.",
  holeTemplateCreateTitle: "\u0414\u043e\u0434\u0430\u0442\u0438 \u0448\u0430\u0431\u043b\u043e\u043d",
  holeTemplateEdit: "\u0420\u0435\u0434\u0430\u0433\u0443\u0432\u0430\u0442\u0438",
  holeTemplateEditDescription: "\u041e\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f \u0448\u0430\u0431\u043b\u043e\u043d\u0443 \u043e\u0442\u0432\u043e\u0440\u0456\u0432 \u0434\u043b\u044f \u0432\u0438\u0431\u0440\u0430\u043d\u043e\u0457 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438.",
  holeTemplateEditFailed: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0432\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u0448\u0430\u0431\u043b\u043e\u043d \u043e\u0442\u0432\u043e\u0440\u0456\u0432 \u0434\u043b\u044f \u0440\u0435\u0434\u0430\u0433\u0443\u0432\u0430\u043d\u043d\u044f",
  holeTemplateEditTitle: "\u0420\u0435\u0434\u0430\u0433\u0443\u0432\u0430\u0442\u0438 \u0448\u0430\u0431\u043b\u043e\u043d \u043e\u0442\u0432\u043e\u0440\u0456\u0432",
  holeTemplateDefault: "\u0417\u0430 \u0437\u0430\u043c\u043e\u0432\u0447\u0443\u0432\u0430\u043d\u043d\u044f\u043c",
  holeTemplateFitting: "\u0424\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
  holeTemplateFittingRequired: "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443 \u043f\u0435\u0440\u0435\u0434 \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043d\u044f\u043c \u0448\u0430\u0431\u043b\u043e\u043d\u0443",
  holeTemplateFittingInfoArticle: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b",
  holeTemplateFittingInfoDescription: "\u041e\u043f\u0438\u0441",
  holeTemplateFittingInfoImageAlt: "\u0417\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u043d\u044f \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438",
  holeTemplateFittingInfoNoImage: "\u0411\u0435\u0437 \u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u043d\u044f",
  holeTemplateFittingInfoTitle: "\u0424\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
  holeTemplateMountingSchemePlaceholder:
    "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0441\u0442\u043e\u0440\u043e\u043d\u0443 \u0434\u0435\u0442\u0430\u043b\u0456, \u0434\u043e \u044f\u043a\u043e\u0457 \u043f\u0440\u0438\u0432'\u044f\u0437\u0430\u043d\u0438\u0439 \u0448\u0430\u0431\u043b\u043e\u043d \u043e\u0442\u0432\u043e\u0440\u0456\u0432.",
  holeTemplateMountingSchemeTitle: "\u0421\u0442\u043e\u0440\u043e\u043d\u0430 \u0448\u0430\u0431\u043b\u043e\u043d\u0443",
  holeTemplateConnectionVariantPlaceholder:
    "\u0422\u0443\u0442 \u0431\u0443\u0434\u0435 \u0432\u0438\u0431\u0456\u0440 \u0441\u0445\u0435\u043c\u0438 \u0437\u2019\u0454\u0434\u043d\u0430\u043d\u043d\u044f \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438.",
  holeTemplateConnectionVariantTitle: "\u0412\u0430\u0440\u0456\u0430\u043d\u0442 \u043a\u0440\u0456\u043f\u043b\u0435\u043d\u043d\u044f",
  holeTemplateMountingSchemeLeftEdge: "\u041b\u0456\u0432\u0438\u0439 \u0442\u043e\u0440\u0435\u0446\u044c",
  holeTemplateMountingSchemeRightEdge: "\u041f\u0440\u0430\u0432\u0438\u0439 \u0442\u043e\u0440\u0435\u0446\u044c",
  holeTemplateMountingSchemeTop: "\u0412\u0435\u0440\u0445",
  holeTemplateMountingSchemeBottom: "\u041d\u0438\u0437",
  holeTemplateMountingSchemeSelected: "\u041e\u0431\u0440\u0430\u043d\u043e",
  holeTemplateName: "\u041d\u0430\u0437\u0432\u0430",
  holeTemplateNameRequired: "\u041d\u0430\u0437\u0432\u0430 \u0448\u0430\u0431\u043b\u043e\u043d\u0443 \u0454 \u043e\u0431\u043e\u0432'\u044f\u0437\u043a\u043e\u0432\u043e\u044e",
  holeTemplateNotes: "\u041f\u0440\u0438\u043c\u0456\u0442\u043a\u0438",
  holeTemplateRefresh: "\u041e\u043d\u043e\u0432\u0438\u0442\u0438",
  holeTemplateSave: "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438",
  holeTemplateSaveChanges: "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u0437\u043c\u0456\u043d\u0438",
  holeTemplateSide: "\u0421\u0442\u043e\u0440\u043e\u043d\u0430",
  holeTemplateTitle: "\u0428\u0430\u0431\u043b\u043e\u043d\u0438",
  holeTemplateType: "\u0422\u0438\u043f",
  holeTemplateUpdateFailed: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u043e\u043d\u043e\u0432\u0438\u0442\u0438 \u0448\u0430\u0431\u043b\u043e\u043d \u043e\u0442\u0432\u043e\u0440\u0456\u0432",
  holeTemplateUpdateSuccess: "\u0428\u0430\u0431\u043b\u043e\u043d \u043e\u0442\u0432\u043e\u0440\u0456\u0432 \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
  holeTemplateEmpty: "\u0428\u0430\u0431\u043b\u043e\u043d\u0438 \u0449\u0435 \u043d\u0435 \u0434\u043e\u0434\u0430\u043d\u0456",
  holeTemplateSelectFitting: "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443",
  holeTemplateSelectTemplate: "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0448\u0430\u0431\u043b\u043e\u043d",
  holeTemplateColumnId: "ID",
  holeTemplateColumnName: "\u041d\u0430\u0437\u0432\u0430",
  holeTemplateColumnType: "\u0422\u0438\u043f",
  holeTemplateColumnSide: "\u0421\u0442\u043e\u0440\u043e\u043d\u0430",
  holeTemplateColumnSystem: "\u0421\u0438\u0441\u0442\u0435\u043c\u0430",
  holeTemplateColumnNotes: "\u041f\u0440\u0438\u043c\u0456\u0442\u043a\u0438",
  holeTemplateColumnDefault: "\u0417\u0430 \u0437\u0430\u043c\u043e\u0432\u0447\u0443\u0432\u0430\u043d\u043d\u044f\u043c",
  holeTemplateColumnActive: "\u0410\u043a\u0442\u0438\u0432\u043d\u0438\u0439",
  holeTemplateTypeAuto: "\u0410\u0432\u0442\u043e\u043c\u0430\u0442\u0438\u0447\u043d\u0438\u0439",
  holeTemplateTypeManual: "\u0420\u0443\u0447\u043d\u0438\u0439",
  holeTemplateTypeSelectAuto: "\u0410\u0432\u0442\u043e",
  holeTemplateTypeSelectManual: "\u0420\u0443\u0447\u043d\u0438\u0439",
  holePointColumnId: "ID",
  holePointColumnLabel: "\u041c\u0456\u0442\u043a\u0430",
  holePointColumnDepth: "\u0413\u043b\u0438\u0431\u0438\u043d\u0430",
  holePointColumnSide: "\u0421\u0442\u043e\u0440\u043e\u043d\u0430",
  holePointColumnOperation: "\u041e\u043f\u0435\u0440\u0430\u0446\u0456\u044f",
  holePointColumnOrder: "\u041f\u043e\u0440\u044f\u0434\u043e\u043a",
  holeTemplateCoordinateSystem2d: "2D",
  holeTemplateCoordinateSystem3d: "3D",
  holePointX: "X, \u043c\u043c",
  holePointY: "Y, \u043c\u043c",
  holePointZ: "Z, \u043c\u043c",
});

Object.assign(TRANSLATIONS.en, {
  viyarEmail: "Viyar email",
  viyarPassword: "Viyar password",
  viyarPasswordHint: "Leave empty to keep the saved password.",
  viyarPasswordSavedHint: "Password is already saved. Enter a new one only to replace it.",
  viyarSaveCredentials: "Save Viyar credentials",
  viyarConnect: "Connect to Viyar",
  viyarConnected: "Viyar connected",
  viyarCredentialsSaved: "Viyar credentials saved",
  viyarSavingCredentials: "Saving Viyar credentials...",
  viyarConnectingNow: "Connecting to Viyar...",
  viyarSyncingPricesNow: "Synchronizing Viyar prices...",
  viyarHasSavedPassword: "Saved password",
  viyarHasSavedSession: "Saved session",
  viyarSavedState: "Saved",
  viyarLastAuthAt: "Last authorization",
  viyarLastAuthStatus: "Authorization status",
  viyarLastAuthError: "Authorization error",
  viyarNotConnected: "Not connected",
  viyarSettingsTitle: "Viyar account",
  viyarStepSave: "Step 1. Save your Viyar credentials.",
  viyarStepConnect: "Step 2. Connect to Viyar and create a session.",
  viyarStepSync: "Step 3. Synchronize your personal Viyar prices.",
  unableToLoadViyarAuth: "Unable to load Viyar authorization settings",
  unableToSaveViyarAuth: "Unable to save Viyar authorization settings",
  unableToRefreshViyarSession: "Unable to connect to Viyar",
  viyarCurrentPrice: "Current Viyar price",
  viyarLastSynced: "Last synced",
  viyarArticle: "Article",
  viyarNoPersonalPrice: "No personal price synced yet",
  viyarSyncStatus: "Sync status",
  viyarCalculable: "Calculable",
  viyarAuthRequired: "Viyar authorization required for actual prices",
  basePrice: "Base price",
  serviceUnit: "Unit",
  showDescription: "Description",
  hideDescription: "Hide description",
  viyarCollapseAll: "Collapse all",
  viyarExpandAll: "Expand all",
  viyarFolder: "Folder",
  viyarImported: "Viyar services imported",
  viyarLoadedFromCache:
    "Showing saved Viyar services from cache. Refresh from Viyar when you need the latest data.",
  viyarPricesSynced: "Viyar prices synchronized",
  viyarRefresh: "Refresh from Viyar",
  viyarSearch: "Search services",
  viyarService: "Service",
  viyarServicesDescription:
    "Folder tree of services prepared for future calculation and connection to project costing.",
  viyarSyncPrices: "Sync prices",
  viyarServicesTitle: "Viyar production services",
  viyarSource: "Source",
  manualServiceArticlePlaceholder: "Optional article",
  manualServiceCreated: "Manual service created",
  manualServiceDescriptionPlaceholder: "Short description",
  manualServiceNamePlaceholder: "Service name",
  manualServiceUpdated: "Manual service updated",
  manualServicesDescription:
    "Your own service items for calculation when the price should not come from Viyar.",
  manualServicesTitle: "My manual services",
  unableToImportViyarServices: "Unable to import Viyar services",
  unableToLoadManualServices: "Unable to load manual services",
  unableToLoadViyarServices: "Unable to load Viyar services",
  unableToSaveManualService: "Unable to save manual service",
  unableToSyncViyarPrices: "Unable to synchronize Viyar prices",
});

Object.assign(TRANSLATIONS.uk, {
  viyarEmail: "Email Viyar",
  viyarPassword: "\u041f\u0430\u0440\u043e\u043b\u044c Viyar",
  viyarPasswordHint:
    "\u0417\u0430\u043b\u0438\u0448\u0442\u0435 \u043f\u043e\u0440\u043e\u0436\u043d\u0456\u043c, \u0449\u043e\u0431 \u0437\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u0443\u0436\u0435 \u0437\u0430\u043f\u0438\u0441\u0430\u043d\u0438\u0439 \u043f\u0430\u0440\u043e\u043b\u044c.",
  viyarPasswordSavedHint:
    "\u041f\u0430\u0440\u043e\u043b\u044c \u0432\u0436\u0435 \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e. \u0412\u0432\u043e\u0434\u044c\u0442\u0435 \u043d\u043e\u0432\u0438\u0439 \u043b\u0438\u0448\u0435 \u044f\u043a\u0449\u043e \u0445\u043e\u0447\u0435\u0442\u0435 \u0439\u043e\u0433\u043e \u0437\u0430\u043c\u0456\u043d\u0438\u0442\u0438.",
  viyarSaveCredentials:
      "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u0434\u0430\u043d\u0456 Viyar",
  viyarConnect: "\u041f\u0456\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u0438 Viyar",
  viyarConnected: "Viyar \u043f\u0456\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043e",
  viyarCredentialsSaved:
      "\u0414\u0430\u043d\u0456 Viyar \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e",
  viyarSavingCredentials:
      "\u0417\u0431\u0435\u0440\u0456\u0433\u0430\u0454\u043c\u043e \u0434\u0430\u043d\u0456 Viyar...",
  viyarConnectingNow:
      "\u041f\u0456\u0434\u043a\u043b\u044e\u0447\u0430\u0454\u043c\u043e\u0441\u044f \u0434\u043e Viyar...",
  viyarSyncingPricesNow:
      "\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0443\u0454\u043c\u043e \u0446\u0456\u043d\u0438 Viyar...",
  viyarHasSavedPassword:
      "\u0417\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u0438\u0439 \u043f\u0430\u0440\u043e\u043b\u044c",
  viyarHasSavedSession:
    "\u0417\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u0430 \u0441\u0435\u0441\u0456\u044f",
  viyarSavedState: "\u0417\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e",
  viyarLastAuthAt:
    "\u041e\u0441\u0442\u0430\u043d\u043d\u044f \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0456\u044f",
  viyarLastAuthStatus:
    "\u0421\u0442\u0430\u0442\u0443\u0441 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0456\u0457",
  viyarLastAuthError:
    "\u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0456\u0457",
  viyarNotConnected: "\u041d\u0435 \u043f\u0456\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043e",
  viyarSettingsTitle: "\u0410\u043a\u0430\u0443\u043d\u0442 Viyar",
  viyarStepSave:
    "\u041a\u0440\u043e\u043a 1. \u0417\u0431\u0435\u0440\u0435\u0436\u0456\u0442\u044c \u0441\u0432\u043e\u0457 \u0434\u0430\u043d\u0456 Viyar.",
  viyarStepConnect:
    "\u041a\u0440\u043e\u043a 2. \u041f\u0456\u0434\u043a\u043b\u044e\u0447\u0456\u0442\u044c\u0441\u044f \u0434\u043e Viyar \u0456 \u0441\u0442\u0432\u043e\u0440\u0456\u0442\u044c \u0441\u0435\u0441\u0456\u044e.",
  viyarStepSync:
    "\u041a\u0440\u043e\u043a 3. \u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0443\u0439\u0442\u0435 \u0441\u0432\u043e\u0457 \u043f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u0456 \u0446\u0456\u043d\u0438 Viyar.",
  unableToLoadViyarAuth:
    "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0438\u0442\u0438 \u043d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f Viyar",
  unableToSaveViyarAuth:
    "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0437\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u043d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f Viyar",
  unableToRefreshViyarSession:
    "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u043f\u0456\u0434\u043a\u043b\u044e\u0447\u0438\u0442\u0438 Viyar",
  viyarCurrentPrice:
    "\u041f\u043e\u0442\u043e\u0447\u043d\u0430 \u0446\u0456\u043d\u0430 Viyar",
  viyarLastSynced:
    "\u041e\u0441\u0442\u0430\u043d\u043d\u044f \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0430\u0446\u0456\u044f",
  viyarArticle: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b",
  viyarNoPersonalPrice:
    "\u041f\u0435\u0440\u0441\u043e\u043d\u0430\u043b\u044c\u043d\u0443 \u0446\u0456\u043d\u0443 \u0449\u0435 \u043d\u0435 \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u043e\u0432\u0430\u043d\u043e",
  viyarSyncStatus: "\u0421\u0442\u0430\u0442\u0443\u0441 \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0430\u0446\u0456\u0457",
  basePrice: "\u0411\u0430\u0437\u043e\u0432\u0430 \u0446\u0456\u043d\u0430",
  serviceUnit: "\u041e\u0434\u0438\u043d\u0438\u0446\u044f",
  showDescription: "\u041e\u043f\u0438\u0441",
  hideDescription: "\u0421\u0445\u043e\u0432\u0430\u0442\u0438 \u043e\u043f\u0438\u0441",
  viyarAuthRequired:
    "\u0414\u043b\u044f \u0430\u043a\u0442\u0443\u0430\u043b\u044c\u043d\u0438\u0445 \u0446\u0456\u043d Viyar \u043f\u043e\u0442\u0440\u0456\u0431\u043d\u0430 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0456\u044f",
  viyarCalculable: "\u0414\u043b\u044f \u0440\u043e\u0437\u0440\u0430\u0445\u0443\u043d\u043a\u0443",
  viyarCollapseAll: "\u0417\u0433\u043e\u0440\u043d\u0443\u0442\u0438 \u0432\u0441\u0435",
  viyarExpandAll: "\u0420\u043e\u0437\u0433\u043e\u0440\u043d\u0443\u0442\u0438 \u0432\u0441\u0435",
  viyarFolder: "\u041f\u0430\u043f\u043a\u0430",
  viyarImported: "\u041f\u043e\u0441\u043b\u0443\u0433\u0438 Viyar \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
  viyarLoadedFromCache:
    "\u041f\u043e\u043a\u0430\u0437\u0430\u043d\u043e \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u0456 \u043f\u043e\u0441\u043b\u0443\u0433\u0438 Viyar \u0437 \u043a\u0435\u0448\u0443. \u041e\u043d\u043e\u0432\u0456\u0442\u044c \u0437 Viyar, \u043a\u043e\u043b\u0438 \u043f\u043e\u0442\u0440\u0456\u0431\u043d\u0456 \u043d\u0430\u0439\u0441\u0432\u0456\u0436\u0456 \u0434\u0430\u043d\u0456.",
  viyarPricesSynced:
    "\u0426\u0456\u043d\u0438 Viyar \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u043e\u0432\u0430\u043d\u043e",
  viyarRefresh: "\u041e\u043d\u043e\u0432\u0438\u0442\u0438 \u0437 Viyar",
  viyarSearch: "\u041f\u043e\u0448\u0443\u043a \u043f\u043e\u0441\u043b\u0443\u0433",
  viyarService: "\u041f\u043e\u0441\u043b\u0443\u0433\u0430",
  viyarServicesDescription:
    "\u0414\u0435\u0440\u0435\u0432\u043e \u043f\u043e\u0441\u043b\u0443\u0433, \u043f\u0456\u0434\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u0435 \u0434\u043b\u044f \u043c\u0430\u0439\u0431\u0443\u0442\u043d\u044c\u043e\u0433\u043e \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443 \u0456 \u043f\u0440\u0438\u0432'\u044f\u0437\u043a\u0438 \u0434\u043e \u0441\u043e\u0431\u0456\u0432\u0430\u0440\u0442\u043e\u0441\u0442\u0456 \u043f\u0440\u043e\u0454\u043a\u0442\u0443.",
  viyarSyncPrices: "\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0443\u0432\u0430\u0442\u0438 \u0446\u0456\u043d\u0438",
  viyarServicesTitle: "\u041f\u043e\u0441\u043b\u0443\u0433\u0438 Viyar",
  viyarSource: "\u0414\u0436\u0435\u0440\u0435\u043b\u043e",
  manualServiceArticlePlaceholder: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b (\u043d\u0435 \u043e\u0431\u043e\u0432'\u044f\u0437\u043a\u043e\u0432\u043e)",
  manualServiceCreated: "\u0420\u0443\u0447\u043d\u0443 \u043f\u043e\u0441\u043b\u0443\u0433\u0443 \u0441\u0442\u0432\u043e\u0440\u0435\u043d\u043e",
  manualServiceDescriptionPlaceholder: "\u041a\u043e\u0440\u043e\u0442\u043a\u0438\u0439 \u043e\u043f\u0438\u0441",
  manualServiceNamePlaceholder: "\u041d\u0430\u0437\u0432\u0430 \u043f\u043e\u0441\u043b\u0443\u0433\u0438",
  manualServiceUpdated: "\u0420\u0443\u0447\u043d\u0443 \u043f\u043e\u0441\u043b\u0443\u0433\u0443 \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
  manualServicesDescription:
    "\u0412\u043b\u0430\u0441\u043d\u0456 \u043f\u043e\u0441\u043b\u0443\u0433\u0438 \u0434\u043b\u044f \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443, \u044f\u043a\u0456 \u043d\u0435 \u043f\u043e\u0432'\u044f\u0437\u0430\u043d\u0456 \u0434\u043e \u0446\u0456\u043d Viyar.",
  manualServicesTitle: "\u041c\u043e\u0457 \u0440\u0443\u0447\u043d\u0456 \u043f\u043e\u0441\u043b\u0443\u0433\u0438",
  unableToImportViyarServices: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u043e\u043d\u043e\u0432\u0438\u0442\u0438 \u043f\u043e\u0441\u043b\u0443\u0433\u0438 Viyar",
  unableToLoadManualServices: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0438\u0442\u0438 \u0440\u0443\u0447\u043d\u0456 \u043f\u043e\u0441\u043b\u0443\u0433\u0438",
  unableToLoadViyarServices: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0437\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0438\u0442\u0438 \u043f\u043e\u0441\u043b\u0443\u0433\u0438 Viyar",
  unableToSaveManualService: "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0437\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u0440\u0443\u0447\u043d\u0443 \u043f\u043e\u0441\u043b\u0443\u0433\u0443",
  unableToSyncViyarPrices:
    "\u041d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u0443\u0432\u0430\u0442\u0438 \u0446\u0456\u043d\u0438 Viyar",
});

Object.assign(TRANSLATIONS.en, {
  loading: "Loading",
  home: "Home",
  homeDescription: "Quick overview of catalogs, prices, and system activity.",
  homeHeroTitle: "Admin dashboard",
  homeHeroDescription:
    "Key catalogs, current city pricing, and automatic sync status in one place.",
  homeOpenProjects: "Open projects",
  homeOpenSettings: "Profile settings",
  homeAutoRefreshTitle: "Auto refresh",
  homeAutoRefreshDescription:
    "Background refresh of Viyar services and parsed material prices.",
  autoRefreshRunning: "Running",
  autoRefreshStopped: "Stopped",
  autoRefreshLastSuccess: "Last successful update",
  autoRefreshLastCycle: "Last cycle",
  autoRefreshQueuedMaterials: "Queued materials",
  autoRefreshSyncedUsers: "Synced users",
  autoRefreshCatalogSync: "Service catalog",
  autoRefreshCatalogUpdated: "Updated in this cycle",
  autoRefreshCatalogWaiting: "Waiting for next cycle",
  autoRefreshLastError: "Last error",
  homeCatalogMenuTitle: "Catalogs",
  homeCatalogMenuDescription:
    "Navigate to the main reference sections without going through the side menu.",
  homeMetricsTitle: "Current workspace",
  homeMetricsDescription:
    "A compact snapshot of projects, users, and reference catalogs.",
  projectsCount: "Projects",
  usersCount: "Users",
  fittingsCount: "Fittings",
  fastenersCount: "Fasteners",
  catalogFittings: "Fittings catalog",
  catalogFittingsDescription:
    "Main fitting assortment for calculations, filtered by city and article.",
  catalogFasteners: "Fasteners",
  catalogFastenersDescription:
    "Technical fasteners such as confirmats, screws, connectors, and related items.",
  fittingName: "Name",
  fittingType: "Fitting type",
  fittingGroup: "Catalog section",
  fittingArticle: "Article",
  fittingCode: "Code",
  fittingSource: "Source",
  fittingSourceUrl: "Source link",
  fittingPrice: "Price",
  fittingStock: "Availability",
  fittingSystemToggle: "Default in system",
  fittingAddSystem: "Add default fitting",
  fittingAddCustom: "Add fitting for calculation",
  fittingCreateSuccess: "Fitting added",
  fittingDelete: "Delete fitting",
  fittingDeleteConfirm: "Delete fitting",
  fittingCustomScope: "My fitting",
  fittingSystemScope: "System fitting",
  fittingNamePrompt: "Enter fitting name",
  fittingTypePrompt: "Select fitting type",
  fittingArticlePrompt: "Enter fitting article",
  fittingSourceUrlPrompt: "Paste source link for the fitting",
  fittingImage: "Image",
  fittingImageUpload: "Upload image",
  fittingImageSelected: "Image selected",
  fittingSystemHint: "Default fitting is saved for all users from the source link.",
  fittingCustomHint: "Your fitting is saved for calculation with your own name, price, and optional image.",
  fittingRowsView: "Rows",
  fittingCardsView: "Cards",
  fittingManualSource: "Manual",
  fittingNoItems: "No fittings yet in this section.",
  fittingsManageDescription:
    "Group fittings by type, keep system defaults, and add personal calculation items.",
  viyarFallbackImportNotice:
    "Viyar returned only a simplified catalog. Existing full service list was kept unchanged.",
  catalogBrowseCategories: "Browse categories",
  backToFittingCategories: "Back to categories",
  fittingCategoriesCount: "categories",
  catalogHubDescription:
    "Quick access to service directories and reference catalogs in a visual category view.",
  catalogHubTitle: "Directories overview",
  openDirectory: "Open directory",
  catalogManualDescription:
    "Create and maintain your own services that do not depend on Viyar pricing.",
  catalogValuesDescription:
    "Edit shared reference values used across projects, forms, and calculations.",
  catalogValuesGroups: "Groups",
  catalogManual: "Manual services",
  catalogValues: "Value catalog",
  catalogViyar: "Viyar catalog",
  authError: "Auth error",
  authStatus: "Auth status",
  connected: "Connected",
  createdProjects: "Created projects",
  openUserCard: "Open user card",
  lastAuth: "Last auth",
  lastUsernameChange: "Last username change",
  noError: "No error",
  noProjectsYet: "No projects yet",
  noRequestsHistory: "No request history",
  notConnected: "Not connected",
  session: "Session",
  telegram: "Telegram",
  userProfile: "Profile",
  viyarConnection: "Viyar",
});

Object.assign(TRANSLATIONS.uk, {
  loading: "Завантаження",
  home: "\u0413\u043e\u043b\u043e\u0432\u043d\u0430",
  homeDescription:
    "\u0428\u0432\u0438\u0434\u043a\u0438\u0439 \u043e\u0433\u043b\u044f\u0434 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0456\u0432, \u0446\u0456\u043d \u0456 \u0441\u0442\u0430\u043d\u0443 \u0441\u0438\u0441\u0442\u0435\u043c\u0438.",
  homeHeroTitle: "\u0413\u043e\u043b\u043e\u0432\u043d\u0430 \u043f\u0430\u043d\u0435\u043b\u044c",
  homeHeroDescription:
    "\u041e\u0441\u043d\u043e\u0432\u043d\u0456 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0438, \u0446\u0456\u043d\u0438 \u0437\u0430 \u043c\u0456\u0441\u0442\u043e\u043c \u0456 \u0441\u0442\u0430\u0442\u0443\u0441 \u0430\u0432\u0442\u043e\u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f \u0432 \u043e\u0434\u043d\u043e\u043c\u0443 \u043c\u0456\u0441\u0446\u0456.",
  homeOpenProjects: "\u0412\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u043f\u0440\u043e\u0454\u043a\u0442\u0438",
  homeOpenSettings: "\u041d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f \u043f\u0440\u043e\u0444\u0456\u043b\u044e",
  homeAutoRefreshTitle: "\u0410\u0432\u0442\u043e\u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f",
  homeAutoRefreshDescription:
    "\u0424\u043e\u043d\u043e\u0432\u0435 \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f \u043f\u043e\u0441\u043b\u0443\u0433 Viyar \u0442\u0430 \u0446\u0456\u043d \u043d\u0430 \u0440\u043e\u0437\u043f\u0430\u0440\u0441\u0435\u043d\u0456 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0438.",
  autoRefreshRunning: "\u041f\u0440\u0430\u0446\u044e\u0454",
  autoRefreshStopped: "\u0417\u0443\u043f\u0438\u043d\u0435\u043d\u043e",
  autoRefreshLastSuccess: "\u041e\u0441\u0442\u0430\u043d\u043d\u0454 \u0432\u0434\u0430\u043b\u0435 \u043e\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f",
  autoRefreshLastCycle: "\u041e\u0441\u0442\u0430\u043d\u043d\u0456\u0439 \u0446\u0438\u043a\u043b",
  autoRefreshQueuedMaterials: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0456\u0432 \u0443 \u0447\u0435\u0440\u0437\u0456",
  autoRefreshSyncedUsers: "\u041a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456\u0432 \u0441\u0438\u043d\u0445\u0440\u043e\u043d\u0456\u0437\u043e\u0432\u0430\u043d\u043e",
  autoRefreshCatalogSync: "\u041a\u0430\u0442\u0430\u043b\u043e\u0433 \u043f\u043e\u0441\u043b\u0443\u0433",
  autoRefreshCatalogUpdated: "\u041e\u043d\u043e\u0432\u043b\u0435\u043d\u043e \u0432 \u0446\u044c\u043e\u043c\u0443 \u0446\u0438\u043a\u043b\u0456",
  autoRefreshCatalogWaiting: "\u041e\u0447\u0456\u043a\u0443\u0454 \u043d\u0430\u0441\u0442\u0443\u043f\u043d\u043e\u0433\u043e \u0446\u0438\u043a\u043b\u0443",
  autoRefreshLastError: "\u041e\u0441\u0442\u0430\u043d\u043d\u044f \u043f\u043e\u043c\u0438\u043b\u043a\u0430",
  homeCatalogMenuTitle: "\u041a\u0430\u0442\u0430\u043b\u043e\u0433\u0438",
  homeCatalogMenuDescription:
    "\u041f\u0435\u0440\u0435\u0445\u0456\u0434 \u0434\u043e \u0433\u043e\u043b\u043e\u0432\u043d\u0438\u0445 \u0434\u043e\u0432\u0456\u0434\u043d\u0438\u043a\u0456\u0432 \u0431\u0435\u0437 \u043f\u043e\u0448\u0443\u043a\u0443 \u0457\u0445 \u0432 \u0431\u043e\u043a\u043e\u0432\u043e\u043c\u0443 \u043c\u0435\u043d\u044e.",
  homeMetricsTitle: "\u0421\u0442\u0430\u043d \u0440\u043e\u0431\u043e\u0447\u043e\u0457 \u0437\u043e\u043d\u0438",
  homeMetricsDescription:
    "\u041a\u043e\u043c\u043f\u0430\u043a\u0442\u043d\u0438\u0439 \u0437\u0440\u0456\u0437 \u043f\u043e \u043f\u0440\u043e\u0454\u043a\u0442\u0430\u0445, \u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0430\u0445 \u0456 \u0434\u043e\u0432\u0456\u0434\u043d\u0438\u043a\u0430\u0445.",
  projectsCount: "\u041f\u0440\u043e\u0454\u043a\u0442\u0438",
  usersCount: "\u041a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456",
  fittingsCount: "\u0424\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
  fastenersCount: "\u041c\u0435\u0442\u0438\u0437\u043d\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
  catalogFittings: "\u041a\u0430\u0442\u0430\u043b\u043e\u0433 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438",
  catalogFittingsDescription:
    "\u041e\u0441\u043d\u043e\u0432\u043d\u0438\u0439 \u0430\u0441\u043e\u0440\u0442\u0438\u043c\u0435\u043d\u0442 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438 \u0434\u043b\u044f \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0456\u0432 \u0437 \u0444\u0456\u043b\u044c\u0442\u0440\u0430\u043c\u0438 \u043f\u043e \u043c\u0456\u0441\u0442\u0443 \u0442\u0430 \u0430\u0440\u0442\u0438\u043a\u0443\u043b\u0443.",
  catalogFasteners: "\u041c\u0435\u0442\u0438\u0437\u043d\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
  catalogFastenersDescription:
    "\u0422\u0435\u0445\u043d\u0456\u0447\u043d\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430: \u0441\u0442\u044f\u0436\u043a\u0438, \u0441\u0430\u043c\u043e\u0440\u0456\u0437\u0438, \u043a\u0440\u0456\u043f\u0438\u043b\u044c\u043d\u0456 \u0435\u043b\u0435\u043c\u0435\u043d\u0442\u0438 \u0442\u0430 \u0441\u0443\u043f\u0443\u0442\u043d\u0456 \u043f\u043e\u0437\u0438\u0446\u0456\u0457.",
  fittingName: "\u041d\u0430\u0437\u0432\u0430",
  fittingType: "\u0422\u0438\u043f \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438",
  fittingGroup: "\u0420\u043e\u0437\u0434\u0456\u043b \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0443",
  fittingArticle: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b",
  fittingCode: "\u041a\u043e\u0434",
  fittingSource: "\u0414\u0436\u0435\u0440\u0435\u043b\u043e",
  fittingSourceUrl: "\u041f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043d\u0430 \u0434\u0436\u0435\u0440\u0435\u043b\u043e",
  fittingPrice: "\u0426\u0456\u043d\u0430",
  fittingStock: "\u041d\u0430\u044f\u0432\u043d\u0456\u0441\u0442\u044c",
  fittingSystemToggle: "\u0417\u0430\u043c\u043e\u0432\u0447\u0443\u0432\u0430\u043d\u043d\u044f \u0432 \u0441\u0438\u0441\u0442\u0435\u043c\u0456",
  fittingAddSystem: "\u0414\u043e\u0434\u0430\u0442\u0438 \u0431\u0430\u0437\u043e\u0432\u0443 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443",
  fittingAddCustom: "\u0414\u043e\u0434\u0430\u0442\u0438 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443 \u0434\u043b\u044f \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443",
  fittingCreateSuccess: "\u0424\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443 \u0434\u043e\u0434\u0430\u043d\u043e",
  fittingDelete: "\u0412\u0438\u0434\u0430\u043b\u0438\u0442\u0438 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443",
  fittingDeleteConfirm: "\u0412\u0438\u0434\u0430\u043b\u0438\u0442\u0438 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443",
  fittingCustomScope: "\u041c\u043e\u044f \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
  fittingSystemScope: "\u0421\u0438\u0441\u0442\u0435\u043c\u043d\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430",
  fittingNamePrompt: "\u0412\u043a\u0430\u0436\u0456\u0442\u044c \u043d\u0430\u0437\u0432\u0443 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438",
  fittingTypePrompt: "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0442\u0438\u043f \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438",
  fittingArticlePrompt: "\u0412\u043a\u0430\u0436\u0456\u0442\u044c \u0430\u0440\u0442\u0438\u043a\u0443\u043b \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438",
  fittingSourceUrlPrompt: "\u0412\u0441\u0442\u0430\u0432\u0442\u0435 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043d\u0430 \u0434\u0436\u0435\u0440\u0435\u043b\u043e \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0438",
  fittingImage: "\u041a\u0430\u0440\u0442\u0438\u043d\u043a\u0430",
  fittingImageUpload: "\u0417\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0438\u0442\u0438 \u043a\u0430\u0440\u0442\u0438\u043d\u043a\u0443",
  fittingImageSelected: "\u041a\u0430\u0440\u0442\u0438\u043d\u043a\u0443 \u0432\u0438\u0431\u0440\u0430\u043d\u043e",
  fittingSystemHint: "\u0421\u0438\u0441\u0442\u0435\u043c\u043d\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430 \u0437\u0431\u0435\u0440\u0456\u0433\u0430\u0454\u0442\u044c\u0441\u044f \u0434\u043b\u044f \u0432\u0441\u0456\u0445 \u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456\u0432 \u0437 \u0434\u0436\u0435\u0440\u0435\u043b\u0430.",
  fittingCustomHint: "\u0412\u0430\u0448\u0430 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0430 \u0437\u0431\u0435\u0440\u0456\u0433\u0430\u0454\u0442\u044c\u0441\u044f \u0434\u043b\u044f \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443 \u0437 \u0432\u043b\u0430\u0441\u043d\u043e\u044e \u043d\u0430\u0437\u0432\u043e\u044e, \u0446\u0456\u043d\u043e\u044e \u0442\u0430 \u043d\u0435\u043e\u0431\u043e\u0432'\u044f\u0437\u043a\u043e\u0432\u043e\u044e \u043a\u0430\u0440\u0442\u0438\u043d\u043a\u043e\u044e.",
  fittingRowsView: "\u0421\u043f\u0438\u0441\u043e\u043a",
  fittingCardsView: "\u041a\u0430\u0440\u0442\u043a\u0438",
  fittingManualSource: "\u0412\u0440\u0443\u0447\u043d\u0443",
  fittingNoItems: "\u0423 \u0446\u044c\u043e\u043c\u0443 \u0440\u043e\u0437\u0434\u0456\u043b\u0456 \u0449\u0435 \u043d\u0435\u043c\u0430\u0454 \u043f\u043e\u0437\u0438\u0446\u0456\u0439.",
  fittingsManageDescription:
    "\u0417\u0433\u0440\u0443\u043f\u0443\u0439\u0442\u0435 \u0444\u0443\u0440\u043d\u0456\u0442\u0443\u0440\u0443 \u043f\u043e \u0442\u0438\u043f\u0430\u0445, \u0442\u0440\u0438\u043c\u0430\u0439\u0442\u0435 \u0441\u0438\u0441\u0442\u0435\u043c\u043d\u0456 \u043f\u043e\u0437\u0438\u0446\u0456\u0457 \u0456 \u0434\u043e\u0434\u0430\u0432\u0430\u0439\u0442\u0435 \u0432\u043b\u0430\u0441\u043d\u0456 \u043f\u043e\u0437\u0438\u0446\u0456\u0457 \u0434\u043b\u044f \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443.",
  viyarFallbackImportNotice:
    "\u0412\u0456\u0434 Viyar \u043e\u0442\u0440\u0438\u043c\u0430\u043d\u043e \u043b\u0438\u0448\u0435 \u0441\u043f\u0440\u043e\u0449\u0435\u043d\u0438\u0439 \u043a\u0430\u0442\u0430\u043b\u043e\u0433. \u041f\u043e\u043f\u0435\u0440\u0435\u0434\u043d\u0456\u0439 \u043f\u043e\u0432\u043d\u0438\u0439 \u0441\u043f\u0438\u0441\u043e\u043a \u043f\u043e\u0441\u043b\u0443\u0433 \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e.",
  catalogBrowseCategories:
    "\u041f\u0435\u0440\u0435\u0433\u043b\u044f\u043d\u0443\u0442\u0438 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0457",
  backToFittingCategories:
    "\u041d\u0430\u0437\u0430\u0434 \u0434\u043e \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0439",
  fittingCategoriesCount: "\u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0439",
  catalogHubDescription:
    "\u0428\u0432\u0438\u0434\u043a\u0438\u0439 \u0434\u043e\u0441\u0442\u0443\u043f \u0434\u043e \u0434\u043e\u0432\u0456\u0434\u043d\u0438\u043a\u0456\u0432 \u043f\u043e\u0441\u043b\u0443\u0433 \u0442\u0430 \u0434\u043e\u0432\u0456\u0434\u043a\u043e\u0432\u0438\u0445 \u0437\u043d\u0430\u0447\u0435\u043d\u044c \u0443 \u0432\u0438\u0433\u043b\u044f\u0434\u0456 \u043a\u0430\u0442\u0435\u0433\u043e\u0440\u0456\u0439.",
  catalogHubTitle:
    "\u041e\u0433\u043b\u044f\u0434 \u0434\u043e\u0432\u0456\u0434\u043d\u0438\u043a\u0456\u0432",
  openDirectory:
    "\u0412\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u0434\u043e\u0432\u0456\u0434\u043d\u0438\u043a",
  catalogManualDescription:
    "\u0421\u0442\u0432\u043e\u0440\u044e\u0439\u0442\u0435 \u0442\u0430 \u043f\u0456\u0434\u0442\u0440\u0438\u043c\u0443\u0439\u0442\u0435 \u0432\u043b\u0430\u0441\u043d\u0456 \u043f\u043e\u0441\u043b\u0443\u0433\u0438, \u044f\u043a\u0456 \u043d\u0435 \u0437\u0430\u043b\u0435\u0436\u0430\u0442\u044c \u0432\u0456\u0434 \u0446\u0456\u043d Viyar.",
  catalogValuesDescription:
    "\u0420\u0435\u0434\u0430\u0433\u0443\u0439\u0442\u0435 \u0441\u043f\u0456\u043b\u044c\u043d\u0456 \u0434\u043e\u0432\u0456\u0434\u043a\u043e\u0432\u0456 \u0437\u043d\u0430\u0447\u0435\u043d\u043d\u044f \u0434\u043b\u044f \u043f\u0440\u043e\u0454\u043a\u0442\u0456\u0432, \u0444\u043e\u0440\u043c \u0442\u0430 \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0456\u0432.",
  catalogValuesGroups: "\u0413\u0440\u0443\u043f\u0438",
  catalogManual: "\u0420\u0443\u0447\u043d\u0456 \u043f\u043e\u0441\u043b\u0443\u0433\u0438",
  catalogValues: "\u0414\u043e\u0432\u0456\u0434\u043d\u0438\u043a \u0437\u043d\u0430\u0447\u0435\u043d\u044c",
  catalogViyar: "\u0414\u043e\u0432\u0456\u0434\u043d\u0438\u043a Viyar",
  authError: "\u041f\u043e\u043c\u0438\u043b\u043a\u0430 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0456\u0457",
  authStatus: "\u0421\u0442\u0430\u0442\u0443\u0441 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0456\u0457",
  connected: "\u041f\u0456\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043e",
  createdProjects: "\u0421\u0442\u0432\u043e\u0440\u0435\u043d\u0456 \u043f\u0440\u043e\u0454\u043a\u0442\u0438",
  lastAuth: "\u041e\u0441\u0442\u0430\u043d\u043d\u044f \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0430\u0446\u0456\u044f",
  lastUsernameChange: "\u041e\u0441\u0442\u0430\u043d\u043d\u044f \u0437\u043c\u0456\u043d\u0430 \u043b\u043e\u0433\u0456\u043d\u0430",
  noError: "\u041d\u0435 \u0432\u043a\u0430\u0437\u0430\u043d\u043e",
  noProjectsYet: "\u0429\u0435 \u043d\u0435\u043c\u0430\u0454 \u043f\u0440\u043e\u0454\u043a\u0442\u0456\u0432",
  noRequestsHistory: "\u0429\u0435 \u043d\u0435\u043c\u0430\u0454 \u0456\u0441\u0442\u043e\u0440\u0456\u0457 \u0437\u0430\u043f\u0438\u0442\u0456\u0432",
  notConnected: "\u041d\u0435 \u043f\u0456\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u043e",
  openUserCard: "\u041a\u0430\u0440\u0442\u043a\u0430 \u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0430",
  session: "\u0421\u0435\u0441\u0456\u044f",
  telegram: "Telegram",
  userProfile: "\u041f\u0440\u043e\u0444\u0456\u043b\u044c",
  viyarConnection: "Viyar",
});

Object.assign(TRANSLATIONS.en, {
  city: "City",
  citySaved: "City saved",
  currentCity: "Current city",
  cityRequiredForMaterialImport: "Select your city in profile settings before adding a material.",
  catalogMaterials: "Materials",
  catalogMaterialsDescription:
    "Board materials shown as cards with image and city-based price.",
  materialAdd: "Add material from source",
  materialModeLinked: "From link",
  materialModeManual: "Manual",
  materialAddArticle: "Product article",
  materialAddArticlePlaceholder: "Enter article and add",
  materialAddUrl: "Product page URL",
  materialAddUrlPlaceholder: "Paste direct product link if search fails",
  materialDefaultForAll: "Default for all users",
  materialCategory: "Material type",
  materialManualAdd: "Add manual material",
  materialManualName: "Material name",
  materialManualNamePlaceholder: "Enter material name",
  materialManualPrice: "Price",
  materialManualImage: "Material image",
  materialManualImageHint: "Optional image for your own material",
  materialImportSuccess: "Material added from source",
  materialImportQueued: "Material import queued. The system will retry automatically.",
  materialImportRunning: "Material import is in progress.",
  materialImportRetry: "Material import is waiting for the next retry.",
  materialImportFailed: "Material import failed after several attempts.",
  materialPriceFallback: "Latest available price",
  materialImportStatusTitle: "Material import status",
  materialImportArticle: "Article",
  materialImportState: "State",
  materialImportAttempts: "Attempts",
  materialImportNextRetry: "Next retry",
  materialImportLastError: "Last error",
  materialImportStateQueued: "Queued",
  materialImportStateRunning: "Running",
  materialImportStateRetry: "Retry scheduled",
  materialImportStateSuccess: "Completed",
  materialImportStateError: "Failed",
  materialPriceForCity: "Price for city",
  materialCardOpen: "Open material",
  materialDetails: "Material details",
  materialDescription: "Description",
  materialColor: "Color",
  materialDimensions: "Dimensions",
  materialThickness: "Thickness",
  materialEdgeBands: "Edge bands",
  materialEdgeAttach: "Add edge",
  materialEdgeAttachConfirm: "Attach",
  materialEdgeAttachPlaceholder: "Paste edge link",
  materialEdgeSlotEmpty: "No edge attached yet",
  materialEdgeTypeLabel: "Edge thickness",
  materialEdgeAdded: "Edge attached to material",
  materialsCount: "Materials",
  materialSystemScope: "System",
  materialCustomScope: "Custom",
  deleteMaterial: "Delete material",
  deleteMaterialConfirm: "Delete custom material",
  materialDeleted: "Material deleted",
  refreshFromViyar: "Refresh from Viyar",
  materialRefreshQueued: "Material refresh queued.",
  materialRefreshStarted: "Refreshing material from Viyar.",
  materialCacheReady: "Image cached",
  materialCachePending: "Image warming",
  saveCity: "Save city",
  dsp: "DSP",
  mdf: "MDF",
  dvp: "DVP",
  kyiv: "Kyiv",
  lviv: "Lviv",
  odessa: "Odesa",
  dnipro: "Dnipro",
  kharkiv: "Kharkiv",
  khmelnytskyi: "Khmelnytskyi",
  rivne: "Rivne",
});

Object.assign(TRANSLATIONS.uk, {
  city: "\u041c\u0456\u0441\u0442\u043e",
  citySaved: "\u041c\u0456\u0441\u0442\u043e \u0437\u0431\u0435\u0440\u0435\u0436\u0435\u043d\u043e",
  currentCity: "\u041f\u043e\u0442\u043e\u0447\u043d\u0435 \u043c\u0456\u0441\u0442\u043e",
  cityRequiredForMaterialImport:
    "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u043c\u0456\u0441\u0442\u043e \u0443 \u043d\u0430\u043b\u0430\u0448\u0442\u0443\u0432\u0430\u043d\u043d\u044f\u0445 \u043f\u0440\u043e\u0444\u0456\u043b\u044e \u043f\u0435\u0440\u0435\u0434 \u0434\u043e\u0434\u0430\u0432\u0430\u043d\u043d\u044f\u043c \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443.",
  catalogMaterials: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0438",
  catalogMaterialsDescription:
    "\u041f\u043b\u0438\u0442\u043d\u0456 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0438 \u0443 \u0432\u0438\u0433\u043b\u044f\u0434\u0456 \u043a\u0430\u0440\u0442\u043e\u043a \u0456\u0437 \u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u043d\u044f\u043c \u0442\u0430 \u0446\u0456\u043d\u043e\u044e \u0437\u0430 \u043c\u0456\u0441\u0442\u043e\u043c.",
  materialAdd: "\u0414\u043e\u0434\u0430\u0442\u0438 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b \u0437 \u0434\u0436\u0435\u0440\u0435\u043b\u0430",
  materialModeLinked: "\u0417\u0430 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f\u043c",
  materialModeManual: "\u0412\u0440\u0443\u0447\u043d\u0443",
  materialAddArticle: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b \u0442\u043e\u0432\u0430\u0440\u0443",
  materialAddArticlePlaceholder:
    "\u0412\u0432\u0435\u0434\u0456\u0442\u044c \u0430\u0440\u0442\u0438\u043a\u0443\u043b \u0456 \u0434\u043e\u0434\u0430\u0439\u0442\u0435",
  materialAddUrl: "\u041f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043d\u0430 \u0441\u0442\u043e\u0440\u0456\u043d\u043a\u0443 \u0442\u043e\u0432\u0430\u0440\u0443",
  materialAddUrlPlaceholder:
    "\u0412\u0441\u0442\u0430\u0432\u0442\u0435 \u043f\u0440\u044f\u043c\u0438\u0439 URL \u0442\u043e\u0432\u0430\u0440\u0443, \u044f\u043a\u0449\u043e \u043f\u043e\u0448\u0443\u043a \u043d\u0435 \u0441\u043f\u0440\u0430\u0446\u044e\u0432\u0430\u0432",
  materialDefaultForAll: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b \u0437\u0430 \u0437\u0430\u043c\u043e\u0432\u0447\u0443\u0432\u0430\u043d\u043d\u044f\u043c \u0434\u043b\u044f \u0432\u0441\u0456\u0445",
  materialCategory: "\u0422\u0438\u043f \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialManualAdd: "\u0414\u043e\u0434\u0430\u0442\u0438 \u0441\u0432\u0456\u0439 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b",
  materialManualName: "\u041d\u0430\u0437\u0432\u0430 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialManualNamePlaceholder:
    "\u0412\u0432\u0435\u0434\u0456\u0442\u044c \u043d\u0430\u0437\u0432\u0443 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialManualPrice: "\u0426\u0456\u043d\u0430",
  materialManualImage: "\u0417\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u043d\u044f \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialManualImageHint:
    "\u041c\u043e\u0436\u043d\u0430 \u0434\u043e\u0434\u0430\u0442\u0438 \u0441\u0432\u043e\u0454 \u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u043d\u044f",
  materialImportSuccess: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b \u0434\u043e\u0434\u0430\u043d\u043e \u0437 \u0434\u0436\u0435\u0440\u0435\u043b\u0430",
  materialImportQueued: "\u0406\u043c\u043f\u043e\u0440\u0442 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443 \u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043e \u0432 \u0447\u0435\u0440\u0433\u0443. \u0421\u0438\u0441\u0442\u0435\u043c\u0430 \u0441\u0430\u043c\u0430 \u043f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u044c \u0441\u043f\u0440\u043e\u0431\u0438.",
  materialImportRunning: "\u0406\u043c\u043f\u043e\u0440\u0442 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443 \u0432\u0438\u043a\u043e\u043d\u0443\u0454\u0442\u044c\u0441\u044f.",
  materialImportRetry: "\u0406\u043c\u043f\u043e\u0440\u0442 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443 \u0447\u0435\u043a\u0430\u0454 \u043d\u0430 \u043d\u0430\u0441\u0442\u0443\u043f\u043d\u0443 \u0441\u043f\u0440\u043e\u0431\u0443.",
  materialImportFailed: "\u0406\u043c\u043f\u043e\u0440\u0442 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443 \u043d\u0435 \u0432\u0434\u0430\u0432\u0441\u044f \u043f\u0456\u0441\u043b\u044f \u043a\u0456\u043b\u044c\u043a\u043e\u0445 \u0441\u043f\u0440\u043e\u0431.",
  materialPriceFallback: "\u041e\u0441\u0442\u0430\u043d\u043d\u044f \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 \u0446\u0456\u043d\u0430",
  materialImportStatusTitle: "\u0421\u0442\u0430\u0442\u0443\u0441 \u0456\u043c\u043f\u043e\u0440\u0442\u0443 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialImportArticle: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b",
  materialImportState: "\u0421\u0442\u0430\u043d",
  materialImportAttempts: "\u0421\u043f\u0440\u043e\u0431\u0438",
  materialImportNextRetry: "\u041d\u0430\u0441\u0442\u0443\u043f\u043d\u0430 \u0441\u043f\u0440\u043e\u0431\u0430",
  materialImportLastError: "\u041e\u0441\u0442\u0430\u043d\u043d\u044f \u043f\u043e\u043c\u0438\u043b\u043a\u0430",
  materialImportStateQueued: "\u0423 \u0447\u0435\u0440\u0437\u0456",
  materialImportStateRunning: "\u0412 \u0440\u043e\u0431\u043e\u0442\u0456",
  materialImportStateRetry: "\u041f\u043e\u0432\u0442\u043e\u0440 \u0437\u0430\u043f\u043b\u0430\u043d\u043e\u0432\u0430\u043d\u043e",
  materialImportStateSuccess: "\u0417\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u043e",
  materialImportStateError: "\u041f\u043e\u043c\u0438\u043b\u043a\u0430",
  materialPriceForCity: "\u0426\u0456\u043d\u0430 \u0434\u043b\u044f \u043c\u0456\u0441\u0442\u0430",
  materialCardOpen: "\u0412\u0456\u0434\u043a\u0440\u0438\u0442\u0438 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b",
  materialDetails: "\u0414\u0435\u0442\u0430\u043b\u0456 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialDescription: "\u041e\u043f\u0438\u0441",
  materialColor: "\u041a\u043e\u043b\u0456\u0440",
  materialDimensions: "\u0413\u0430\u0431\u0430\u0440\u0438\u0442",
  materialThickness: "\u0422\u043e\u0432\u0449\u0438\u043d\u0430",
  materialEdgeBands: "\u041a\u0440\u0430\u0439\u043a\u0430",
  materialEdgeAttach: "\u0414\u043e\u0434\u0430\u0442\u0438",
  materialEdgeAttachConfirm: "\u041f\u0440\u0438\u0454\u0434\u043d\u0430\u0442\u0438",
  materialEdgeAttachPlaceholder: "\u0412\u0441\u0442\u0430\u0432\u0442\u0435 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f \u043d\u0430 \u043a\u0440\u0430\u0439\u043a\u0443",
  materialEdgeSlotEmpty: "\u041a\u0440\u0430\u0439\u043a\u0443 \u0449\u0435 \u043d\u0435 \u043f\u0440\u0438\u0432'\u044f\u0437\u0430\u043d\u043e",
  materialEdgeTypeLabel: "\u0422\u043e\u0432\u0449\u0438\u043d\u0430 \u043a\u0440\u0430\u0439\u043a\u0438",
  materialEdgeAdded: "\u041a\u0440\u0430\u0439\u043a\u0443 \u043f\u0440\u0438\u0432'\u044f\u0437\u0430\u043d\u043e \u0434\u043e \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialsCount: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0438",
  materialSystemScope: "\u0421\u0438\u0441\u0442\u0435\u043c\u043d\u0438\u0439",
  materialCustomScope: "\u0412\u043b\u0430\u0441\u043d\u0438\u0439",
  deleteMaterial: "\u0412\u0438\u0434\u0430\u043b\u0438\u0442\u0438 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b",
  deleteMaterialConfirm: "\u0412\u0438\u0434\u0430\u043b\u0438\u0442\u0438 \u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0446\u044c\u043a\u0438\u0439 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b",
  materialDeleted: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b \u0432\u0438\u0434\u0430\u043b\u0435\u043d\u043e",
  refreshFromViyar: "\u041e\u043d\u043e\u0432\u0438\u0442\u0438 \u0437 Viyar",
  materialRefreshQueued: "\u041e\u043d\u043e\u0432\u043b\u0435\u043d\u043d\u044f \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443 \u043f\u043e\u0441\u0442\u0430\u0432\u043b\u0435\u043d\u043e \u0432 \u0447\u0435\u0440\u0433\u0443.",
  materialRefreshStarted: "\u041e\u043d\u043e\u0432\u043b\u044e\u0454\u043c\u043e \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b \u0437 Viyar.",
  materialCacheReady: "\u041a\u0430\u0440\u0442\u0438\u043d\u043a\u0430 \u0432 \u043a\u0435\u0448\u0456",
  materialCachePending: "\u041a\u0435\u0448 \u043f\u0440\u043e\u0433\u0440\u0456\u0432\u0430\u0454\u0442\u044c\u0441\u044f",
  saveCity: "\u0417\u0431\u0435\u0440\u0435\u0433\u0442\u0438 \u043c\u0456\u0441\u0442\u043e",
  dsp: "\u0414\u0421\u041f",
  mdf: "\u041c\u0414\u0424",
  dvp: "\u0414\u0412\u041f",
  kyiv: "\u041a\u0438\u0457\u0432",
  lviv: "\u041b\u044c\u0432\u0456\u0432",
  odessa: "\u041e\u0434\u0435\u0441\u0430",
  dnipro: "\u0414\u043d\u0456\u043f\u0440\u043e",
  kharkiv: "\u0425\u0430\u0440\u043a\u0456\u0432",
  khmelnytskyi: "\u0425\u043c\u0435\u043b\u044c\u043d\u0438\u0446\u044c\u043a\u0438\u0439",
  rivne: "\u0420\u0456\u0432\u043d\u0435",
});

Object.assign(TRANSLATIONS.en, {
  disabled: "Disabled",
  forCalculation: "For calculation",
});

Object.assign(TRANSLATIONS.uk, {
  disabled: "\u0412\u0438\u043c\u043a\u043d\u0435\u043d\u043e",
  forCalculation: "\u0414\u043b\u044f \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443",
});

Object.assign(TRANSLATIONS.en, {
  aiScanApply: "Apply to form",
  aiScanConfirmed: "Recognition confirmed",
  aiScanDescription: "Upload a photo, sketch, or PDF. The system will try to detect furniture type and dimensions.",
  aiScanFound: "Draft result",
  aiScanHistory: "Recent recognition drafts",
  aiScanNeedsConfirmation: "Needs confirmation",
  aiScanProOnly: "AI recognition is available for PRO, Premium, and admins.",
  aiScanRawText: "OCR text",
  aiScanTitle: "AI recognition",
  aiScanUnsupported: "Recognition failed",
  aiScanUpload: "Analyze file",
  projectPremiumOpenUpload: "Open upload",
  projectPremiumOptionBatch: "Batch start",
  projectPremiumOptionBatchDescription: "Reserved for future import of several products at once.",
  projectPremiumOptionRecognition: "File or sketch",
  projectPremiumOptionRecognitionDescription: "Photo, drawing, or PDF for initial recognition.",
  projectPremiumOptionTemplates: "Smart templates",
  projectPremiumOptionTemplatesDescription: "Fast construction presets with base parameters.",
  projectSpecificationTitle: "Project specification",
  projectStartAiDescription: "Upload a sketch, photo, or PDF and confirm detected project data.",
  projectStartAiTitle: "PRO AI scan",
  projectStartDescription: "Choose a start scenario: template, PRO scan, or extended Premium start.",
  projectStartFreeBadge: "Free",
  projectStartManualDescription: "Free start: choose a prepared construction template and adjust fields.",
  projectStartManualTitle: "Prepared templates",
  projectStartPremiumBadge: "Premium",
  projectStartPremiumDescription: "Maximum start with templates, scan, PDF, and future batch imports.",
  projectStartPremiumOnly: "Premium start is available for Premium users and admins.",
  projectStartPremiumTitle: "Premium start",
  projectStartProBadge: "PRO / Premium",
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

Object.assign(TRANSLATIONS.uk, {
  aiScanApply: "\u0417\u0430\u0441\u0442\u043e\u0441\u0443\u0432\u0430\u0442\u0438 \u0434\u043e \u0444\u043e\u0440\u043c\u0438",
  aiScanConfirmed: "\u0420\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f \u043f\u0456\u0434\u0442\u0432\u0435\u0440\u0434\u0436\u0435\u043d\u043e",
  aiScanDescription:
    "\u0417\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0442\u0435 \u0444\u043e\u0442\u043e, \u0435\u0441\u043a\u0456\u0437 \u0430\u0431\u043e PDF. \u0421\u0438\u0441\u0442\u0435\u043c\u0430 \u0441\u043f\u0440\u043e\u0431\u0443\u0454 \u0432\u0438\u0437\u043d\u0430\u0447\u0438\u0442\u0438 \u0442\u0438\u043f \u043c\u0435\u0431\u043b\u0456\u0432 \u0456 \u0440\u043e\u0437\u043c\u0456\u0440\u0438.",
  aiScanFound: "\u041f\u043e\u043f\u0435\u0440\u0435\u0434\u043d\u0456\u0439 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442",
  aiScanHistory: "\u041e\u0441\u0442\u0430\u043d\u043d\u0456 \u0447\u0435\u0440\u043d\u0435\u0442\u043a\u0438 \u0440\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u044c",
  aiScanNeedsConfirmation: "\u041f\u043e\u0442\u0440\u0456\u0431\u043d\u0435 \u043f\u0456\u0434\u0442\u0432\u0435\u0440\u0434\u0436\u0435\u043d\u043d\u044f",
  aiScanProOnly: "AI-\u0440\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0435 \u0434\u043b\u044f PRO, Premium \u0442\u0430 \u0430\u0434\u043c\u0456\u043d\u0430.",
  aiScanRawText: "OCR-\u0442\u0435\u043a\u0441\u0442",
  aiScanTitle: "AI-\u0440\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f",
  aiScanUnsupported: "\u0420\u043e\u0437\u043f\u0456\u0437\u043d\u0430\u0432\u0430\u043d\u043d\u044f \u043d\u0435 \u0432\u0434\u0430\u043b\u043e\u0441\u044f",
  aiScanUpload: "\u041f\u0440\u043e\u0430\u043d\u0430\u043b\u0456\u0437\u0443\u0432\u0430\u0442\u0438 \u0444\u0430\u0439\u043b",
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
  projectSpecificationTitle: "\u0421\u043f\u0435\u0446\u0438\u0444\u0456\u043a\u0430\u0446\u0456\u044f \u043f\u0440\u043e\u0435\u043a\u0442\u0443",
  projectStartAiDescription:
    "\u0417\u0430\u0432\u0430\u043d\u0442\u0430\u0436\u0442\u0435 \u0435\u0441\u043a\u0456\u0437, \u0444\u043e\u0442\u043e \u0430\u0431\u043e PDF \u0456 \u043f\u0456\u0434\u0442\u0432\u0435\u0440\u0434\u0456\u0442\u044c \u0437\u043d\u0430\u0439\u0434\u0435\u043d\u0456 \u0434\u0430\u043d\u0456.",
  projectStartAiTitle: "PRO AI-\u0441\u043a\u0430\u043d",
  projectStartDescription:
    "\u041e\u0431\u0435\u0440\u0456\u0442\u044c \u0441\u0446\u0435\u043d\u0430\u0440\u0456\u0439: \u0448\u0430\u0431\u043b\u043e\u043d, PRO-\u0441\u043a\u0430\u043d \u0430\u0431\u043e \u0440\u043e\u0437\u0448\u0438\u0440\u0435\u043d\u0438\u0439 Premium-\u0441\u0442\u0430\u0440\u0442.",
  projectStartFreeBadge: "\u0411\u0435\u0437\u043a\u043e\u0448\u0442\u043e\u0432\u043d\u043e",
  projectStartManualDescription:
    "\u0411\u0435\u0437\u043a\u043e\u0448\u0442\u043e\u0432\u043d\u0438\u0439 \u0441\u0442\u0430\u0440\u0442: \u0432\u0438\u0431\u0435\u0440\u0456\u0442\u044c \u0433\u043e\u0442\u043e\u0432\u0438\u0439 \u0448\u0430\u0431\u043b\u043e\u043d \u0456 \u0434\u043e\u043f\u0440\u0430\u0446\u044e\u0439\u0442\u0435 \u043f\u043e\u043b\u044f.",
  projectStartManualTitle: "\u0413\u043e\u0442\u043e\u0432\u0456 \u0448\u0430\u0431\u043b\u043e\u043d\u0438",
  projectStartPremiumBadge: "Premium",
  projectStartPremiumDescription:
    "\u041c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u0438\u0439 \u0441\u0442\u0430\u0440\u0442: \u0448\u0430\u0431\u043b\u043e\u043d\u0438, \u0441\u043a\u0430\u043d, PDF \u0442\u0430 \u043c\u0430\u0439\u0431\u0443\u0442\u043d\u0456 \u043f\u0430\u043a\u0435\u0442\u043d\u0456 \u0456\u043c\u043f\u043e\u0440\u0442\u0438.",
  projectStartPremiumOnly: "Premium-\u0441\u0442\u0430\u0440\u0442 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0438\u0439 \u0434\u043b\u044f Premium \u0442\u0430 \u0430\u0434\u043c\u0456\u043d\u0430.",
  projectStartPremiumTitle: "Premium \u0441\u0442\u0430\u0440\u0442",
  projectStartProBadge: "PRO / Premium",
  projectStartTitle: "\u041f\u043e\u0447\u0430\u0442\u043e\u043a \u043f\u0440\u043e\u0435\u043a\u0442\u0443",
  projectTemplateApplied: "\u0428\u0430\u0431\u043b\u043e\u043d \u0437\u0430\u0441\u0442\u043e\u0441\u043e\u0432\u0430\u043d\u043e \u0434\u043e \u0444\u043e\u0440\u043c\u0438",
  projectTemplateCabinetDescription: "\u041a\u043e\u043c\u043f\u0430\u043a\u0442\u043d\u0430 \u0442\u0443\u043c\u0431\u0430 \u0434\u043b\u044f \u0448\u0432\u0438\u0434\u043a\u043e\u0433\u043e \u0440\u0443\u0447\u043d\u043e\u0433\u043e \u043f\u0440\u043e\u0440\u0430\u0445\u0443\u043d\u043a\u0443.",
  projectTemplateCabinetTitle: "\u0422\u0443\u043c\u0431\u0430",
  projectTemplateDrawerUnitDescription: "\u0411\u043b\u043e\u043a \u0448\u0443\u0445\u043b\u044f\u0434 \u0437 \u0431\u0430\u0437\u043e\u0432\u0438\u043c\u0438 \u043d\u0430\u043f\u0440\u0430\u0432\u043b\u044f\u044e\u0447\u0438\u043c\u0438.",
  projectTemplateDrawerUnitTitle: "\u0411\u043b\u043e\u043a \u0448\u0443\u0445\u043b\u044f\u0434",
  projectTemplateDresserDescription: "\u041a\u043e\u043c\u043e\u0434 \u0437 \u0441\u0435\u043a\u0446\u0456\u044f\u043c\u0438 \u0442\u0430 \u0448\u0443\u0445\u043b\u044f\u0434\u0430\u043c\u0438 \u0437\u0430 \u0431\u0430\u0437\u043e\u0432\u0438\u043c \u0441\u0446\u0435\u043d\u0430\u0440\u0456\u0454\u043c.",
  projectTemplateDresserTitle: "\u041a\u043e\u043c\u043e\u0434",
  projectTemplateWardrobeDescription: "\u0412\u0438\u0441\u043e\u043a\u0430 \u0448\u0430\u0444\u0430 \u0437 \u0441\u0435\u043a\u0446\u0456\u044f\u043c\u0438 \u0442\u0430 \u043e\u0434\u043d\u0456\u0454\u044e \u0448\u0443\u0445\u043b\u044f\u0434\u043e\u044e.",
  projectTemplateWardrobeTitle: "\u0428\u0430\u0444\u0430",
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

function buildProjectPayload(form) {
  const normalizeText = (value) => {
    const trimmed = String(value || "").trim();
    return trimmed || null;
  };
  const normalizeNumber = (value) => {
    if (value === null || value === undefined || value === "") {
      return null;
    }

    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const drawerConfig = String(form.drawers || "")
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);

  return {
    metadata: {
      name: normalizeText(form.projectName) || DEFAULT_PROJECT_NAME,
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
      facade_edge_banding: normalizeText(form.facadeEdgeBanding),
      inside_edge_banding: normalizeText(form.insideEdgeBanding),
      edge_banding: normalizeText(form.insideEdgeBanding || form.facadeEdgeBanding),
      facade_thickness: normalizeNumber(form.facadeThickness),
      inside_thickness: normalizeNumber(form.insideThickness),
      thickness: normalizeNumber(form.insideThickness || form.facadeThickness),
    },
    fittings: {
      slide_type: normalizeText(form.slideType) || "tandem",
      bottom_type: normalizeText(form.bottomType) || "hdf",
      handle_type: normalizeText(form.handleType),
      handle_position: normalizeText(form.handlePosition),
    },
  };
}

function projectToForm(project) {
  return {
    projectName: project?.project_name || DEFAULT_PROJECT_NAME,
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
    facadeEdgeBanding: project?.facade_edge_banding || project?.edge_banding || "",
    insideEdgeBanding: project?.inside_edge_banding || project?.edge_banding || "",
    facadeThickness: project?.facade_thickness || project?.material_thickness || 18,
    insideThickness: project?.inside_thickness || project?.material_thickness || 18,
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

function buildProjectMaterialOption(item) {
  const name = String(item?.name || "").trim();
  const article = String(item?.display_article || item?.article || "").trim();
  const dimensions = String(item?.dimensions || "").trim();
  const thickness = String(item?.thickness || "").trim();

  const suffix = [dimensions, thickness].filter(Boolean).join(" / ");
  const primary = name || article;

  if (!primary) {
    return "";
  }

  if (suffix) {
    return `${primary} (${suffix})`;
  }

  return primary;
}

function buildProjectHandleOption(item) {
  const name = String(item?.name || "").trim();
  const article = String(item?.article || "").trim();
  const code = String(item?.code || "").trim();
  const primary = name || code || article;

  if (!primary) {
    return "";
  }

  if (article && article !== primary) {
    return `${primary} [${article}]`;
  }

  return primary;
}

function parseProjectMaterialThicknessValue(value) {
  const normalized = String(value || "").replace(",", ".").trim();
  const match = normalized.match(/(\d+(?:\.\d+)?)/);

  if (!match) {
    return null;
  }

  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? parsed : null;
}

function findProjectMaterialItemByValue(items, value) {
  const normalizedValue = String(value || "").trim();

  if (!normalizedValue) {
    return null;
  }

  return (
    items.find((item) => String(item.pickerValue || "").trim() === normalizedValue) ||
    items.find((item) => String(item.name || "").trim() === normalizedValue) ||
    items.find((item) => String(item.article || "").trim() === normalizedValue) ||
    null
  );
}

function buildProjectEdgeBandingOption(materialItem, edgeItem, slotLabel) {
  if (!edgeItem) {
    return null;
  }

  const name = String(edgeItem.name || "").trim();
  const article = String(edgeItem.article || "").trim();
  const thickness = String(edgeItem.thickness || "").trim();
  const materialName = getMaterialShortName(materialItem);

  return {
    ...edgeItem,
    id: `${materialItem?.article || materialItem?.id || "material"}-${edgeItem.edge_key || article || name}`,
    pickerValue: name || article || slotLabel,
    pickerTitle: name || article || slotLabel,
    pickerSubtitle: [slotLabel, thickness, materialName].filter(Boolean).join(" / "),
    pickerSearch: [name, article, thickness, materialName, slotLabel].filter(Boolean).join(" ").toLowerCase(),
  };
}

function getProjectMaterialDependencyConfig(field) {
  if (
    field === "facadeMaterial" ||
    field === "facadeEdgeBanding" ||
    field === "facadeThickness"
  ) {
    return {
      edgeField: "facadeEdgeBanding",
      materialField: "facadeMaterial",
      thicknessField: "facadeThickness",
    };
  }

  if (
    field === "insideMaterial" ||
    field === "insideEdgeBanding" ||
    field === "insideThickness"
  ) {
    return {
      edgeField: "insideEdgeBanding",
      materialField: "insideMaterial",
      thicknessField: "insideThickness",
    };
  }

  return {
    edgeField: "",
    materialField: "",
    thicknessField: "",
  };
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

function getSlideLengthForDepth(depth) {
  const value = Number(depth);

  if (!Number.isFinite(value) || value <= 0) {
    return 500;
  }

  if (value >= 290 && value < 340) return 250;
  if (value >= 340 && value < 390) return 300;
  if (value >= 390 && value < 440) return 350;
  if (value >= 440 && value < 490) return 400;
  if (value >= 490 && value < 540) return 450;
  if (value >= 540 && value < 590) return 500;
  if (value >= 590 && value < 640) return 550;
  return 600;
}

function detectProjectSlideFamily(value) {
  const haystack = String(value || "").toLowerCase();

  if (haystack.includes("movento")) {
    return "movento";
  }

  if (haystack.includes("tandem")) {
    return "tandem";
  }

  if (haystack.includes("telescopic") || haystack.includes("телескоп")) {
    return "telescopic";
  }

  return "";
}

function detectProjectSlideLength(value) {
  const haystack = String(value || "");

  for (const length of DRAWER_SLIDE_LENGTHS) {
    const matcher = new RegExp(`(^|[^0-9])${length}([^0-9]|$)`);
    if (matcher.test(haystack)) {
      return length;
    }
  }

  return null;
}

function buildMaterialImageCandidates(item, token = "") {
  const candidates = [];
  const article = String(item?.article || "").trim();
  const cacheVersion = item?.has_cached_image ? "db" : "source";
  // Always use the stable API URL first. The endpoint serves the database BLOB
  // and fills that cache once when an older record has only a source URL.
  const imageEndpoint = article
    ? `${API_BASE_URL}/catalog/materials/${encodeURIComponent(article)}/image?v=${cacheVersion}`
    : "";

  if (imageEndpoint) {
    candidates.push(imageEndpoint);
  }

  const sourceSite = item?.source_site || detectFittingSourceSite(item?.source_url);
  if (sourceSite === "kronas" && article) {
    candidates.push(`https://kronas.com.ua/Media/images/catalog/medium/${encodeURIComponent(article)}.jpg`);
  }

  return [...new Set(candidates.filter(Boolean))];
}

function buildMaterialEdgeImageCandidates(materialItem, edgeItem, token = "") {
  const candidates = [];
  const article = String(materialItem?.article || "").trim();
  const edgeKey = String(edgeItem?.edge_key || "").trim();
  const cacheVersion = edgeItem?.has_cached_image ? "db" : "source";
  const cachedImage = article && edgeKey
    ? `${API_BASE_URL}/catalog/materials/${encodeURIComponent(article)}/edges/${encodeURIComponent(edgeKey)}/image?v=${cacheVersion}`
    : "";

  if (cachedImage) {
    candidates.push(cachedImage);
  }

  return [...new Set(candidates.filter(Boolean))];
}

function buildFittingImageCandidates(item) {
  const candidates = [];
  const itemId = String(item?.id || "").trim();
  const cacheVersion = item?.has_cached_image ? "db" : "source";
  const cachedImage = itemId
    ? `${API_BASE_URL}/catalog/fittings/${encodeURIComponent(itemId)}/image?v=${cacheVersion}`
    : "";

  if (cachedImage) {
    candidates.push(cachedImage);
  }

  return [...new Set(candidates.filter(Boolean))];
}

function handleFittingImageError(event, item) {
  const candidates = buildFittingImageCandidates(item);
  const currentIndex = Number(event.currentTarget.dataset.fallbackIndex || "0");
  const nextIndex = currentIndex + 1;

  if (nextIndex >= candidates.length) {
    event.currentTarget.style.display = "none";
    return;
  }

  event.currentTarget.dataset.fallbackIndex = String(nextIndex);
  event.currentTarget.src = candidates[nextIndex];
}

function handleMaterialImageError(event, item, token = "") {
  const candidates = buildMaterialImageCandidates(item, token);
  const currentIndex = Number(event.currentTarget.dataset.fallbackIndex || "0");
  const nextIndex = currentIndex + 1;

  if (nextIndex >= candidates.length) {
    event.currentTarget.style.display = "none";
    const placeholder = event.currentTarget.parentElement?.querySelector(".material-card-placeholder");
    if (placeholder) {
      placeholder.hidden = false;
    }
    return;
  }

  event.currentTarget.dataset.fallbackIndex = String(nextIndex);
  event.currentTarget.src = candidates[nextIndex];
}

function handleMaterialEdgeImageError(event, materialItem, edgeItem, token = "") {
  const candidates = buildMaterialEdgeImageCandidates(materialItem, edgeItem, token);
  const currentIndex = Number(event.currentTarget.dataset.fallbackIndex || "0");
  const nextIndex = currentIndex + 1;

  if (nextIndex >= candidates.length) {
    event.currentTarget.style.display = "none";
    const placeholder = event.currentTarget.parentElement?.querySelector(".material-edge-card-preview-placeholder");
    if (placeholder) {
      placeholder.hidden = false;
    }
    return;
  }

  event.currentTarget.dataset.fallbackIndex = String(nextIndex);
  event.currentTarget.src = candidates[nextIndex];
}

function hasProCatalogAccess(user) {
  return user?.role === "admin" || user?.role === "premium" || user?.role === "pro";
}

function canManageMaterialCatalog(user) {
  return hasProCatalogAccess(user);
}

function canManageSystemMaterials(user) {
  return hasProCatalogAccess(user);
}

function canEditMaterialItem(user, item) {
  if (!user || !item) {
    return false;
  }

  if (!hasProCatalogAccess(user)) {
    return false;
  }

  if (item.is_default) {
    return true;
  }

  return item.owner_user_id === String(user.id);
}

function canDeleteMaterialItem(user, item) {
  return canEditMaterialItem(user, item);
}

function getMaterialSourceMeta(item, t) {
  const sourceSite = item?.source_site || detectFittingSourceSite(item?.source_url);

  if (sourceSite === "viyar") {
    return { code: "viyar", label: "Viyar", logo: buildAdminAssetUrl("brand/source-logos/viyar.jpg") };
  }

  if (sourceSite === "blum") {
    return { code: "blum", label: "BLUM", logo: buildAdminAssetUrl("brand/source-logos/blum.jpg") };
  }

  if (sourceSite === "kronas") {
    return { code: "kronas", label: "Kronas", logo: buildAdminAssetUrl("brand/source-logos/kronas.jpg") };
  }

  return { code: "manual", label: t.fittingManualSource, logo: buildAdminAssetUrl("brand/source-logos/manual.svg") };
}

function stripMaterialSizeSuffix(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (!text) {
    return "";
  }

  return text
    .replace(/\s+\d{2,4}\s*[xXхХ×]\s*\d{2,4}\s*[xXхХ×]\s*\d{1,3}\s*(?:мм|mm)?\b.*$/iu, "")
    .trim();
}

function getMaterialShortName(item) {
  const shortName = stripMaterialSizeSuffix(item?.name || "");
  return shortName || item?.name || item?.article || "";
}

function getMaterialDescriptionText(item, t) {
  const description = String(item?.description || "").replace(/\s+/g, " ").trim();
  const shortName = getMaterialShortName(item);

  if (!description) {
    return shortName || t.notSet;
  }

  const normalizedDescription = description.toLowerCase();
  const promoMarkers = [
    "інтернет-магазин",
    "интернет-магазин",
    "пропонує замовити",
    "з доставкою по україні",
    "телефонуйте",
    "купити",
    "купить",
    "лучшие цены",
    "кращі ціни",
    "доставка по",
    "доставка до",
    "консультации по телефону",
    "консультації за телефоном",
  ];

  if (promoMarkers.some((marker) => normalizedDescription.includes(marker))) {
    return shortName || t.notSet;
  }

  return description;
}

function getMaterialColorText(item, t) {
  const color = String(item?.color || "").replace(/\s+/g, " ").trim();
  if (!color) {
    return t.notSet;
  }
  return stripMaterialSizeSuffix(color) || color;
}

function renderSourceBadge(sourceMeta, withLabel = false) {
  if (!sourceMeta) {
    return null;
  }

  return (
    <span className={`fitting-source-logo ${sourceMeta.code}`} title={sourceMeta.label}>
      {sourceMeta.logo ? (
        <img alt={sourceMeta.label} className="fitting-source-logo-image" src={sourceMeta.logo} />
      ) : null}
      {withLabel ? <span className="fitting-source-logo-text">{sourceMeta.label}</span> : null}
    </span>
  );
}

function getMaterialEdgeItem(item, edgeKey) {
  return (item?.edge_options || []).find((edge) => edge.edge_key === edgeKey) || null;
}

function getMaterialEdgeSlot(edgeKey) {
  return MATERIAL_EDGE_SLOTS.find((slot) => slot.key === edgeKey) || null;
}

function getMaterialEdgeSlotIndex(edgeKey) {
  const index = MATERIAL_EDGE_SLOTS.findIndex((slot) => slot.key === edgeKey);
  return index === -1 ? MATERIAL_EDGE_SLOTS.length : index;
}

function getSortedMaterialEdgeItems(item) {
  return [...(item?.edge_options || [])]
    .filter(Boolean)
    .sort((left, right) => getMaterialEdgeSlotIndex(left.edge_key) - getMaterialEdgeSlotIndex(right.edge_key));
}

function getDefaultMaterialEdgeKey(item) {
  const existingKeys = new Set((item?.edge_options || []).map((edge) => edge.edge_key));
  return MATERIAL_EDGE_SLOTS.find((slot) => !existingKeys.has(slot.key))?.key || MATERIAL_EDGE_SLOTS[0].key;
}

function canManageSystemFittings(user) {
  return user?.role === "admin";
}

function canManageOwnFittings(user) {
  return hasProCatalogAccess(user);
}

function canDeleteFittingItem(user, item) {
  if (!user || !item) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  return !item.is_system && item.owner_user_id === user.id;
}

function canEditProject(project, user) {
  if (!project || !user) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  if (user.role === "free" || user.role === "pro" || user.role === "premium") {
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
  return Boolean(user);
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
          <linearGradient id="panel-front-gradient-admin" x1="0%" x2="0%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#fbfdfe" />
            <stop offset="100%" stopColor="#d8e2e8" />
          </linearGradient>
          <linearGradient id="panel-top-gradient-admin" x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#f7fbfd" />
            <stop offset="100%" stopColor="#bcc8d1" />
          </linearGradient>
          <linearGradient id="panel-side-gradient-admin" x1="0%" x2="100%" y1="0%" y2="100%">
            <stop offset="0%" stopColor="#cbd6de" />
            <stop offset="100%" stopColor="#a8b6bf" />
          </linearGradient>
          <filter id="panel-shadow-admin" colorInterpolationFilters="sRGB" height="160%" width="160%" x="-30%" y="-30%">
            <feDropShadow dx="0" dy="10" floodColor="rgba(13,20,26,0.18)" stdDeviation="10" />
          </filter>
        </defs>
        <ellipse className="part-3d-shadow" cx={viewWidth / 2} cy={faceY + faceHeight + 56} rx={faceWidth * 0.42} ry="24" />
        <g filter="url(#panel-shadow-admin)">
          <polygon
            className="part-3d-face part-3d-top"
            fill="url(#panel-top-gradient-admin)"
            points={pointsToString([topLeft, topRight, backTopRight, backTopLeft])}
          />
          {dx >= 0 ? (
            <polygon
              className="part-3d-face part-3d-side"
              fill="url(#panel-side-gradient-admin)"
              points={pointsToString([topRight, bottomRight, backBottomRight, backTopRight])}
            />
          ) : (
            <polygon
              className="part-3d-face part-3d-side"
              fill="url(#panel-side-gradient-admin)"
              points={pointsToString([topLeft, bottomLeft, backBottomLeft, backTopLeft])}
            />
          )}
          <rect
            className="part-board"
            fill="url(#panel-front-gradient-admin)"
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
        {t.save}
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
              <th>{t.action}</th>
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
                    <X size={14} />
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
        <span>{t.productionPartViewer}</span>
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
        {t.save}
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
                    <th>{t.catalogCategory}</th>
                    <th>X</th>
                    <th>Y</th>
                    <th>{t.materialThickness}</th>
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
                    <th>{t.catalogCategory}</th>
                    <th>X</th>
                    <th>Y</th>
                    <th>{t.cuttingLength}</th>
                    <th>{t.materialThickness}</th>
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
                    <th>{t.catalogCategory}</th>
                    <th>{t.cuttingLength}</th>
                    <th>{t.cuttingSize}</th>
                    <th>{t.materialThickness}</th>
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
    () => localStorage.getItem(LANGUAGE_STORAGE_KEY) || "en",
  );
  const [token, setToken] = useState(
    () => consumeAdminTokenHandoff(),
  );
  const tokenRef = useRef(token);
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(Boolean(token));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showLoginPassword, setShowLoginPassword] = useState(false);
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
  const [viyarAuth, setViyarAuth] = useState(null);
  const [viyarAuthForm, setViyarAuthForm] = useState({
    email: "",
    password: "",
  });
  const [viyarAction, setViyarAction] = useState("");
  const [newUserForm, setNewUserForm] = useState({
    email: "",
    password: "",
    role: "free",
  });
  const [newCatalogItemForm, setNewCatalogItemForm] = useState({
    category: "project_type",
    value: "",
    sortOrder: 0,
  });
  const [newManualServiceForm, setNewManualServiceForm] = useState({
    article: "",
    base_price: "",
    description: "",
    is_active: true,
    is_calculable: true,
    name: "",
    unit: "service",
  });
  const [newProjectForm, setNewProjectForm] = useState(DEFAULT_PROJECT_FORM);
  const [projectStartMode, setProjectStartMode] = useState("templates");
  const [aiScanFile, setAiScanFile] = useState(null);
  const [aiScanResult, setAiScanResult] = useState(null);
  const [aiScanSession, setAiScanSession] = useState(null);
  const [aiScanHistory, setAiScanHistory] = useState([]);
  const [projectFilters, setProjectFilters] = useState(DEFAULT_PROJECT_FILTERS);
  const [resetPasswordForms, setResetPasswordForms] = useState({});
  const [projects, setProjects] = useState([]);
  const [users, setUsers] = useState([]);
  const [userChangeRequests, setUserChangeRequests] = useState([]);
  const [selectedUserDetails, setSelectedUserDetails] = useState(null);
  const [auditLogs, setAuditLogs] = useState([]);
  const [catalogItems, setCatalogItems] = useState([]);
  const [viyarServiceTree, setViyarServiceTree] = useState([]);
  const [manualServiceItems, setManualServiceItems] = useState([]);
  const [materialItems, setMaterialItems] = useState([]);
  const [materialCategories, setMaterialCategories] = useState([]);
  const [materialCityOptions, setMaterialCityOptions] = useState(DEFAULT_CITY_OPTIONS);
  const [materialSelectedCity, setMaterialSelectedCity] = useState("");
  const [materialCreateMode, setMaterialCreateMode] = useState("source");
  const [materialSearch, setMaterialSearch] = useState("");
  const [materialCategoryFilter, setMaterialCategoryFilter] = useState("dsp");
  const [newMaterialArticle, setNewMaterialArticle] = useState("");
  const [newMaterialSourceUrl, setNewMaterialSourceUrl] = useState("");
  const [newMaterialName, setNewMaterialName] = useState("");
  const [newMaterialPrice, setNewMaterialPrice] = useState("");
  const [newMaterialImageUrl, setNewMaterialImageUrl] = useState("");
  const [newMaterialIsDefault, setNewMaterialIsDefault] = useState(false);
  const [activeMaterialImportJobId, setActiveMaterialImportJobId] = useState("");
  const [activeMaterialImportJob, setActiveMaterialImportJob] = useState(null);
  const [openMaterialMenuId, setOpenMaterialMenuId] = useState("");
  const [selectedMaterialDetail, setSelectedMaterialDetail] = useState(null);
  const [materialDetailLoading, setMaterialDetailLoading] = useState(false);
  const [materialEdgeForms, setMaterialEdgeForms] = useState({});
  const [materialEdgeCreateForm, setMaterialEdgeCreateForm] = useState({
    open: false,
    edge_key: "edge_08",
    source_url: "",
  });
  const [openFittingMenuId, setOpenFittingMenuId] = useState("");
  const [projectOptionPicker, setProjectOptionPicker] = useState({
    open: false,
    target: "create",
    field: "",
    mode: "materials",
    title: "",
  });
  const [projectOptionPickerSearch, setProjectOptionPickerSearch] = useState("");
  const [viyarServiceSource, setViyarServiceSource] = useState("viyar");
  const [viyarTreeLoading, setViyarTreeLoading] = useState(false);
  const [viyarPriceSyncSummary, setViyarPriceSyncSummary] = useState(null);
  const [viyarServiceSearch, setViyarServiceSearch] = useState("");
  const [collapsedViyarFolders, setCollapsedViyarFolders] = useState({});
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
  const [cuttingAssembly, setCuttingAssembly] = useState({});
  const [cuttingSummary, setCuttingSummary] = useState(null);
  const [selectedPartDetail, setSelectedPartDetail] = useState(null);
  const [selectedCuttingPartCode, setSelectedCuttingPartCode] = useState(null);
  const [hoveredCuttingPartCode, setHoveredCuttingPartCode] = useState(null);
  const [collapsedCuttingGroups, setCollapsedCuttingGroups] = useState({});
  const [cuttingSearch, setCuttingSearch] = useState("");
  const [selectedEdgeSide, setSelectedEdgeSide] = useState(null);
  const [activeProjectTab, setActiveProjectTab] = useState("data");
  const [projectOverviewOpen, setProjectOverviewOpen] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [productionLoaded, setProductionLoaded] = useState(false);
  const [form, setForm] = useState(projectToForm(null));
  const [status, setStatusState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [confirmAction, setConfirmAction] = useState(null);
  const [activeView, setActiveView] = useState(
    () => normalizeCatalogView(localStorage.getItem(ACTIVE_VIEW_STORAGE_KEY) || "home"),
  );
  const [isCatalogMenuOpen, setIsCatalogMenuOpen] = useState(false);
  const [fittingItems, setFittingItems] = useState([]);
  const [fittingCategories, setFittingCategories] = useState([]);
  const [fittingSearch, setFittingSearch] = useState("");
  const [selectedFittingCategory, setSelectedFittingCategory] = useState("");
  const [fittingViewMode, setFittingViewMode] = useState("rows");
  const [holeTemplateItems, setHoleTemplateItems] = useState([]);
  const [holeSelectedFittingId, setHoleSelectedFittingId] = useState("");
  const [holeSelectedTemplateId, setHoleSelectedTemplateId] = useState("");
  const [holeSelectedTemplate, setHoleSelectedTemplate] = useState(null);
  const [holePoints, setHolePoints] = useState([]);
  const [holeTemplateCreateOpen, setHoleTemplateCreateOpen] = useState(false);
  const [holeTemplateCreateError, setHoleTemplateCreateError] = useState("");
  const [holeTemplateCreateForm, setHoleTemplateCreateForm] = useState(DEFAULT_HOLE_TEMPLATE_FORM);
  const [holeTemplateEditOpen, setHoleTemplateEditOpen] = useState(false);
  const [holeTemplateEditError, setHoleTemplateEditError] = useState("");
  const [holeTemplateEditForm, setHoleTemplateEditForm] = useState(DEFAULT_HOLE_TEMPLATE_FORM);
  const [holeTemplateEditTemplateId, setHoleTemplateEditTemplateId] = useState("");
  const [holeTemplateEditSaving, setHoleTemplateEditSaving] = useState(false);
  const [holePointCreateOpen, setHolePointCreateOpen] = useState(false);
  const [holePointCreateError, setHolePointCreateError] = useState("");
  const [holePointCreateForm, setHolePointCreateForm] = useState(DEFAULT_HOLE_POINT_FORM);
  const [holePointEditOpen, setHolePointEditOpen] = useState(false);
  const [holePointEditError, setHolePointEditError] = useState("");
  const [holePointEditForm, setHolePointEditForm] = useState(DEFAULT_HOLE_POINT_FORM);
  const [holePointEditPointId, setHolePointEditPointId] = useState("");
  const [hoveredHolePointId, setHoveredHolePointId] = useState("");
  const [selectedHoleMountingVariantKey, setSelectedHoleMountingVariantKey] =
    useState("plane_to_edge");
  const [newFittingForm, setNewFittingForm] = useState(DEFAULT_FITTING_FORM);
  const [autoRefreshStatus, setAutoRefreshStatus] = useState(null);
  const storedProjectId = localStorage.getItem(ACTIVE_PROJECT_ID_STORAGE_KEY) || "";
  const storedProjectTab = localStorage.getItem(ACTIVE_PROJECT_TAB_STORAGE_KEY) || "data";

  const t = TRANSLATIONS[language] || TRANSLATIONS.en;
  const userLoginName = user?.username || user?.email?.split("@")[0] || "";
  const canUseAiScan = user?.role === "admin" || user?.role === "premium" || user?.role === "pro";
  const canUsePremiumStart = user?.role === "admin" || user?.role === "premium";
  const canViewFittingHoles = user?.role === "admin" || user?.role === "premium" || user?.role === "pro";
  const selectedHoleFitting = useMemo(
    () => fittingItems.find((item) => String(item.id) === String(holeSelectedFittingId)) || null,
    [fittingItems, holeSelectedFittingId],
  );
  const selectedHoleTemplate = useMemo(
    () => holeTemplateItems.find((item) => String(item.id) === String(holeSelectedTemplateId)) || holeSelectedTemplate || null,
    [holeSelectedTemplate, holeSelectedTemplateId, holeTemplateItems],
  );
  const holeMountingVariantOptions = useMemo(
    () => [
      {
        description: "Установка фурнітури на площині.",
        key: "surface_mount",
        icon: surfaceMountIcon,
        label: "Установка фурнітури на площині",
      },
      {
        description: "Кріплення між двома непаралельними площинами.",
        key: "angled_two_planes",
        icon: angledTwoPlanesIcon,
        label: "Установка фурнітури на дві непаралельні площини",
      },
      {
        description: "Установка на плаcті однієї та торця іншої панелі.",
        key: "face_to_edge",
        icon: faceToEdgeIcon,
        label: "Установка на плаcті однієї та торця іншої панелі",
      },
      {
        description: "Установка фурнітури по торцях панелей.",
        key: "edge_to_edge",
        icon: edgeToEdgeIcon,
        label: "Установка фурнітури по торцях панелей",
      },
      {
        description: "Напрямні для висувних елементів.",
        key: "drawer_slides",
        icon: drawerSlidesIcon,
        label: "Напрямні",
      },
    ],
    [],
  );
  const selectedHoleMountingVariant = useMemo(
    () =>
      holeMountingVariantOptions.find((item) => item.key === selectedHoleMountingVariantKey) ||
      holeMountingVariantOptions[0] ||
      null,
    [holeMountingVariantOptions, selectedHoleMountingVariantKey],
  );
  const holesMaterialPlanesModel = useMemo(() => {
    switch (selectedHoleMountingVariant?.key || selectedHoleMountingVariantKey || "surface_mount") {
      case "angled_two_planes":
        return {
          connectionDirection: "angled_two_planes",
          planeA: {
            key: "vertical_plane",
            label: "Вертикальна площина",
            role: "source",
          },
          planeB: {
            key: "angled_plane",
            label: "Непаралельна площина",
            role: "target",
          },
        };
      case "face_to_edge":
        return {
          connectionDirection: "face_to_edge",
          planeA: {
            key: "face",
            label: "Пласть панелі",
            role: "source",
          },
          planeB: {
            key: "edge",
            label: "Торець панелі",
            role: "target",
          },
        };
      case "edge_to_edge":
        return {
          connectionDirection: "edge_to_edge",
          planeA: {
            key: "edge_left",
            label: "Торець панелі A",
            role: "source",
          },
          planeB: {
            key: "edge_right",
            label: "Торець панелі B",
            role: "target",
          },
        };
      case "drawer_slides":
        return {
          connectionDirection: "drawer_slides",
          planeA: {
            key: "side_left",
            label: "Ліва боковина",
            role: "side",
          },
          planeB: {
            key: "side_right",
            label: "Права боковина",
            role: "side",
          },
        };
      case "surface_mount":
      default:
        return {
          connectionDirection: "surface_mount",
          planeA: {
            key: "surface",
            label: "Площина",
            role: "base",
          },
          planeB: {
            key: "hardware",
            label: "Фурнітура",
            role: "mounted",
          },
        };
    }
  }, [selectedHoleMountingVariant?.key, selectedHoleMountingVariantKey]);
  const holePreviewData = useMemo(() => {
    const numericValue = (value) => {
      if (value === null || value === undefined || value === "") {
        return null;
      }

      const parsed = Number(String(value).replace(",", "."));
      return Number.isFinite(parsed) ? parsed : null;
    };

    const previewPoints = (Array.isArray(holePoints) ? holePoints : []).map((point, index) => {
      const x = numericValue(point?.x_mm) ?? 0;
      const y = numericValue(point?.y_mm) ?? 0;
      const z = numericValue(point?.z_mm);
      const diameter = numericValue(point?.diameter_mm) ?? 0;
      const depth = numericValue(point?.depth_mm);
      const label = String(point?.label || "").trim() || `P${point?.id || index + 1}`;
      const operation = String(point?.operation || "").trim() || "";
      const side = String(point?.side || "").trim() || "";

      return {
        diameter,
        depth,
        fallbackLabel: label,
        id: point?.id ?? index + 1,
        label,
        mirrored: Boolean(point?.mirrored),
        notes: String(point?.notes || "").trim(),
        operation,
        orderIndex: point?.order_index ?? 0,
        quantity: point?.quantity ?? 1,
        side,
        x,
        y,
        z,
      };
    });

    if (!previewPoints.length) {
      return {
        hasPoints: false,
        height: 240,
        points: [],
        width: 320,
      };
    }

    const xValues = previewPoints.map((point) => point.x);
    const yValues = previewPoints.map((point) => point.y);
    const minX = Math.min(0, ...xValues);
    const minY = Math.min(0, ...yValues);
    const maxX = Math.max(0, ...xValues);
    const maxY = Math.max(0, ...yValues);
    const maxDiameter = Math.max(18, ...previewPoints.map((point) => point.diameter || 0));
    const padding = 36;
    const width = Math.max(260, (maxX - minX) + (padding * 2) + maxDiameter);
    const height = Math.max(220, (maxY - minY) + (padding * 2) + maxDiameter);

    return {
      hasPoints: true,
      height,
      points: previewPoints.map((point) => ({
        ...point,
        labelX: point.x - minX + padding + Math.max(10, Math.min(18, point.diameter / 2 + 6)),
        labelY: point.y - minY + padding - Math.max(10, Math.min(18, point.diameter / 2 + 6)),
        previewX: point.x - minX + padding,
        previewY: point.y - minY + padding,
        radius: Math.max(6, Math.min(18, Math.round((point.diameter || 0) / 2) || 6)),
      })),
      width,
    };
  }, [holePoints]);
  const holesPreviewSceneModel = useMemo(() => {
    const sceneHoles = Array.isArray(holePreviewData.points)
      ? holePreviewData.points.map((point) => ({
          depth: point.depth,
          diameter: point.diameter,
          id: point.id,
          isHovered: String(hoveredHolePointId) === String(point.id),
          operation: point.operation,
          side: point.side,
          x: point.x,
          y: point.y,
        }))
      : [];
    const hoveredHole = sceneHoles.find((point) => point.isHovered) || null;

    return {
      fitting: selectedHoleFitting,
      hoveredHole,
      hoveredHoleId: hoveredHolePointId || "",
      holes: sceneHoles,
      materialPlanes: holesMaterialPlanesModel,
      mountingVariant: selectedHoleMountingVariant,
      stats: {
        hasFitting: Boolean(selectedHoleFitting),
        hasMountingVariant: Boolean(selectedHoleMountingVariant),
        hasTemplate: Boolean(selectedHoleTemplate),
        holesCount: sceneHoles.length,
      },
      template: selectedHoleTemplate,
    };
  }, [
    holePreviewData.points,
    hoveredHolePointId,
    holesMaterialPlanesModel,
    selectedHoleFitting,
    selectedHoleMountingVariant,
    selectedHoleTemplate,
  ]);
  const holesPreviewModel = useMemo(
    () => ({
      fitting: selectedHoleFitting,
      materialPlanes: holesMaterialPlanesModel,
      mountingVariant: selectedHoleMountingVariant,
      hoveredPointId: hoveredHolePointId || "",
      pointCount: holePoints.length,
      points: holePoints,
      scene: holesPreviewSceneModel,
      side: selectedHoleTemplate?.side ?? "",
      template: selectedHoleTemplate,
      type: selectedHoleTemplate?.template_type ?? "",
    }),
    [
      holePoints,
      hoveredHolePointId,
      selectedHoleFitting,
      holesMaterialPlanesModel,
      selectedHoleMountingVariant,
      selectedHoleTemplate,
      holesPreviewSceneModel,
    ],
  );
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
  const viyarServicesCache = user?.id ? readViyarServicesCache(user.id) : null;
  const normalizedViyarEmail = viyarAuthForm.email.trim();
  const viyarHasSavedPassword = Boolean(viyarAuth?.has_password);
  const viyarHasSavedSession = Boolean(viyarAuth?.has_cookie);
  const viyarEmailChanged = normalizedViyarEmail !== (viyarAuth?.email || "");
  const viyarHasUnsavedPassword = Boolean(viyarAuthForm.password);
  const canSaveViyarAuth =
      Boolean(normalizedViyarEmail) &&
      (!viyarAuth?.email || viyarEmailChanged || viyarHasUnsavedPassword);
  const canConnectViyar =
      Boolean(normalizedViyarEmail) &&
      (viyarHasSavedPassword || viyarHasUnsavedPassword);
  const canSyncViyar = viyarHasSavedSession;

  useEffect(() => {
    tokenRef.current = token;
  }, [token]);
  const viyarActionLabel =
    viyarAction === "saving"
      ? t.viyarSavingCredentials
      : viyarAction === "connecting"
        ? t.viyarConnectingNow
        : viyarAction === "syncing"
          ? t.viyarSyncingPricesNow
          : "";
  const hasProfileChanges =
    (ownProfileForm.username || "") !== (user?.username || "") ||
    (ownProfileForm.phone || "") !== (user?.phone || "") ||
    (ownProfileForm.city || "") !== (user?.city || "");
  const viyarNextStep = !viyarHasSavedPassword || canSaveViyarAuth
    ? "save"
    : !viyarHasSavedSession
      ? "connect"
      : "sync";
  const viyarNextStepLabel =
    viyarNextStep === "save"
      ? t.viyarStepSave
      : viyarNextStep === "connect"
        ? t.viyarStepConnect
        : t.viyarStepSync;

  const canGoBack = offset > 0;
  const canGoForward = offset + PAGE_SIZE < total;
  const canUsersGoBack = usersOffset > 0;
  const canUsersGoForward = usersOffset + PAGE_SIZE < usersTotal;
  const canAuditGoBack = auditOffset > 0;
  const canAuditGoForward = auditOffset + PAGE_SIZE < auditTotal;
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

  const selectedProjectId = selectedProject?.id || "";
  const canEditSelectedProject = canEditProject(selectedProject, user);
  const canDeleteSelectedProject = canDeleteProject(user);
  const canRollbackSelectedProject = canRollbackProject(user);
  const effectiveSelectedPartCode =
    selectedCuttingPartCode || selectedPartDetail?.part?.export_code || "";
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
  const viyarServiceCounts = useMemo(() => {
    function walk(nodes) {
      return nodes.reduce(
        (accumulator, node) => {
          if (node.item_type === "folder") {
            accumulator.folders += 1;
          }

          if (node.item_type === "service") {
            accumulator.services += 1;
          }

          if (node.children?.length) {
            const nested = walk(node.children);
            accumulator.folders += nested.folders;
            accumulator.services += nested.services;
          }

          return accumulator;
        },
        { folders: 0, services: 0 },
      );
    }

    return walk(viyarServiceTree);
  }, [viyarServiceTree]);
  const filteredViyarServiceTree = useMemo(
    () => filterServiceCatalogTree(viyarServiceTree, viyarServiceSearch),
    [viyarServiceSearch, viyarServiceTree],
  );
  const viyarFolderCodes = useMemo(
    () => collectServiceFolderCodes(viyarServiceTree),
    [viyarServiceTree],
  );
  const viyarTopFolders = useMemo(
    () =>
      flattenServiceTree(viyarServiceTree).filter(
        (item) =>
          item.item_type === "folder" &&
          item.parent_external_code === "viyar-services",
      ),
    [viyarServiceTree],
  );
  const viyarSyncOverview = useMemo(() => {
    const serviceItems = flattenServiceTree(viyarServiceTree).filter(
      (item) => item.item_type === "service",
    );
    const syncedItems = serviceItems.filter(
      (item) => item.user_last_synced_at || item.user_price_sync_status,
    );
    const latestSyncedAt = syncedItems.reduce((latest, item) => {
      if (!item.user_last_synced_at) {
        return latest;
      }

      if (!latest || new Date(item.user_last_synced_at) > new Date(latest)) {
        return item.user_last_synced_at;
      }

      return latest;
    }, null);

    return syncedItems.reduce(
      (accumulator, item) => {
        const status = item.user_price_sync_status || "unknown";

        accumulator.total += 1;
        accumulator.statuses[status] = (accumulator.statuses[status] || 0) + 1;

        if (item.user_price !== null && item.user_price !== undefined) {
          accumulator.priced += 1;
        }

        return accumulator;
      },
      {
        latestSyncedAt,
        priced: 0,
        statuses: {},
        total: 0,
      },
    );
  }, [viyarServiceTree]);
  const materialImportStateLabel = useMemo(() => {
    if (!activeMaterialImportJob?.status) {
      return "";
    }

    const labels = {
      error: t.materialImportStateError,
      queued: t.materialImportStateQueued,
      retry: t.materialImportStateRetry,
      running: t.materialImportStateRunning,
      success: t.materialImportStateSuccess,
    };

    return labels[activeMaterialImportJob.status] || activeMaterialImportJob.status;
  }, [
    activeMaterialImportJob?.status,
    t.materialImportStateError,
    t.materialImportStateQueued,
    t.materialImportStateRetry,
    t.materialImportStateRunning,
    t.materialImportStateSuccess,
  ]);

  function hydrateViyarServicesFromCache(options = {}) {
    const cached = viyarServicesCache;

    if (!cached?.items?.length) {
      return false;
    }

    setViyarServiceSource(cached.source || "viyar");
    setViyarServiceTree(cached.items || []);
    setViyarPriceSyncSummary(cached.priceSyncSummary || null);

    if (options.withStatus) {
      setStatus(t.viyarLoadedFromCache);
    }

    return true;
  }

  useEffect(() => {
    setProjectOverviewOpen(false);
  }, [selectedProjectId]);
  useEffect(() => {
    setCollapsedCuttingGroups({});
  }, [selectedProjectId]);
  useEffect(() => {
    setCuttingSearch("");
  }, [selectedProjectId]);
  useEffect(() => {
    setViyarServiceSearch("");
    setCollapsedViyarFolders({});
  }, [activeView]);
  useEffect(() => {
    if (!user?.id || user.role !== "admin" || viyarServiceTree.length > 0) {
      return;
    }

    hydrateViyarServicesFromCache();
  }, [user?.id, user?.role]);
  useEffect(() => {
    if (!user?.id || user.role !== "admin" || viyarServiceTree.length === 0) {
      return;
    }

    writeViyarServicesCache(user.id, {
      items: viyarServiceTree,
      priceSyncSummary: viyarPriceSyncSummary,
      source: viyarServiceSource,
    });
  }, [user?.id, user?.role, viyarPriceSyncSummary, viyarServiceSource, viyarServiceTree]);
  useEffect(() => {
    setOwnProfileForm({
      username: user?.username || "",
      phone: user?.phone || "",
      city: user?.city || "",
    });
    setMaterialSelectedCity(user?.city || "");
    setEmailChangeForm({
      newEmail: "",
    });
  }, [user?.city, user?.id, user?.phone, user?.username]);
  useEffect(() => {
    if (!activeMaterialImportJobId || !token) {
      setActiveMaterialImportJob(null);
      return undefined;
    }

    let isCancelled = false;

    async function pollMaterialImportJob() {
      const result = await getMaterialImportJob(token, activeMaterialImportJobId);

      if (isCancelled || !result.success || !result.job) {
        return;
      }

      setActiveMaterialImportJob(result.job);

      if (result.job.status === "success") {
        setActiveMaterialImportJobId("");
        setStatus({ message: t.materialImportSuccess, tone: "success" });
        await loadMaterialsCatalog(token);
        const detailResult = await getMaterialDetails(
          token,
          result.job.article,
          result.job.city || "",
        );
        if (detailResult.success && detailResult.item) {
          setSelectedMaterialDetail((current) =>
            current?.article === result.job.article ? detailResult.item : current,
          );
        }
        return;
      }

      if (result.job.status === "error") {
        setActiveMaterialImportJobId("");
        setStatus(result.job.last_error || t.materialImportFailed);
        return;
      }

      if (result.job.status === "running") {
        setStatus(t.materialImportRunning);
      } else {
        setStatus(t.materialImportRetry);
      }
    }

    pollMaterialImportJob();
    const intervalId = window.setInterval(pollMaterialImportJob, 10000);

    return () => {
      isCancelled = true;
      window.clearInterval(intervalId);
    };
  }, [activeMaterialImportJobId, token, t.materialImportFailed, t.materialImportRetry, t.materialImportRunning, t.materialImportSuccess]);
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

  function toggleViyarFolder(externalCode) {
    setCollapsedViyarFolders((current) => ({
      ...current,
      [externalCode]: !current[externalCode],
    }));
  }

  function collapseAllViyarFolders() {
    setCollapsedViyarFolders(
      viyarFolderCodes.reduce((accumulator, code) => {
        accumulator[code] = true;
        return accumulator;
      }, {}),
    );
  }

  function expandAllViyarFolders() {
    setCollapsedViyarFolders({});
  }

  async function openViyarFolderCatalog(folderCode) {
    setCollapsedViyarFolders({});
    setViyarServiceSearch("");
    setActiveView("catalogViyar");
    await loadViyarServices(token);
    requestAnimationFrame(() => {
      const target = document.querySelector(
        `[data-folder-code="${folderCode}"]`,
      );

      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  }
  const canCreateNewProject = canCreateProject(user);
  const canEditMaterialCatalog = canManageMaterialCatalog(user);
  const canEditSystemFittings = canManageSystemFittings(user);
  const canEditOwnFittings = canManageOwnFittings(user);
  const isHomeView = activeView === "home";
  const isCatalogMaterialsView = activeView === "catalogMaterials";
  const isCatalogFittingsView = activeView === "catalogFittings";
  const isCatalogFastenersView = activeView === "catalogFasteners";
  const isCatalogHolesView = activeView === "catalogHoles";
  const isCatalogValuesView = activeView === "catalogValues";
  const isCatalogViyarView = activeView === "catalogViyar";
  const isCatalogManualView = activeView === "catalogManual";
  const isCatalogHubView = activeView === "catalogHub";
  const isCatalogView =
    isCatalogHubView ||
    isCatalogMaterialsView ||
    isCatalogFittingsView ||
    isCatalogFastenersView ||
    isCatalogHolesView ||
    isCatalogValuesView ||
    isCatalogViyarView ||
    isCatalogManualView;
  const fastenerItems = useMemo(
    () => fittingItems.filter((item) => isFastenerFitting(item)),
    [fittingItems],
  );
  const visibleFittingCategories = useMemo(() => fittingCategories, [fittingCategories]);
  const activeFittingCategory = useMemo(() => {
    if (
      selectedFittingCategory &&
      visibleFittingCategories.some((item) => item.code === selectedFittingCategory)
    ) {
      return selectedFittingCategory;
    }

    return "";
  }, [selectedFittingCategory, visibleFittingCategories]);
  const currentFittingCategoryMeta = useMemo(
    () =>
      visibleFittingCategories.find((item) => item.code === activeFittingCategory) ||
      null,
    [activeFittingCategory, visibleFittingCategories],
  );
  const visibleFittingItems = useMemo(
    () =>
      activeFittingCategory
        ? fittingItems.filter((item) => item.fitting_type === activeFittingCategory)
        : [],
    [activeFittingCategory, fittingItems],
  );
  const projectMaterialPickerItems = useMemo(
    () =>
      materialItems
        .map((item) => ({
          ...item,
          pickerValue: buildProjectMaterialOption(item),
          pickerTitle: getMaterialShortName(item) || buildProjectMaterialOption(item),
          pickerSubtitle: [item.dimensions, item.thickness].filter(Boolean).join(" / "),
          pickerSearch: [
            item.name,
            item.article,
            item.display_article,
            item.dimensions,
            item.thickness,
            item.color_name,
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase(),
        }))
        .filter((item) => item.pickerValue),
    [materialItems],
  );
  const projectHandlePickerItems = useMemo(
    () =>
      fittingItems
        .filter((item) =>
          ["handles_hooks", "profiles_gola"].includes(item.fitting_type),
        )
        .map((item) => ({
          ...item,
          pickerValue: buildProjectHandleOption(item),
          pickerTitle: item.name || item.code || item.article,
          pickerSubtitle: [item.article, item.code].filter(Boolean).join(" / "),
          pickerSearch: [
            item.name,
            item.article,
            item.code,
            item.city,
            item.source_url,
          ]
            .filter(Boolean)
            .join(" ")
            .toLowerCase(),
        }))
        .filter((item) => item.pickerValue),
    [fittingItems],
  );
  const activeProjectDraft = projectOptionPicker.target === "edit" ? form : newProjectForm;
  const buildProjectSlidePickerItems = useCallback(
    (depthValue) => {
      const targetLength = getSlideLengthForDepth(depthValue);
      const drawerSlideItems = fittingItems.filter((item) => item.fitting_type === "drawer_slides");

      return drawerSlideItems
        .map((item) => {
          const slideLength = detectProjectSlideLength(
            [item.name, item.article, item.code, item.source_url].filter(Boolean).join(" "),
          );
          const slideFamily = detectProjectSlideFamily(
            [item.name, item.article, item.code, item.source_url].filter(Boolean).join(" "),
          );
          const familyLabel =
            slideFamily === "movento"
              ? "Movento"
              : slideFamily === "telescopic"
                ? language === "uk"
                  ? "Телескопічні"
                  : "Telescopic"
                : slideFamily === "tandem"
                  ? "Tandem"
                  : language === "uk"
                    ? "Напрямні"
                    : "Slides";

          return {
            ...item,
            image_url: item.image_url || "/static/fittings/drawer-slides.png",
            pickerLength: slideLength,
            pickerRecommended: slideLength === targetLength,
            pickerSubtitle: [
              familyLabel,
              slideLength ? `${slideLength} мм` : "",
              item.article || item.code || "",
            ]
              .filter(Boolean)
              .join(" / "),
            pickerTitle: item.name || item.code || item.article || familyLabel,
            pickerSearch: [
              item.name,
              item.article,
              item.code,
              item.city,
              item.source_url,
              familyLabel,
              slideLength,
            ]
              .filter(Boolean)
              .join(" ")
              .toLowerCase(),
            pickerValue: String(item.code || item.article || item.name || ""),
            slideFamily,
          };
        })
        .filter((item) => item.pickerValue)
        .sort((left, right) => {
          if (Number(Boolean(right.pickerRecommended)) !== Number(Boolean(left.pickerRecommended))) {
            return Number(Boolean(right.pickerRecommended)) - Number(Boolean(left.pickerRecommended));
          }

          const leftDistance = Math.abs((left.pickerLength || targetLength) - targetLength);
          const rightDistance = Math.abs((right.pickerLength || targetLength) - targetLength);

          if (leftDistance !== rightDistance) {
            return leftDistance - rightDistance;
          }

          return String(left.pickerTitle || "").localeCompare(
            String(right.pickerTitle || ""),
            language === "uk" ? "uk" : "en",
          );
        });
    },
    [fittingItems, language],
  );
  const createProjectSlideTypePickerItems = useMemo(
    () => buildProjectSlidePickerItems(newProjectForm.depth),
    [buildProjectSlidePickerItems, newProjectForm.depth],
  );
  const editProjectSlideTypePickerItems = useMemo(
    () => buildProjectSlidePickerItems(form.depth),
    [buildProjectSlidePickerItems, form.depth],
  );
  const activeProjectPickerMaterial = useMemo(() => {
    const dependencyConfig = getProjectMaterialDependencyConfig(projectOptionPicker.field);
    const preferredMaterialValue = dependencyConfig.materialField
      ? activeProjectDraft[dependencyConfig.materialField]
      : activeProjectDraft.facadeMaterial || activeProjectDraft.insideMaterial;

    return findProjectMaterialItemByValue(projectMaterialPickerItems, preferredMaterialValue);
  }, [
    activeProjectDraft,
    projectMaterialPickerItems,
    projectOptionPicker.field,
  ]);
  const activeProjectEdgeBandingItems = useMemo(() => {
    if (!activeProjectPickerMaterial) {
      return [];
    }

    return MATERIAL_EDGE_SLOTS.map((slot) =>
      buildProjectEdgeBandingOption(
        activeProjectPickerMaterial,
        getMaterialEdgeItem(activeProjectPickerMaterial, slot.key),
        slot.label,
      ),
    ).filter(Boolean);
  }, [activeProjectPickerMaterial]);
  const projectTypePickerItems = useMemo(
    () =>
      specificationCatalog.project_types.map((value) => ({
        id: `project-type-${value}`,
        pickerValue: value,
        pickerTitle: formatCatalogLabel(value, t),
        pickerSubtitle:
          language === "uk"
            ? "Тип виробу для старту проекту."
            : "Project construction type.",
        pickerSearch: `${value} ${formatCatalogLabel(value, t)}`.toLowerCase(),
      })),
    [language, specificationCatalog.project_types, t],
  );
  const legacyProjectThicknessPickerItems = useMemo(
    () =>
      specificationCatalog.material_thicknesses.map((value) => ({
        id: `thickness-${value}`,
        pickerValue: String(value),
        pickerTitle: `${value}`,
        pickerSubtitle:
          language === "uk" ? "Товщина плитного матеріалу." : "Board material thickness.",
        pickerSearch: `${value} ${t.materialThickness}`.toLowerCase(),
      })),
    [language, specificationCatalog.material_thicknesses, t],
  );
  const legacyProjectSlideTypePickerItems = useMemo(
    () =>
      specificationCatalog.slide_types.map((value) => ({
        id: `slide-${value}`,
        pickerValue: value,
        pickerTitle: formatCatalogLabel(value, t),
        pickerSubtitle:
          language === "uk" ? "Тип направляючих для шухляд." : "Drawer slide type.",
        pickerSearch: `${value} ${formatCatalogLabel(value, t)}`.toLowerCase(),
      })),
    [language, specificationCatalog.slide_types, t],
  );
  const legacyProjectBottomTypePickerItems = useMemo(
    () =>
      specificationCatalog.bottom_types.map((value) => ({
        id: `bottom-${value}`,
        pickerValue: value,
        pickerTitle: formatCatalogLabel(value, t),
        pickerSubtitle:
          language === "uk" ? "Матеріал або тип дна." : "Bottom material or type.",
        pickerSearch: `${value} ${formatCatalogLabel(value, t)}`.toLowerCase(),
      })),
    [language, specificationCatalog.bottom_types, t],
  );
  const projectSlideTypePickerItems = useMemo(
    () =>
      projectOptionPicker.target === "edit"
        ? editProjectSlideTypePickerItems
        : createProjectSlideTypePickerItems,
    [
      createProjectSlideTypePickerItems,
      editProjectSlideTypePickerItems,
      projectOptionPicker.target,
    ],
  );
  const projectBottomTypePickerItems = useMemo(
    () =>
      PROJECT_DRAWER_TYPE_PRESETS.map((item) => ({
        ...item,
        pickerSearch: `${item.search} ${item.pickerTitleUk} ${item.pickerTitleEn}`.toLowerCase(),
        pickerSubtitle: language === "uk" ? item.pickerSubtitleUk : item.pickerSubtitleEn,
        pickerTitle: language === "uk" ? item.pickerTitleUk : item.pickerTitleEn,
      })),
    [language],
  );
  const projectHandlePositionPickerItems = useMemo(
    () =>
      ["", ...specificationCatalog.handle_positions].map((value) => ({
        id: `handle-position-${value || "not-set"}`,
        pickerValue: value,
        pickerTitle: formatCatalogLabel(value, t),
        pickerSubtitle:
          language === "uk" ? "Положення ручки на фасаді." : "Handle position on the facade.",
        pickerSearch: `${value || ""} ${formatCatalogLabel(value, t)}`.toLowerCase(),
      })),
    [language, specificationCatalog.handle_positions, t],
  );
  const getFittingSourceMeta = (item) => {
    const sourceSite = item?.source_site || detectFittingSourceSite(item?.source_url);

    if (sourceSite === "viyar") {
      return {
        code: "viyar",
        label: "Viyar",
        shortLabel: "viyar",
        logo: buildAdminAssetUrl("brand/source-logos/viyar.jpg"),
      };
    }

    if (sourceSite === "blum") {
      return {
        code: "blum",
        label: "BLUM",
        shortLabel: "blum",
        logo: buildAdminAssetUrl("brand/source-logos/blum.jpg"),
      };
    }

    if (sourceSite === "kronas") {
      return {
        code: "kronas",
        label: "Kronas",
        shortLabel: "kronas",
        logo: buildAdminAssetUrl("brand/source-logos/kronas.jpg"),
      };
    }

    return {
      code: "manual",
      label: t.fittingManualSource,
      shortLabel: t.fittingManualSource,
      logo: buildAdminAssetUrl("brand/source-logos/manual.svg"),
    };
  };

  const closeProjectOptionPicker = useCallback(() => {
    setProjectOptionPicker({
      open: false,
      target: "create",
      field: "",
      mode: "materials",
      title: "",
    });
    setProjectOptionPickerSearch("");
  }, []);

  const openProjectOptionPicker = useCallback((config) => {
    setProjectOptionPicker({
      open: true,
      target: config.target,
      field: config.field,
      mode: config.mode,
      title: config.title,
    });
    setProjectOptionPickerSearch("");
  }, []);

  const applyProjectOptionValue = useCallback(
    (value) => {
      if (!projectOptionPicker.field) {
        return;
      }

      const applyMaterialDependencies = (draft, materialValue) => {
        if (projectOptionPicker.mode !== "materials") {
          return draft;
        }

        const dependencyConfig = getProjectMaterialDependencyConfig(projectOptionPicker.field);

        if (!dependencyConfig.materialField) {
          return draft;
        }

        const selectedMaterial = findProjectMaterialItemByValue(
          projectMaterialPickerItems,
          materialValue,
        );

        if (!selectedMaterial) {
          return draft;
        }

        const nextDraft = { ...draft };
        const parsedThickness = parseProjectMaterialThicknessValue(selectedMaterial.thickness);
        if (parsedThickness !== null) {
          nextDraft[dependencyConfig.thicknessField] = String(parsedThickness);
        }

        const materialEdgeOptions = MATERIAL_EDGE_SLOTS.map((slot) =>
          buildProjectEdgeBandingOption(
            selectedMaterial,
            getMaterialEdgeItem(selectedMaterial, slot.key),
            slot.label,
          ),
        ).filter(Boolean);

        if (materialEdgeOptions.length) {
          const hasCurrentEdge = materialEdgeOptions.some(
            (item) =>
              String(item.pickerValue || "").trim() ===
              String(nextDraft[dependencyConfig.edgeField] || "").trim(),
          );

          if (!hasCurrentEdge) {
            nextDraft[dependencyConfig.edgeField] = materialEdgeOptions[0].pickerValue;
          }
        }

        return nextDraft;
      };

      if (projectOptionPicker.target === "edit") {
        setForm((current) =>
          applyMaterialDependencies(
            {
              ...current,
              [projectOptionPicker.field]: value,
            },
            value,
          ),
        );
      } else {
        setNewProjectForm((current) =>
          applyMaterialDependencies(
            {
              ...current,
              [projectOptionPicker.field]: value,
            },
            value,
          ),
        );
      }

      closeProjectOptionPicker();
    },
    [
      closeProjectOptionPicker,
      projectMaterialPickerItems,
      projectOptionPicker.field,
      projectOptionPicker.mode,
      projectOptionPicker.target,
    ],
  );

  const projectOptionPickerConfig = useMemo(() => {
    if (projectOptionPicker.mode === "projectType") {
      return {
        description:
          language === "uk"
            ? "Виберіть тип виробу, з якого почнеться проект."
            : "Choose the product type your project starts from.",
        empty:
          language === "uk" ? "Типи проектів ще не завантажені." : "Project types are not loaded yet.",
        items: projectTypePickerItems,
        placeholder: language === "uk" ? "Пошук типу проекту" : "Search project type",
      };
    }

    if (projectOptionPicker.mode === "edgeBanding") {
      return {
        description:
          language === "uk"
            ? "Виберіть крайку, яка прив’язана до вибраного матеріалу."
            : "Choose edge banding linked to the selected material.",
        empty:
          activeProjectPickerMaterial
            ? language === "uk"
              ? "Для цього матеріалу ще не прив’язано крайку."
              : "No edge banding is attached to this material yet."
            : language === "uk"
              ? "Спочатку виберіть матеріал фасаду або корпусу."
              : "Select facade or inside material first.",
        items: activeProjectEdgeBandingItems,
        placeholder: language === "uk" ? "Пошук крайки" : "Search edge banding",
      };
    }

    if (projectOptionPicker.mode === "materialThickness") {
      return {
        description:
          language === "uk"
            ? "Виберіть товщину матеріалу."
            : "Choose material thickness.",
        empty:
          language === "uk" ? "Немає товщин у довіднику." : "No thickness values are available.",
        items: legacyProjectThicknessPickerItems,
        placeholder: language === "uk" ? "Пошук товщини" : "Search thickness",
      };
    }

    if (projectOptionPicker.mode === "slideType") {
      return {
        description:
          language === "uk"
            ? "Виберіть тип направляючих."
            : "Choose the drawer slide type.",
        empty:
          language === "uk" ? "Типи направляючих ще не заповнені." : "No slide types are available.",
        items: projectSlideTypePickerItems,
        placeholder: language === "uk" ? "Пошук направляючих" : "Search slide type",
      };
    }

    if (projectOptionPicker.mode === "bottomType") {
      return {
        description:
          language === "uk"
            ? "Виберіть тип дна."
            : "Choose bottom type.",
        empty:
          language === "uk" ? "Типи дна ще не заповнені." : "No bottom types are available.",
        items: projectBottomTypePickerItems,
        placeholder: language === "uk" ? "Пошук типу дна" : "Search bottom type",
      };
    }

    if (projectOptionPicker.mode === "handlePosition") {
      return {
        description:
          language === "uk"
            ? "Виберіть положення ручки."
            : "Choose handle position.",
        empty:
          language === "uk" ? "Положення ручок ще не заповнені." : "No handle positions are available.",
        items: projectHandlePositionPickerItems,
        placeholder: language === "uk" ? "Пошук позиції ручки" : "Search handle position",
      };
    }

    if (projectOptionPicker.mode === "handles") {
      return {
        description:
          language === "uk"
            ? "Виберіть ручку або профіль із зображенням, ціною та короткими даними."
            : "Choose a handle or profile with image, price, and short details.",
        empty:
          language === "uk"
            ? "Для цього параметра ще немає доступних позицій."
            : "No items are available for this parameter yet.",
        items: projectHandlePickerItems,
        placeholder: language === "uk" ? "Пошук ручки" : "Search handle",
      };
    }

    return {
      description:
        language === "uk"
          ? "Виберіть матеріал по картці з фото, ціною та основними характеристиками."
          : "Choose a material card with image, price, and main specifications.",
      empty:
        language === "uk"
          ? "Для цього параметра ще немає доступних матеріалів."
          : "No materials are available for this parameter yet.",
      items: projectMaterialPickerItems,
      placeholder: language === "uk" ? "Пошук матеріалу" : "Search material",
    };
  }, [
    language,
    projectBottomTypePickerItems,
    projectHandlePickerItems,
    projectHandlePositionPickerItems,
    projectMaterialPickerItems,
    projectOptionPicker.mode,
    activeProjectEdgeBandingItems,
    activeProjectPickerMaterial,
    projectSlideTypePickerItems,
    legacyProjectThicknessPickerItems,
    projectTypePickerItems,
  ]);

  const filteredProjectOptionItems = useMemo(() => {
    const query = projectOptionPickerSearch.trim().toLowerCase();

    if (!query) {
      return projectOptionPickerConfig.items;
    }

    return projectOptionPickerConfig.items.filter((item) =>
      String(item.pickerSearch || "").includes(query),
    );
  }, [projectOptionPickerConfig.items, projectOptionPickerSearch]);

  const getProjectOptionTitleByValue = useCallback((items, value, fallback = "") => {
    const normalizedValue = String(value || "").trim();

    if (!normalizedValue) {
      return fallback || t.notSet;
    }

    return (
      items.find((item) => String(item.pickerValue || "").trim() === normalizedValue)?.pickerTitle ||
      fallback ||
      normalizedValue
    );
  }, [t.notSet]);

  const formatProjectSlideValue = useCallback(
    (value, target) =>
      getProjectOptionTitleByValue(
        target === "edit" ? editProjectSlideTypePickerItems : createProjectSlideTypePickerItems,
        value,
        formatCatalogLabel(detectProjectSlideFamily(value) || value, t),
      ),
    [
      createProjectSlideTypePickerItems,
      editProjectSlideTypePickerItems,
      getProjectOptionTitleByValue,
      t,
    ],
  );

  const formatProjectBottomValue = useCallback(
    (value) =>
      getProjectOptionTitleByValue(
        projectBottomTypePickerItems,
        value,
        formatCatalogLabel(value, t),
      ),
    [getProjectOptionTitleByValue, projectBottomTypePickerItems, t],
  );

  useEffect(() => {
    if (!createProjectSlideTypePickerItems.length) {
      return;
    }

    setNewProjectForm((current) => {
      const currentValue = String(current.slideType || "").trim();
      if (
        currentValue &&
        createProjectSlideTypePickerItems.some(
          (item) => String(item.pickerValue || "").trim() === currentValue,
        )
      ) {
        return current;
      }

      return {
        ...current,
        slideType: createProjectSlideTypePickerItems[0].pickerValue,
      };
    });
  }, [createProjectSlideTypePickerItems]);

  useEffect(() => {
    if (!editProjectSlideTypePickerItems.length) {
      return;
    }

    setForm((current) => {
      const currentValue = String(current.slideType || "").trim();
      if (
        currentValue &&
        editProjectSlideTypePickerItems.some(
          (item) => String(item.pickerValue || "").trim() === currentValue,
        )
      ) {
        return current;
      }

      return {
        ...current,
        slideType: editProjectSlideTypePickerItems[0].pickerValue,
      };
    });
  }, [editProjectSlideTypePickerItems]);

  const renderProjectOptionField = ({ disabled = false, field, mode, target, title, value }) => (
    <label>
      {title}
      <button
        className={`project-option-trigger${value ? "" : " is-placeholder"}`}
        disabled={disabled}
        onClick={() =>
          openProjectOptionPicker({
            field,
            mode,
            target,
            title,
          })
        }
        type="button"
      >
        <span className="project-option-trigger-text">{value || title}</span>
        <span className="project-option-trigger-action">
          <Search size={16} />
          {language === "uk" ? "Вибрати" : "Choose"}
        </span>
      </button>
    </label>
  );

  useEffect(() => {
    if (isCatalogView) {
      setIsCatalogMenuOpen(true);
    }
  }, [isCatalogView]);

  useEffect(() => {
    setOpenFittingMenuId("");
    const defaultCategory =
      visibleFittingCategories.find((item) => item.code === selectedFittingCategory) ||
      visibleFittingCategories[0] ||
      null;
    setNewFittingForm((current) => ({
      ...current,
      city: materialSelectedCity || user?.city || "",
      fitting_group: defaultCategory?.group || current.fitting_group,
      fitting_type: defaultCategory?.code || current.fitting_type,
      is_system: canEditSystemFittings ? current.is_system : false,
    }));
  }, [
    canEditSystemFittings,
    materialSelectedCity,
    selectedFittingCategory,
    user?.city,
    visibleFittingCategories,
  ]);

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
    if (isHomeView) {
      return t.homeDescription;
    }

    if (activeView === "projects") {
      return pageLabel;
    }

    if (activeView === "createProject") {
      return t.specification;
    }

    if (activeView === "projectDetails") {
      return selectedProject?.project_name || t.newProjectDefault;
    }

    if (activeView === "users") {
      return usersPageLabel;
    }

    if (isCatalogHubView) {
      return t.catalogHubTitle;
    }

    if (isCatalogMaterialsView) {
      return `${materialItems.length} ${t.of} ${materialItems.length}`;
    }

    if (isCatalogFittingsView) {
      return `${fittingItems.length} ${t.of} ${fittingItems.length}`;
    }

    if (isCatalogFastenersView) {
      return `${fastenerItems.length} ${t.of} ${fastenerItems.length}`;
    }

    if (isCatalogValuesView) {
      return `${catalogItems.length} ${t.of} ${catalogItems.length}`;
    }

    if (isCatalogViyarView) {
      return `${viyarServiceCounts.services} ${t.of} ${viyarServiceCounts.services}`;
    }

    if (isCatalogManualView) {
      return `${manualServiceItems.length} ${t.of} ${manualServiceItems.length}`;
    }

    if (activeView === "settings") {
      return t.myData;
    }

    return auditPageLabel;
  }, [
    activeView,
    auditPageLabel,
    catalogItems.length,
    fastenerItems.length,
    fittingItems.length,
    isHomeView,
    isCatalogHubView,
    isCatalogMaterialsView,
    isCatalogFittingsView,
    isCatalogFastenersView,
    isCatalogManualView,
    isCatalogValuesView,
    isCatalogViyarView,
    materialItems.length,
    manualServiceItems.length,
    pageLabel,
    selectedProject,
    t,
    usersPageLabel,
    viyarServiceCounts.services,
  ]);

  function changeLanguage(nextLanguage) {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
    setLanguage(nextLanguage);
  }

  async function loadUser(activeToken) {
    const result = await getCurrentUser(activeToken);

    if (tokenRef.current !== activeToken) {
      return null;
    }

    if (!result.success) {
      if (result.status && result.status !== 401) {
        setStatus(result.error || t.loginFailed);
        return null;
      }
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      setToken("");
      setUser(null);
      return null;
    }

    setUser(result.user);
    return result.user;
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

  async function loadUsers(activeToken = token, nextOffset = usersOffset, viewer = user) {
    if (!activeToken || viewer?.role !== "admin") {
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

  async function loadUserChangeRequests(activeToken = token, viewer = user) {
    if (!activeToken || viewer?.role !== "admin") {
      return;
    }

    setLoading(true);
    const result = await listUserChangeRequests(activeToken, "pending");
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.noPendingRequests);
      return;
    }

    setUserChangeRequests(result.requests || []);
  }

  async function openUserDetails(targetUser) {
    setLoading(true);
    const result = await getUserDetails(token, targetUser.id);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadUsers);
      return;
    }

    setSelectedUserDetails(result.details);
  }

  async function loadAuditLogs(activeToken = token, nextOffset = auditOffset, viewer = user) {
    if (!activeToken || viewer?.role !== "admin") {
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

  async function loadCatalogItems(activeToken = token, viewer = user) {
    if (!activeToken || viewer?.role !== "admin") {
      return;
    }

    setLoading(true);
    const result = await listCatalogItems(activeToken);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    setCatalogItems(result.items);
  }

  async function loadViyarServices(activeToken = token, viewer = user) {
    if (!activeToken || viewer?.role !== "admin") {
      return;
    }

    const hasCachedTree = hydrateViyarServicesFromCache();

    setViyarTreeLoading(true);
    if (!hasCachedTree) {
      setLoading(true);
    }
    const result = await getViyarServicesTree(activeToken);
    setViyarTreeLoading(false);
    if (!hasCachedTree) {
      setLoading(false);
    }

    if (!result.success) {
      if (hydrateViyarServicesFromCache({ withStatus: true })) {
        return;
      }

      setStatus(result.error || t.unableToLoadViyarServices);
      return;
    }

    if (!result.items?.length && hydrateViyarServicesFromCache({ withStatus: true })) {
      return;
    }

    setViyarServiceSource(result.source || "viyar");
    setViyarServiceTree(result.items || []);
  }

  async function loadMaterialsCatalog(
    activeToken = token,
    options = {},
  ) {
    if (!activeToken) {
      return;
    }

    setLoading(true);
    const result = await getMaterialsCatalog(activeToken, {
      category: options.category ?? materialCategoryFilter ?? "dsp",
      city:
        options.city ??
        materialSelectedCity ??
        ownProfileForm.city ??
        user?.city ??
        "",
      search: options.search ?? materialSearch,
    });
    setLoading(false);

    if (!result.success) {
      const timeoutError = String(result.error || "").includes("Request timed out after");
      if (timeoutError && materialItems.length) {
        return;
      }
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    setMaterialItems(result.items || []);
    setMaterialCategories(result.categories || []);
    setMaterialCityOptions(result.city_options?.length ? result.city_options : DEFAULT_CITY_OPTIONS);
    setMaterialSelectedCity(result.selected_city || "");
    setStatus((current) =>
      String(current || "").includes("Request timed out after") ? "" : current,
    );
  }

  async function openMaterialDetails(item) {
    if (!token || !item?.article) {
      return;
    }

    setMaterialDetailLoading(true);
    setSelectedMaterialDetail((current) => current || item);

    const result = await getMaterialDetails(
      token,
      item.article,
      materialSelectedCity || ownProfileForm.city || user?.city || "",
    );

    setMaterialDetailLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      setSelectedMaterialDetail(item);
      return;
    }

    setSelectedMaterialDetail(result.item || item);
    if (result.job?.id) {
      setActiveMaterialImportJobId(result.job.id);
      setActiveMaterialImportJob(result.job);
    }
    setMaterialEdgeForms({});
    setMaterialEdgeCreateForm({ open: false, edge_key: getDefaultMaterialEdgeKey(result.item || item), source_url: "" });
  }

  function closeMaterialDetails() {
    setSelectedMaterialDetail(null);
    setMaterialDetailLoading(false);
    setMaterialEdgeForms({});
    setMaterialEdgeCreateForm({ open: false, edge_key: "edge_08", source_url: "" });
  }

  async function loadFittingsCatalog(
    activeToken = token,
    options = {},
  ) {
    if (!activeToken) {
      return;
    }

    setLoading(true);
    const result = await getFittingsCatalog(activeToken, {
      city:
        options.city ??
        materialSelectedCity ??
        ownProfileForm.city ??
        user?.city ??
        "",
      search: options.search ?? fittingSearch,
    });
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    setFittingItems(result.items || []);
    setFittingCategories(result.categories || []);
    if (result.city_options?.length) {
      setMaterialCityOptions(result.city_options);
    }
    if (result.selected_city) {
      setMaterialSelectedCity(result.selected_city);
    }
  }

  async function loadHoleTemplates(activeToken = token, fittingId = holeSelectedFittingId) {
    if (!activeToken || !fittingId) {
      setHoleTemplateItems([]);
      setHoleSelectedTemplateId("");
      setHoleSelectedTemplate(null);
      setHolePoints([]);
      return;
    }

    setLoading(true);
    const result = await listFittingHoleTemplatesByFitting(activeToken, fittingId);
    setLoading(false);
    if (import.meta.env.DEV) {
      console.debug("fitting-holes templates", {
        fittingId,
        success: Boolean(result?.success),
        count: Array.isArray(result?.templates) ? result.templates.length : 0,
      });
    }

    if (!result.success) {
      setHoleTemplateItems([]);
      setHoleSelectedTemplateId("");
      setHoleSelectedTemplate(null);
      setHolePoints([]);
      setStatus({ message: result.error || "Unable to load fitting hole templates", tone: "error" });
      return;
    }

    setHoleTemplateItems(Array.isArray(result.templates) ? result.templates : []);
    setHoleSelectedTemplate(null);
    setHolePoints([]);
  }

  function openHoleTemplateCreateForm() {
    if (!holeSelectedFittingId) {
      setHoleTemplateCreateError("Оберіть фурнітуру перед створенням шаблону");
      return;
    }

    setHoleTemplateCreateForm({
      ...DEFAULT_HOLE_TEMPLATE_FORM,
      fitting_id: holeSelectedFittingId,
    });
    setHoleTemplateCreateError("");
    setHoleTemplateCreateOpen(true);
  }

  function closeHoleTemplateCreateForm() {
    setHoleTemplateCreateOpen(false);
    setHoleTemplateCreateError("");
    setHoleTemplateCreateForm(DEFAULT_HOLE_TEMPLATE_FORM);
  }

  function openHoleTemplateEditForm(template) {
    if (!template?.id) {
      setHoleTemplateEditError(t.holeTemplateEditFailed);
      return;
    }

    setHoleTemplateEditTemplateId(String(template.id));
    setHoleTemplateEditForm(buildHoleTemplateFormFromTemplate(template));
    setHoleTemplateEditError("");
    setHoleTemplateEditOpen(true);
  }

  function closeHoleTemplateEditForm() {
    setHoleTemplateEditOpen(false);
    setHoleTemplateEditError("");
    setHoleTemplateEditForm(DEFAULT_HOLE_TEMPLATE_FORM);
    setHoleTemplateEditTemplateId("");
    setHoleTemplateEditSaving(false);
  }

  function renderHoleTemplateMountingSchemeIcon(schemeKey, isActive) {
    const barStyles = {
      bottom: { bottom: 6, left: 10, right: 10, height: 6 },
      left_edge: { bottom: 10, left: 6, top: 10, width: 6 },
      right_edge: { bottom: 10, right: 6, top: 10, width: 6 },
      top: { top: 6, left: 10, right: 10, height: 6 },
    };

    const accentBarStyle = barStyles[schemeKey] || barStyles.left_edge;
    const frameColor = isActive ? "#2563eb" : "#94a3b8";
    const fillColor = isActive ? "rgba(37, 99, 235, 0.08)" : "rgba(148, 163, 184, 0.08)";
    const barColor = isActive ? "#2563eb" : "#cbd5e1";

    return (
      <span
        style={{
          alignItems: "center",
          background: fillColor,
          border: `1px solid ${frameColor}`,
          borderRadius: 10,
          boxSizing: "border-box",
          display: "inline-flex",
          height: 44,
          justifyContent: "center",
          position: "relative",
          width: 44,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            inset: 7,
            border: `1px solid ${frameColor}`,
            borderRadius: 6,
            position: "absolute",
          }}
        />
        <span
          style={{
            background: barColor,
            borderRadius: 999,
            position: "absolute",
            ...accentBarStyle,
          }}
        />
      </span>
    );
  }

  function normalizeHoleTemplateSide(side) {
    const allowedSides = new Set(["left", "right", "top", "bottom"]);

    return allowedSides.has(side) ? side : "left";
  }

  function updateHoleTemplateSide(setForm, side) {
    const normalizedSide = normalizeHoleTemplateSide(side);

    setForm((current) => ({
      ...current,
      side: normalizedSide,
    }));
  }

  function renderHoleTemplateFittingInfo(fitting) {
    if (!fitting) {
      return null;
    }

    const fittingName = String(fitting.name || fitting.code || fitting.article || "").trim();
    const fittingArticle = String(fitting.article || "").trim();
    const fittingDescription = String(fitting.description || "").trim();
    const fittingImageUrl = String(fitting.image_url || fitting.image || "").trim();

    return (
      <section className="hole-template-fitting-info">
        <div className="hole-template-fitting-info-head">
          <strong>{t.holeTemplateFittingInfoTitle}</strong>
          <div className="hole-template-fitting-info-name">{fittingName || t.holeTemplateFitting}</div>
        </div>

        <div className={`hole-template-fitting-info-body${fittingImageUrl ? "" : " no-image"}`}>
          {fittingImageUrl ? (
            <img
              alt={t.holeTemplateFittingInfoImageAlt}
              className="hole-template-fitting-info-image"
              src={fittingImageUrl}
            />
          ) : (
            <div className="hole-template-fitting-info-placeholder">{t.holeTemplateFittingInfoNoImage}</div>
          )}

          <div className="hole-template-fitting-info-meta">
            {fittingArticle ? (
              <div className="hole-template-fitting-info-line">
                {t.holeTemplateFittingInfoArticle}: {fittingArticle}
              </div>
            ) : null}
            {fittingDescription ? (
              <div className="hole-template-fitting-info-line hole-template-fitting-info-description">
                {t.holeTemplateFittingInfoDescription}: {fittingDescription}
              </div>
            ) : null}
          </div>
        </div>
      </section>
    );
  }

  function normalizeHoleWorkspaceMountingVariantKey(key) {
    const allowedVariants = new Set([
      "surface_mount",
      "angled_two_planes",
      "face_to_edge",
      "edge_to_edge",
      "drawer_slides",
    ]);

    return allowedVariants.has(key) ? key : "surface_mount";
  }

  function renderHoleWorkspaceFittingInfo(fitting) {
    if (!fitting) {
      return (
        <div className="empty-state compact-empty-state">
          <span>{t.holeTemplateSelectFitting}</span>
        </div>
      );
    }

    const fittingName = String(fitting.name || fitting.code || fitting.article || "").trim();
    const fittingArticle = String(fitting.article || "").trim();
    const fittingDescription = String(fitting.description || "").trim();
    const fittingImageUrl = String(fitting.image_url || "").trim();

    return (
      <section className="hole-template-fitting-info">
        <div className="hole-template-fitting-info-head">
          <strong>{t.holeWorkspaceFittingInfoTitle}</strong>
          <div className="hole-template-fitting-info-name">{fittingName || t.holeTemplateFitting}</div>
        </div>

        <div className={`hole-template-fitting-info-body${fittingImageUrl ? "" : " no-image"}`}>
          {fittingImageUrl ? (
            <img
              alt={t.holeWorkspaceFittingInfoImageAlt || t.holeTemplateFittingInfoImageAlt}
              className="hole-template-fitting-info-image"
              src={fittingImageUrl}
            />
          ) : (
            <div className="hole-template-fitting-info-placeholder">{t.holeWorkspaceNoImage}</div>
          )}

          <div className="hole-template-fitting-info-meta">
            {fittingArticle ? (
              <div className="hole-template-fitting-info-line">
                {t.holeWorkspaceFittingInfoArticle}: {fittingArticle}
              </div>
            ) : null}
            {fittingDescription ? (
              <div className="hole-template-fitting-info-line hole-template-fitting-info-description">
                {t.holeWorkspaceFittingInfoDescription}: {fittingDescription}
              </div>
            ) : null}
          </div>
        </div>
      </section>
    );
  }

  function renderHoleWorkspaceConnectionVariantCards() {
    const normalizedSelectedVariantKey = normalizeHoleWorkspaceMountingVariantKey(
      selectedHoleMountingVariantKey,
    );

    return (
      <section className="holes-panel holes-connection-variant-panel">
        <div className="holes-panel-header">
          <h4>{t.holeWorkspaceConnectionVariantTitle}</h4>
          <span className="service-tree-badge subtle">{t.holeWorkspaceSelected}</span>
        </div>
        <div className="holes-connection-variant-grid">
          {holeMountingVariantOptions.map((variant) => {
            const isActive = normalizedSelectedVariantKey === variant.key;

            return (
              <button
                aria-pressed={isActive}
                className={`holes-connection-variant-card${isActive ? " active" : ""}`}
                key={variant.key}
                onClick={() => setSelectedHoleMountingVariantKey(variant.key)}
                type="button"
              >
                <span className="holes-connection-variant-card-mark">
                  <img
                    alt=""
                    className="holes-connection-variant-card-icon-image"
                    src={variant.icon}
                  />
                </span>
                <span className="holes-connection-variant-card-copy">
                  <strong>{variant.label}</strong>
                  <span>{variant.description}</span>
                </span>
              </button>
            );
          })}
        </div>
      </section>
    );
  }

  function renderHolesSceneSchematicPreview(sceneModel) {
    const scene = sceneModel || holesPreviewSceneModel || {};
    const variantKey = normalizeHoleWorkspaceMountingVariantKey(
      scene?.mountingVariant?.key || selectedHoleMountingVariantKey,
    );
    const holes = Array.isArray(scene?.holes) ? scene.holes : [];
    const materialPlaneA = scene?.materialPlanes?.planeA?.label || "Площина A";
    const materialPlaneB = scene?.materialPlanes?.planeB?.label || "Площина B";
    const connectionDirection = scene?.materialPlanes?.connectionDirection || "—";
    const xValues = holes.map((hole) => Number(hole?.x)).filter(Number.isFinite);
    const yValues = holes.map((hole) => Number(hole?.y)).filter(Number.isFinite);
    const hasCoordinates = xValues.length > 0 || yValues.length > 0;
    const minX = xValues.length ? Math.min(...xValues) : 0;
    const maxX = xValues.length ? Math.max(...xValues) : 1;
    const minY = yValues.length ? Math.min(...yValues) : 0;
    const maxY = yValues.length ? Math.max(...yValues) : 1;
    const spanX = Math.max(1, maxX - minX);
    const spanY = Math.max(1, maxY - minY);
    const zoneByVariant = {
      angled_two_planes: { height: 126, width: 160, x: 266, y: 118 },
      drawer_slides: { height: 118, width: 120, x: 320, y: 110 },
      edge_to_edge: { height: 88, width: 138, x: 304, y: 136 },
      face_to_edge: { height: 110, width: 122, x: 272, y: 114 },
      surface_mount: { height: 108, width: 132, x: 242, y: 108 },
    };
    const holeZone = zoneByVariant[variantKey] || zoneByVariant.surface_mount;

    function getHolePosition(hole, index) {
      const rawX = Number(hole?.x);
      const rawY = Number(hole?.y);
      const hasX = Number.isFinite(rawX);
      const hasY = Number.isFinite(rawY);

      if (hasCoordinates && (hasX || hasY)) {
        const mappedX = hasX
          ? holeZone.x + ((rawX - minX) / spanX) * holeZone.width
          : holeZone.x + holeZone.width / 2;
        const mappedY = hasY
          ? holeZone.y + ((rawY - minY) / spanY) * holeZone.height
          : holeZone.y + holeZone.height / 2;

        return {
          x: Math.max(holeZone.x + 10, Math.min(holeZone.x + holeZone.width - 10, mappedX)),
          y: Math.max(holeZone.y + 10, Math.min(holeZone.y + holeZone.height - 10, mappedY)),
        };
      }

      const fallbackColumns = 4;
      const fallbackRows = Math.max(1, Math.ceil(Math.max(1, holes.length) / fallbackColumns));
      const column = index % fallbackColumns;
      const row = Math.floor(index / fallbackColumns);
      return {
        x: holeZone.x + ((column + 1) / (fallbackColumns + 1)) * holeZone.width,
        y: holeZone.y + ((row + 1) / (fallbackRows + 1)) * holeZone.height,
      };
    }

    function renderHolePanelBodies() {
      switch (variantKey) {
        case "angled_two_planes":
          return (
            <>
              <rect className="holes-preview-schematic-panel" height="206" rx="10" width="88" x="92" y="44" />
              <path
                className="holes-preview-schematic-panel is-secondary"
                d="M 236 138 L 390 70 L 434 166 L 286 216 Z"
              />
            </>
          );
        case "face_to_edge":
          return (
            <>
              <rect className="holes-preview-schematic-panel" height="208" rx="10" width="88" x="94" y="46" />
              <rect className="holes-preview-schematic-panel is-secondary" height="70" rx="10" width="244" x="246" y="122" />
            </>
          );
        case "edge_to_edge":
          return (
            <>
              <rect className="holes-preview-schematic-panel" height="64" rx="10" width="214" x="138" y="128" />
              <rect className="holes-preview-schematic-panel is-secondary" height="64" rx="10" width="214" x="356" y="128" />
            </>
          );
        case "drawer_slides":
          return (
            <>
              <rect className="holes-preview-schematic-panel" height="204" rx="10" width="76" x="102" y="56" />
              <rect className="holes-preview-schematic-panel is-secondary" height="204" rx="10" width="76" x="578" y="56" />
              <rect className="holes-preview-schematic-bridge" height="56" rx="8" width="212" x="242" y="122" />
            </>
          );
        case "surface_mount":
        default:
          return (
            <>
              <rect className="holes-preview-schematic-panel" height="220" rx="10" width="92" x="98" y="40" />
              <rect className="holes-preview-schematic-bridge" height="86" rx="8" width="132" x="274" y="108" />
              <path className="holes-preview-schematic-panel is-secondary" d="M 392 106 L 430 106 L 454 128 L 454 176 L 430 198 L 392 198 Z" />
            </>
          );
      }
    }

    const points = holes.map((hole, index) => {
      const position = getHolePosition(hole, index);
      const diameter = Number(hole?.diameter);
      const radius = Math.max(4, Math.min(10, Number.isFinite(diameter) ? Math.round(diameter / 2) : 5));

      return {
        cx: position.x,
        cy: position.y,
        hole,
        radius,
      };
    });

    return (
      <section className={`holes-preview-schematic variant-${variantKey}`}>
        <div className="holes-preview-schematic-head">
          <strong>Схема сцени</strong>
          <span>
            {materialPlaneA} → {materialPlaneB} · {connectionDirection}
          </span>
        </div>

        <svg
          aria-label="Scene schematic preview"
          className="holes-preview-schematic-svg"
          role="img"
          viewBox="0 0 760 320"
        >
          <defs>
            <pattern id="holes-preview-schematic-hatch" height="10" patternUnits="userSpaceOnUse" width="10">
              <path d="M 0 10 L 10 0" fill="none" stroke="#d8e1e8" strokeWidth="1" />
            </pattern>
            <linearGradient id="holes-preview-schematic-panel-fill" x1="0%" x2="100%" y1="0%" y2="100%">
              <stop offset="0%" stopColor="#f8fafb" />
              <stop offset="100%" stopColor="#eef2f6" />
            </linearGradient>
          </defs>

          <rect className="holes-preview-schematic-backdrop" height="320" width="760" x="0" y="0" />
          <g className="holes-preview-schematic-grid">
            <path d="M 40 80 H 720" />
            <path d="M 40 160 H 720" />
            <path d="M 40 240 H 720" />
            <path d="M 120 32 V 288" />
            <path d="M 380 32 V 288" />
            <path d="M 640 32 V 288" />
          </g>

          {renderHolePanelBodies()}

          <g className="holes-preview-schematic-connectors">
            {variantKey === "drawer_slides" ? (
              <>
                <path d="M 178 158 H 242" />
                <path d="M 454 150 H 578" />
                <path d="M 348 150 H 388" />
              </>
            ) : variantKey === "edge_to_edge" ? (
              <>
                <path d="M 246 160 H 356" />
                <path d="M 352 160 H 462" />
              </>
            ) : variantKey === "angled_two_planes" ? (
              <>
                <path d="M 182 144 L 246 146" />
                <path d="M 252 140 L 320 120" />
                <path d="M 318 120 L 384 92" />
              </>
            ) : variantKey === "face_to_edge" ? (
              <>
                <path d="M 182 154 H 246" />
                <path d="M 248 154 H 300" />
              </>
            ) : (
              <>
                <path d="M 190 150 H 274" />
                <path d="M 340 150 H 392" />
              </>
            )}
          </g>

          <g className="holes-preview-schematic-plane-labels">
            <text x="132" y="68">{materialPlaneA}</text>
            <text x="528" y="68">{materialPlaneB}</text>
            <text x="42" y="300">{connectionDirection}</text>
          </g>

          {points.length ? (
            <g className="holes-preview-schematic-holes">
              {points.map((point) => (
                <g
                  className={`holes-preview-schematic-hole${point.hole.isHovered ? " is-hovered" : ""}`}
                  key={point.hole.id}
                >
                  <circle cx={point.cx} cy={point.cy} r={Math.max(point.radius + 3, 8)} />
                  <circle cx={point.cx} cy={point.cy} r={point.radius} />
                  <text x={point.cx + 10} y={point.cy - 10}>
                    #{point.hole.id}
                  </text>
                </g>
              ))}
            </g>
          ) : (
            <text className="holes-preview-schematic-empty" x="380" y="160">
              Отвори сцени ще не додані
            </text>
          )}
        </svg>
      </section>
    );
  }

  function renderHoleTemplateMountingSchemePicker(selectedSide, onSelectSide) {
    const schemeCards = [
      {
        side: "left",
        label: t.holeTemplateMountingSchemeLeftEdge,
      },
      {
        side: "right",
        label: t.holeTemplateMountingSchemeRightEdge,
      },
      {
        side: "top",
        label: t.holeTemplateMountingSchemeTop,
      },
      {
        side: "bottom",
        label: t.holeTemplateMountingSchemeBottom,
      },
    ];

    return (
      <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
        <div style={{ display: "grid", gap: 4 }}>
          <div>{t.holeTemplateMountingSchemeTitle}</div>
          <p>{t.holeTemplateMountingSchemePlaceholder}</p>
        </div>
        <div
          style={{
            display: "grid",
            gap: 8,
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          }}
        >
          {schemeCards.map((scheme) => {
            const isActive = normalizeHoleTemplateSide(selectedSide) === scheme.side;

            return (
              <button
                aria-pressed={isActive}
                key={scheme.side}
                onClick={() => onSelectSide(scheme.side)}
                type="button"
                style={{
                  alignItems: "center",
                  background: isActive ? "rgba(37, 99, 235, 0.08)" : "transparent",
                  border: `1px solid ${isActive ? "#2563eb" : "#d1d5db"}`,
                  borderRadius: 12,
                  color: "inherit",
                  cursor: "pointer",
                  display: "flex",
                  gap: 10,
                  minHeight: 72,
                  padding: "10px 12px",
                  textAlign: "left",
                }}
              >
                {renderHoleTemplateMountingSchemeIcon(scheme.side, isActive)}
                <span style={{ display: "grid", gap: 4, minWidth: 0 }}>
                  <span style={{ fontWeight: 600 }}>{scheme.label}</span>
                  <span style={{ fontSize: 12, opacity: 0.8 }}>
                    {isActive ? t.holeTemplateMountingSchemeSelected : "\u00A0"}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  async function handleHoleTemplateCreate(event) {
    event.preventDefault();

    if (!holeSelectedFittingId) {
      setHoleTemplateCreateError("Оберіть фурнітуру перед створенням шаблону");
      return;
    }

    const trimmedName = holeTemplateCreateForm.name.trim();

    if (!trimmedName) {
      setHoleTemplateCreateError("Назва шаблону є обов'язковою");
      return;
    }

    const payload = {
      fitting_id: Number(holeSelectedFittingId),
      name: trimmedName,
      template_type: holeTemplateCreateForm.template_type || "manual",
      side: holeTemplateCreateForm.side || "left",
      coordinate_system: holeTemplateCreateForm.coordinate_system || "2d",
      is_default: Boolean(holeTemplateCreateForm.is_default),
      is_active: Boolean(holeTemplateCreateForm.is_active),
      notes: holeTemplateCreateForm.notes.trim() || null,
    };

    setLoading(true);
    const result = await createFittingHoleTemplate(token, payload);
    setLoading(false);

    if (!result.success) {
      const errorMessage = result.error || "Не вдалося створити шаблон отворів";
      setHoleTemplateCreateError(errorMessage);
      setStatus({ message: errorMessage, tone: "error" });
      return;
    }

    const createdTemplate = result.template || result.item || result.data || null;
    const createdTemplateId =
      createdTemplate?.id || result.template_id || result.id || "";

    closeHoleTemplateCreateForm();
    await loadHoleTemplates(token, holeSelectedFittingId);

    if (createdTemplateId) {
      setHoleSelectedTemplateId(String(createdTemplateId));
      await loadHoleTemplateDetails(token, createdTemplateId);
    }

    setStatus({ message: "Шаблон отворів створено", tone: "success" });
  }

  async function handleHoleTemplateEdit(event) {
    event.preventDefault();

    if (!holeSelectedFittingId || !holeTemplateEditTemplateId) {
      setHoleTemplateEditError(t.holeTemplateEditFailed);
      return;
    }

    const trimmedName = holeTemplateEditForm.name.trim();

    if (!trimmedName) {
      setHoleTemplateEditError(t.holeTemplateNameRequired);
      return;
    }

    const payload = {
      name: trimmedName,
      template_type: holeTemplateEditForm.template_type || "manual",
      side: holeTemplateEditForm.side || "left",
      coordinate_system: holeTemplateEditForm.coordinate_system || "2d",
      is_default: Boolean(holeTemplateEditForm.is_default),
      is_active: Boolean(holeTemplateEditForm.is_active),
      notes: holeTemplateEditForm.notes.trim() || null,
    };

    setHoleTemplateEditSaving(true);
    try {
      const result = await updateFittingHoleTemplate(token, holeTemplateEditTemplateId, payload);

      if (!result.success) {
        const errorMessage = result.error || t.holeTemplateUpdateFailed;
        setHoleTemplateEditError(errorMessage);
        setStatus({ message: errorMessage, tone: "error" });
        return;
      }

      const updatedTemplate = result.template || result.item || result.data || null;
      const updatedTemplateId = String(updatedTemplate?.id || holeTemplateEditTemplateId);

      const templatesResult = await listFittingHoleTemplatesByFitting(token, holeSelectedFittingId);

      if (!templatesResult.success) {
        const errorMessage = templatesResult.error || t.holeTemplateUpdateFailed;
        setHoleTemplateEditError(errorMessage);
        setStatus({ message: errorMessage, tone: "error" });
        return;
      }

      setHoleTemplateItems(Array.isArray(templatesResult.templates) ? templatesResult.templates : []);
      setHoleSelectedTemplateId(updatedTemplateId);
      const detailsLoaded = await loadHoleTemplateDetails(token, updatedTemplateId);

      if (!detailsLoaded) {
        setHoleTemplateEditError(t.holeTemplateUpdateFailed);
        return;
      }

      closeHoleTemplateEditForm();
      setStatus({ message: t.holeTemplateUpdateSuccess, tone: "success" });
    } finally {
      setHoleTemplateEditSaving(false);
    }
  }

  function openHolePointCreateForm() {
    if (!holeSelectedTemplateId) {
      setHolePointCreateError(t.holePointTemplateRequired);
      return;
    }

    setHolePointCreateForm({
      ...DEFAULT_HOLE_POINT_FORM,
      template_id: holeSelectedTemplateId,
    });
    setHolePointCreateError("");
    setHolePointCreateOpen(true);
  }

  function closeHolePointCreateForm() {
    setHolePointCreateOpen(false);
    setHolePointCreateError("");
    setHolePointCreateForm(DEFAULT_HOLE_POINT_FORM);
  }

  function openHolePointEditForm(point) {
    if (!point?.id) {
      setHolePointEditError(t.holePointEditFailed);
      return;
    }

    setHolePointEditPointId(String(point.id));
    setHolePointEditForm(buildHolePointFormFromPoint(point));
    setHolePointEditError("");
    setHolePointEditOpen(true);
  }

  function closeHolePointEditForm() {
    setHolePointEditOpen(false);
    setHolePointEditError("");
    setHolePointEditForm(DEFAULT_HOLE_POINT_FORM);
    setHolePointEditPointId("");
  }

  function parseMaybeNumber(value, fieldName) {
    const text = String(value ?? "").trim();

    if (!text) {
      return undefined;
    }

    const numericValue = Number(text.replace(",", "."));

    if (!Number.isFinite(numericValue)) {
      throw new Error(fieldName);
    }

    return numericValue;
  }

  function buildHolePointPayload(form) {
    const diameterText = String(form.diameter_mm || "").trim();

    if (!diameterText) {
      throw new Error(t.holePointDiameterRequired);
    }

    const payload = {
      label: String(form.label || "").trim() || null,
      x_mm: parseMaybeNumber(form.x_mm, t.holePointX),
      y_mm: parseMaybeNumber(form.y_mm, t.holePointY),
      z_mm: parseMaybeNumber(form.z_mm, t.holePointZ),
      diameter_mm: parseMaybeNumber(diameterText, t.holePointDiameter),
      depth_mm: parseMaybeNumber(form.depth_mm, t.holePointDepth),
      side: String(form.side || "").trim() || "front",
      operation: String(form.operation || "").trim() || "drill",
      order_index: Number.parseInt(String(form.order_index || "0").trim(), 10),
      quantity: Number.parseInt(String(form.quantity || "1").trim(), 10),
      mirrored: Boolean(form.mirrored),
      notes: String(form.notes || "").trim() || null,
    };

    if (!Number.isFinite(payload.x_mm)) {
      payload.x_mm = undefined;
    }
    if (!Number.isFinite(payload.y_mm)) {
      payload.y_mm = undefined;
    }
    if (!Number.isFinite(payload.z_mm)) {
      payload.z_mm = undefined;
    }
    if (!Number.isFinite(payload.depth_mm)) {
      payload.depth_mm = undefined;
    }

    if (!Number.isFinite(payload.order_index)) {
      throw new Error(t.holePointOrderIndexInvalid);
    }

    if (!Number.isFinite(payload.quantity) || payload.quantity <= 0) {
      throw new Error(t.holePointQuantityInvalid);
    }

    return payload;
  }

  async function handleHolePointCreate(event) {
    event.preventDefault();

    if (!holeSelectedTemplateId) {
      setHolePointCreateError(t.holePointTemplateRequired);
      return;
    }

    try {
      const payload = buildHolePointPayload(holePointCreateForm);

      setLoading(true);
      const result = await createFittingHolePoint(token, holeSelectedTemplateId, payload);
      setLoading(false);

      if (!result.success) {
        const errorMessage = result.error || t.holePointCreateFailed;
        setHolePointCreateError(errorMessage);
        setStatus({ message: errorMessage, tone: "error" });
        return;
      }

      closeHolePointCreateForm();
      const reloaded = await loadHoleTemplateDetails(token, holeSelectedTemplateId);
      if (reloaded) {
        setStatus({ message: t.holePointCreateSuccess, tone: "success" });
      }
    } catch (error) {
      const errorMessage =
        error?.message === t.holePointOrderIndexInvalid ||
        error?.message === t.holePointQuantityInvalid ||
        error?.message === t.holePointDiameterRequired
          ? error.message
          : t.holePointNumericInvalid;
      setHolePointCreateError(errorMessage);
      setLoading(false);
      return;
    }
  }

  async function handleHolePointEdit(event) {
    event.preventDefault();

    if (!holeSelectedTemplateId || !holePointEditPointId) {
      setHolePointEditError(t.holePointEditFailed);
      return;
    }

    try {
      const payload = buildHolePointPayload(holePointEditForm);

      setLoading(true);
      const result = await updateFittingHolePoint(token, holePointEditPointId, payload);
      setLoading(false);

      if (!result.success) {
        const errorMessage = result.error || t.holePointUpdateFailed;
        setHolePointEditError(errorMessage);
        setStatus({ message: errorMessage, tone: "error" });
        return;
      }

      closeHolePointEditForm();
      const reloaded = await loadHoleTemplateDetails(token, holeSelectedTemplateId);
      if (reloaded) {
        setStatus({ message: t.holePointUpdateSuccess, tone: "success" });
      }
    } catch (error) {
      const errorMessage =
        error?.message === t.holePointOrderIndexInvalid ||
        error?.message === t.holePointQuantityInvalid ||
        error?.message === t.holePointDiameterRequired
          ? error.message
          : t.holePointNumericInvalid;
      setHolePointEditError(errorMessage);
      setLoading(false);
    }
  }

  async function loadHoleTemplateDetails(activeToken = token, templateId = holeSelectedTemplateId) {
    if (!activeToken || !templateId) {
      setHoleSelectedTemplate(null);
      setHolePoints([]);
      return false;
    }

    setLoading(true);
    const [templateResult, pointsResult] = await Promise.all([
      getFittingHoleTemplate(activeToken, templateId),
      listFittingHolePoints(activeToken, templateId),
    ]);
    setLoading(false);
    if (import.meta.env.DEV) {
      console.debug("fitting-holes points", {
        templateId,
        templateSuccess: Boolean(templateResult?.success),
        pointCount: Array.isArray(pointsResult?.points) ? pointsResult.points.length : 0,
      });
    }

    if (!templateResult.success) {
      setHoleSelectedTemplate(null);
      setHolePoints([]);
      setStatus({ message: templateResult.error || "Unable to load fitting hole template", tone: "error" });
      return false;
    }

    if (!pointsResult.success) {
      setHoleSelectedTemplate(templateResult.template || null);
      setHolePoints([]);
      setStatus({ message: pointsResult.error || "Unable to load fitting hole points", tone: "error" });
      return false;
    }

    setHoleSelectedTemplate(templateResult.template || null);
    setHolePoints(Array.isArray(pointsResult.points) ? pointsResult.points : []);
    return true;
  }

  async function handleHoleFittingChange(nextFittingId) {
    if (import.meta.env.DEV) {
      console.debug("selected fitting id", nextFittingId);
    }
    setHoleSelectedFittingId(nextFittingId);
    setHoleSelectedTemplateId("");
    setHoleSelectedTemplate(null);
    setHoleTemplateItems([]);
    setHolePoints([]);
    closeHoleTemplateCreateForm();
    closeHolePointCreateForm();
    closeHolePointEditForm();
    setStatus("");

    if (!nextFittingId) {
      return;
    }

    await loadHoleTemplates(token, nextFittingId);
  }

  async function handleHoleTemplateChange(nextTemplateId) {
    setHoleSelectedTemplateId(nextTemplateId);
    setHoleSelectedTemplate(null);
    setHolePoints([]);
    closeHolePointCreateForm();
    closeHolePointEditForm();
    setStatus("");

    if (!nextTemplateId) {
      return;
    }

    await loadHoleTemplateDetails(token, nextTemplateId);
  }

  async function handleMaterialCitySave(event) {
    event.preventDefault();

    if (!token) {
      return;
    }

    const trimmedPhone = ownProfileForm.phone.trim();
    const trimmedUsername = ownProfileForm.username.trim();
    const trimmedCity = materialSelectedCity.trim();

    const profilePayload = {
      phone: trimmedPhone || null,
      city: trimmedCity || null,
    };

    if (trimmedUsername) {
      profilePayload.username = trimmedUsername;
    }

    setLoading(true);
    const result = await updateMyProfile(token, profilePayload);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    setUser(result.user);
    const savedCity = result.user.city || "";
    setMaterialSelectedCity(savedCity);
    setOwnProfileForm((current) => ({
      ...current,
      city: savedCity,
    }));
    setStatus(t.citySaved);
    await Promise.all([
      loadMaterialsCatalog(token, {
        category: materialCategoryFilter,
        city: savedCity,
        search: materialSearch,
      }),
      loadFittingsCatalog(token, {
        city: savedCity,
        search: fittingSearch,
      }),
    ]);
  }

  async function loadManualServices(activeToken = token, viewer = user) {
    if (!activeToken) {
      return;
    }

    setLoading(true);
    const result = await getManualServicesTree(activeToken);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadManualServices);
      return;
    }

    setManualServiceItems(result.items || []);
  }

  async function loadOwnViyarAuth(activeToken = token) {
    if (!activeToken) {
      return;
    }

    setLoading(true);
    const result = await getMyViyarAuthStatus(activeToken);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadViyarAuth);
      return;
    }

    setViyarAuth(result.viyar || null);
    setViyarAuthForm((current) => ({
      ...current,
      email: result.viyar?.email || "",
      password: "",
    }));
  }

  async function loadCatalogView(activeToken = token, viewer = user) {
    await loadCatalogItems(activeToken, viewer);
    await loadMaterialsCatalog(activeToken, { category: "dsp", search: "" });
    await loadViyarServices(activeToken, viewer);
    await loadManualServices(activeToken, viewer);
  }

  async function loadAutoRefreshStatus(activeToken = token) {
    if (!activeToken) {
      return;
    }

    const result = await getCatalogAutoRefreshStatus(activeToken);

    if (!result.success) {
      return;
    }

    setAutoRefreshStatus(result.status || null);
  }

  async function loadHomeView(activeToken = token, viewer = user) {
    await loadProjects(activeToken, 0);
    await loadMaterialsCatalog(activeToken, { category: "dsp", search: "" });
    await loadFittingsCatalog(activeToken, {
      city: materialSelectedCity ?? ownProfileForm.city ?? viewer?.city ?? "",
      search: "",
    });
    await loadAutoRefreshStatus(activeToken);

    if (viewer?.role === "admin") {
      await loadUsers(activeToken, 0, viewer);
      await loadViyarServices(activeToken, viewer);
    }
  }

  async function loadSettingsView(activeToken = token) {
    await loadOwnViyarAuth(activeToken);
  }

  async function loadProject(projectId, options = {}) {
    const requestedTab = options.projectTab || "data";
    const projectResult = await getProject(token, projectId);

    if (!projectResult.success) {
      setStatus(projectResult.error || t.projectNotFound);
      return;
    }

    setSelectedProject(projectResult.project);
    setForm(projectToForm(projectResult.project));
    setHistoryItems([]);
    setCuttingItems([]);
    setCuttingAssembly({});
    setCuttingSummary(null);
    setSelectedPartDetail(null);
    setSelectedEdgeSide(null);
    setHistoryLoaded(false);
    setProductionLoaded(false);
    setActiveProjectTab(requestedTab === "partDetail" ? "production" : requestedTab);
    setStatus("");
    setActiveView("projectDetails");

    if (requestedTab === "history") {
      await loadProjectHistory(projectId);
      return;
    }

    if (requestedTab === "production" || requestedTab === "partDetail") {
      await loadProjectProduction(projectId);
    }
  }

  async function loadProjectHistory(projectId = selectedProjectId) {
    if (!projectId) {
      return;
    }

    setLoading(true);
    const result = await getProjectHistory(token, projectId);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.projectNotFound);
      return;
    }

    setHistoryItems(result.versions || []);
    setHistoryLoaded(true);
    setStatus("");
  }

  async function loadProjectProduction(
    projectId = selectedProjectId,
    clearSelectedPart = true,
  ) {
    if (!projectId) {
      return;
    }

    setLoading(true);
    const result = await getProjectCutting(token, projectId);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadCutting);
      return;
    }

    setCuttingItems(result.items || []);
    setCuttingAssembly(result.assembly || {});
    setCuttingSummary(result.summary || null);
    if (clearSelectedPart) {
      setSelectedPartDetail(null);
      setSelectedCuttingPartCode(null);
      setHoveredCuttingPartCode(null);
      setSelectedEdgeSide(null);
    }
    setProductionLoaded(true);
    setStatus("");
  }

  async function handleProjectTabChange(tabName) {
    setActiveProjectTab(tabName);

    if (tabName === "history" && !historyLoaded) {
      await loadProjectHistory();
      return;
    }

    if (tabName === "production" && !productionLoaded) {
      await loadProjectProduction();
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    setLoginLoading(true);
    setStatus("");

    const result = await login(email.trim(), password);
    setLoginLoading(false);

    if (!result.success) {
      setStatus(result.error || t.loginFailed);
      return;
    }

    localStorage.setItem(TOKEN_STORAGE_KEY, result.access_token);
    localStorage.setItem(ACTIVE_VIEW_STORAGE_KEY, "home");
    localStorage.removeItem(ACTIVE_PROJECT_ID_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_TAB_STORAGE_KEY);
    setToken(result.access_token);
    setUser(result.user);
    setActiveView("home");
    setSelectedProject(null);
    setStatus("");
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_VIEW_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_ID_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_TAB_STORAGE_KEY);
    setToken("");
    setAuthChecking(false);
    setUser(null);
    setProjects([]);
    setUsers([]);
    setAuditLogs([]);
    setCatalogItems([]);
    setViyarServiceTree([]);
    setManualServiceItems([]);
    setViyarServiceSource("viyar");
    setViyarPriceSyncSummary(null);
    setViyarServiceSearch("");
    setCollapsedViyarFolders({});
    setHoleTemplateItems([]);
    setHoleSelectedFittingId("");
    setHoleSelectedTemplateId("");
    setHoleSelectedTemplate(null);
    setHolePoints([]);
    closeHoleTemplateCreateForm();
    closeHolePointCreateForm();
    closeHolePointEditForm();
    setResetPasswordForms({});
    setNewManualServiceForm({
      article: "",
      base_price: "",
      description: "",
      is_active: true,
      is_calculable: true,
      name: "",
      unit: "service",
    });
    setOwnPasswordForm({
      currentPassword: "",
      newPassword: "",
    });
    setViyarAuth(null);
    setViyarAuthForm({
      email: "",
      password: "",
    });
    setViyarAction("");
    setSelectedProject(null);
    setHistoryItems([]);
    setCuttingItems([]);
    setCuttingAssembly({});
    setCuttingSummary(null);
    setSelectedPartDetail(null);
    setSelectedCuttingPartCode(null);
    setSelectedEdgeSide(null);
    setHistoryLoaded(false);
    setProductionLoaded(false);
    setActiveProjectTab("data");
    setStatus("");
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
    if (!selectedProjectId) {
      return;
    }

    if (!partCode) {
      return;
    }

    const result = await getProjectPartDetail(token, selectedProjectId, partCode);

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
    if (!selectedProjectId || !selectedPartDetail?.part) {
      return;
    }

    setLoading(true);
    const result = await updateProjectPartEdges(
      token,
      selectedProjectId,
      selectedPartDetail.part.export_code,
      {
        top: selectedPartDetail.part.edge_top || null,
        bottom: selectedPartDetail.part.edge_bottom || null,
        left: selectedPartDetail.part.edge_left || null,
        right: selectedPartDetail.part.edge_right || null,
      },
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveEdges);
      return;
    }

    setSelectedPartDetail(result);
    await loadProjectProduction(selectedProjectId, false);
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
    if (!selectedProjectId || !selectedPartDetail?.part) {
      return;
    }

    setLoading(true);
    const result = await updateProjectPartMachining(
      token,
      selectedProjectId,
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

  async function switchView(view, viewer = user) {
    const nextView = normalizeCatalogView(view === "catalog" ? "catalogViyar" : view);

    setActiveView(nextView);
    setStatus("");

    if (nextView === "catalogFittings") {
      setSelectedFittingCategory("");
    }

    if (nextView === "home") {
      await loadHomeView(token, viewer);
      return;
    }

    if (nextView === "projects") {
      await loadProjects(token, offset);
      return;
    }

    if (nextView === "createProject") {
      return;
    }

    if (nextView === "users") {
      await loadUsers(token, usersOffset, viewer);
      await loadUserChangeRequests(token, viewer);
      return;
    }

    if (nextView === "catalogValues") {
      await loadCatalogItems(token, viewer);
      return;
    }

    if (nextView === "catalogHub") {
      await loadCatalogView(token, viewer);
      return;
    }

    if (nextView === "catalogMaterials") {
      await loadMaterialsCatalog(token);
      return;
    }

    if (nextView === "catalogFittings") {
      await loadFittingsCatalog(token);
      return;
    }

    if (nextView === "catalogHoles") {
      await loadFittingsCatalog(token);
      setHoleSelectedFittingId("");
      setHoleSelectedTemplateId("");
      setHoleSelectedTemplate(null);
      setHoleTemplateItems([]);
      setHolePoints([]);
      closeHoleTemplateCreateForm();
      closeHolePointCreateForm();
      closeHolePointEditForm();
      return;
    }

    if (nextView === "catalogViyar") {
      await loadViyarServices(token, viewer);
      return;
    }

    if (nextView === "catalogManual") {
      await loadManualServices(token, viewer);
      return;
    }

    if (nextView === "settings") {
      await loadSettingsView(token);
      return;
    }

    if (nextView === "audit") {
      await loadAuditLogs(token, auditOffset, viewer);
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

  async function handleUserChangeRequestReview(changeRequest, decision) {
    setLoading(true);
    const result = await reviewUserChangeRequest(token, changeRequest.id, decision);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.requestReviewed);
      return;
    }

    setStatus(t.requestReviewed);
    await loadUsers(token, usersOffset);
    await loadUserChangeRequests(token);
  }

  function setResetPasswordValue(userId, passwordValue) {
    setResetPasswordForms({
      ...resetPasswordForms,
      [userId]: passwordValue,
    });
  }

  async function handleOwnProfileSave(event) {
    event.preventDefault();

    const trimmedPhone = ownProfileForm.phone.trim();
    const trimmedUsername = ownProfileForm.username.trim();
    const trimmedCity = ownProfileForm.city.trim();

    const profilePayload = {
      phone: trimmedPhone || null,
      city: trimmedCity || null,
    };

    if (trimmedUsername) {
      profilePayload.username = trimmedUsername;
    }

    setLoading(true);
    const result = await updateMyProfile(token, profilePayload);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.usernameChangeWeekly);
      return;
    }

    setUser(result.user);
    const savedCity = result.user.city || "";
    setMaterialSelectedCity(savedCity);
    setOwnProfileForm({
      username: result.user.username || "",
      phone: result.user.phone || "",
      city: savedCity,
    });
    setStatus(t.profileSaved);

    await Promise.all([
      loadMaterialsCatalog(token, {
        category: materialCategoryFilter,
        city: savedCity,
        search: materialSearch,
      }),
      loadFittingsCatalog(token, {
        city: savedCity,
        search: fittingSearch,
      }),
    ]);
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
      setStatus(result.error || t.requestEmailChange);
      return;
    }

    setEmailChangeForm({
      newEmail: "",
    });
    setStatus(t.emailChangeRequested);
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

  async function handleSaveViyarAuth(event) {
    event.preventDefault();

    setViyarAction("saving");
    setStatus({ message: t.viyarSavingCredentials, tone: "info" });
    setLoading(true);
    const result = await updateMyViyarAuth(
      token,
      normalizedViyarEmail,
      viyarAuthForm.password || null,
    );
    setLoading(false);

    if (!result.success) {
      setViyarAction("");
      setStatus({ message: result.error || t.unableToSaveViyarAuth, tone: "error" });
      return;
    }

    setViyarAuth(result.viyar || null);
    setViyarAuthForm((current) => ({
      ...current,
      email: result.viyar?.email || current.email,
        password: "",
      }));
    setViyarAction("");
    setStatus({ message: t.viyarCredentialsSaved, tone: "success" });
  }

  async function handleRefreshViyarSession() {
    if (!normalizedViyarEmail) {
      setStatus({ message: t.viyarStepSave, tone: "info" });
      return;
    }

    if (viyarEmailChanged || viyarHasUnsavedPassword || !viyarHasSavedPassword) {
      setViyarAction("saving");
      setStatus({ message: t.viyarSavingCredentials, tone: "info" });
      setLoading(true);
      const saveResult = await updateMyViyarAuth(
        token,
        normalizedViyarEmail,
        viyarAuthForm.password || null,
      );
      setLoading(false);

      if (!saveResult.success) {
        setViyarAction("");
        setStatus({ message: saveResult.error || t.unableToSaveViyarAuth, tone: "error" });
        return;
      }

      setViyarAuth(saveResult.viyar || null);
      setViyarAuthForm((current) => ({
        ...current,
        email: saveResult.viyar?.email || normalizedViyarEmail,
          password: "",
        }));
    }

    setViyarAction("connecting");
    setStatus({ message: t.viyarConnectingNow, tone: "info" });
    setLoading(true);
    const result = await refreshMyViyarSession(token);
    setLoading(false);

    if (!result.success) {
      if (result.viyar) {
        setViyarAuth(result.viyar);
      }
      setViyarAction("");
      setStatus({ message: result.error || t.unableToRefreshViyarSession, tone: "error" });
      return;
    }

    setViyarAuth(result.viyar || null);
    setViyarAction("");
    setStatus({ message: t.viyarConnected, tone: "success" });
  }

  async function handleResetPassword(targetUser) {
    const passwordValue = resetPasswordForms[targetUser.id] || "";

    if (passwordValue.length < 8) {
      setStatus({ message: t.passwordMustBeLong, tone: "error" });
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
      setStatus({ message: result.error || t.unableToResetPassword, tone: "error" });
      return;
    }

    setResetPasswordForms({
      ...resetPasswordForms,
      [targetUser.id]: "",
    });
    setStatus({ message: t.passwordReset, tone: "success" });
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
      setStatus({ message: result.error || t.unableToCreateUser, tone: "error" });
      return;
    }

    setNewUserForm({
      email: "",
      password: "",
      role: "free",
    });
    setStatus({ message: t.userCreated, tone: "success" });
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

  async function handleImportViyarServices() {
    setLoading(true);
    const result = await importViyarServices(token);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToImportViyarServices);
      return;
    }

    setViyarServiceSource(result.source || "viyar");
    setViyarServiceTree(result.items || []);
    setViyarPriceSyncSummary(null);
    setStatus(
      result.fallback_only_import
        ? t.viyarFallbackImportNotice
        : t.viyarImported,
    );
  }

  async function handleSyncViyarPrices() {
    setViyarAction("syncing");
    setStatus(t.viyarSyncingPricesNow);
    setLoading(true);
    const result = await syncViyarServicePrices(token);
    setLoading(false);

    if (!result.success) {
      setViyarAction("");
      setStatus(result.error || t.unableToSyncViyarPrices);
      return;
    }

    setViyarServiceSource(result.source || "viyar");
    setViyarServiceTree(result.items || []);
    setViyarPriceSyncSummary({
      auth_required: Boolean(result.auth_required),
      priced_count: Number(result.priced_count || 0),
      skipped_count: Number(result.skipped_count || 0),
      total_count: Number(result.priced_count || 0) + Number(result.skipped_count || 0),
    });
    if (activeView === "settings") {
      await loadOwnViyarAuth(token);
    }
    setViyarAction("");
    setStatus(
      result.auth_required
        ? `${t.viyarAuthRequired} (${Number(result.priced_count || 0)}/${Number(result.priced_count || 0) + Number(result.skipped_count || 0)})`
        : `${t.viyarPricesSynced}: ${Number(result.priced_count || 0)} / ${Number(result.priced_count || 0) + Number(result.skipped_count || 0)}`,
    );
  }

  function handleViyarServiceFieldChange(itemId, field, value) {
    setViyarServiceTree((current) =>
      updateServiceTreeNode(current, itemId, (node) => ({
        ...node,
        [field]: value,
      })),
    );
  }

  async function handleSaveViyarService(node) {
    setLoading(true);
    const result = await updateViyarService(token, node.id, {
      base_price:
        node.base_price === "" || node.base_price === null
          ? null
          : Number(node.base_price),
      is_active: Boolean(node.is_active),
      is_calculable: Boolean(node.is_calculable),
      unit: node.unit || null,
    });
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveCatalogItem);
      return;
    }

    setViyarServiceTree((current) =>
      updateServiceTreeNode(current, node.id, () => ({
        ...node,
        ...result.item,
      })),
    );
    setStatus(t.catalogItemUpdated);
  }

  function handleManualServiceFieldChange(itemId, field, value) {
    setManualServiceItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              [field]: value,
            }
          : item,
      ),
    );
  }

  async function handleCreateManualService(event) {
    event.preventDefault();

    setLoading(true);
    const result = await createManualService(token, {
      article: newManualServiceForm.article || null,
      base_price:
        newManualServiceForm.base_price === "" || newManualServiceForm.base_price === null
          ? null
          : Number(newManualServiceForm.base_price),
      description: newManualServiceForm.description || null,
      is_active: Boolean(newManualServiceForm.is_active),
      is_calculable: Boolean(newManualServiceForm.is_calculable),
      name: newManualServiceForm.name.trim(),
      unit: newManualServiceForm.unit || null,
    });
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveManualService);
      return;
    }

    setNewManualServiceForm({
      article: "",
      base_price: "",
      description: "",
      is_active: true,
      is_calculable: true,
      name: "",
      unit: "service",
    });
    setStatus(t.manualServiceCreated);
    await loadManualServices(token);
  }

  async function handleSaveManualService(item) {
    setLoading(true);
    const result = await updateManualService(token, item.id, {
      article: item.article || null,
      base_price:
        item.base_price === "" || item.base_price === null
          ? null
          : Number(item.base_price),
      description: item.description || null,
      is_active: Boolean(item.is_active),
      is_calculable: Boolean(item.is_calculable),
      name: item.name.trim(),
      unit: item.unit || null,
    });
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToSaveManualService);
      return;
    }

    setManualServiceItems((current) =>
      current.map((serviceItem) =>
        serviceItem.id === item.id
          ? {
              ...serviceItem,
              ...result.item,
            }
          : serviceItem,
      ),
    );
    setStatus(t.manualServiceUpdated);
  }

  async function handleImportMaterial(event) {
    event.preventDefault();

    const effectiveCity = materialSelectedCity || ownProfileForm.city || user?.city || "";

    if (!String(effectiveCity).trim()) {
      setStatus({ message: t.cityRequiredForMaterialImport, tone: "error" });
      return;
    }

    const isSourceMode = materialCreateMode === "source";
    const payload = {
      category: materialCategoryFilter || "dsp",
      city: effectiveCity,
      article: newMaterialArticle.trim() || null,
      source_url: isSourceMode ? newMaterialSourceUrl.trim() || null : null,
      name: isSourceMode ? null : newMaterialName.trim() || null,
      price: isSourceMode ? null : (newMaterialPrice === "" ? null : Number(newMaterialPrice)),
      image_url: isSourceMode ? null : newMaterialImageUrl || null,
      is_default: isSourceMode ? Boolean(newMaterialIsDefault && canManageSystemMaterials(user)) : false,
    };

    setLoading(true);
    const result = await createMaterial(token, payload);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    setNewMaterialArticle("");
    setNewMaterialSourceUrl("");
    setNewMaterialName("");
    setNewMaterialPrice("");
    setNewMaterialImageUrl("");
    setNewMaterialIsDefault(false);

    if (result.item) {
      if (result.job) {
        setActiveMaterialImportJobId(result.job.id);
        setActiveMaterialImportJob(result.job);
        setStatus({ message: t.materialImportQueued, tone: "info" });
      } else {
        setStatus({ message: result.error || t.materialImportSuccess, tone: "success" });
      }
      await loadMaterialsCatalog(token);
      return;
    }

    if (result.job?.id) {
      setActiveMaterialImportJobId(result.job.id);
      setActiveMaterialImportJob(result.job);
      setStatus({ message: t.materialImportQueued, tone: "info" });
      return;
    }

    setStatus({ message: result.error || t.materialImportQueued, tone: "info" });
  }

  async function handleMaterialImageUpload(event) {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    try {
      const imageUrl = await compressImageFileToDataUrl(file);
      setNewMaterialImageUrl(imageUrl);
    } catch {
      setStatus({ message: t.unableToLoadCatalog, tone: "error" });
    } finally {
      event.target.value = "";
    }
  }

  function openDeleteMaterialConfirm(item) {
    if (!canDeleteMaterialItem(user, item)) {
      return;
    }

    setOpenMaterialMenuId("");
    setConfirmAction({
      type: "deleteMaterial",
      title: t.deleteMaterial,
      message: `${t.deleteMaterial}: ${item.name || item.article}?`,
      confirmLabel: t.delete,
      targetId: item.article,
    });
  }

  async function handleDeleteMaterial(article) {
    if (!article) {
      return;
    }

    setLoading(true);
    const result = await deleteMaterial(token, article);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.deleteFailed, tone: "error" });
      return;
    }

    setMaterialItems((current) => current.filter((item) => item.article !== article));
    if (selectedMaterialDetail?.article === article) {
      closeMaterialDetails();
    }
    setStatus({ message: t.materialDeleted, tone: "success" });
    closeConfirm();
  }

  async function handleRefreshMaterial(item) {
    if (!item?.article) {
      return;
    }

    setOpenMaterialMenuId("");
    setStatus({ message: t.materialRefreshStarted, tone: "info" });
    setLoading(true);
    const result = await importMaterialFromViyar(
      token,
      item.article,
      item.category || materialCategoryFilter || "dsp",
      item.source_url || "",
      true,
    );
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    if (result.job?.id) {
      setActiveMaterialImportJobId(result.job.id);
      setActiveMaterialImportJob(result.job);
      setStatus({ message: t.materialRefreshQueued, tone: "info" });
      return;
    }

    if (result.item) {
      setStatus({ message: t.materialImportSuccess, tone: "success" });
      await loadMaterialsCatalog(token);
    }
  }

  function toggleMaterialEdgeForm(edgeKey) {
    setMaterialEdgeForms((current) => {
      const next = { ...current };
      if (next[edgeKey]?.open) {
        delete next[edgeKey];
        return next;
      }
      next[edgeKey] = { open: true, source_url: "" };
      return next;
    });
  }

  function updateMaterialEdgeForm(edgeKey, value) {
    setMaterialEdgeForms((current) => ({
      ...current,
      [edgeKey]: {
        ...(current[edgeKey] || { open: true }),
        source_url: value,
      },
    }));
  }

  function toggleMaterialEdgeCreateForm() {
    setMaterialEdgeCreateForm((current) =>
      current.open
        ? { ...current, open: false, source_url: "" }
        : {
            open: true,
            edge_key: getDefaultMaterialEdgeKey(selectedMaterialDetail),
            source_url: "",
          },
    );
  }

  function updateMaterialEdgeCreateForm(field, value) {
    setMaterialEdgeCreateForm((current) => ({
      ...current,
      open: true,
      [field]: value,
    }));
  }

  async function handleAttachMaterialEdge(edgeKey, sourceUrlOverride = null) {
    if (!token || !selectedMaterialDetail?.article) {
      return;
    }

    const sourceUrl = String(sourceUrlOverride ?? materialEdgeForms[edgeKey]?.source_url ?? "").trim();

    if (!sourceUrl) {
      setStatus({ message: t.materialEdgeAttachPlaceholder, tone: "error" });
      return;
    }

    setLoading(true);
    const result = await attachMaterialEdge(token, selectedMaterialDetail.article, {
      edge_key: edgeKey,
      source_url: sourceUrl,
      city: materialSelectedCity || ownProfileForm.city || user?.city || "",
    });
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    setSelectedMaterialDetail(result.item || selectedMaterialDetail);
    setMaterialItems((current) =>
      current.map((item) =>
        item.article === selectedMaterialDetail.article
          ? { ...item, ...(result.item || {}) }
          : item,
      ),
    );
    setMaterialEdgeForms((current) => {
      const next = { ...current };
      delete next[edgeKey];
      return next;
    });
    setMaterialEdgeCreateForm({
      open: false,
      edge_key: getDefaultMaterialEdgeKey(result.item || selectedMaterialDetail),
      source_url: "",
    });
    setStatus({ message: t.materialEdgeAdded, tone: "success" });
  }

  function openDeleteFittingConfirm(item) {
    if (!canDeleteFittingItem(user, item)) {
      return;
    }

    setOpenFittingMenuId("");
    setConfirmAction({
      type: "deleteFitting",
      title: t.fittingDelete,
      message: `${t.fittingDeleteConfirm}: ${item.name || item.article}?`,
      confirmLabel: t.delete,
      targetId: item.id,
    });
  }

  async function handleDeleteFitting(itemId) {
    if (!itemId) {
      return;
    }

    setLoading(true);
    const result = await deleteFitting(token, itemId);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.deleteFailed, tone: "error" });
      return;
    }

    setFittingItems((current) => current.filter((item) => item.id !== itemId));
    setStatus({ message: t.fittingDelete, tone: "success" });
    closeConfirm();
  }

  async function handleFittingImageSelected(event) {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) {
      return;
    }

    try {
      const imageUrl = await compressImageFileToDataUrl(file);
      setNewFittingForm((current) => ({
        ...current,
        image_url: imageUrl,
      }));
      setStatus({ message: t.fittingImageSelected, tone: "success" });
    } catch (error) {
      setStatus({ message: error?.message || t.unableToLoadCatalog, tone: "error" });
    }
  }

  async function handleCreateFitting(event) {
    event.preventDefault();

    if (!token || !canEditOwnFittings) {
      return;
    }

    const isSystemFitting = canEditSystemFittings ? Boolean(newFittingForm.is_system) : false;
    const normalizedArticle = newFittingForm.article.trim();
    const normalizedSourceUrl = newFittingForm.source_url.trim();
    const normalizedName = newFittingForm.name.trim();

    const payload = {
      article: normalizedArticle || null,
      city: (newFittingForm.city || materialSelectedCity || user?.city || "").trim() || null,
      code: null,
      fitting_group: newFittingForm.fitting_group,
      fitting_type: newFittingForm.fitting_type,
      image_url: isSystemFitting ? null : newFittingForm.image_url.trim() || null,
      source_url: isSystemFitting ? normalizedSourceUrl || null : null,
      is_active: Boolean(newFittingForm.is_active),
      is_system: isSystemFitting,
      name: isSystemFitting ? normalizedArticle : normalizedName,
      price:
        isSystemFitting || newFittingForm.price === "" || newFittingForm.price === null
          ? null
          : Number(String(newFittingForm.price).replace(",", ".")),
      sort_order: Number(newFittingForm.sort_order || 0),
      stock: null,
    };

    if (!payload.fitting_type) {
      setStatus({ message: t.fittingTypePrompt, tone: "error" });
      return;
    }

    if (!payload.article) {
      setStatus({ message: t.fittingArticlePrompt, tone: "error" });
      return;
    }

    if (isSystemFitting && !payload.source_url) {
      setStatus({ message: t.fittingSourceUrlPrompt, tone: "error" });
      return;
    }

    if (!isSystemFitting && !payload.name) {
      setStatus({ message: t.fittingNamePrompt, tone: "error" });
      return;
    }

    setLoading(true);
    const result = await createFitting(token, payload);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.unableToLoadCatalog, tone: "error" });
      return;
    }

    setStatus({ message: t.fittingCreateSuccess, tone: "success" });
    setNewFittingForm((current) => ({
      ...DEFAULT_FITTING_FORM,
      city: current.city || materialSelectedCity || user?.city || "",
      fitting_group: current.fitting_group,
      fitting_type: current.fitting_type,
      is_system: canEditSystemFittings ? current.is_system : false,
    }));
    await loadFittingsCatalog(token, {
      city: materialSelectedCity || user?.city || "",
    });
  }

  async function handleApplyProjectFilters(event) {
    event.preventDefault();

    await loadProjects(token, 0, projectFilters);
  }

  async function handleResetProjectFilters() {
    setProjectFilters(DEFAULT_PROJECT_FILTERS);
    await loadProjects(token, 0, DEFAULT_PROJECT_FILTERS);
  }

  function handleApplyProjectTemplate(template) {
    setProjectStartMode("templates");
    setNewProjectForm((current) => ({
      ...current,
      ...template.fields,
      projectName:
        current.projectName && current.projectName !== DEFAULT_PROJECT_NAME
          ? current.projectName
          : t[template.titleKey] || current.projectName,
      notes: current.notes || t[template.descriptionKey] || current.notes,
    }));
    setStatus(t.projectTemplateApplied);
  }

  async function loadAiScanHistory(activeToken) {
    const result = await listProjectScans(activeToken, 5);

    if (result.success) {
      setAiScanHistory(result.items || []);
    }
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
    const result = await scanProjectFile(token, aiScanFile);
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
      : newProjectForm.projectType;
    const scanNotes = defaults.notes || aiScanResult.raw_text || "";

    setNewProjectForm({
      ...newProjectForm,
      projectName:
        newProjectForm.projectName && newProjectForm.projectName !== DEFAULT_PROJECT_NAME
          ? newProjectForm.projectName
          : defaults.projectName || newProjectForm.projectName,
      projectType: nextProjectType,
      width: defaults.width || aiScanResult.width || newProjectForm.width,
      height: defaults.height || aiScanResult.height || newProjectForm.height,
      depth: defaults.depth || aiScanResult.depth || newProjectForm.depth,
      notes: [
        newProjectForm.notes,
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

    setNewProjectForm(DEFAULT_PROJECT_FORM);
    setAiScanFile(null);
    setAiScanResult(null);
    setAiScanSession(null);
    setProjectFilters(DEFAULT_PROJECT_FILTERS);
    setStatus({ message: t.projectCreated, tone: "success" });
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
      setStatus({ message: t.projectEditRestricted, tone: "info" });
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
      setStatus({ message: result.error || t.updateFailed, tone: "error" });
      return;
    }

    setStatus({ message: t.projectUpdated, tone: "success" });
    await loadProject(selectedProjectId);
    await loadProjects(token, offset);
  }

  function openRollbackConfirm(version) {
    if (!canRollbackSelectedProject) {
      setStatus({ message: t.projectRollbackRestricted, tone: "info" });
      return;
    }

    setConfirmAction({
      type: "rollback",
      title: t.rollbackProject,
      message: `${t.rollbackProject} ${selectedProject?.project_name || t.newProjectDefault} ${t.to} ${version.width} x ${version.height} x ${version.depth}?`,
      confirmLabel: t.rollback,
      targetId: version.id,
    });
  }

  function openDeleteConfirm() {
    if (!selectedProjectId) {
      return;
    }

    if (!canDeleteSelectedProject) {
      setStatus({ message: t.projectDeleteRestricted, tone: "info" });
      return;
    }

    setConfirmAction({
      type: "delete",
      title: t.deleteProject,
      message: `${t.deleteProjectConfirm} ${selectedProject?.project_name || t.newProjectDefault}?`,
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
      return;
    }

    if (confirmAction.type === "deleteMaterial") {
      await handleDeleteMaterial(confirmAction.targetId);
      return;
    }

    if (confirmAction.type === "deleteFitting") {
      await handleDeleteFitting(confirmAction.targetId);
    }
  }

  async function handleRollback(versionId) {
    if (!selectedProjectId) {
      return;
    }

    if (!canRollbackSelectedProject) {
      setStatus({ message: t.projectRollbackRestricted, tone: "info" });
      return;
    }

    setLoading(true);
    const result = await rollbackProject(token, selectedProjectId, versionId);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.rollbackFailed, tone: "error" });
      return;
    }

    setStatus({ message: t.projectRolledBack, tone: "success" });
    closeConfirm();
    await loadProject(selectedProjectId);
    setActiveProjectTab("history");
    await loadProjectHistory(selectedProjectId);
    await loadProjects(token, offset);
  }

  async function handleDelete() {
    if (!selectedProjectId) {
      return;
    }

    if (!canDeleteSelectedProject) {
      setStatus({ message: t.projectDeleteRestricted, tone: "info" });
      return;
    }

    setLoading(true);
    const result = await deleteProject(token, selectedProjectId);
    setLoading(false);

    if (!result.success) {
      setStatus({ message: result.error || t.deleteFailed, tone: "error" });
      return;
    }

    setStatus({ message: t.projectDeleted, tone: "success" });
    closeConfirm();
    setSelectedProject(null);
    setHistoryItems([]);
    setCuttingItems([]);
    setCuttingAssembly({});
    setCuttingSummary(null);
    setSelectedPartDetail(null);
    setHistoryLoaded(false);
    setProductionLoaded(false);
    setActiveProjectTab("data");
    setActiveView("projects");
    await loadProjects(token, offset);
  }

  useEffect(() => {
    if (!token) {
      setAuthChecking(false);
      return;
    }

    async function bootstrapAuthorizedApp() {
      setAuthChecking(true);
      try {
        const loadedUser = await loadUser(token);

        if (!loadedUser) {
          return;
        }

        await loadSpecificationCatalog();

        if (activeView === "projectDetails" && storedProjectId) {
          await loadProject(storedProjectId, {
            projectTab: storedProjectTab,
          });
          return;
        }

        if (activeView === "home") {
          await loadHomeView(token, loadedUser);
          return;
        }

        if (activeView === "settings") {
          await loadSettingsView(token);
          return;
        }

        if (activeView && activeView !== "projects") {
          if (CATALOG_SERVICE_VIEWS.has(activeView) || activeView === "users" || activeView === "audit") {
            return;
          }

          await switchView(activeView, loadedUser);
          return;
        }

        await loadProjects(token, 0);
      } finally {
        if (tokenRef.current === token) {
          setAuthChecking(false);
        }
      }
    }

    bootstrapAuthorizedApp();
  }, [token]);

  useEffect(() => {
    if (!token) {
      setAuthChecking(false);
    }
  }, [token]);

  useEffect(() => {
    localStorage.setItem(ACTIVE_VIEW_STORAGE_KEY, activeView);
  }, [activeView]);

  useEffect(() => {
    if (activeView === "projectDetails" && selectedProject?.id) {
      localStorage.setItem(ACTIVE_PROJECT_ID_STORAGE_KEY, selectedProject.id);
      localStorage.setItem(ACTIVE_PROJECT_TAB_STORAGE_KEY, activeProjectTab);
      return;
    }

    localStorage.removeItem(ACTIVE_PROJECT_ID_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_TAB_STORAGE_KEY);
  }, [activeProjectTab, activeView, selectedProject?.id]);

  useEffect(() => {
    if (!token || activeView !== "home") {
      return;
    }

    loadAutoRefreshStatus(token);
    const timerId = window.setInterval(() => {
      loadAutoRefreshStatus(token);
    }, 60000);

    return () => {
      window.clearInterval(timerId);
    };
  }, [activeView, token]);

  useEffect(() => {
    function handleUnauthorized(event) {
      const eventToken = String(event?.detail?.token || "").trim();

      if (!eventToken || !tokenRef.current) {
        return;
      }

      if (eventToken !== tokenRef.current) {
        return;
      }

      handleLogout();
      setStatus({ message: t.loginFailed, tone: "error" });
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
    if (!token || !canUseAiScan || activeView !== "createProject") {
      return;
    }

    loadAiScanHistory(token);
  }, [token, canUseAiScan, activeView]);

  useEffect(() => {
    if (!token) {
      return;
    }

    const needsProjectOptionData =
      activeView === "createProject" ||
      (activeView === "projectDetails" && activeProjectTab === "data");

    if (!needsProjectOptionData) {
      return;
    }

    if (!materialItems.length) {
      loadMaterialsCatalog(token, {
        category: "dsp",
        city: materialSelectedCity || ownProfileForm.city || user?.city || "",
        search: "",
      });
    }

    if (!fittingItems.length) {
      loadFittingsCatalog(token, {
        city: materialSelectedCity || ownProfileForm.city || user?.city || "",
        search: "",
      });
    }
  }, [
    activeProjectTab,
    activeView,
    fittingItems.length,
    materialItems.length,
    materialSelectedCity,
    ownProfileForm.city,
    token,
    user?.city,
  ]);

  useEffect(() => {
    if (
      (projectStartMode === "ai" && !canUseAiScan) ||
      (projectStartMode === "premium" && !canUsePremiumStart)
    ) {
      setProjectStartMode("templates");
    }
  }, [projectStartMode, canUseAiScan, canUsePremiumStart]);

  useEffect(() => {
    if (!token || user?.role !== "admin" || !isCatalogValuesView) {
      return;
    }

    loadCatalogItems(token);
  }, [token, user, isCatalogValuesView]);

  useEffect(() => {
    if (!token || !isCatalogMaterialsView) {
      return;
    }

    loadMaterialsCatalog(token);
  }, [token, user?.city, isCatalogMaterialsView, materialCategoryFilter, materialSearch]);

  useEffect(() => {
    if (!token || (!isCatalogFittingsView && !isCatalogFastenersView)) {
      return;
    }

    loadFittingsCatalog(token);
  }, [token, user?.city, isCatalogFittingsView, isCatalogFastenersView, fittingSearch]);

  useEffect(() => {
    if (!token || !isCatalogHolesView || fittingItems.length) {
      return;
    }

    loadFittingsCatalog(token);
  }, [token, user?.city, isCatalogHolesView, fittingItems.length, fittingSearch]);

  useEffect(() => {
    if (!token || user?.role !== "admin" || !isCatalogViyarView) {
      return;
    }

    loadViyarServices(token);
  }, [token, user, isCatalogViyarView]);

  useEffect(() => {
    if (!token || user?.role !== "admin" || !isCatalogHubView) {
      return;
    }

    loadCatalogView(token);
  }, [token, user, isCatalogHubView]);

  useEffect(() => {
    if (!token || !isCatalogManualView) {
      return;
    }

    loadManualServices(token);
  }, [token, user, isCatalogManualView]);

  if (token && authChecking && !user) {
    return (
      <main className="auth-screen">
        <div className="login-panel">
          <div className="auth-brand">
            <img
              alt={t.furniturePlatform}
              className="brand-logo"
              src="/brand/mproject-logo-reference.jpg"
            />
            <div className="auth-heading">
              <p>{t.brandTagline}</p>
              <h1>{t.admin}</h1>
            </div>
          </div>
          <p>{t.loading}</p>
        </div>
      </main>
    );
  }

  if (!token || !user) {
    return (
      <main className="auth-screen">
        {statusNotice}
        <form className="login-panel" onSubmit={handleLogin}>
          <div className="auth-brand">
            <img
              alt={t.furniturePlatform}
              className="brand-logo"
              src="/brand/mproject-logo-reference.jpg"
            />
            <div className="auth-heading">
              <p>{t.brandTagline}</p>
              <h1>{t.admin}</h1>
            </div>
          </div>

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
            <div className="password-field">
              <input
                autoComplete="current-password"
                minLength={8}
                onChange={(event) => setPassword(event.target.value)}
                required
                type={showLoginPassword ? "text" : "password"}
                value={password}
              />
              <button
                aria-label={showLoginPassword ? t.hidePassword : t.showPassword}
                className="password-toggle-button"
                onClick={() => setShowLoginPassword((current) => !current)}
                title={showLoginPassword ? t.hidePassword : t.showPassword}
                type="button"
              >
                {showLoginPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>

          <button className="primary-button" disabled={loginLoading} type="submit">
            <Search size={18} />
            {loginLoading ? t.loading : t.signIn}
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="app-shell">
      {statusNotice}
      <aside className="sidebar">
        <div className="brand-block sidebar-brand-block">
          <button
            className="sidebar-brand-link"
            onClick={() => switchView("home")}
            type="button"
          >
            <img
              alt={t.furniturePlatform}
              className="sidebar-brand-logo"
              src="/brand/mproject-logo-reference.jpg"
            />
          </button>
          <div className="brand-copy">
            <p className="eyebrow">{t.brandTagline}</p>
            <div className="brand-copy-header">
              <h1>{t.admin}</h1>
              <div className="language-switcher compact" aria-label="Language">
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
          </div>
        </div>

        <div className="user-block">
          <span>{userLoginName}</span>
          <strong>{user.role}</strong>
          <small>
            {t.currentCity}: {formatCatalogLabel(user.city, t)}
          </small>
        </div>

        <nav className="nav-tabs" aria-label="Admin sections">
          <button
            className={isHomeView ? "active" : ""}
            onClick={() => switchView("home")}
            type="button"
          >
            {t.home}
          </button>
          <button
            className={
              activeView === "projects" || activeView === "projectDetails"
                ? "active"
                : ""
            }
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
                className={activeView === "audit" ? "active" : ""}
                onClick={() => switchView("audit")}
                type="button"
              >
                {t.audit}
              </button>
            </>
          ) : null}
          <div className={`nav-group${isCatalogView ? " active" : ""}`}>
            <div className={`nav-group-header${isCatalogView ? " active" : ""}`}>
              <button
                className={`nav-group-link${isCatalogHubView || isCatalogMaterialsView || isCatalogFittingsView || isCatalogFastenersView || isCatalogHolesView ? " active" : ""}`}
                onClick={() => switchView(user.role === "admin" ? "catalogHub" : "catalogMaterials")}
                type="button"
              >
                <span className="nav-group-title">{t.catalog}</span>
              </button>
              <button
                aria-expanded={isCatalogMenuOpen}
                className={`nav-group-toggle${isCatalogView ? " active" : ""}`}
                onClick={() => setIsCatalogMenuOpen((current) => !current)}
                type="button"
              >
                <ChevronRight
                  className={`nav-group-icon${isCatalogMenuOpen ? " expanded" : ""}`}
                  size={16}
                />
              </button>
            </div>
            {isCatalogMenuOpen ? (
              <div className="nav-subtabs">
                <button
                  className={isCatalogMaterialsView ? "active" : ""}
                  onClick={() => switchView("catalogMaterials")}
                  type="button"
                >
                  {t.catalogMaterials}
                </button>
                <button
                  className={isCatalogFittingsView ? "active" : ""}
                  onClick={() => switchView("catalogFittings")}
                  type="button"
                >
                  {t.catalogFittings}
                </button>
                {canViewFittingHoles ? (
                  <button
                    className={isCatalogHolesView ? "active" : ""}
                    onClick={() => switchView("catalogHoles")}
                    type="button"
                  >
                    {t.holeTabTitle}
                  </button>
                ) : null}
                {user.role === "admin" ? (
                  <>
                    <button
                      className={isCatalogViyarView ? "active" : ""}
                      onClick={() => switchView("catalogViyar")}
                      type="button"
                    >
                      {t.catalogViyar}
                    </button>
                    <button
                      className={isCatalogManualView ? "active" : ""}
                      onClick={() => switchView("catalogManual")}
                      type="button"
                    >
                      {t.catalogManual}
                    </button>
                    <button
                      className={isCatalogValuesView ? "active" : ""}
                      onClick={() => switchView("catalogValues")}
                      type="button"
                    >
                      {t.catalogValues}
                    </button>
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
          <button
            className={activeView === "settings" ? "active" : ""}
            onClick={() => switchView("settings")}
            type="button"
          >
            {t.settings}
          </button>
        </nav>

        <button className="ghost-button" onClick={handleLogout} type="button">
          <LogOut size={18} />
          {t.logout}
        </button>
      </aside>

      <section className="workspace">
        <header
          className={`toolbar${activeView === "projectDetails" ? " project-toolbar" : ""}`}
        >
          <div className="toolbar-heading">
            <h2>
              {isHomeView
                ? t.home
                : activeView === "projects"
                ? t.projects
                : activeView === "createProject"
                  ? t.createProject
                : activeView === "projectDetails"
                  ? t.projectDetails
                : activeView === "users"
                  ? t.users
                : isCatalogHubView
                  ? t.catalog
                : isCatalogMaterialsView
                  ? t.catalogMaterials
                : isCatalogFittingsView
                  ? t.catalogFittings
                : isCatalogFastenersView
                  ? t.catalogFasteners
                : isCatalogHolesView
                  ? t.holeTabTitle
                : isCatalogValuesView
                  ? t.catalogValues
                : isCatalogViyarView
                  ? t.catalogViyar
                : isCatalogManualView
                  ? t.catalogManual
                : activeView === "settings"
                  ? t.settings
                  : t.audit}
            </h2>
            {activeView === "projectDetails" && selectedProject ? (
              <div className="toolbar-project-meta">
                <span>{selectedProject.project_name || t.newProjectDefault}</span>
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
              <p>{activePageLabel}</p>
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
            ) : activeView === "projectDetails" && selectedProject ? (
              <div className="toolbar-project-controls">
                <div className="detail-tabs toolbar-project-tabs" role="tablist">
                  <button
                    className={activeProjectTab === "data" ? "active" : ""}
                    onClick={() => handleProjectTabChange("data")}
                    type="button"
                  >
                    {t.dataProject}
                  </button>
                  <button
                    className={activeProjectTab === "production" ? "active" : ""}
                    onClick={() => handleProjectTabChange("production")}
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
                      {t.productionPartViewer}
                    </button>
                  ) : null}
                  <button
                    className={activeProjectTab === "history" ? "active" : ""}
                    onClick={() => handleProjectTabChange("history")}
                    type="button"
                  >
                    {t.history}
                  </button>
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
                <button
                  className="ghost-button"
                  disabled={loading}
                  onClick={() => switchView("projects")}
                  type="button"
                >
                  <ChevronLeft size={18} />
                  {t.projects}
                </button>
              </div>
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
            ) : isHomeView ? (
              <button
                aria-label="Refresh dashboard"
                className="icon-button"
                disabled={loading}
                onClick={() => loadHomeView(token)}
                type="button"
              >
                <RefreshCw size={18} />
              </button>
            ) : isCatalogView ? (
              <button
                aria-label="Refresh catalog"
                className="icon-button"
                disabled={loading}
                onClick={() => {
                  if (isCatalogHubView) {
                    loadCatalogView(token);
                    return;
                  }

                  if (isCatalogValuesView) {
                    loadCatalogItems(token);
                    return;
                  }

                  if (isCatalogMaterialsView) {
                    loadMaterialsCatalog(token);
                    return;
                  }

                  if (isCatalogFittingsView || isCatalogFastenersView) {
                    loadFittingsCatalog(token);
                    return;
                  }

                  if (isCatalogViyarView) {
                    loadViyarServices(token);
                    return;
                  }

                  loadManualServices(token);
                }}
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

        {isHomeView ? (
          <section className="dashboard-layout">
            <article className="dashboard-hero-card">
              <div className="dashboard-hero-copy">
                <span className="dashboard-eyebrow">{t.home}</span>
                <h3>{t.homeHeroTitle}</h3>
                <p>{t.homeHeroDescription}</p>
                <div className="dashboard-hero-actions">
                  <button
                    className="primary-button"
                    onClick={() => switchView("projects")}
                    type="button"
                  >
                    <House size={18} />
                    {t.homeOpenProjects}
                  </button>
                  <button
                    className="ghost-button"
                    onClick={() => switchView("settings")}
                    type="button"
                  >
                    <Settings2 size={18} />
                    {t.homeOpenSettings}
                  </button>
                </div>
              </div>
              <div className="dashboard-status-card">
                <div className="dashboard-status-head">
                  <div className="dashboard-status-title">
                    <strong>{t.homeAutoRefreshTitle}</strong>
                    <p>{t.homeAutoRefreshDescription}</p>
                  </div>
                  <span className={`dashboard-status-badge${autoRefreshStatus?.loop_running ? " live" : ""}`}>
                    {autoRefreshStatus?.loop_running ? t.autoRefreshRunning : t.autoRefreshStopped}
                  </span>
                </div>
                <div className="dashboard-status-grid">
                  <div className="dashboard-status-item">
                    <span>{t.autoRefreshLastSuccess}</span>
                    <strong>{formatDateTimeValue(autoRefreshStatus?.last_success_at) || t.notSet}</strong>
                  </div>
                  <div className="dashboard-status-item">
                    <span>{t.autoRefreshLastCycle}</span>
                    <strong>{formatDateTimeValue(autoRefreshStatus?.last_cycle_finished_at) || t.notSet}</strong>
                  </div>
                  <div className="dashboard-status-item">
                    <span>{t.autoRefreshQueuedMaterials}</span>
                    <strong>{autoRefreshStatus?.material_jobs_queued ?? 0}</strong>
                  </div>
                  <div className="dashboard-status-item">
                    <span>{t.autoRefreshSyncedUsers}</span>
                    <strong>{autoRefreshStatus?.service_users_synced ?? 0}</strong>
                  </div>
                </div>
                <div className="dashboard-status-meta">
                  <span>
                    {t.autoRefreshCatalogSync}:{" "}
                    {autoRefreshStatus?.service_catalog_synced
                      ? t.autoRefreshCatalogUpdated
                      : t.autoRefreshCatalogWaiting}
                  </span>
                  {autoRefreshStatus?.last_error ? (
                    <small>
                      {t.autoRefreshLastError}: {autoRefreshStatus.last_error}
                    </small>
                  ) : null}
                </div>
              </div>
            </article>

            <article className="dashboard-panel">
              <div className="dashboard-panel-head">
                <div>
                  <h3>{t.homeMetricsTitle}</h3>
                  <p>{t.homeMetricsDescription}</p>
                </div>
              </div>
              <div className="dashboard-stats-grid">
                {[
                  {
                    key: "projects",
                    label: t.projectsCount,
                    value: total,
                    icon: LayoutGrid,
                  },
                  {
                    key: "users",
                    label: t.usersCount,
                    value: user.role === "admin" ? usersTotal : 1,
                    icon: Users,
                  },
                  {
                    key: "materials",
                    label: t.materialsCount,
                    value: materialItems.length,
                    icon: Package,
                  },
                  {
                    key: "fittings",
                    label: t.fittingsCount,
                    value: fittingItems.length,
                    icon: Wrench,
                  },
                ].map((item) => {
                  const Icon = item.icon;

                  return (
                    <div className="dashboard-stat-card" key={item.key}>
                      <span className="dashboard-stat-icon">
                        <Icon size={18} />
                      </span>
                      <strong>{item.value}</strong>
                      <span>{item.label}</span>
                    </div>
                  );
                })}
              </div>
            </article>

            <article className="dashboard-panel">
              <div className="dashboard-panel-head">
                <div>
                  <h3>{t.homeCatalogMenuTitle}</h3>
                  <p>{t.homeCatalogMenuDescription}</p>
                </div>
              </div>
              <div className="dashboard-tile-grid">
                {[
                  {
                    key: "materials",
                    label: t.catalogMaterials,
                    description: t.catalogMaterialsDescription,
                    count: materialItems.length,
                    onClick: () => switchView("catalogMaterials"),
                  },
                  {
                    key: "fittings",
                    label: t.catalogFittings,
                    description: t.catalogFittingsDescription,
                    count: fittingItems.length,
                    onClick: () => switchView("catalogFittings"),
                  },
                  {
                    key: "services",
                    label: t.catalog,
                    description: t.catalogHubDescription,
                    count: viyarServiceCounts.services,
                    onClick: () => switchView(user.role === "admin" ? "catalogHub" : "catalogMaterials"),
                  },
                ].map((item) => {
                  const visual = HOME_QUICK_TILE_VISUALS[item.key];
                  const Icon = visual.icon;

                  return (
                    <button
                      className="dashboard-tile-card"
                      key={item.key}
                      onClick={item.onClick}
                      type="button"
                    >
                      <span
                        className="dashboard-tile-art"
                        style={{ "--catalog-accent": visual.accent }}
                      >
                        <Icon size={30} />
                      </span>
                      <div className="dashboard-tile-copy">
                        <strong>{item.label}</strong>
                        <span>{item.description}</span>
                      </div>
                      <span className="service-tree-badge subtle">{item.count}</span>
                    </button>
                  );
                })}
              </div>
            </article>
          </section>
        ) : activeView === "projects" ? (
          <section className="table-panel full-panel">
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
                  <th>{t.projectName}</th>
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
                    <td>{project.project_name || t.newProjectDefault}</td>
                    <td>{formatCatalogLabel(project.project_type, t)}</td>
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
            <section className="user-change-requests-panel">
              <div className="settings-card-header">
                <h3>{t.pendingRequests}</h3>
              </div>
              {userChangeRequests.length ? (
                <table>
                  <thead>
                    <tr>
                      <th>{t.email}</th>
                      <th>{t.changeType}</th>
                      <th>{t.oldValue}</th>
                      <th>{t.newValue}</th>
                      <th>{t.requestedAt}</th>
                      <th>{t.action}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {userChangeRequests.map((changeRequest) => {
                      const targetUser = users.find((item) => item.id === changeRequest.user_id);
                      return (
                        <tr key={changeRequest.id}>
                          <td>{targetUser?.email || changeRequest.user_id}</td>
                          <td>{changeRequest.change_type}</td>
                          <td>{changeRequest.old_value || t.notSet}</td>
                          <td>{changeRequest.new_value}</td>
                          <td>{formatDateTime(changeRequest.created_at, t)}</td>
                          <td>
                            <div className="request-actions">
                              <button
                                className="ghost-button"
                                disabled={loading}
                                onClick={() => handleUserChangeRequestReview(changeRequest, "approved")}
                                type="button"
                              >
                                {t.approve}
                              </button>
                              <button
                                className="ghost-button"
                                disabled={loading}
                                onClick={() => handleUserChangeRequestReview(changeRequest, "rejected")}
                                type="button"
                              >
                                {t.reject}
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <p className="empty-inline-note">{t.noPendingRequests}</p>
              )}
            </section>
          </section>

        ) : activeView === "createProject" ? (
          <section className="table-panel full-panel create-project-panel">
            <div className="project-start-shell">
              <div className="project-start-heading">
                <div>
                  <strong>{t.projectStartTitle}</strong>
                  <span>{t.projectStartDescription}</span>
                </div>
                <span className="project-start-current-tier">
                  {(user?.role || "free").toUpperCase()}
                </span>
              </div>

              <div className="project-start-grid">
                <article className="project-start-card free">
                  <div className="project-start-card-head">
                    <span className="project-start-icon">
                      <FileSliders size={20} />
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
                          <span className={`project-template-visual ${template.visual || ""}`}>
                            <img
                              alt={t[template.titleKey]}
                              loading="lazy"
                              src={template.image}
                            />
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
                  className={`project-start-card action${projectStartMode === "ai" ? " active" : ""}${!canUseAiScan ? " locked" : ""}`}
                  onClick={() => {
                    if (!canUseAiScan) {
                      setStatus({ message: t.aiScanProOnly, tone: "info" });
                      return;
                    }
                    setProjectStartMode("ai");
                  }}
                  type="button"
                >
                  <span className="project-start-action-visual pro-scan">
                    <img
                      alt={t.projectStartAiTitle}
                      loading="lazy"
                      src="/static/project-start/hero-scene.png"
                    />
                  </span>
                  <span className="project-start-icon pro">
                    <Wrench size={20} />
                  </span>
                  <strong>{t.projectStartAiTitle}</strong>
                  <small>{t.projectStartAiDescription}</small>
                  <em>{t.projectStartProBadge}</em>
                </button>

                <button
                  className={`project-start-card action${projectStartMode === "premium" ? " active" : ""}${!canUsePremiumStart ? " locked" : ""}`}
                  onClick={() => {
                    if (!canUsePremiumStart) {
                      setStatus({ message: t.projectStartPremiumOnly, tone: "info" });
                      return;
                    }
                    setProjectStartMode("premium");
                  }}
                  type="button"
                >
                  <span className="project-start-action-visual premium-power">
                    <img
                      alt={t.projectStartPremiumTitle}
                      loading="lazy"
                      src="/static/project-start/hero-scene.png"
                    />
                  </span>
                  <span className="project-start-icon premium">
                    <LayoutGrid size={20} />
                  </span>
                  <strong>{t.projectStartPremiumTitle}</strong>
                  <small>{t.projectStartPremiumDescription}</small>
                  <em>{t.projectStartPremiumBadge}</em>
                </button>
              </div>
            </div>

            {projectStartMode === "ai" ? (
              <div className="ai-scan-panel">
                <div className="ai-scan-copy">
                  <h3>{t.aiScanTitle}</h3>
                  <p>{t.aiScanDescription}</p>
                  {!canUseAiScan ? (
                    <span className="ai-scan-lock">{t.aiScanProOnly}</span>
                  ) : null}
                </div>

                <form className="ai-scan-form" onSubmit={handleScanProjectFile}>
                  <input
                    accept=".jpg,.jpeg,.png,.pdf,.webp"
                    disabled={!canUseAiScan || loading}
                    onChange={(event) => setAiScanFile(event.target.files?.[0] || null)}
                    type="file"
                  />
                  <button
                    className="primary-button"
                    disabled={!canUseAiScan || loading || !aiScanFile}
                    type="submit"
                  >
                    {t.aiScanUpload}
                  </button>
                </form>

                {aiScanResult ? (
                  <div className="ai-scan-result">
                    <div>
                      <span>{t.projectType}</span>
                      <strong>{formatCatalogLabel(aiScanResult.type || aiScanResult.form_defaults?.projectType, t)}</strong>
                    </div>
                    <div>
                      <span>{t.size}</span>
                      <strong>
                        {(aiScanResult.width || aiScanResult.form_defaults?.width || "?")} x{" "}
                        {(aiScanResult.height || aiScanResult.form_defaults?.height || "?")} x{" "}
                        {(aiScanResult.depth || aiScanResult.form_defaults?.depth || "?")}
                      </strong>
                    </div>
                    <div>
                      <span>{t.aiScanFound}</span>
                      <strong>{aiScanSession?.status || t.aiScanNeedsConfirmation}</strong>
                    </div>
                    <button
                      className="ghost-button"
                      disabled={loading}
                      onClick={handleApplyAiScanResult}
                      type="button"
                    >
                      <CheckCircle2 size={16} />
                      {t.aiScanApply}
                    </button>
                  </div>
                ) : null}

                {aiScanHistory.length ? (
                  <div className="service-sync-overview">
                    <span className="service-tree-badge subtle">{t.aiScanHistory}: {aiScanHistory.length}</span>
                  </div>
                ) : null}
              </div>
            ) : null}

            {projectStartMode === "premium" ? (
              <div className="premium-start-panel">
                <article>
                  <Wrench size={18} />
                  <strong>{t.projectPremiumOptionRecognition}</strong>
                  <span>{t.projectPremiumOptionRecognitionDescription}</span>
                </article>
                <article>
                  <FolderTree size={18} />
                  <strong>{t.projectPremiumOptionBatch}</strong>
                  <span>{t.projectPremiumOptionBatchDescription}</span>
                </article>
                <article>
                  <Blocks size={18} />
                  <strong>{t.projectPremiumOptionTemplates}</strong>
                  <span>{t.projectPremiumOptionTemplatesDescription}</span>
                </article>
                <button
                  className="primary-button"
                  disabled={!canUsePremiumStart}
                  onClick={() => setProjectStartMode("ai")}
                  type="button"
                >
                  {t.projectPremiumOpenUpload}
                </button>
              </div>
            ) : null}

            <div className="project-form-caption">
              <strong>{t.projectSpecificationTitle}</strong>
              <span>
                {projectStartMode === "premium"
                  ? t.projectStartPremiumDescription
                  : projectStartMode === "ai"
                    ? t.projectStartAiDescription
                    : t.projectStartManualDescription}
              </span>
            </div>

            <form className="create-project-form standalone-create-project-form" onSubmit={handleCreateProject}>
              <label>
                {t.projectName}
                <input
                  onChange={(event) =>
                    setNewProjectForm((current) => ({ ...current, projectName: event.target.value }))
                  }
                  type="text"
                  value={newProjectForm.projectName}
                />
              </label>
              {renderProjectOptionField({
                field: "projectType",
                mode: "projectType",
                target: "create",
                title: t.projectType,
                value: formatCatalogLabel(newProjectForm.projectType, t),
              })}
              <label>
                {t.client}
                <input
                  onChange={(event) =>
                    setNewProjectForm((current) => ({ ...current, clientName: event.target.value }))
                  }
                  type="text"
                  value={newProjectForm.clientName}
                />
              </label>
              <label>
                {t.room}
                <input
                  onChange={(event) =>
                    setNewProjectForm((current) => ({ ...current, roomName: event.target.value }))
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
                    setNewProjectForm((current) => ({ ...current, width: event.target.value }))
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
                    setNewProjectForm((current) => ({ ...current, height: event.target.value }))
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
                    setNewProjectForm((current) => ({ ...current, depth: event.target.value }))
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
                    setNewProjectForm((current) => ({ ...current, sections: event.target.value }))
                  }
                  required
                  type="number"
                  value={newProjectForm.sections}
                />
              </label>
              <label className="wide-field">
                {t.drawers}
                <input
                  onChange={(event) =>
                    setNewProjectForm((current) => ({ ...current, drawers: event.target.value }))
                  }
                  placeholder="1, 2, 3"
                  type="text"
                  value={newProjectForm.drawers}
                />
              </label>
              {renderProjectOptionField({
                field: "facadeMaterial",
                mode: "materials",
                target: "create",
                title: t.facadeMaterial,
                value: newProjectForm.facadeMaterial,
              })}
              {renderProjectOptionField({
                field: "insideMaterial",
                mode: "materials",
                target: "create",
                title: t.insideMaterial,
                value: newProjectForm.insideMaterial,
              })}
              {renderProjectOptionField({
                field: "facadeEdgeBanding",
                mode: "edgeBanding",
                target: "create",
                title: language === "uk" ? "Крайка фасаду" : "Facade edge banding",
                value: newProjectForm.facadeEdgeBanding || t.notSet,
              })}
              {renderProjectOptionField({
                field: "insideEdgeBanding",
                mode: "edgeBanding",
                target: "create",
                title: language === "uk" ? "Крайка корпусу" : "Inside edge banding",
                value: newProjectForm.insideEdgeBanding || t.notSet,
              })}
              {renderProjectOptionField({
                field: "slideType",
                mode: "slideType",
                target: "create",
                title: t.slideType,
                value: formatProjectSlideValue(newProjectForm.slideType, "create"),
              })}
              {renderProjectOptionField({
                field: "bottomType",
                mode: "bottomType",
                target: "create",
                title: language === "uk" ? "Вид шухлядки" : "Drawer type",
                value: formatProjectBottomValue(newProjectForm.bottomType),
              })}
              {renderProjectOptionField({
                field: "handleType",
                mode: "handles",
                target: "create",
                title: t.handleType,
                value: newProjectForm.handleType || t.notSet,
              })}
              {renderProjectOptionField({
                field: "handlePosition",
                mode: "handlePosition",
                target: "create",
                title: t.handlePosition,
                value: formatCatalogLabel(newProjectForm.handlePosition, t),
              })}
              <label className="wide-field">
                {t.notes}
                <input
                  onChange={(event) =>
                    setNewProjectForm((current) => ({ ...current, notes: event.target.value }))
                  }
                  type="text"
                  value={newProjectForm.notes}
                />
              </label>
              <button className="primary-button wide-button" disabled={loading} type="submit">
                <Plus size={18} />
                {t.createProject}
              </button>
            </form>
          </section>
        ) : activeView === "projectDetails" ? (
          <section className="detail-panel full-panel">
            {selectedProject ? (
              <>
                {!canEditSelectedProject ? (
                  <div className="readonly-note">
                    <strong>{t.readOnlyProject}</strong>
                    <span>{t.readOnlyProjectDescription}</span>
                  </div>
                ) : null}

                {activeProjectTab === "data" ? (
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
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "projectType",
                    mode: "projectType",
                    target: "edit",
                    title: t.projectType,
                    value: formatCatalogLabel(form.projectType, t),
                  })}
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
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "facadeMaterial",
                    mode: "materials",
                    target: "edit",
                    title: t.facadeMaterial,
                    value: form.facadeMaterial,
                  })}
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "facadeEdgeBanding",
                    mode: "edgeBanding",
                    target: "edit",
                    title: language === "uk" ? "Крайка фасаду" : "Facade edge banding",
                    value: form.facadeEdgeBanding || t.notSet,
                  })}
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "insideMaterial",
                    mode: "materials",
                    target: "edit",
                    title: t.insideMaterial,
                    value: form.insideMaterial,
                  })}
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "insideEdgeBanding",
                    mode: "edgeBanding",
                    target: "edit",
                    title: language === "uk" ? "Крайка корпусу" : "Inside edge banding",
                    value: form.insideEdgeBanding || t.notSet,
                  })}
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "slideType",
                    mode: "slideType",
                    target: "edit",
                    title: t.slideType,
                    value: formatProjectSlideValue(form.slideType, "edit"),
                  })}
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "bottomType",
                    mode: "bottomType",
                    target: "edit",
                    title: language === "uk" ? "Вид шухлядки" : "Drawer type",
                    value: formatProjectBottomValue(form.bottomType),
                  })}
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "handleType",
                    mode: "handles",
                    target: "edit",
                    title: t.handleType,
                    value: form.handleType,
                  })}
                  {renderProjectOptionField({
                    disabled: !canEditSelectedProject || loading,
                    field: "handlePosition",
                    mode: "handlePosition",
                    target: "edit",
                    title: t.handlePosition,
                    value: formatCatalogLabel(form.handlePosition, t),
                  })}
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
                ) : (
                  <article className="settings-card">
                    <div className="settings-card-header">
                      <h3>{t.projectDetails}</h3>
                      <p>{t.showProjectOverview}</p>
                    </div>
                  </article>
                )}
              </>
            ) : (
              <article className="settings-card">
                <div className="settings-card-header">
                  <h3>{t.selectProject}</h3>
                  <p>{t.projectNotFound}</p>
                </div>
              </article>
            )}
          </section>
        ) : activeView === "settings" ? (
          <section className="settings-panel full-panel">
            <div className="settings-grid">
              <article className="settings-card">
                <div className="settings-card-header">
                  <h3>{t.myData}</h3>
                </div>
                <form className="settings-info-grid" onSubmit={handleOwnProfileSave}>
                  <label>
                    {t.email}
                    <input disabled readOnly type="email" value={user?.email || ""} />
                  </label>
                  <label>
                    {t.role}
                    <input disabled readOnly type="text" value={user?.role || ""} />
                  </label>
                  <label>
                    {t.username}
                    <input
                      onChange={(event) =>
                        setOwnProfileForm((current) => ({ ...current, username: event.target.value }))
                      }
                      type="text"
                      value={ownProfileForm.username}
                    />
                  </label>
                  <label>
                    {t.phone}
                    <input
                      onChange={(event) =>
                        setOwnProfileForm((current) => ({ ...current, phone: event.target.value }))
                      }
                      type="text"
                      value={ownProfileForm.phone}
                    />
                  </label>
                  <label>
                    {t.city}
                    <select
                      onChange={(event) =>
                        setOwnProfileForm((current) => ({ ...current, city: event.target.value }))
                      }
                      value={ownProfileForm.city}
                    >
                      {(materialCityOptions.length ? materialCityOptions : DEFAULT_CITY_OPTIONS).map((city) => (
                        <option key={city} value={city}>
                          {formatCatalogLabel(city, t)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="settings-actions">
                    <button
                      className="ghost-button"
                      disabled={loading || !hasProfileChanges}
                      type="submit"
                    >
                      {t.saveProfile}
                    </button>
                  </div>
                </form>
                <form className="settings-info-grid settings-subform" onSubmit={handleOwnEmailChangeRequest}>
                  <label className="settings-full-row">
                    {t.newEmail}
                    <input
                      onChange={(event) =>
                        setEmailChangeForm({ newEmail: event.target.value })
                      }
                      placeholder={t.newEmail}
                      type="email"
                      value={emailChangeForm.newEmail}
                    />
                  </label>
                  <div className="settings-actions">
                    <button
                      className="ghost-button"
                      disabled={loading || !emailChangeForm.newEmail.trim()}
                      type="submit"
                    >
                      {t.requestEmailChange}
                    </button>
                  </div>
                </form>
              </article>
              <article className="settings-card">
                <div className="settings-card-header">
                  <h3>{t.changePassword}</h3>
                </div>
                <form className="settings-password-form" onSubmit={handleOwnPasswordChange}>
                  <label>
                    {t.currentPassword}
                    <input
                      autoComplete="current-password"
                      onChange={(event) =>
                        setOwnPasswordForm((current) => ({
                          ...current,
                          currentPassword: event.target.value,
                        }))
                      }
                      placeholder={t.currentPassword}
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
                        setOwnPasswordForm((current) => ({
                          ...current,
                          newPassword: event.target.value,
                        }))
                      }
                      placeholder={t.newPassword}
                      type="password"
                      value={ownPasswordForm.newPassword}
                    />
                  </label>
                  <div className="settings-actions">
                    <button
                      className="ghost-button"
                      disabled={
                        loading ||
                        !ownPasswordForm.currentPassword ||
                        !ownPasswordForm.newPassword ||
                        ownPasswordForm.newPassword.length < 8
                      }
                      type="submit"
                    >
                      {t.changePassword}
                    </button>
                  </div>
                </form>
              </article>
              <article className="settings-card settings-full-row">
                <div className="settings-card-header">
                  <h3>{t.viyarAccountTitle}</h3>
                </div>
                <form className="settings-info-grid" onSubmit={handleSaveViyarAuth}>
                  <label>
                    {t.viyarEmail}
                    <input
                      autoComplete="username"
                      onChange={(event) =>
                        setViyarAuthForm({
                          ...viyarAuthForm,
                          email: event.target.value,
                        })
                      }
                      placeholder={t.viyarEmail}
                      required
                      type="email"
                      value={viyarAuthForm.email}
                    />
                  </label>
                  <label>
                    {t.viyarPassword}
                    <input
                      autoComplete="new-password"
                      onChange={(event) =>
                        setViyarAuthForm({
                          ...viyarAuthForm,
                          password: event.target.value,
                        })
                      }
                      placeholder={
                        viyarAuth?.has_password
                          ? t.viyarPasswordSavedHint
                          : t.viyarPassword
                      }
                      type="password"
                      value={viyarAuthForm.password}
                    />
                    <small className="settings-hint">{t.viyarPasswordHint}</small>
                  </label>
                  <div className="settings-info-grid viyar-status-grid settings-full-row">
                    <label>
                      {t.viyarHasSavedPassword}
                      <input
                        disabled
                        readOnly
                        type="text"
                        value={viyarAuth?.has_password ? t.enabled : t.notSet}
                      />
                    </label>
                    <label>
                      {t.viyarHasSavedSession}
                      <input
                        disabled
                        readOnly
                        type="text"
                        value={viyarAuth?.has_cookie ? t.enabled : t.viyarNotConnected}
                      />
                    </label>
                    <label>
                      {t.viyarLastAuthStatus}
                      <input
                        disabled
                        readOnly
                        type="text"
                        value={viyarAuth?.last_auth_status || t.viyarNotConnected}
                      />
                    </label>
                    <label>
                      {t.viyarLastAuthAt}
                      <input
                        disabled
                        readOnly
                        type="text"
                        value={
                          viyarAuth?.last_auth_at
                            ? formatDateTime(viyarAuth.last_auth_at, t)
                            : t.notSet
                        }
                      />
                    </label>
                    <label className="settings-full-row">
                      {t.viyarLastAuthError}
                      <textarea
                        disabled
                        readOnly
                        rows={3}
                        value={viyarAuth?.last_auth_error || t.notSet}
                      />
                    </label>
                  </div>
                  <div className="settings-inline-status info settings-full-row">
                    {viyarNextStepLabel}
                  </div>
                  {viyarActionLabel ? (
                    <div className="settings-inline-status progress settings-full-row">
                      {viyarActionLabel}
                    </div>
                  ) : null}
                  <div className="settings-actions settings-full-row">
                    <button
                      className={`ghost-button ${viyarNextStep === "save" ? "recommended-action" : ""}`}
                      disabled={loading || !canSaveViyarAuth}
                      type="submit"
                    >
                      {viyarAction === "saving" ? t.viyarSavingCredentials : t.viyarSaveCredentials}
                    </button>
                    <button
                      className={`primary-button ${viyarNextStep === "connect" ? "recommended-action" : ""}`}
                      disabled={loading || !canConnectViyar}
                      onClick={handleRefreshViyarSession}
                      type="button"
                    >
                      {viyarAction === "connecting" ? t.viyarConnectingNow : t.viyarConnect}
                    </button>
                    <button
                      className={`ghost-button ${viyarNextStep === "sync" ? "recommended-action" : ""}`}
                      disabled={loading || !canSyncViyar}
                      onClick={handleSyncViyarPrices}
                      type="button"
                    >
                      {viyarAction === "syncing" ? t.viyarSyncingPricesNow : t.viyarSyncPrices}
                    </button>
                  </div>
                </form>
              </article>
            </div>
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
                  <option value="premium">premium</option>
                  <option value="pro">pro</option>
                  <option value="free">free</option>
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
                  <th>{t.userProfile}</th>
                  <th>{t.role}</th>
                  <th>{t.status}</th>
                  <th>{t.viyarConnection}</th>
                  <th>{t.action}</th>
                  <th>{t.access}</th>
                  <th>{t.password}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((targetUser) => (
                  <tr key={targetUser.id}>
                    <td>{targetUser.email}</td>
                    <td>
                      <div className="user-data-cell">
                        <span>
                          <strong>{t.username}:</strong> {targetUser.username || t.notSet}
                        </span>
                        <span>
                          <strong>{t.phone}:</strong> {targetUser.phone || t.notSet}
                        </span>
                        <span>
                          <strong>{t.telegram}:</strong> {targetUser.telegram_id || t.notSet}
                        </span>
                        <span>
                          <strong>{t.lastUsernameChange}:</strong>{" "}
                          {formatDateTime(targetUser.last_username_change_at, t)}
                        </span>
                      </div>
                    </td>
                    <td>
                      <select
                        disabled={loading || targetUser.id === user.id}
                        onChange={(event) =>
                          handleUserRoleChange(targetUser, event.target.value)
                        }
                        value={targetUser.role}
                      >
                        <option value="admin">admin</option>
                        <option value="premium">premium</option>
                        <option value="pro">pro</option>
                        <option value="free">free</option>
                      </select>
                    </td>
                    <td>{targetUser.is_active ? t.active : t.inactive}</td>
                    <td>
                      <div className="user-data-cell">
                        <span>
                          <strong>{t.email}:</strong> {targetUser.viyar_email || t.notSet}
                        </span>
                        <span>
                          <strong>{t.session}:</strong>{" "}
                          {targetUser.viyar_has_cookie ? t.connected : t.notConnected}
                        </span>
                        <span>
                          <strong>{t.authStatus}:</strong>{" "}
                          {targetUser.viyar_last_auth_status || t.notSet}
                        </span>
                        <span>
                          <strong>{t.lastAuth}:</strong>{" "}
                          {formatDateTime(targetUser.viyar_last_auth_at, t)}
                        </span>
                        <span>
                          <strong>{t.authError}:</strong>{" "}
                          {targetUser.viyar_last_auth_error || t.noError}
                        </span>
                      </div>
                    </td>
                    <td>
                      <button
                        className="ghost-button"
                        disabled={loading}
                        onClick={() => openUserDetails(targetUser)}
                        type="button"
                      >
                        {t.openUserCard}
                      </button>
                    </td>
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
        ) : isCatalogHubView ? (
          <section className="table-panel full-panel">
            <div className="catalog-hub-layout">
              <article className="catalog-hub-card catalog-hub-card-hero">
                <div className="service-catalog-title">
                  <h3>{t.catalogHubTitle}</h3>
                  <p>{t.catalogHubDescription}</p>
                </div>
                <div className="catalog-hub-quick-grid">
                  {[
                    {
                      key: "materials",
                      count: materialItems.length,
                      description: t.catalogMaterialsDescription,
                      label: t.catalogMaterials,
                      onClick: () => switchView("catalogMaterials"),
                    },
                    {
                      key: "viyar",
                      count: viyarServiceCounts.services,
                      description: t.viyarServicesDescription,
                      label: t.catalogViyar,
                      onClick: () => switchView("catalogViyar"),
                    },
                    {
                      key: "manual",
                      count: manualServiceItems.length,
                      description: t.catalogManualDescription,
                      label: t.catalogManual,
                      onClick: () => switchView("catalogManual"),
                    },
                    {
                      key: "values",
                      count: catalogItems.length,
                      description: t.catalogValuesDescription,
                      label: t.catalogValues,
                      onClick: () => switchView("catalogValues"),
                    },
                  ].map((item) => {
                    const visual = CATALOG_TILE_VISUALS[item.key];
                    const Icon = visual.icon;

                    return (
                      <button
                        className="catalog-choice-card"
                        key={item.key}
                        onClick={item.onClick}
                        type="button"
                      >
                        <span
                          className="catalog-choice-art"
                          style={{ "--catalog-accent": visual.accent }}
                        >
                          <Icon size={34} />
                        </span>
                        <div className="catalog-choice-copy">
                          <strong>{item.label}</strong>
                          <span>{item.description}</span>
                        </div>
                        <div className="catalog-choice-meta">
                          <span className="service-tree-badge subtle">{item.count}</span>
                          <span>{t.openDirectory}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </article>

              <article className="catalog-hub-card">
                <div className="service-catalog-header">
                  <div className="service-catalog-title">
                    <h3>{t.catalogBrowseCategories}</h3>
                    <p>{t.viyarServicesDescription}</p>
                  </div>
                </div>
                <div className="catalog-category-grid">
                  {viyarTopFolders.map((folder) => {
                    const visual = VIYAR_FOLDER_TILE_VISUALS[folder.external_code] || {
                      accent: "#2f8ecb",
                      icon: FolderTree,
                    };
                    const Icon = visual.icon;

                    return (
                      <button
                        className="catalog-category-card"
                        key={folder.external_code}
                        onClick={() => openViyarFolderCatalog(folder.external_code)}
                        type="button"
                      >
                        <span
                          className="catalog-category-art"
                          style={{ "--catalog-accent": visual.accent }}
                        >
                          <Icon size={44} />
                        </span>
                        <div className="catalog-category-copy">
                          <strong>{folder.name}</strong>
                          <span>{folder.description}</span>
                        </div>
                        <span className="service-tree-badge subtle">
                          {countServiceTreeItems(folder.children || [])}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </article>
            </div>
          </section>
        ) : isCatalogMaterialsView ? (
          <section className="table-panel full-panel">
            <article className="catalog-card service-catalog-card service-catalog-card-full">
              <div className="service-catalog-header">
                <div className="service-catalog-title">
                  <h3>{t.catalogMaterials}</h3>
                  <p>{t.catalogMaterialsDescription}</p>
                </div>
                <div className="service-catalog-header-actions">
                  <span className="service-tree-badge subtle">
                    {t.currentCity}: {formatCatalogLabel(materialSelectedCity || user?.city, t)}
                  </span>
                  <span className="service-tree-badge subtle">
                    {materialItems.length} {t.materialsCount}
                  </span>
                </div>
              </div>

              <div className="materials-toolbar">
                <label className="service-catalog-search">
                  <Search size={16} />
                  <input
                    onChange={(event) => setMaterialSearch(event.target.value)}
                    placeholder={t.viyarSearch}
                    type="search"
                    value={materialSearch}
                  />
                </label>
                <label className="materials-filter">
                  <span>{t.materialCategory}</span>
                  <select
                    onChange={(event) => setMaterialCategoryFilter(event.target.value)}
                    value={materialCategoryFilter}
                  >
                    {materialCategories.map((category) => (
                      <option key={category.code} value={category.code}>
                        {formatCatalogLabel(category.code, t)}
                      </option>
                    ))}
                  </select>
                </label>
                <form className="materials-city-form" onSubmit={handleMaterialCitySave}>
                  <label className="materials-filter">
                    <span>{t.city}</span>
                    <select
                      onChange={(event) => setMaterialSelectedCity(event.target.value)}
                      value={materialSelectedCity}
                    >
                      <option value="">{t.notSet}</option>
                      {(materialCityOptions.length ? materialCityOptions : DEFAULT_CITY_OPTIONS).map((city) => (
                        <option key={city} value={city}>
                          {formatCatalogLabel(city, t)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    className="ghost-button"
                    disabled={loading || materialSelectedCity === (user?.city || "")}
                    type="submit"
                  >
                    {t.saveCity}
                  </button>
                </form>
                <button
                  className="ghost-button"
                  disabled={loading}
                  onClick={() => loadMaterialsCatalog(token)}
                  type="button"
                >
                  <RefreshCw size={16} />
                  {t.refresh}
                </button>
              </div>

              {canEditMaterialCatalog ? (
                <>
                  <form className="materials-import-form" onSubmit={handleImportMaterial}>
                    <div className="materials-mode-switch" role="tablist" aria-label={t.catalogMaterials}>
                      <button
                        className={`ghost-button${materialCreateMode === "source" ? " active" : ""}`}
                        onClick={() => setMaterialCreateMode("source")}
                        type="button"
                      >
                        {t.materialModeLinked}
                      </button>
                      <button
                        className={`ghost-button${materialCreateMode === "manual" ? " active" : ""}`}
                        onClick={() => setMaterialCreateMode("manual")}
                        type="button"
                      >
                        {t.materialModeManual}
                      </button>
                    </div>
                    {materialCreateMode === "source" ? (
                      <>
                        <label>
                          {t.materialAddArticle}
                          <input
                            onChange={(event) => setNewMaterialArticle(event.target.value)}
                            placeholder={t.materialAddArticlePlaceholder}
                            type="text"
                            value={newMaterialArticle}
                          />
                        </label>
                        <label>
                          {t.materialAddUrl}
                          <input
                            onChange={(event) => setNewMaterialSourceUrl(event.target.value)}
                            placeholder={t.materialAddUrlPlaceholder}
                            type="url"
                            value={newMaterialSourceUrl}
                          />
                        </label>
                        {canManageSystemMaterials(user) ? (
                          <label className="material-inline-check">
                            <input
                              checked={newMaterialIsDefault}
                              onChange={(event) => setNewMaterialIsDefault(event.target.checked)}
                              type="checkbox"
                            />
                            {t.materialDefaultForAll}
                          </label>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <label>
                          {t.materialManualName}
                          <input
                            onChange={(event) => setNewMaterialName(event.target.value)}
                            placeholder={t.materialManualNamePlaceholder}
                            type="text"
                            value={newMaterialName}
                          />
                        </label>
                        <label>
                          {t.materialManualPrice}
                          <input
                            min="0"
                            onChange={(event) => setNewMaterialPrice(event.target.value)}
                            placeholder="0"
                            step="0.01"
                            type="number"
                            value={newMaterialPrice}
                          />
                        </label>
                        <label>
                          {t.materialManualImage}
                          <input
                            accept="image/*"
                            onChange={handleMaterialImageUpload}
                            type="file"
                          />
                          <small className="settings-hint">
                            {newMaterialImageUrl ? t.fittingImageSelected : t.materialManualImageHint}
                          </small>
                        </label>
                      </>
                    )}
                    <label>
                      {t.city}
                      <input disabled readOnly type="text" value={formatCatalogLabel(materialSelectedCity || user?.city, t)} />
                    </label>
                    <button
                      className="primary-button"
                      disabled={
                        loading || (
                          materialCreateMode === "source"
                            ? (!newMaterialArticle.trim() || !newMaterialSourceUrl.trim())
                            : (!newMaterialName.trim() || newMaterialPrice === "")
                        )
                      }
                      type="submit"
                    >
                      <Plus size={16} />
                      {materialCreateMode === "source" ? t.materialAdd : t.materialManualAdd}
                    </button>
                  </form>
                  {activeMaterialImportJob ? (
                    <div className={`material-import-status material-import-status-${activeMaterialImportJob.status || "queued"}`}>
                      <div className="material-import-status-header">
                        <strong>{t.materialImportStatusTitle}</strong>
                        <span className={`service-tree-badge subtle material-import-state-badge material-import-state-badge-${activeMaterialImportJob.status || "queued"}`}>
                          <span className="material-import-state-dot" />
                          {materialImportStateLabel}
                        </span>
                      </div>
                      <div className="material-import-status-grid">
                        <div>
                          <span>{t.materialImportArticle}</span>
                          <b>{activeMaterialImportJob.article}</b>
                        </div>
                        <div>
                          <span>{t.materialImportAttempts}</span>
                          <b>
                            {activeMaterialImportJob.attempt_count} / {activeMaterialImportJob.max_attempts}
                          </b>
                        </div>
                        <div>
                          <span>{t.materialImportNextRetry}</span>
                          <b>
                            {activeMaterialImportJob.next_retry_at
                              ? formatDateTimeValue(activeMaterialImportJob.next_retry_at)
                              : t.notSet}
                          </b>
                        </div>
                        <div>
                          <span>{t.materialImportStrategy || "Стратегія"}</span>
                          <b>{activeMaterialImportJob.last_strategy || t.notSet}</b>
                        </div>
                        <div>
                          <span>{t.materialImportSourceUrl || "Сторінка"}</span>
                          <b className="material-import-source-url">
                            {activeMaterialImportJob.last_source_url || t.notSet}
                          </b>
                        </div>
                      </div>
                      {activeMaterialImportJob.last_error ? (
                        <div className="material-import-status-error">
                          <span>{t.materialImportLastError}</span>
                          <p>{formatMaterialImportDiagnostic(activeMaterialImportJob.last_error, 420)}</p>
                        </div>
                      ) : null}
                      {Array.isArray(activeMaterialImportJob.debug_trace) && activeMaterialImportJob.debug_trace.length ? (
                        <details className="material-import-status-trace">
                          <summary>{t.materialImportTrace || "Технічні деталі"}</summary>
                          <ul>
                            {activeMaterialImportJob.debug_trace.slice(-8).map((entry, index) => (
                              <li key={`${entry.stage || "trace"}-${index}`}>
                                <b>{entry.stage || "step"}</b>
                                {entry.message ? `: ${formatMaterialImportDiagnostic(entry.message)}` : ""}
                                {!entry.message && entry.url ? `: ${entry.url}` : ""}
                                {!entry.message && !entry.url && entry.product_url ? `: ${entry.product_url}` : ""}
                              </li>
                            ))}
                          </ul>
                        </details>
                      ) : null}
                    </div>
                  ) : null}
                </>
              ) : null}

              {materialItems.length ? (
                <div className="material-card-grid">
                  {materialItems.map((item) => {
                    const sourceMeta = getMaterialSourceMeta(item, t);
                    const canManageItem = canEditMaterialItem(user, item);

                    return (
                    <article
                      className="material-card material-card-clickable"
                      key={item.id}
                      onClick={() => openMaterialDetails(item)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          openMaterialDetails(item);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      {canManageItem ? (
                        <div className="material-card-menu">
                          <button
                            aria-label={t.refreshFromViyar}
                            className="icon-button material-card-menu-trigger"
                            onClick={(event) => {
                              event.stopPropagation();
                              setOpenMaterialMenuId((current) =>
                                current === item.id ? "" : item.id,
                              );
                            }}
                            type="button"
                          >
                            <MoreHorizontal size={16} />
                          </button>
                          {openMaterialMenuId === item.id ? (
                            <div className="material-card-menu-dropdown">
                              {item.source_url ? (
                              <button
                                className="material-card-menu-action"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  handleRefreshMaterial(item);
                                }}
                                type="button"
                              >
                                <RefreshCw size={14} />
                                {t.refreshFromViyar}
                              </button>
                              ) : null}
                              <button
                                className="material-card-menu-action danger"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  openDeleteMaterialConfirm(item);
                                }}
                                type="button"
                              >
                                <Trash2 size={14} />
                                {t.deleteMaterial}
                              </button>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="material-card-media">
                        {buildMaterialImageCandidates(item).length ? (
                          <>
                            <img
                              alt={item.name || item.article}
                              data-fallback-index="0"
                              decoding="async"
                              loading="lazy"
                              onError={(event) => handleMaterialImageError(event, item, token)}
                              src={buildMaterialImageCandidates(item, token)[0]}
                            />
                            <div className="material-card-placeholder" hidden>
                              {formatCatalogLabel(item.category, t)}
                            </div>
                          </>
                        ) : (
                          <div className="material-card-placeholder">{formatCatalogLabel(item.category, t)}</div>
                        )}
                      </div>
                      <div className="material-card-body">
                        <div className="material-card-topline">
                          <span className="service-tree-badge subtle">
                            {formatCatalogLabel(item.category, t)}
                          </span>
                          {item.display_article ? (
                            <span className="material-card-article">{item.display_article}</span>
                          ) : null}
                        </div>
                        <strong>{item.name || item.article}</strong>
                        <div className="material-card-price">
                          <span>{t.materialPriceForCity}</span>
                          <b>
                            {item.current_price !== null && item.current_price !== undefined
                              ? `${item.current_price} UAH`
                              : t.notSet}
                          </b>
                        </div>
                        <div className="material-card-meta">
                          {renderSourceBadge(sourceMeta)}
                        </div>
                      </div>
                    </article>
                  )})}
                </div>
              ) : (
                <div className="empty-state compact-empty-state">
                  <span>{t.catalogMaterialsDescription}</span>
                </div>
              )}
            </article>
          </section>
        ) : isCatalogFittingsView || isCatalogFastenersView ? (
          <section className="table-panel full-panel">
            <article className="catalog-card service-catalog-card service-catalog-card-full">
              <div className="catalog-page-header">
                <div className="service-catalog-title">
                  <h3>{t.catalogFittings}</h3>
                  <p>
                    {t.fittingsManageDescription}
                  </p>
                </div>
                <div className="service-catalog-header-actions">
                  <span className="service-tree-badge subtle">
                    {t.currentCity}: {formatCatalogLabel(materialSelectedCity || user?.city, t)}
                  </span>
                  <span className="service-tree-badge subtle">
                    {activeFittingCategory ? visibleFittingItems.length : visibleFittingCategories.length}{" "}
                    {activeFittingCategory ? t.fittingsCount : t.fittingCategoriesCount}
                  </span>
                </div>
              </div>

              <div className="materials-toolbar fittings-toolbar">
                <label className="service-catalog-search">
                  <Search size={16} />
                  <input
                    onChange={(event) => setFittingSearch(event.target.value)}
                    placeholder={t.viyarSearch}
                    type="search"
                    value={fittingSearch}
                  />
                </label>
                <label>
                  <span>{t.city}</span>
                  <select
                    onChange={(event) => {
                      const nextCity = event.target.value;
                      setMaterialSelectedCity(nextCity);
                      loadFittingsCatalog(token, { city: nextCity });
                    }}
                    value={materialSelectedCity || user?.city || ""}
                  >
                    <option value="">{t.notSet}</option>
                    {materialCityOptions.map((cityOption) => (
                      <option key={cityOption} value={cityOption}>
                        {formatCatalogLabel(cityOption, t)}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="ghost-button"
                  disabled={loading}
                  onClick={() => loadFittingsCatalog(token)}
                  type="button"
                >
                  <RefreshCw size={16} />
                  {t.refresh}
                </button>
              </div>

              {!activeFittingCategory ? (
                <div className="fitting-category-grid">
                  {visibleFittingCategories.map((category) => {
                    const visual = FITTING_CATEGORY_VISUALS[category.code] || {
                      accent: "#64748b",
                      icon: Package,
                    };
                    const Icon = visual.icon;
                    const hasPreviewImage = Boolean(visual.image);

                    return (
                      <button
                        className="catalog-choice-card fitting-category-card"
                        key={category.code}
                        onClick={() => {
                          setSelectedFittingCategory(category.code);
                          setFittingViewMode("rows");
                          setNewFittingForm((current) => ({
                            ...current,
                            fitting_group: category.group,
                            fitting_type: category.code,
                          }));
                        }}
                        type="button"
                      >
                        {hasPreviewImage ? (
                          <span
                            className="catalog-choice-media"
                            style={{ "--catalog-accent": visual.accent }}
                          >
                            <img
                              alt={category.name}
                              loading="lazy"
                              src={visual.image}
                            />
                          </span>
                        ) : (
                          <span
                            className="catalog-choice-art"
                            style={{ "--catalog-accent": visual.accent }}
                          >
                            <Icon size={30} />
                          </span>
                        )}
                        <div className="fitting-category-content">
                          <div className="catalog-choice-copy">
                            <strong>{category.name}</strong>
                            <span>{category.description}</span>
                          </div>
                          <div className="catalog-choice-meta">
                            <span className="service-tree-badge subtle">{category.item_count}</span>
                            <span>{category.group_name}</span>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="fitting-category-detail-head">
                  <button
                    className="ghost-button"
                    onClick={() => {
                      setSelectedFittingCategory("");
                      setFittingViewMode("rows");
                    }}
                    type="button"
                  >
                    <ChevronLeft size={16} />
                    {t.backToFittingCategories}
                  </button>
                  <div className="service-catalog-title compact">
                    <strong>{currentFittingCategoryMeta?.name || t.catalogFittings}</strong>
                    <span>{currentFittingCategoryMeta?.description || ""}</span>
                  </div>
                  <div className="fittings-view-toggle" role="tablist" aria-label={t.catalogBrowseCategories}>
                    <button
                      className={`icon-button${fittingViewMode === "rows" ? " active" : ""}`}
                      onClick={() => setFittingViewMode("rows")}
                      title={t.fittingRowsView}
                      type="button"
                    >
                      <Blocks size={16} />
                    </button>
                    <button
                      className={`icon-button${fittingViewMode === "cards" ? " active" : ""}`}
                      onClick={() => setFittingViewMode("cards")}
                      title={t.fittingCardsView}
                      type="button"
                    >
                      <LayoutGrid size={16} />
                    </button>
                  </div>
                </div>
              )}

              {activeFittingCategory && canEditOwnFittings ? (
                <form className="fitting-create-form" onSubmit={handleCreateFitting}>
                  <label>
                    <span>{t.fittingType}</span>
                    <select
                      onChange={(event) =>
                        setNewFittingForm((current) => {
                          const category = visibleFittingCategories.find(
                            (item) => item.code === event.target.value,
                          );

                          return {
                            ...current,
                            fitting_group: category?.group || current.fitting_group,
                            fitting_type: event.target.value,
                          };
                        })
                      }
                      value={newFittingForm.fitting_type}
                    >
                      {(visibleFittingCategories.length ? visibleFittingCategories : fittingCategories).map((category) => (
                        <option key={category.code} value={category.code}>
                          {category.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>{t.fittingArticle}</span>
                    <input
                      onChange={(event) =>
                        setNewFittingForm((current) => ({ ...current, article: event.target.value }))
                      }
                      type="text"
                      value={newFittingForm.article}
                    />
                  </label>
                  <label>
                    <span>{t.city}</span>
                    <select
                      onChange={(event) =>
                        setNewFittingForm((current) => ({ ...current, city: event.target.value }))
                      }
                      value={newFittingForm.city}
                    >
                      <option value="">{t.notSet}</option>
                      {materialCityOptions.map((cityOption) => (
                        <option key={cityOption} value={cityOption}>
                          {formatCatalogLabel(cityOption, t)}
                        </option>
                      ))}
                    </select>
                  </label>
                  {canEditSystemFittings ? (
                    <label className="toggle-label">
                      <input
                        checked={Boolean(newFittingForm.is_system)}
                        onChange={(event) =>
                          setNewFittingForm((current) => ({
                            ...current,
                            image_url: event.target.checked ? "" : current.image_url,
                            is_system: event.target.checked,
                            name: event.target.checked ? "" : current.name,
                            price: event.target.checked ? "" : current.price,
                            source_url: event.target.checked ? current.source_url : "",
                          }))
                        }
                        type="checkbox"
                      />
                      {newFittingForm.is_system ? t.fittingSystemScope : t.fittingCustomScope}
                    </label>
                  ) : null}
                  {newFittingForm.is_system ? (
                    <>
                      <label>
                        <span>{t.fittingSourceUrl}</span>
                        <input
                          onChange={(event) =>
                            setNewFittingForm((current) => ({ ...current, source_url: event.target.value }))
                          }
                          placeholder="https://..."
                          type="url"
                          value={newFittingForm.source_url}
                        />
                      </label>
                      <div className="fitting-form-note">
                        {t.fittingSystemHint}
                      </div>
                    </>
                  ) : (
                    <>
                      <label>
                        <span>{t.fittingName}</span>
                        <input
                          onChange={(event) =>
                            setNewFittingForm((current) => ({ ...current, name: event.target.value }))
                          }
                          placeholder={t.fittingName}
                          type="text"
                          value={newFittingForm.name}
                        />
                      </label>
                      <label>
                        <span>{t.fittingPrice}</span>
                        <input
                          min="0"
                          onChange={(event) =>
                            setNewFittingForm((current) => ({ ...current, price: event.target.value }))
                          }
                          step="0.01"
                          type="number"
                          value={newFittingForm.price}
                        />
                      </label>
                      <label>
                        <span>{t.fittingImage}</span>
                        <input
                          accept="image/*"
                          onChange={handleFittingImageSelected}
                          type="file"
                        />
                      </label>
                      <div className="fitting-form-note">
                        {newFittingForm.image_url ? t.fittingImageSelected : t.fittingCustomHint}
                      </div>
                    </>
                  )}
                  <button className="primary-button" disabled={loading} type="submit">
                    <Plus size={16} />
                    {newFittingForm.is_system ? t.fittingAddSystem : t.fittingAddCustom}
                  </button>
                </form>
              ) : null}

              {activeFittingCategory ? (
              <div className="fittings-table-shell">
                {visibleFittingItems.length ? (
                  fittingViewMode === "cards" ? (
                    <div className="fittings-card-grid">
                      {visibleFittingItems.map((item) => {
                        const sourceMeta = getFittingSourceMeta(item);
                        return (
                          <article className="fitting-item-card" key={item.id}>
                            <div className="fitting-item-card-head">
                              <div className="fitting-item-card-preview">
                                {buildFittingImageCandidates(item).length ? (
                                  <img
                                    alt={item.name || item.article || t.catalogFittings}
                                    data-fallback-index="0"
                                    decoding="async"
                                    loading="lazy"
                                    onError={(event) => handleFittingImageError(event, item)}
                                    src={buildFittingImageCandidates(item)[0]}
                                  />
                                ) : (
                                  <Package size={24} />
                                )}
                              </div>
                              {canDeleteFittingItem(user, item) ? (
                                <div className="material-card-menu fitting-row-menu">
                                  <button
                                    className="icon-button material-card-menu-trigger"
                                    onClick={() =>
                                      setOpenFittingMenuId((current) => (current === item.id ? "" : item.id))
                                    }
                                    type="button"
                                  >
                                    <MoreHorizontal size={16} />
                                  </button>
                                  {openFittingMenuId === item.id ? (
                                    <div className="material-card-menu-dropdown">
                                      <button
                                        className="material-card-menu-action danger"
                                        onClick={() => openDeleteFittingConfirm(item)}
                                        type="button"
                                      >
                                        <Trash2 size={14} />
                                        {t.fittingDelete}
                                      </button>
                                    </div>
                                  ) : null}
                                </div>
                              ) : null}
                            </div>
                            <div className="fitting-item-card-copy">
                              <strong>{item.name || item.code || item.article}</strong>
                              <div className="fittings-table-badges">
                                {renderSourceBadge(sourceMeta)}
                              </div>
                            </div>
                            <div className="fitting-item-card-meta">
                              <span>{t.fittingArticle}: {item.article || t.notSet}</span>
                              <span>{t.fittingCode}: {item.code || t.notSet}</span>
                              <span>{t.city}: {formatCatalogLabel(item.city, t)}</span>
                              <span>{t.fittingPrice}: {item.price ?? t.notSet}</span>
                              <span>{t.fittingStock}: {item.stock || t.notSet}</span>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  ) : (
                    <>
                      <div className="fittings-table-header">
                        <span>{currentFittingCategoryMeta?.name || t.catalogFittings}</span>
                        <span>{t.fittingArticle}</span>
                        <span>{t.fittingCode}</span>
                        <span>{t.city}</span>
                        <span>{t.fittingPrice}</span>
                        <span>{t.fittingStock}</span>
                        <span>{t.fittingSource}</span>
                      </div>

                      <div className="fittings-table-list">
                        {visibleFittingItems.map((item) => {
                          const sourceMeta = getFittingSourceMeta(item);

                          return (
                            <article className="fittings-table-row" key={item.id}>
                              <div className="fittings-table-name">
                                <div className="fittings-table-name-main">
                                  <div className="fittings-table-thumb">
                                    {buildFittingImageCandidates(item).length ? (
                                      <img
                                        alt={item.name || item.article || t.catalogFittings}
                                        data-fallback-index="0"
                                        decoding="async"
                                        loading="lazy"
                                        onError={(event) => handleFittingImageError(event, item)}
                                        src={buildFittingImageCandidates(item)[0]}
                                      />
                                    ) : (
                                      <Package size={18} />
                                    )}
                                  </div>
                                  <div className="fittings-table-name-copy">
                                    <strong>{item.name || item.code || item.article}</strong>
                                    <div className="fittings-table-badges">
                                      {item.owner_user_id && !item.is_system ? (
                                        <span className="service-tree-badge subtle">{t.forCalculation}</span>
                                      ) : null}
                                    </div>
                                  </div>
                                </div>
                                {canDeleteFittingItem(user, item) ? (
                                  <div className="material-card-menu fitting-row-menu">
                                    <button
                                      className="icon-button material-card-menu-trigger"
                                      onClick={() =>
                                        setOpenFittingMenuId((current) => (current === item.id ? "" : item.id))
                                      }
                                      type="button"
                                    >
                                      <MoreHorizontal size={16} />
                                    </button>
                                    {openFittingMenuId === item.id ? (
                                      <div className="material-card-menu-dropdown">
                                        <button
                                          className="material-card-menu-action danger"
                                          onClick={() => openDeleteFittingConfirm(item)}
                                          type="button"
                                        >
                                          <Trash2 size={14} />
                                          {t.fittingDelete}
                                        </button>
                                      </div>
                                    ) : null}
                                  </div>
                                ) : null}
                              </div>
                              <span>{item.article || t.notSet}</span>
                              <span>{item.code || t.notSet}</span>
                              <span>{formatCatalogLabel(item.city, t)}</span>
                              <span>{item.price ?? t.notSet}</span>
                              <span>{item.stock || t.notSet}</span>
                              {renderSourceBadge(sourceMeta)}
                            </article>
                          );
                        })}
                      </div>
                    </>
                  )
                ) : (
                  <div className="empty-state compact-empty-state">
                    <span>{t.fittingNoItems}</span>
                  </div>
                )}
              </div>
              ) : null}
            </article>
          </section>
        ) : isCatalogHolesView ? (
          <section className="table-panel full-panel">
            <article className="catalog-card service-catalog-card service-catalog-card-full holes-view-card">
              <div className="catalog-page-header">
                <div className="service-catalog-title">
                  <h3>{t.holeTabTitle}</h3>
                  <p>{t.holeTabDescription}</p>
                </div>
                <div className="service-catalog-header-actions">
                  <span className="service-tree-badge subtle">
                    {t.holeReadOnlyBadge}
                  </span>
                  <button
                    className="primary-button compact-button"
                    disabled={loading || !holeSelectedFittingId}
                    onClick={openHoleTemplateCreateForm}
                    type="button"
                  >
                    <Plus size={16} />
                    {t.holeTemplateCreateTitle}
                  </button>
                  <button
                    className="ghost-button"
                    disabled={loading || !holeSelectedFittingId}
                    onClick={() => loadHoleTemplates(token, holeSelectedFittingId)}
                    type="button"
                  >
                    <RefreshCw size={16} />
                    {t.holeTemplateRefresh}
                  </button>
                </div>
              </div>

              <div className="holes-selector-grid">
                <label className="service-catalog-search holes-search">
                  <Search size={16} />
                  <input
                    onChange={(event) => setFittingSearch(event.target.value)}
                    placeholder={t.holeTabSearchPlaceholder}
                    type="search"
                    value={fittingSearch}
                  />
                </label>
                <label className="holes-select">
                  <span>{t.holeTemplateFitting}</span>
                  <select
                    onChange={(event) => handleHoleFittingChange(event.target.value)}
                    value={holeSelectedFittingId}
                  >
                    <option value="">{t.holeTemplateSelectFitting}</option>
                    {fittingItems.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name || item.article || item.code || item.id}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="holes-select">
                  <span>{t.holePointTemplate}</span>
                  <select
                    disabled={!holeTemplateItems.length}
                    onChange={(event) => handleHoleTemplateChange(event.target.value)}
                    value={holeSelectedTemplateId}
                  >
                    <option value="">{t.holeTemplateSelectTemplate}</option>
                    {holeTemplateItems.map((template) => (
                      <option key={template.id} value={template.id}>
                        {template.name || `${t.holePointTemplate} ${template.id}`}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="holes-grid">
                <div className="holes-left-column">
                  {renderHoleWorkspaceFittingInfo(selectedHoleFitting)}
                  {renderHoleWorkspaceConnectionVariantCards()}
                  <section className="holes-panel">
                  <div className="holes-panel-header">
                    <h4>{t.holeTemplateTitle}</h4>
                    <span className="service-tree-badge subtle">
                      {holeTemplateItems.length}
                    </span>
                  </div>
                  {holeSelectedFittingId ? (
                    holeTemplateItems.length ? (
                      <div className="holes-table-shell">
                        <div className="holes-table-header">
                          <span>{t.holeTemplateColumnId}</span>
                          <span>{t.holeTemplateColumnName}</span>
                          <span>{t.holeTemplateColumnType}</span>
                          <span>{t.holeTemplateColumnSide}</span>
                          <span>{t.holeTemplateColumnSystem}</span>
                          <span>{t.holeTemplateColumnDefault}</span>
                          <span>{t.holeTemplateColumnActive}</span>
                          <span>{t.holeTemplateColumnNotes}</span>
                        </div>
                        <div className="holes-table-list">
                          {holeTemplateItems.map((template) => {
                            const isSelected = String(template.id) === String(holeSelectedTemplateId);

                            return (
                              <article
                                className={`holes-table-row${isSelected ? " active" : ""}`}
                                key={template.id}
                              >
                                <div className="holes-template-id-cell">
                                  <span className="holes-template-id-value">{template.id}</span>
                                  <button
                                    aria-label={t.holeTemplateEdit}
                                    className="ghost-button compact-button holes-template-edit-button"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      openHoleTemplateEditForm(template);
                                    }}
                                    title={t.holeTemplateEdit}
                                    type="button"
                                  >
                                    <Pencil size={14} />
                                  </button>
                                </div>
                                <span>{template.name || "—"}</span>
                                <span>{formatHoleTemplateType(template.template_type, t)}</span>
                                <span>{formatHolePointSide(template.side, t)}</span>
                                <span>{formatHoleTemplateCoordinateSystem(template.coordinate_system, t)}</span>
                                <span>{template.is_default ? t.holePointSelectionYes : t.holePointSelectionNo}</span>
                                <span>{template.is_active ? t.holePointSelectionYes : t.holePointSelectionNo}</span>
                                <span>{template.notes || "—"}</span>
                              </article>
                            );
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="empty-state compact-empty-state">
                        <span>{t.holeTemplateEmpty}</span>
                      </div>
                    )
                  ) : (
                    <div className="empty-state compact-empty-state">
                      <span>{t.holeTemplateSelectFitting}</span>
                    </div>
                  )}
                </section>

                <section className="holes-panel">
                  <div className="holes-panel-header">
                    <h4>{t.holeTabPoints}</h4>
                    <span className="service-tree-badge subtle">
                      {holePoints.length}
                    </span>
                    <button
                      className="ghost-button compact-button"
                      disabled={loading || !holeSelectedTemplateId}
                      onClick={openHolePointCreateForm}
                      type="button"
                    >
                      <Plus size={14} />
                      {t.holePointAdd}
                    </button>
                  </div>
                  {holeSelectedTemplate ? (
                    holePoints.length ? (
                      <div className="holes-table-shell">
                        <div className="holes-points-table-header">
                          <span>{t.holePointColumnId}</span>
                          <span>{t.holePointColumnLabel}</span>
                          <span>x</span>
                          <span>y</span>
                          <span>z</span>
                          <span>Ø</span>
                          <span>{t.holePointColumnDepth}</span>
                          <span>{t.holePointColumnSide}</span>
                          <span>{t.holePointColumnOperation}</span>
                          <span>{t.holePointColumnOrder}</span>
                          <span>{t.holePointQuantity}</span>
                          <span>{t.holePointMirrored}</span>
                          <span>{t.holePointNotes}</span>
                        </div>
                        <div className="holes-table-list">
                          {holePoints.map((point) => (
                            <article
                              className={`holes-points-table-row${String(hoveredHolePointId) === String(point.id) ? " is-hovered" : ""}`}
                              key={point.id}
                              onMouseEnter={() => setHoveredHolePointId(String(point.id))}
                              onMouseLeave={() => setHoveredHolePointId("")}
                            >
                              <div className="holes-point-id-cell">
                                <span>{point.id}</span>
                                <button
                                  aria-label={t.holePointEdit}
                                  className="ghost-button compact-button holes-point-edit-button"
                                  onClick={() => openHolePointEditForm(point)}
                                  title={t.holePointEdit}
                                  type="button"
                                >
                                  <Pencil size={14} />
                                </button>
                              </div>
                               <span className="holes-point-label-cell">{point.label || "—"}</span>
                              <span>{point.x_mm ?? "—"}</span>
                              <span>{point.y_mm ?? "—"}</span>
                              <span>{point.z_mm ?? "—"}</span>
                              <span>{point.diameter_mm ?? "—"}</span>
                              <span>{point.depth_mm ?? "—"}</span>
                              <span>{formatHolePointSide(point.side, t)}</span>
                              <span>{formatHolePointOperation(point.operation, t)}</span>
                              <span>{point.order_index}</span>
                              <span>{point.quantity}</span>
                              <span>{point.mirrored ? t.holePointSelectionYes : t.holePointSelectionNo}</span>
                               <span className="holes-point-notes-cell">{point.notes || "—"}</span>
                            </article>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="empty-state compact-empty-state">
                        <span>{t.holePreviewEmpty}</span>
                      </div>
                    )
                  ) : (
                    <div className="empty-state compact-empty-state">
                      <span>{t.holeTemplateSelectTemplate}</span>
                    </div>
                  )}
                  </section>
                </div>

                <section className="holes-preview-card holes-preview-3d-card">
                    <div className="holes-preview-header">
                      <div>
                        <h4>{t.holeWorkspacePreview3dTitle}</h4>
                        <p>{t.holeWorkspacePreview3dPlaceholder}</p>
                      </div>
                    </div>
                    <div className="holes-preview-stage holes-preview-stage-placeholder">
                      <span>{t.holeWorkspacePreview3dPlaceholder}</span>
                    </div>
                    <div className="holes-preview-material-planes" aria-label={t.holeWorkspacePreview3dTitle}>
                      <div className="holes-preview-material-planes-title">Площини матеріалу</div>
                      <div className="holes-preview-material-planes-flow">
                        <span className="holes-preview-material-plane-card">
                          {holesPreviewModel.materialPlanes?.planeA?.label || "Площина A"}
                        </span>
                        <span className="holes-preview-material-planes-arrow" aria-hidden="true">
                          →
                        </span>
                        <span className="holes-preview-material-plane-card">
                          {holesPreviewModel.materialPlanes?.planeB?.label || "Площина B"}
                        </span>
                      </div>
                    </div>
                    {renderHolesSceneSchematicPreview(holesPreviewModel.scene)}
                    <div className="holes-preview-scene" aria-label="Scene model">
                      <div className="holes-preview-scene-title">Scene model</div>
                      <div className="holes-preview-scene-stats">
                        <div className="holes-preview-scene-stat">
                          <span>Фурнітура:</span>
                          <strong>{holesPreviewModel.scene?.stats?.hasFitting ? "так" : "ні"}</strong>
                        </div>
                        <div className="holes-preview-scene-stat">
                          <span>Шаблон:</span>
                          <strong>{holesPreviewModel.scene?.stats?.hasTemplate ? "так" : "ні"}</strong>
                        </div>
                        <div className="holes-preview-scene-stat">
                          <span>Варіант кріплення:</span>
                          <strong>{holesPreviewModel.scene?.stats?.hasMountingVariant ? "так" : "ні"}</strong>
                        </div>
                        <div className="holes-preview-scene-stat">
                          <span>Площини:</span>
                          <strong>{holesPreviewModel.scene?.materialPlanes ? "так" : "ні"}</strong>
                        </div>
                        <div className="holes-preview-scene-stat">
                          <span>Отворів у сцені:</span>
                          <strong>{holesPreviewModel.scene?.stats?.holesCount ?? 0}</strong>
                        </div>
                        <div className="holes-preview-scene-stat">
                          <span>Hovered hole:</span>
                          <strong>{holesPreviewModel.scene?.hoveredHoleId || "—"}</strong>
                        </div>
                      </div>
                      <div className="holes-preview-scene-holes">
                        <div className="holes-preview-scene-holes-title">Отвори сцени</div>
                        {holesPreviewModel.scene?.holes?.length ? (
                          <div className="holes-preview-scene-holes-list">
                            {holesPreviewModel.scene.holes.map((hole) => (
                              <div
                                className={`holes-preview-scene-hole${hole.isHovered ? " is-hovered" : ""}`}
                                key={hole.id}
                              >
                                <strong>
                                  #{hole.id}
                                  {Number.isFinite(hole.diameter) ? ` Ø${hole.diameter}` : " Ø—"}
                                </strong>
                                <span>
                                  x:{Number.isFinite(hole.x) ? hole.x : "—"} y:{Number.isFinite(hole.y) ? hole.y : "—"}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="holes-preview-scene-empty">Отвори сцени ще не додані</div>
                        )}
                      </div>
                    </div>
                    <div className="holes-preview-debug" aria-label={t.holeWorkspacePreview3dTitle}>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Фурнітура</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.fitting?.name ||
                            holesPreviewModel.fitting?.article ||
                            holesPreviewModel.fitting?.code ||
                            "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Артикул</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.fitting?.article || "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Шаблон</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.template?.name || `#${holesPreviewModel.template?.id ?? "—"}`}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Варіант кріплення</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.mountingVariant?.label || "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Площина A</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.materialPlanes?.planeA?.label || "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Площина B</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.materialPlanes?.planeB?.label || "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Напрям</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.materialPlanes?.connectionDirection || "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Сторона</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.side
                            ? formatHolePointSide(holesPreviewModel.side, t) || holesPreviewModel.side
                            : "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Тип</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.type
                            ? formatHoleTemplateType(holesPreviewModel.type, t) || holesPreviewModel.type
                            : "—"}
                        </strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Точок</span>
                        <strong className="holes-preview-debug-value">{holesPreviewModel.pointCount}</strong>
                      </div>
                      <div className="holes-preview-debug-row">
                        <span className="holes-preview-debug-label">Hover point</span>
                        <strong className="holes-preview-debug-value">
                          {holesPreviewModel.hoveredPointId || "—"}
                        </strong>
                      </div>
                    </div>
                    {holePreviewData.hasPoints ? (
                      <>
                    <div
                      className="holes-preview-stage"
                      data-placeholder={t.holeWorkspacePreview3dPlaceholder}
                    >
                          <svg
                            className="holes-preview-svg"
                            preserveAspectRatio="xMinYMin meet"
                            role="img"
                            viewBox={`0 0 ${holePreviewData.width} ${holePreviewData.height}`}
                          >
                            <defs>
                              <pattern id="holes-preview-grid" height="24" patternUnits="userSpaceOnUse" width="24">
                                <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#e6ecf1" strokeWidth="1" />
                              </pattern>
                            </defs>
                            <rect
                              fill="#fbfdfe"
                              height={holePreviewData.height}
                              width={holePreviewData.width}
                              x="0"
                              y="0"
                            />
                            <rect
                              fill="url(#holes-preview-grid)"
                              height={holePreviewData.height}
                              opacity="0.92"
                              width={holePreviewData.width}
                              x="0"
                              y="0"
                            />
                            {holePreviewData.points.map((point) => (
                              <g
                                key={point.id}
                                className={String(hoveredHolePointId) === String(point.id) ? "is-hovered" : ""}
                                onMouseEnter={() => setHoveredHolePointId(String(point.id))}
                                onMouseLeave={() => setHoveredHolePointId("")}
                                transform={`translate(${point.previewX}, ${point.previewY})`}
                              >
                                <title>
                                  {[
                                    point.label,
                                    `${t.holePreviewCoordinates}: x=${formatMetricValue(point.x)} y=${formatMetricValue(point.y)} z=${formatMetricValue(point.z)}`,
                                    `${t.holePreviewDiameter}: ${formatMetricValue(point.diameter)}`,
                                    `${t.holePreviewDepth}: ${formatMetricValue(point.depth)}`,
                                    `${t.holePreviewSide}: ${formatHolePointSide(point.side, t)}`,
                                    `${t.holePreviewOperation}: ${formatHolePointOperation(point.operation, t)}`,
                                  ].join(" | ")}
                                </title>
                                <circle
                                  cx="0"
                                  cy="0"
                                  r={point.radius}
                                  className={`holes-preview-point${String(hoveredHolePointId) === String(point.id) ? " is-hovered" : ""}`}
                                />
                                <text
                                  className={`holes-preview-label${String(hoveredHolePointId) === String(point.id) ? " is-hovered" : ""}`}
                                  x={point.labelX - point.previewX}
                                  y={point.labelY - point.previewY}
                                >
                                  {point.label}
                                </text>
                              </g>
                            ))}
                          </svg>
                        </div>
                        <div className="holes-preview-legend">
                          <span>Ø - {t.holePreviewDiameter}</span>
                          <span>{t.holePreviewDepth}</span>
                          <span>{t.holePreviewSide}</span>
                          <span>{t.holePreviewOperation}</span>
                        </div>
                      </>
                    ) : (
                      <div className="empty-state compact-empty-state">
                        <span>{t.holePreviewEmpty}</span>
                      </div>
                    )}
                  </section>

                  <section className="holes-preview-card holes-preview-2d-card">
                    <div className="holes-preview-header">
                      <div>
                        <h4>{t.holePreviewTitle}</h4>
                        <p>{t.holePreviewHelper}</p>
                      </div>
                      <span className="service-tree-badge subtle">
                        {holePreviewData.points.length}
                      </span>
                    </div>
                    {holePreviewData.hasPoints ? (
                      <>
                        <div className="holes-preview-stage">
                          <svg
                            className="holes-preview-svg"
                            preserveAspectRatio="xMinYMin meet"
                            role="img"
                            viewBox={`0 0 ${holePreviewData.width} ${holePreviewData.height}`}
                          >
                            <defs>
                              <pattern id="holes-preview-grid" height="24" patternUnits="userSpaceOnUse" width="24">
                                <path d="M 24 0 L 0 0 0 24" fill="none" stroke="#e6ecf1" strokeWidth="1" />
                              </pattern>
                            </defs>
                            <rect
                              fill="#fbfdfe"
                              height={holePreviewData.height}
                              width={holePreviewData.width}
                              x="0"
                              y="0"
                            />
                            <rect
                              fill="url(#holes-preview-grid)"
                              height={holePreviewData.height}
                              opacity="0.92"
                              width={holePreviewData.width}
                              x="0"
                              y="0"
                            />
                            {holePreviewData.points.map((point) => (
                              <g
                                key={point.id}
                                className={String(hoveredHolePointId) === String(point.id) ? "is-hovered" : ""}
                                onMouseEnter={() => setHoveredHolePointId(String(point.id))}
                                onMouseLeave={() => setHoveredHolePointId("")}
                                transform={`translate(${point.previewX}, ${point.previewY})`}
                              >
                                <title>
                                  {[
                                    point.label,
                                    `${t.holePreviewCoordinates}: x=${formatMetricValue(point.x)} y=${formatMetricValue(point.y)} z=${formatMetricValue(point.z)}`,
                                    `${t.holePreviewDiameter}: ${formatMetricValue(point.diameter)}`,
                                    `${t.holePreviewDepth}: ${formatMetricValue(point.depth)}`,
                                    `${t.holePreviewSide}: ${formatHolePointSide(point.side, t)}`,
                                    `${t.holePreviewOperation}: ${formatHolePointOperation(point.operation, t)}`,
                                  ].join(" | ")}
                                </title>
                                <circle
                                  cx="0"
                                  cy="0"
                                  r={point.radius}
                                  className={`holes-preview-point${String(hoveredHolePointId) === String(point.id) ? " is-hovered" : ""}`}
                                />
                                <text
                                  className={`holes-preview-label${String(hoveredHolePointId) === String(point.id) ? " is-hovered" : ""}`}
                                  x={point.labelX - point.previewX}
                                  y={point.labelY - point.previewY}
                                >
                                  {point.label}
                                </text>
                              </g>
                            ))}
                          </svg>
                        </div>
                        <div className="holes-preview-legend">
                          <span>Ø - {t.holePreviewDiameter}</span>
                          <span>{t.holePreviewDepth}</span>
                          <span>{t.holePreviewSide}</span>
                          <span>{t.holePreviewOperation}</span>
                        </div>
                      </>
                    ) : (
                      <div className="empty-state compact-empty-state">
                        <span>{t.holePreviewEmpty}</span>
                      </div>
                    )}
                  </section>
                </div>
              </article>
            </section>
        ) : isCatalogValuesView ? (
          <section className="table-panel full-panel">
            <article className="catalog-card">
              <div className="catalog-page-header">
                <div className="service-catalog-title">
                  <h3>{t.catalogValues}</h3>
                  <p>{t.catalogValuesDescription}</p>
                </div>
                <div className="service-catalog-header-actions">
                  <span className="service-tree-badge subtle">
                    {catalogItems.length} {t.catalog}
                  </span>
                  <span className="service-tree-badge subtle">
                    {CATALOG_CATEGORIES.length} {t.catalogValuesGroups}
                  </span>
                </div>
              </div>
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
            </article>
          </section>
        ) : isCatalogViyarView ? (
          <section className="table-panel full-panel">
            <article className="catalog-card service-catalog-card service-catalog-card-full">
              <div className="service-catalog-header">
                <div className="service-catalog-title">
                  <h3>{t.viyarServicesTitle}</h3>
                  <p>{t.viyarServicesDescription}</p>
                </div>
                <div className="service-catalog-header-actions">
                  <span className="service-tree-badge subtle">
                    {t.viyarSource}: {viyarServiceSource}
                  </span>
                  <span className="service-tree-badge subtle">
                    {viyarServiceCounts.folders} / {viyarServiceCounts.services}
                  </span>
                  {viyarPriceSyncSummary ? (
                    <span className="service-tree-badge subtle">
                      {viyarPriceSyncSummary.priced_count} / {viyarPriceSyncSummary.total_count}
                    </span>
                  ) : null}
                  <button
                    className="ghost-button"
                    disabled={loading}
                    onClick={handleImportViyarServices}
                    type="button"
                  >
                    <RefreshCw size={16} />
                    {t.viyarRefresh}
                  </button>
                  <button
                    className="ghost-button"
                    disabled={loading}
                    onClick={handleSyncViyarPrices}
                    type="button"
                  >
                    <RefreshCw size={16} />
                    {t.viyarSyncPrices}
                  </button>
                </div>
              </div>
              <div className="service-catalog-toolbar">
                <label className="service-catalog-search">
                  <Search size={16} />
                  <input
                    onChange={(event) => setViyarServiceSearch(event.target.value)}
                    placeholder={t.viyarSearch}
                    type="search"
                    value={viyarServiceSearch}
                  />
                </label>
                <div className="service-catalog-tree-actions">
                  <button
                    className="ghost-button compact-button"
                    disabled={viyarTreeLoading || !viyarFolderCodes.length}
                    onClick={collapseAllViyarFolders}
                    type="button"
                  >
                    {t.viyarCollapseAll}
                  </button>
                  <button
                    className="ghost-button compact-button"
                    disabled={viyarTreeLoading || !viyarFolderCodes.length}
                    onClick={expandAllViyarFolders}
                    type="button"
                  >
                    {t.viyarExpandAll}
                  </button>
                  </div>
                </div>
              <div className="service-sync-overview">
                <span className="service-tree-badge subtle">
                  {t.viyarService}: {viyarServiceCounts.services}
                </span>
                <span className="service-tree-badge subtle">
                  {t.viyarCurrentPrice}: {viyarSyncOverview.priced}
                </span>
                {Object.entries(viyarSyncOverview.statuses).map(([status, count]) => (
                  <span className="service-tree-badge subtle" key={status}>
                    {t.viyarSyncStatus}: {status} ({count})
                  </span>
                ))}
                {viyarSyncOverview.latestSyncedAt ? (
                  <span className="service-tree-badge subtle">
                    {t.viyarLastSynced}: {formatDateTime(viyarSyncOverview.latestSyncedAt, t)}
                  </span>
                ) : null}
              </div>
              <div className="service-tree-table-head">
                <span>{t.viyarService}</span>
                <span>{t.viyarArticle}</span>
                <span>{t.serviceUnit}</span>
                <span>{t.basePrice}</span>
                <span>{t.showDescription}</span>
                <span>{t.viyarCalculable}</span>
                <span>{t.enabled}</span>
                <span>{t.save}</span>
              </div>
              {filteredViyarServiceTree.length ? (
                <ul className="service-tree-root">
                  {filteredViyarServiceTree.map((node) => (
                    <ServiceCatalogTreeNode
                      collapsedFolders={collapsedViyarFolders}
                      key={node.external_code}
                      loading={loading}
                      mutationLoading={loading}
                      node={node}
                      onSaveService={handleSaveViyarService}
                      onServiceFieldChange={handleViyarServiceFieldChange}
                      onToggleCollapse={toggleViyarFolder}
                      searchQuery={viyarServiceSearch}
                      t={t}
                    />
                  ))}
                </ul>
              ) : (
                <div className="empty-state compact-empty-state">
                  <span>{t.unableToLoadViyarServices}</span>
                </div>
              )}
            </article>
          </section>
        ) : isCatalogManualView ? (
          <section className="table-panel full-panel">
            <article className="catalog-card service-catalog-card service-catalog-card-full">
              <div className="service-catalog-header nested-service-catalog-header">
                <div className="service-catalog-title">
                  <h3>{t.catalogManual}</h3>
                  <p>{t.catalogManualDescription}</p>
                </div>
                <div className="service-catalog-header-actions">
                  <span className="service-tree-badge subtle">
                    {manualServiceItems.length} {t.viyarService}
                  </span>
                </div>
              </div>

              <form className="manual-service-form" onSubmit={handleCreateManualService}>
                <input
                  onChange={(event) =>
                    setNewManualServiceForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  placeholder={t.manualServiceNamePlaceholder}
                  type="text"
                  value={newManualServiceForm.name}
                />
                <input
                  onChange={(event) =>
                    setNewManualServiceForm((current) => ({
                      ...current,
                      article: event.target.value,
                    }))
                  }
                  placeholder={t.manualServiceArticlePlaceholder}
                  type="text"
                  value={newManualServiceForm.article}
                />
                <input
                  onChange={(event) =>
                    setNewManualServiceForm((current) => ({
                      ...current,
                      unit: event.target.value,
                    }))
                  }
                  placeholder={t.serviceUnit}
                  type="text"
                  value={newManualServiceForm.unit}
                />
                <input
                  min="0"
                  onChange={(event) =>
                    setNewManualServiceForm((current) => ({
                      ...current,
                      base_price: event.target.value,
                    }))
                  }
                  placeholder={t.basePrice}
                  step="0.01"
                  type="number"
                  value={newManualServiceForm.base_price}
                />
                <input
                  onChange={(event) =>
                    setNewManualServiceForm((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                  placeholder={t.manualServiceDescriptionPlaceholder}
                  type="text"
                  value={newManualServiceForm.description}
                />
                <label className="toggle-label">
                  <input
                    checked={newManualServiceForm.is_calculable}
                    onChange={(event) =>
                      setNewManualServiceForm((current) => ({
                        ...current,
                        is_calculable: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.viyarCalculable}
                </label>
                <label className="toggle-label">
                  <input
                    checked={newManualServiceForm.is_active}
                    onChange={(event) =>
                      setNewManualServiceForm((current) => ({
                        ...current,
                        is_active: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.enabled}
                </label>
                <button
                  className="primary-button"
                  disabled={loading || !newManualServiceForm.name.trim()}
                  type="submit"
                >
                  <Plus size={16} />
                  {t.create}
                </button>
              </form>

              {manualServiceItems.length ? (
                <div className="manual-service-list">
                  {manualServiceItems.map((item) => (
                    <div className="manual-service-item" key={item.id}>
                      <div className="manual-service-item-head">
                        <strong>{item.name}</strong>
                        <span className="service-tree-badge subtle">
                          {item.article || t.notSet}
                        </span>
                      </div>
                      <div className="manual-service-editor">
                        <input
                          onChange={(event) =>
                            handleManualServiceFieldChange(item.id, "name", event.target.value)
                          }
                          type="text"
                          value={item.name || ""}
                        />
                        <input
                          onChange={(event) =>
                            handleManualServiceFieldChange(item.id, "article", event.target.value)
                          }
                          type="text"
                          value={item.article || ""}
                        />
                        <input
                          onChange={(event) =>
                            handleManualServiceFieldChange(item.id, "unit", event.target.value)
                          }
                          type="text"
                          value={item.unit || ""}
                        />
                        <input
                          min="0"
                          onChange={(event) =>
                            handleManualServiceFieldChange(item.id, "base_price", event.target.value)
                          }
                          step="0.01"
                          type="number"
                          value={item.base_price ?? ""}
                        />
                        <input
                          onChange={(event) =>
                            handleManualServiceFieldChange(
                              item.id,
                              "description",
                              event.target.value,
                            )
                          }
                          type="text"
                          value={item.description || ""}
                        />
                        <label className="toggle-label">
                          <input
                            checked={Boolean(item.is_calculable)}
                            onChange={(event) =>
                              handleManualServiceFieldChange(
                                item.id,
                                "is_calculable",
                                event.target.checked,
                              )
                            }
                            type="checkbox"
                          />
                          {t.viyarCalculable}
                        </label>
                        <label className="toggle-label">
                          <input
                            checked={Boolean(item.is_active)}
                            onChange={(event) =>
                              handleManualServiceFieldChange(
                                item.id,
                                "is_active",
                                event.target.checked,
                              )
                            }
                            type="checkbox"
                          />
                          {t.enabled}
                        </label>
                        <button
                          className="ghost-button compact-button"
                          disabled={loading || !String(item.name || "").trim()}
                          onClick={() => handleSaveManualService(item)}
                          type="button"
                        >
                          <Save size={16} />
                          {t.save}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact-empty-state">
                  <span>{t.manualServicesDescription}</span>
                </div>
              )}
            </article>
          </section>
        ) : activeView === "catalog" ? (
          <section className="table-panel full-panel">
            <div className="catalog-layout">
              <article className="catalog-card">
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
              </article>
              <article className="catalog-card service-catalog-card">
                <div className="service-catalog-header">
                  <div className="service-catalog-title">
                    <h3>{t.viyarServicesTitle}</h3>
                    <p>{t.viyarServicesDescription}</p>
                  </div>
                  <div className="service-catalog-header-actions">
                    <span className="service-tree-badge subtle">
                      {t.viyarSource}: {viyarServiceSource}
                    </span>
                    <span className="service-tree-badge subtle">
                      {viyarServiceCounts.folders} / {viyarServiceCounts.services}
                    </span>
                    {viyarPriceSyncSummary ? (
                      <span className="service-tree-badge subtle">
                        {viyarPriceSyncSummary.priced_count} / {viyarPriceSyncSummary.total_count}
                      </span>
                    ) : null}
                    <button
                      className="ghost-button"
                      disabled={viyarTreeLoading}
                      onClick={handleImportViyarServices}
                      type="button"
                    >
                      <RefreshCw size={16} />
                      {t.viyarRefresh}
                    </button>
                    <button
                      className="ghost-button"
                      disabled={viyarTreeLoading}
                      onClick={handleSyncViyarPrices}
                      type="button"
                    >
                      <RefreshCw size={16} />
                      {t.viyarSyncPrices}
                    </button>
                  </div>
                </div>
                <div className="service-catalog-toolbar">
                  <label className="service-catalog-search">
                    <Search size={16} />
                    <input
                      onChange={(event) => setViyarServiceSearch(event.target.value)}
                      placeholder={t.viyarSearch}
                      type="search"
                      value={viyarServiceSearch}
                    />
                  </label>
                  <div className="service-catalog-tree-actions">
                    <button
                      className="ghost-button compact-button"
                      disabled={viyarTreeLoading || !viyarFolderCodes.length}
                      onClick={collapseAllViyarFolders}
                      type="button"
                    >
                      {t.viyarCollapseAll}
                    </button>
                    <button
                      className="ghost-button compact-button"
                      disabled={viyarTreeLoading || !viyarFolderCodes.length}
                      onClick={expandAllViyarFolders}
                      type="button"
                    >
                      {t.viyarExpandAll}
                    </button>
                  </div>
                </div>
                {filteredViyarServiceTree.length ? (
                  <ul className="service-tree-root">
                    {filteredViyarServiceTree.map((node) => (
                      <ServiceCatalogTreeNode
                        collapsedFolders={collapsedViyarFolders}
                        key={node.external_code}
                        loading={loading}
                        mutationLoading={loading}
                        node={node}
                        onSaveService={handleSaveViyarService}
                        onServiceFieldChange={handleViyarServiceFieldChange}
                        onToggleCollapse={toggleViyarFolder}
                        searchQuery={viyarServiceSearch}
                        t={t}
                      />
                    ))}
                  </ul>
                ) : (
                  <div className="empty-state compact-empty-state">
                    <span>{t.unableToLoadViyarServices}</span>
                  </div>
                )}

                <div className="service-catalog-divider" />

                <div className="service-catalog-header nested-service-catalog-header">
                  <div className="service-catalog-title">
                    <h3>{t.manualServicesTitle}</h3>
                    <p>{t.manualServicesDescription}</p>
                  </div>
                </div>

                <form className="manual-service-form" onSubmit={handleCreateManualService}>
                  <input
                    onChange={(event) =>
                      setNewManualServiceForm((current) => ({
                        ...current,
                        name: event.target.value,
                      }))
                    }
                    placeholder={t.manualServiceNamePlaceholder}
                    type="text"
                    value={newManualServiceForm.name}
                  />
                  <input
                    onChange={(event) =>
                      setNewManualServiceForm((current) => ({
                        ...current,
                        article: event.target.value,
                      }))
                    }
                    placeholder={t.manualServiceArticlePlaceholder}
                    type="text"
                    value={newManualServiceForm.article}
                  />
                  <input
                    onChange={(event) =>
                      setNewManualServiceForm((current) => ({
                        ...current,
                        unit: event.target.value,
                      }))
                    }
                    placeholder={t.serviceUnit}
                    type="text"
                    value={newManualServiceForm.unit}
                  />
                  <input
                    min="0"
                    onChange={(event) =>
                      setNewManualServiceForm((current) => ({
                        ...current,
                        base_price: event.target.value,
                      }))
                    }
                    placeholder={t.basePrice}
                    step="0.01"
                    type="number"
                    value={newManualServiceForm.base_price}
                  />
                  <input
                    onChange={(event) =>
                      setNewManualServiceForm((current) => ({
                        ...current,
                        description: event.target.value,
                      }))
                    }
                    placeholder={t.manualServiceDescriptionPlaceholder}
                    type="text"
                    value={newManualServiceForm.description}
                  />
                  <label className="toggle-label">
                    <input
                      checked={newManualServiceForm.is_calculable}
                      onChange={(event) =>
                        setNewManualServiceForm((current) => ({
                          ...current,
                          is_calculable: event.target.checked,
                        }))
                      }
                      type="checkbox"
                    />
                    {t.viyarCalculable}
                  </label>
                  <label className="toggle-label">
                    <input
                      checked={newManualServiceForm.is_active}
                      onChange={(event) =>
                        setNewManualServiceForm((current) => ({
                          ...current,
                          is_active: event.target.checked,
                        }))
                      }
                      type="checkbox"
                    />
                    {t.enabled}
                  </label>
                  <button
                    className="primary-button"
                    disabled={loading || !newManualServiceForm.name.trim()}
                    type="submit"
                  >
                    <Plus size={16} />
                    {t.create}
                  </button>
                </form>

                {manualServiceItems.length ? (
                  <div className="manual-service-list">
                    {manualServiceItems.map((item) => (
                      <div className="manual-service-item" key={item.id}>
                        <div className="manual-service-item-head">
                          <strong>{item.name}</strong>
                          <span className="service-tree-badge subtle">
                            {item.article || t.notSet}
                          </span>
                        </div>
                        <div className="manual-service-editor">
                          <input
                            onChange={(event) =>
                              handleManualServiceFieldChange(item.id, "name", event.target.value)
                            }
                            type="text"
                            value={item.name || ""}
                          />
                          <input
                            onChange={(event) =>
                              handleManualServiceFieldChange(item.id, "article", event.target.value)
                            }
                            type="text"
                            value={item.article || ""}
                          />
                          <input
                            onChange={(event) =>
                              handleManualServiceFieldChange(item.id, "unit", event.target.value)
                            }
                            type="text"
                            value={item.unit || ""}
                          />
                          <input
                            min="0"
                            onChange={(event) =>
                              handleManualServiceFieldChange(item.id, "base_price", event.target.value)
                            }
                            step="0.01"
                            type="number"
                            value={item.base_price ?? ""}
                          />
                          <input
                            onChange={(event) =>
                              handleManualServiceFieldChange(
                                item.id,
                                "description",
                                event.target.value,
                              )
                            }
                            type="text"
                            value={item.description || ""}
                          />
                          <label className="toggle-label">
                            <input
                              checked={Boolean(item.is_calculable)}
                              onChange={(event) =>
                                handleManualServiceFieldChange(
                                  item.id,
                                  "is_calculable",
                                  event.target.checked,
                                )
                              }
                              type="checkbox"
                            />
                            {t.viyarCalculable}
                          </label>
                          <label className="toggle-label">
                            <input
                              checked={Boolean(item.is_active)}
                              onChange={(event) =>
                                handleManualServiceFieldChange(
                                  item.id,
                                  "is_active",
                                  event.target.checked,
                                )
                              }
                              type="checkbox"
                            />
                            {t.enabled}
                          </label>
                          <button
                            className="ghost-button compact-button"
                            disabled={loading || !String(item.name || "").trim()}
                            onClick={() => handleSaveManualService(item)}
                            type="button"
                          >
                            <Save size={16} />
                            {t.save}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact-empty-state">
                    <span>{t.manualServicesDescription}</span>
                  </div>
                )}
              </article>
            </div>
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

      {selectedProject && projectOverviewOpen ? (
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
                <strong>{t.selectedProject}</strong>
                <p>{selectedProject.project_name || t.newProjectDefault}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="ghost-button compact-button detail-info-button"
                onClick={() => setProjectOverviewOpen(false)}
                type="button"
              >
                <X size={16} />
              </button>
            </header>
            <div className="project-info-grid">
              <span>{t.projectType}</span>
              <strong>{formatCatalogLabel(selectedProject.project_type, t)}</strong>
              <span>{t.client}</span>
              <strong>{selectedProject.client_name || t.notSet}</strong>
              <span>{t.room}</span>
              <strong>{selectedProject.room_name || t.notSet}</strong>
              <span>{t.width} x {t.height} x {t.depth}</span>
              <strong>{selectedProject.width} x {selectedProject.height} x {selectedProject.depth}</strong>
              <span>{t.sections}</span>
              <strong>{selectedProject.sections}</strong>
              <span>{t.drawers}</span>
              <strong>{formatDrawers(selectedProject.drawers, t)}</strong>
              <span>{t.facadeMaterial}</span>
              <strong>{selectedProject.facade_material || t.notSet}</strong>
              <span>{t.insideMaterial}</span>
              <strong>{selectedProject.inside_material || t.notSet}</strong>
              <span>{`${t.facadeMaterial} · ${t.edgeBanding}`}</span>
              <strong>{selectedProject.facade_edge_banding || selectedProject.edge_banding || t.notSet}</strong>
              <span>{`${t.insideMaterial} · ${t.edgeBanding}`}</span>
              <strong>{selectedProject.inside_edge_banding || selectedProject.edge_banding || t.notSet}</strong>
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

      {selectedUserDetails ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={() => setSelectedUserDetails(null)}
          role="dialog"
        >
          <section
            className="confirm-modal user-details-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>{selectedUserDetails.user.email}</strong>
                <p>{t.openUserCard}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="ghost-button compact-button detail-info-button"
                onClick={() => setSelectedUserDetails(null)}
                type="button"
              >
                <X size={16} />
              </button>
            </header>
            <div className="user-details-modal-grid">
              <section className="user-details-section">
                <h4>{t.userProfile}</h4>
                <div className="project-info-grid">
                  <span>{t.email}</span>
                  <strong>{selectedUserDetails.user.email}</strong>
                  <span>{t.username}</span>
                  <strong>{selectedUserDetails.user.username || t.notSet}</strong>
                  <span>{t.phone}</span>
                  <strong>{selectedUserDetails.user.phone || t.notSet}</strong>
                  <span>{t.telegram}</span>
                  <strong>{selectedUserDetails.user.telegram_id || t.notSet}</strong>
                  <span>{t.role}</span>
                  <strong>{selectedUserDetails.user.role}</strong>
                  <span>{t.status}</span>
                  <strong>{selectedUserDetails.user.is_active ? t.active : t.inactive}</strong>
                  <span>{t.lastUsernameChange}</span>
                  <strong>{formatDateTime(selectedUserDetails.user.last_username_change_at, t)}</strong>
                </div>
              </section>

              <section className="user-details-section">
                <h4>{t.viyarConnection}</h4>
                <div className="project-info-grid">
                  <span>{t.email}</span>
                  <strong>{selectedUserDetails.user.viyar_email || t.notSet}</strong>
                  <span>{t.session}</span>
                  <strong>{selectedUserDetails.user.viyar_has_cookie ? t.connected : t.notConnected}</strong>
                  <span>{t.authStatus}</span>
                  <strong>{selectedUserDetails.user.viyar_last_auth_status || t.notSet}</strong>
                  <span>{t.lastAuth}</span>
                  <strong>{formatDateTime(selectedUserDetails.user.viyar_last_auth_at, t)}</strong>
                  <span>{t.authError}</span>
                  <strong>{selectedUserDetails.user.viyar_last_auth_error || t.noError}</strong>
                </div>
              </section>

              <section className="user-details-section">
                <h4>{t.pendingRequests}</h4>
                {selectedUserDetails.change_requests.length ? (
                  <table>
                    <thead>
                      <tr>
                        <th>{t.changeType}</th>
                        <th>{t.oldValue}</th>
                        <th>{t.newValue}</th>
                        <th>{t.status}</th>
                        <th>{t.requestedAt}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedUserDetails.change_requests.map((request) => (
                        <tr key={request.id}>
                          <td>{request.change_type}</td>
                          <td>{request.old_value || t.notSet}</td>
                          <td>{request.new_value}</td>
                          <td>{request.status}</td>
                          <td>{formatDateTime(request.created_at, t)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="empty-inline-note">{t.noRequestsHistory}</p>
                )}
              </section>

              <section className="user-details-section">
                <h4>{t.createdProjects}</h4>
                {selectedUserDetails.projects.length ? (
                  <table>
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>{t.projectName}</th>
                        <th>{t.projectType}</th>
                        <th>{t.client}</th>
                        <th>{t.updated}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedUserDetails.projects.map((project) => (
                        <tr key={project.id}>
                          <td>{project.id}</td>
                          <td>{project.project_name || t.newProjectDefault}</td>
                          <td>{formatCatalogLabel(project.project_type, t)}</td>
                          <td>{project.client_name || t.notSet}</td>
                          <td>{formatDateTime(project.updated_at, t)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <p className="empty-inline-note">{t.noProjectsYet}</p>
                )}
              </section>
            </div>
          </section>
        </div>
      ) : null}

      {projectOptionPicker.open ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={closeProjectOptionPicker}
          role="dialog"
        >
          <section
            className="confirm-modal project-option-picker-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>{projectOptionPicker.title}</strong>
                <p>{projectOptionPickerConfig.description}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="ghost-button compact-button detail-info-button"
                onClick={closeProjectOptionPicker}
                type="button"
              >
                <X size={16} />
              </button>
            </header>

            <div className="project-option-picker-toolbar">
              <label className="project-option-picker-search">
                <Search size={16} />
                <input
                  autoFocus
                  onChange={(event) => setProjectOptionPickerSearch(event.target.value)}
                  placeholder={projectOptionPickerConfig.placeholder}
                  type="search"
                  value={projectOptionPickerSearch}
                />
              </label>
              <span className="service-tree-badge subtle">
                {filteredProjectOptionItems.length} {language === "uk" ? "позицій" : "items"}
              </span>
            </div>

            {filteredProjectOptionItems.length ? (
              <div className="project-option-picker-grid">
                {filteredProjectOptionItems.map((item) => {
                  if (
                    projectOptionPicker.mode === "handles" ||
                    projectOptionPicker.mode === "slideType"
                  ) {
                    const sourceMeta = getFittingSourceMeta(item);
                    const badgeLabel =
                      projectOptionPicker.mode === "slideType"
                        ? item.pickerRecommended
                          ? language === "uk"
                            ? "Рекомендовано"
                            : "Recommended"
                          : item.pickerLength
                            ? `${item.pickerLength} мм`
                            : t.slideType
                        : currentFittingCategoryMeta?.name || t.handleType;

                    return (
                      <article
                        className="project-option-picker-card"
                        key={`${projectOptionPicker.mode}-${item.id}`}
                        onClick={() => applyProjectOptionValue(item.pickerValue)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            applyProjectOptionValue(item.pickerValue);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="project-option-picker-card-media">
                          {buildFittingImageCandidates(item).length ? (
                            <img
                              alt={item.name || item.article || item.code || t.catalogFittings}
                              data-fallback-index="0"
                              decoding="async"
                              loading="lazy"
                              onError={(event) => handleFittingImageError(event, item)}
                              src={buildFittingImageCandidates(item)[0]}
                            />
                          ) : (
                            <div className="material-card-placeholder">
                              <Package size={22} />
                            </div>
                          )}
                        </div>
                        <div className="project-option-picker-card-body">
                          <div className="project-option-picker-card-topline">
                            <span className="service-tree-badge subtle">
                              {badgeLabel}
                            </span>
                            {item.article ? (
                              <span className="project-option-picker-card-article">{item.article}</span>
                            ) : null}
                          </div>
                          <strong>{item.pickerTitle || item.pickerValue}</strong>
                          {item.pickerSubtitle ? (
                            <p className="project-option-picker-card-subtitle">{item.pickerSubtitle}</p>
                          ) : null}
                          <div className="project-option-picker-card-price">
                            <span>{t.fittingPrice}</span>
                            <b>{item.price !== null && item.price !== undefined ? `${item.price} UAH` : t.notSet}</b>
                          </div>
                          <div className="project-option-picker-card-meta">
                            <span>{t.city}: {formatCatalogLabel(item.city, t)}</span>
                            {renderSourceBadge(sourceMeta)}
                          </div>
                        </div>
                      </article>
                    );
                  }

                  if (projectOptionPicker.mode === "bottomType") {
                    return (
                      <article
                        className="project-option-picker-card"
                        key={`${projectOptionPicker.mode}-${item.id}`}
                        onClick={() => applyProjectOptionValue(item.pickerValue)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            applyProjectOptionValue(item.pickerValue);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="project-option-picker-card-media">
                          {item.image_url ? (
                            <img alt={item.pickerTitle || item.pickerValue} loading="lazy" src={item.image_url} />
                          ) : (
                            <div className="material-card-placeholder">
                              <Package size={22} />
                            </div>
                          )}
                        </div>
                        <div className="project-option-picker-card-body">
                          <div className="project-option-picker-card-topline">
                            <span className="service-tree-badge subtle">
                              {language === "uk" ? "2 варіанти" : "2 variants"}
                            </span>
                          </div>
                          <strong>{item.pickerTitle || item.pickerValue || t.notSet}</strong>
                          {item.pickerSubtitle ? (
                            <p className="project-option-picker-card-subtitle">{item.pickerSubtitle}</p>
                          ) : null}
                        </div>
                      </article>
                    );
                  }

                  if (projectOptionPicker.mode === "edgeBanding") {
                    return (
                      <article
                        className="project-option-picker-card"
                        key={`${projectOptionPicker.mode}-${item.id}`}
                        onClick={() => applyProjectOptionValue(item.pickerValue)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            applyProjectOptionValue(item.pickerValue);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="project-option-picker-card-body">
                          <div className="project-option-picker-card-topline">
                            <span className="service-tree-badge subtle">
                              {item.edge_key
                                ? MATERIAL_EDGE_SLOTS.find((slot) => slot.key === item.edge_key)?.label || t.edgeBanding
                                : t.edgeBanding}
                            </span>
                            {item.article ? (
                              <span className="project-option-picker-card-article">{item.article}</span>
                            ) : null}
                          </div>
                          <strong>{item.pickerTitle || item.pickerValue}</strong>
                          {item.pickerSubtitle ? (
                            <p className="project-option-picker-card-subtitle">{item.pickerSubtitle}</p>
                          ) : null}
                          <div className="project-option-picker-card-price">
                            <span>{t.materialPriceForCity}</span>
                            <b>
                              {item.price !== null && item.price !== undefined
                                ? `${item.price} UAH`
                                : t.notSet}
                            </b>
                          </div>
                          <div className="project-option-picker-card-meta">
                            <span>{t.materialThickness}: {item.thickness || t.notSet}</span>
                          </div>
                          <div className="project-option-picker-card-edge-preview">
                            {buildMaterialEdgeImageCandidates(activeProjectPickerMaterial, item).length ? (
                              <>
                                <img
                                  alt={item.name || item.article || t.edgeBanding}
                                  data-fallback-index="0"
                                  decoding="async"
                                  loading="lazy"
                                  onError={(event) =>
                                    handleMaterialEdgeImageError(
                                      event,
                                      activeProjectPickerMaterial,
                                      item,
                                      token,
                                    )
                                  }
                                  src={buildMaterialEdgeImageCandidates(activeProjectPickerMaterial, item, token)[0]}
                                />
                                <div className="material-card-placeholder" hidden>
                                  {t.edgeBanding}
                                </div>
                              </>
                            ) : (
                              <div className="material-card-placeholder">{t.edgeBanding}</div>
                            )}
                          </div>
                        </div>
                      </article>
                    );
                  }

                  if (projectOptionPicker.mode !== "materials") {
                    return (
                      <article
                        className="project-option-picker-card compact"
                        key={`${projectOptionPicker.mode}-${item.id}`}
                        onClick={() => applyProjectOptionValue(item.pickerValue)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            applyProjectOptionValue(item.pickerValue);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <div className="project-option-picker-card-body">
                          <div className="project-option-picker-card-topline">
                            <span className="service-tree-badge subtle">
                              {projectOptionPicker.title}
                            </span>
                          </div>
                          <strong>{item.pickerTitle || item.pickerValue || t.notSet}</strong>
                          {item.pickerSubtitle ? (
                            <p className="project-option-picker-card-subtitle">{item.pickerSubtitle}</p>
                          ) : null}
                        </div>
                      </article>
                    );
                  }

                  return (
                    <article
                      className="project-option-picker-card"
                      key={`${projectOptionPicker.mode}-${item.id}`}
                      onClick={() => applyProjectOptionValue(item.pickerValue)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          applyProjectOptionValue(item.pickerValue);
                        }
                      }}
                      role="button"
                      tabIndex={0}
                    >
                      <div className="project-option-picker-card-media">
                        {buildMaterialImageCandidates(item).length ? (
                          <>
                            <img
                              alt={item.name || item.article}
                              data-fallback-index="0"
                              decoding="async"
                              loading="lazy"
                              onError={(event) => handleMaterialImageError(event, item, token)}
                              src={buildMaterialImageCandidates(item, token)[0]}
                            />
                            <div className="material-card-placeholder" hidden>
                              {formatCatalogLabel(item.category, t)}
                            </div>
                          </>
                        ) : (
                          <div className="material-card-placeholder">
                            {formatCatalogLabel(item.category, t)}
                          </div>
                        )}
                      </div>
                      <div className="project-option-picker-card-body">
                        <div className="project-option-picker-card-topline">
                          <span className="service-tree-badge subtle">
                            {formatCatalogLabel(item.category, t)}
                          </span>
                          {item.display_article || item.article ? (
                            <span className="project-option-picker-card-article">
                              {item.display_article || item.article}
                            </span>
                          ) : null}
                        </div>
                        <strong>{item.pickerTitle || item.pickerValue}</strong>
                        {item.pickerSubtitle ? (
                          <p className="project-option-picker-card-subtitle">{item.pickerSubtitle}</p>
                        ) : null}
                        <div className="project-option-picker-card-price">
                          <span>{t.materialPriceForCity}</span>
                          <b>
                            {item.current_price !== null && item.current_price !== undefined
                              ? `${item.current_price} UAH`
                              : t.notSet}
                          </b>
                        </div>
                        <div className="project-option-picker-card-meta">
                          <span>
                            {t.city}: {formatCatalogLabel(item.current_price_city || materialSelectedCity || user?.city, t)}
                          </span>
                          {renderSourceBadge(getMaterialSourceMeta(item, t))}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state compact-empty-state">
                <p>{projectOptionPickerConfig.empty}</p>
              </div>
            )}
          </section>
        </div>
      ) : null}

      {selectedMaterialDetail ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={closeMaterialDetails}
          role="dialog"
        >
          <section
            className="confirm-modal material-details-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>{t.materialDetails}</strong>
                <p>{getMaterialShortName(selectedMaterialDetail)}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="ghost-button compact-button detail-info-button"
                onClick={closeMaterialDetails}
                type="button"
              >
                <X size={16} />
              </button>
            </header>

            <div className="material-details-layout">
              <div className="material-details-media">
                {buildMaterialImageCandidates(selectedMaterialDetail).length ? (
                  <>
                    <img
                      alt={selectedMaterialDetail.name || selectedMaterialDetail.article}
                      data-fallback-index="0"
                      decoding="async"
                      loading="eager"
                      onError={(event) => handleMaterialImageError(event, selectedMaterialDetail, token)}
                      src={buildMaterialImageCandidates(selectedMaterialDetail, token)[0]}
                    />
                    <div className="material-card-placeholder" hidden>
                      {formatCatalogLabel(selectedMaterialDetail.category, t)}
                    </div>
                  </>
                ) : (
                  <div className="material-card-placeholder">
                    {formatCatalogLabel(selectedMaterialDetail.category, t)}
                  </div>
                )}
              </div>

              <div className="material-details-content">
                <div className="material-details-badges">
                  <span className="service-tree-badge subtle">
                    {formatCatalogLabel(selectedMaterialDetail.category, t)}
                  </span>
                  {selectedMaterialDetail.display_article ? (
                    <span className="service-tree-badge subtle">
                      {selectedMaterialDetail.display_article}
                    </span>
                  ) : null}
                  {renderSourceBadge(getMaterialSourceMeta(selectedMaterialDetail, t))}
                </div>

                <div className="material-details-grid">
                  <div>
                    <span>{t.materialPriceForCity}</span>
                    <strong>
                      {selectedMaterialDetail.current_price !== null && selectedMaterialDetail.current_price !== undefined
                        ? `${selectedMaterialDetail.current_price} UAH`
                        : t.notSet}
                    </strong>
                  </div>
                  <div>
                    <span>{t.city}</span>
                    <strong>
                      {formatCatalogLabel(
                        selectedMaterialDetail.current_price_city || materialSelectedCity || user?.city,
                        t,
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>{t.materialColor}</span>
                    <strong>{getMaterialColorText(selectedMaterialDetail, t)}</strong>
                  </div>
                  <div>
                    <span>{t.materialDimensions}</span>
                    <strong>{selectedMaterialDetail.dimensions || t.notSet}</strong>
                  </div>
                  <div>
                    <span>{t.materialThickness}</span>
                    <strong>{selectedMaterialDetail.thickness || t.notSet}</strong>
                  </div>
                </div>

                <div className="material-details-description">
                  <span>{t.materialDescription}</span>
                  <p>{getMaterialDescriptionText(selectedMaterialDetail, t)}</p>
                </div>
              </div>
            </div>

            <section className="material-edge-section">
              <div className="material-edge-section-header">
                <h4>{t.materialEdgeBands}</h4>
                <div className="material-edge-section-actions">
                  {materialDetailLoading ? <span className="service-tree-badge subtle">{t.loading}</span> : null}
                  {canEditMaterialItem(user, selectedMaterialDetail) ? (
                    <button
                      className="ghost-button compact-button"
                      onClick={toggleMaterialEdgeCreateForm}
                      type="button"
                    >
                      <Plus size={14} />
                      {t.materialEdgeAttach}
                    </button>
                  ) : null}
                </div>
              </div>

              {materialEdgeCreateForm.open ? (
                <div className="material-edge-form material-edge-create-form">
                  <select
                    aria-label={t.materialEdgeTypeLabel}
                    onChange={(event) => updateMaterialEdgeCreateForm("edge_key", event.target.value)}
                    value={materialEdgeCreateForm.edge_key}
                  >
                    {MATERIAL_EDGE_SLOTS.map((slot) => (
                      <option key={slot.key} value={slot.key}>
                        {slot.label}
                      </option>
                    ))}
                  </select>
                  <input
                    onChange={(event) => updateMaterialEdgeCreateForm("source_url", event.target.value)}
                    placeholder={t.materialEdgeAttachPlaceholder}
                    type="url"
                    value={materialEdgeCreateForm.source_url}
                  />
                  <button
                    className="primary-button compact-button"
                    disabled={loading || !String(materialEdgeCreateForm.source_url || "").trim()}
                    onClick={() =>
                      handleAttachMaterialEdge(materialEdgeCreateForm.edge_key, materialEdgeCreateForm.source_url)
                    }
                    type="button"
                  >
                    {t.materialEdgeAttachConfirm}
                  </button>
                </div>
              ) : null}

              {getSortedMaterialEdgeItems(selectedMaterialDetail).length ? (
                <div className="material-edge-grid">
                  {getSortedMaterialEdgeItems(selectedMaterialDetail).map((edgeItem) => {
                  const slot = getMaterialEdgeSlot(edgeItem.edge_key) || {
                    key: edgeItem.edge_key || edgeItem.article || edgeItem.name,
                    label: edgeItem.thickness || t.materialEdgeBands,
                  };
                  const edgeForm = materialEdgeForms[slot.key] || { open: false, source_url: "" };
                  const canEditEdge = canEditMaterialItem(user, selectedMaterialDetail);

                  return (
                    <article className="material-edge-card" key={slot.key}>
                      <div className="material-edge-card-head">
                        <strong>{slot.label}</strong>
                        {canEditEdge ? (
                          <button
                            className="ghost-button compact-button"
                            onClick={() => toggleMaterialEdgeForm(slot.key)}
                            type="button"
                          >
                            <Plus size={14} />
                            {t.materialEdgeAttach}
                          </button>
                        ) : null}
                      </div>

                      <div className="material-edge-card-body">
                        <div className="material-edge-card-copy">
                          <div className="material-edge-card-topline">
                            <b>{edgeItem.name || edgeItem.article || slot.label}</b>
                          </div>
                          <div className="material-edge-card-details-row">
                            <div className="material-edge-card-meta">
                              {edgeItem.article ? <span>{edgeItem.article}</span> : null}
                              <span>{t.materialThickness}: {edgeItem.thickness || slot.label}</span>
                              <span>
                                {t.materialPriceForCity}:{" "}
                                {edgeItem.current_price !== null && edgeItem.current_price !== undefined
                                  ? `${edgeItem.current_price} UAH`
                                  : t.notSet}
                              </span>
                            </div>
                            <div className="material-edge-card-preview material-edge-card-preview-rect">
                              {buildMaterialEdgeImageCandidates(
                                selectedMaterialDetail,
                                edgeItem,
                                token,
                              ).length ? (
                                <>
                                  <img
                                    alt={edgeItem.name || edgeItem.article || slot.label}
                                    data-fallback-index="0"
                                    decoding="async"
                                    loading="lazy"
                                    onError={(event) =>
                                      handleMaterialEdgeImageError(
                                        event,
                                        selectedMaterialDetail,
                                        edgeItem,
                                        token,
                                      )
                                    }
                                    src={buildMaterialEdgeImageCandidates(
                                      selectedMaterialDetail,
                                      edgeItem,
                                      token,
                                    )[0]}
                                  />
                                  <div className="material-edge-card-preview-placeholder" hidden>
                                    {slot.label}
                                  </div>
                                </>
                              ) : (
                                <div className="material-edge-card-preview-placeholder">
                                  {slot.label}
                                </div>
                              )}
                              </div>
                            </div>
                          </div>
                        </div>

                      {edgeForm.open ? (
                        <div className="material-edge-form">
                          <input
                            onChange={(event) => updateMaterialEdgeForm(slot.key, event.target.value)}
                            placeholder={t.materialEdgeAttachPlaceholder}
                            type="url"
                            value={edgeForm.source_url}
                          />
                          <button
                            className="primary-button compact-button"
                            disabled={loading || !String(edgeForm.source_url || "").trim()}
                            onClick={() => handleAttachMaterialEdge(slot.key)}
                            type="button"
                          >
                            {t.materialEdgeAttachConfirm}
                          </button>
                        </div>
                      ) : null}
                    </article>
                  );
                  })}
                </div>
              ) : (
                <p className="empty-inline-note material-edge-empty-note">{t.materialEdgeSlotEmpty}</p>
              )}
            </section>
          </section>
        </div>
      ) : null}

      {holeTemplateCreateOpen ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={closeHoleTemplateCreateForm}
          role="dialog"
        >
          <section
            className="confirm-modal hole-template-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>{t.holeTemplateCreateTitle}</strong>
                <p>{t.holeTemplateCreateDescription}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="icon-button"
                disabled={loading}
                onClick={closeHoleTemplateCreateForm}
                type="button"
              >
                <X size={18} />
              </button>
            </header>

            <form className="hole-template-form" onSubmit={handleHoleTemplateCreate}>
              <label>
                {t.holeTemplateFitting}
                <input
                  disabled
                  readOnly
                  type="text"
                  value={
                    selectedHoleFitting
                      ? selectedHoleFitting.name || selectedHoleFitting.article || selectedHoleFitting.code || selectedHoleFitting.id
                      : holeSelectedFittingId
                  }
                />
              </label>

              {renderHoleTemplateFittingInfo(selectedHoleFitting)}

              <label>
                {t.holeTemplateName}
                <input
                  autoFocus
                  disabled={loading}
                  onChange={(event) =>
                    setHoleTemplateCreateForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  required
                  type="text"
                  value={holeTemplateCreateForm.name}
                />
              </label>

              <div className="hole-template-form-grid">
                <label>
                  {t.holeTemplateType}
                  <select
                    disabled={loading}
                    onChange={(event) =>
                      setHoleTemplateCreateForm((current) => ({
                        ...current,
                        template_type: event.target.value,
                      }))
                    }
                    value={holeTemplateCreateForm.template_type}
                  >
                    <option value="manual">{t.holeTemplateTypeSelectManual}</option>
                    <option value="auto">{t.holeTemplateTypeSelectAuto}</option>
                  </select>
                </label>

                <label>
                  {t.holeTemplateSide}
                  <select
                    disabled={loading}
                    onChange={(event) =>
                      updateHoleTemplateSide(setHoleTemplateCreateForm, event.target.value)
                    }
                    value={normalizeHoleTemplateSide(holeTemplateCreateForm.side)}
                  >
                    <option value="left">{t.holePointSideLeft}</option>
                    <option value="right">{t.holePointSideRight}</option>
                    <option value="top">{t.holePointSideTop}</option>
                    <option value="bottom">{t.holePointSideBottom}</option>
                    <option value="front">{t.holePointSideFront}</option>
                    <option value="back">{t.holePointSideBack}</option>
                  </select>
                </label>

                <label>
                  {t.holeTemplateCoordinateSystem}
                  <select
                    disabled={loading}
                    onChange={(event) =>
                      setHoleTemplateCreateForm((current) => ({
                        ...current,
                        coordinate_system: event.target.value,
                      }))
                    }
                    value={holeTemplateCreateForm.coordinate_system}
                  >
                    <option value="2d">{t.holeTemplateCoordinateSystem2d}</option>
                    <option value="3d">{t.holeTemplateCoordinateSystem3d}</option>
                  </select>
                </label>
              </div>

              {renderHoleTemplateMountingSchemePicker(
                holeTemplateCreateForm.side,
                (side) => updateHoleTemplateSide(setHoleTemplateCreateForm, side),
              )}

              <div>
                <div>{t.holeTemplateConnectionVariantTitle}</div>
                <p>{t.holeTemplateConnectionVariantPlaceholder}</p>
              </div>

              <div className="hole-template-checks">
                <label className="material-inline-check">
                  <input
                    checked={holeTemplateCreateForm.is_default}
                    disabled={loading}
                    onChange={(event) =>
                      setHoleTemplateCreateForm((current) => ({
                        ...current,
                        is_default: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.holeTemplateDefault}
                </label>
                <label className="material-inline-check">
                  <input
                    checked={holeTemplateCreateForm.is_active}
                    disabled={loading}
                    onChange={(event) =>
                      setHoleTemplateCreateForm((current) => ({
                        ...current,
                        is_active: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.holeTemplateActive}
                </label>
              </div>

              <label>
                {t.holeTemplateNotes}
                <textarea
                  disabled={loading}
                  onChange={(event) =>
                    setHoleTemplateCreateForm((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                  rows="3"
                  value={holeTemplateCreateForm.notes}
                />
              </label>

              {holeTemplateCreateError ? (
                <p className="hole-template-error">{holeTemplateCreateError}</p>
              ) : null}

              <div className="confirm-actions hole-template-actions">
                <button
                  className="ghost-button"
                  disabled={loading}
                  onClick={closeHoleTemplateCreateForm}
                  type="button"
                >
                  {t.cancel}
                </button>
                <button className="primary-button" disabled={loading || !holeSelectedFittingId} type="submit">
                  <Plus size={16} />
                  {t.holeTemplateSave}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {holeTemplateEditOpen ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={closeHoleTemplateEditForm}
          role="dialog"
        >
          <section
            className="confirm-modal hole-template-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>{t.holeTemplateEditTitle}</strong>
                <p>{t.holeTemplateEditDescription}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="icon-button"
                disabled={holeTemplateEditSaving}
                onClick={closeHoleTemplateEditForm}
                type="button"
              >
                <X size={18} />
              </button>
            </header>

            <form className="hole-template-form" onSubmit={handleHoleTemplateEdit}>
              <label>
                {t.holeTemplateFitting}
                <input
                  disabled
                  readOnly
                  type="text"
                  value={
                    selectedHoleFitting
                      ? selectedHoleFitting.name || selectedHoleFitting.article || selectedHoleFitting.code || selectedHoleFitting.id
                      : holeSelectedFittingId
                  }
                />
              </label>

              {renderHoleTemplateFittingInfo(selectedHoleFitting)}

              <label>
                {t.holeTemplateName}
                <input
                  autoFocus
                  disabled={holeTemplateEditSaving}
                  onChange={(event) =>
                    setHoleTemplateEditForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                  required
                  type="text"
                  value={holeTemplateEditForm.name}
                />
              </label>

              <div className="hole-template-form-grid">
                <label>
                  {t.holeTemplateType}
                  <select
                    disabled={holeTemplateEditSaving}
                    onChange={(event) =>
                      setHoleTemplateEditForm((current) => ({
                        ...current,
                        template_type: event.target.value,
                      }))
                    }
                    value={holeTemplateEditForm.template_type}
                  >
                    <option value="manual">{t.holeTemplateTypeSelectManual}</option>
                    <option value="auto">{t.holeTemplateTypeSelectAuto}</option>
                  </select>
                </label>

                <label>
                  {t.holeTemplateSide}
                  <select
                    disabled={holeTemplateEditSaving}
                    onChange={(event) =>
                      updateHoleTemplateSide(setHoleTemplateEditForm, event.target.value)
                    }
                    value={normalizeHoleTemplateSide(holeTemplateEditForm.side)}
                  >
                    <option value="left">{t.holePointSideLeft}</option>
                    <option value="right">{t.holePointSideRight}</option>
                    <option value="top">{t.holePointSideTop}</option>
                    <option value="bottom">{t.holePointSideBottom}</option>
                    <option value="front">{t.holePointSideFront}</option>
                    <option value="back">{t.holePointSideBack}</option>
                  </select>
                </label>

                <label>
                  {t.holeTemplateCoordinateSystem}
                  <select
                    disabled={holeTemplateEditSaving}
                    onChange={(event) =>
                      setHoleTemplateEditForm((current) => ({
                        ...current,
                        coordinate_system: event.target.value,
                      }))
                    }
                    value={holeTemplateEditForm.coordinate_system}
                  >
                    <option value="2d">{t.holeTemplateCoordinateSystem2d}</option>
                    <option value="3d">{t.holeTemplateCoordinateSystem3d}</option>
                  </select>
                </label>
              </div>

              {renderHoleTemplateMountingSchemePicker(
                holeTemplateEditForm.side,
                (side) => updateHoleTemplateSide(setHoleTemplateEditForm, side),
              )}

              <div>
                <div>{t.holeTemplateConnectionVariantTitle}</div>
                <p>{t.holeTemplateConnectionVariantPlaceholder}</p>
              </div>

              <div className="hole-template-checks">
                <label className="material-inline-check">
                  <input
                    checked={holeTemplateEditForm.is_default}
                    disabled={holeTemplateEditSaving}
                    onChange={(event) =>
                      setHoleTemplateEditForm((current) => ({
                        ...current,
                        is_default: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.holeTemplateDefault}
                </label>
                <label className="material-inline-check">
                  <input
                    checked={holeTemplateEditForm.is_active}
                    disabled={holeTemplateEditSaving}
                    onChange={(event) =>
                      setHoleTemplateEditForm((current) => ({
                        ...current,
                        is_active: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.holeTemplateActive}
                </label>
              </div>

              <label>
                {t.holeTemplateNotes}
                <textarea
                  disabled={holeTemplateEditSaving}
                  onChange={(event) =>
                    setHoleTemplateEditForm((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                  rows="3"
                  value={holeTemplateEditForm.notes}
                />
              </label>

              {holeTemplateEditError ? (
                <p className="hole-template-error">{holeTemplateEditError}</p>
              ) : null}

              <div className="confirm-actions hole-template-actions">
                <button
                  className="ghost-button"
                  disabled={holeTemplateEditSaving}
                  onClick={closeHoleTemplateEditForm}
                  type="button"
                >
                  {t.cancel}
                </button>
                <button
                  className="primary-button"
                  disabled={holeTemplateEditSaving || !holeTemplateEditTemplateId}
                  type="submit"
                >
                  <Save size={16} />
                  {t.holeTemplateSaveChanges}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {holePointCreateOpen ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={closeHolePointCreateForm}
          role="dialog"
        >
          <section
            className="confirm-modal hole-template-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>{t.holePointCreateTitle}</strong>
                <p>{t.holePointCreateDescription}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="icon-button"
                disabled={loading}
                onClick={closeHolePointCreateForm}
                type="button"
              >
                <X size={18} />
              </button>
            </header>

            <form className="hole-template-form" onSubmit={handleHolePointCreate}>
              <label>
                {t.holePointTemplate}
                <input
                  disabled
                  readOnly
                  type="text"
                  value={
                    selectedHoleTemplate
                      ? `${selectedHoleTemplate.id} · ${selectedHoleTemplate.name || t.notSet}`
                      : holeSelectedTemplateId
                  }
                />
              </label>

              <label>
                {t.holePointLabel}
                <input
                  disabled={loading}
                  onChange={(event) =>
                    setHolePointCreateForm((current) => ({
                      ...current,
                      label: event.target.value,
                    }))
                  }
                  type="text"
                  value={holePointCreateForm.label}
                />
              </label>

              <div className="hole-template-form-grid">
                <label>
                  {t.holePointX}
                  <input
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        x_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointCreateForm.x_mm}
                  />
                </label>

                <label>
                  {t.holePointY}
                  <input
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        y_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointCreateForm.y_mm}
                  />
                </label>

                <label>
                  {t.holePointZ}
                  <input
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        z_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointCreateForm.z_mm}
                  />
                </label>
              </div>

              <div className="hole-template-form-grid">
                <label>
                  {t.holePointDiameter}
                  <input
                    disabled={loading}
                    min="0.01"
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        diameter_mm: event.target.value,
                      }))
                    }
                    required
                    step="any"
                    type="number"
                    value={holePointCreateForm.diameter_mm}
                  />
                </label>

                <label>
                  {t.holePointDepth}
                  <input
                    disabled={loading}
                    min="0"
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        depth_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointCreateForm.depth_mm}
                  />
                </label>

                <label>
                  {t.holePointSide}
                  <select
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        side: event.target.value,
                      }))
                    }
                    value={holePointCreateForm.side}
                  >
                    {HOLE_POINT_SIDE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t[option.labelKey] || option.value}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="hole-template-form-grid">
                <label>
                  {t.holePointOperation}
                  <select
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        operation: event.target.value,
                      }))
                    }
                    value={holePointCreateForm.operation}
                  >
                    {HOLE_POINT_OPERATION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t[option.labelKey] || option.value}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  {t.holePointOrderIndex}
                  <input
                    disabled={loading}
                    min="0"
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        order_index: event.target.value,
                      }))
                    }
                    step="1"
                    type="number"
                    value={holePointCreateForm.order_index}
                  />
                </label>

                <label>
                  {t.holePointQuantity}
                  <input
                    disabled={loading}
                    min="1"
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        quantity: event.target.value,
                      }))
                    }
                    step="1"
                    type="number"
                    value={holePointCreateForm.quantity}
                  />
                </label>
              </div>

              <div className="hole-template-checks">
                <label className="material-inline-check">
                  <input
                    checked={holePointCreateForm.mirrored}
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointCreateForm((current) => ({
                        ...current,
                        mirrored: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.holePointMirrored}
                </label>
              </div>

              <label>
                {t.holePointNotes}
                <textarea
                  disabled={loading}
                  onChange={(event) =>
                    setHolePointCreateForm((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                  rows="3"
                  value={holePointCreateForm.notes}
                />
              </label>

              {holePointCreateError ? (
                <p className="hole-template-error">{holePointCreateError}</p>
              ) : null}

              <div className="confirm-actions hole-template-actions">
                <button
                  className="ghost-button"
                  disabled={loading}
                  onClick={closeHolePointCreateForm}
                  type="button"
                >
                  {t.cancel}
                </button>
                <button className="primary-button" disabled={loading || !holeSelectedTemplateId} type="submit">
                  <Plus size={16} />
                  {t.save}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      {holePointEditOpen ? (
        <div
          aria-modal="true"
          className="modal-backdrop"
          onClick={closeHolePointEditForm}
          role="dialog"
        >
          <section
            className="confirm-modal hole-template-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>{t.holePointEditTitle}</strong>
                <p>{t.holePointEditDescription}</p>
              </div>
              <button
                aria-label={t.cancel}
                className="icon-button"
                disabled={loading}
                onClick={closeHolePointEditForm}
                type="button"
              >
                <X size={18} />
              </button>
            </header>

            <form className="hole-template-form" onSubmit={handleHolePointEdit}>
              <label>
                {t.holePointTemplate}
                <input
                  disabled
                  readOnly
                  type="text"
                  value={
                    selectedHoleTemplate
                      ? `${selectedHoleTemplate.id} · ${selectedHoleTemplate.name || t.notSet}`
                      : holePointEditForm.template_id
                  }
                />
              </label>

              <label>
                {t.holePointLabel}
                <input
                  disabled={loading}
                  onChange={(event) =>
                    setHolePointEditForm((current) => ({
                      ...current,
                      label: event.target.value,
                    }))
                  }
                  type="text"
                  value={holePointEditForm.label}
                />
              </label>

              <div className="hole-template-form-grid">
                <label>
                  {t.holePointX}
                  <input
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        x_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointEditForm.x_mm}
                  />
                </label>

                <label>
                  {t.holePointY}
                  <input
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        y_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointEditForm.y_mm}
                  />
                </label>

                <label>
                  {t.holePointZ}
                  <input
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        z_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointEditForm.z_mm}
                  />
                </label>
              </div>

              <div className="hole-template-form-grid">
                <label>
                  {t.holePointDiameter}
                  <input
                    disabled={loading}
                    min="0.01"
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        diameter_mm: event.target.value,
                      }))
                    }
                    required
                    step="any"
                    type="number"
                    value={holePointEditForm.diameter_mm}
                  />
                </label>

                <label>
                  {t.holePointDepth}
                  <input
                    disabled={loading}
                    min="0"
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        depth_mm: event.target.value,
                      }))
                    }
                    step="any"
                    type="number"
                    value={holePointEditForm.depth_mm}
                  />
                </label>

                <label>
                  {t.holePointSide}
                  <select
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        side: event.target.value,
                      }))
                    }
                    value={holePointEditForm.side}
                  >
                    {HOLE_POINT_SIDE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t[option.labelKey] || option.value}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="hole-template-form-grid">
                <label>
                  {t.holePointOperation}
                  <select
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        operation: event.target.value,
                      }))
                    }
                    value={holePointEditForm.operation}
                  >
                    {HOLE_POINT_OPERATION_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {t[option.labelKey] || option.value}
                      </option>
                    ))}
                  </select>
                </label>

                <label>
                  {t.holePointOrderIndex}
                  <input
                    disabled={loading}
                    min="0"
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        order_index: event.target.value,
                      }))
                    }
                    step="1"
                    type="number"
                    value={holePointEditForm.order_index}
                  />
                </label>

                <label>
                  {t.holePointQuantity}
                  <input
                    disabled={loading}
                    min="1"
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        quantity: event.target.value,
                      }))
                    }
                    step="1"
                    type="number"
                    value={holePointEditForm.quantity}
                  />
                </label>
              </div>

              <div className="hole-template-checks">
                <label className="material-inline-check">
                  <input
                    checked={holePointEditForm.mirrored}
                    disabled={loading}
                    onChange={(event) =>
                      setHolePointEditForm((current) => ({
                        ...current,
                        mirrored: event.target.checked,
                      }))
                    }
                    type="checkbox"
                  />
                  {t.holePointMirrored}
                </label>
              </div>

              <label>
                {t.holePointNotes}
                <textarea
                  disabled={loading}
                  onChange={(event) =>
                    setHolePointEditForm((current) => ({
                      ...current,
                      notes: event.target.value,
                    }))
                  }
                  rows="3"
                  value={holePointEditForm.notes}
                />
              </label>

              {holePointEditError ? (
                <p className="hole-template-error">{holePointEditError}</p>
              ) : null}

              <div className="confirm-actions hole-template-actions">
                <button
                  className="ghost-button"
                  disabled={loading}
                  onClick={closeHolePointEditForm}
                  type="button"
                >
                  {t.cancel}
                </button>
                <button className="primary-button" disabled={loading || !holePointEditPointId} type="submit">
                  <Save size={16} />
                  {t.holePointSaveChanges}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

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
