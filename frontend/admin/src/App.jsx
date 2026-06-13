import {
  Blocks,
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
  LogOut,
  Plus,
  RefreshCw,
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
import { Component, Suspense, lazy, useEffect, useMemo, useState } from "react";

import {
  changeOwnPassword,
  createFitting,
  createManualService,
  createMyEmailChangeRequest,
  createCatalogItem,
  createUser,
  deleteFitting,
  deleteMaterial,
  deleteProject,
  generateProject,
  getCatalogAutoRefreshStatus,
  getCurrentUser,
  getFittingsCatalog,
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
  listUsers,
  listUserChangeRequests,
  listProjects,
  login,
  reviewUserChangeRequest,
  rollbackProject,
  resetUserPassword,
  updateCatalogItem,
  updateCatalogItemActive,
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
} from "./api";
const PartThreeViewer = lazy(() => import("./components/PartThreeViewer"));
const ProjectThreeViewer = lazy(() => import("./components/ProjectThreeViewer"));


const TOKEN_STORAGE_KEY = "furniture_admin_token";
const LANGUAGE_STORAGE_KEY = "furniture_admin_language";
const ACTIVE_VIEW_STORAGE_KEY = "furniture_admin_active_view";
const ACTIVE_PROJECT_ID_STORAGE_KEY = "furniture_admin_active_project_id";
const ACTIVE_PROJECT_TAB_STORAGE_KEY = "furniture_admin_active_project_tab";
const VIYAR_SERVICES_CACHE_PREFIX = "furniture_admin_viyar_services_cache";
const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
);
const PAGE_SIZE = 20;
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

const DEFAULT_CITY_OPTIONS = [
  "kyiv",
  "lviv",
  "odessa",
  "dnipro",
  "kharkiv",
  "khmelnytskyi",
  "rivne",
];

const CATALOG_SERVICE_VIEWS = new Set([
  "catalogHub",
  "catalogViyar",
  "catalogManual",
  "catalogMaterials",
  "catalogFittings",
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
    image: "/catalog/fittings/connectors-fasteners.png",
  },
  drawer_slides: {
    accent: "#0f766e",
    icon: ChevronRight,
    image: "/catalog/fittings/drawer-slides.png",
  },
  handles_hooks: {
    accent: "#2563eb",
    icon: Wrench,
    image: "/catalog/fittings/handles-hooks.png",
  },
  profiles_gola: {
    accent: "#1f6b34",
    icon: LayoutGrid,
    image: "/catalog/fittings/profiles-gola.png",
  },
  plinth_vents: {
    accent: "#2f8ecb",
    icon: LayoutGrid,
    image: "/catalog/fittings/plinth-vents.png",
  },
  legs_wheels: {
    accent: "#8b5cf6",
    icon: LayoutGrid,
    image: "/catalog/fittings/legs-wheels.png",
  },
  locks_magnets: {
    accent: "#f97316",
    icon: Settings2,
    image: "/catalog/fittings/locks-magnets.png",
  },
  wardrobe_systems: {
    accent: "#14b8a6",
    icon: LayoutGrid,
    image: "/catalog/fittings/wardrobe-systems.png",
  },
  hinges: {
    accent: "#ec4899",
    icon: LayoutGrid,
    image: "/catalog/fittings/hinges.png",
  },
  bathroom: {
    accent: "#0ea5e9",
    icon: House,
    image: "/catalog/fittings/bathroom.png",
  },
  packaging: {
    accent: "#f97316",
    icon: Package,
    image: "/catalog/fittings/packaging.png",
  },
  bed_components: {
    accent: "#6366f1",
    icon: LayoutGrid,
    image: "/catalog/fittings/bed-components.png",
  },
  wardrobe_fillings: {
    accent: "#10b981",
    icon: LayoutGrid,
    image: "/catalog/fittings/wardrobe-fillings.png",
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
  materialAdd: "Add material from Viyar",
  materialAddArticle: "Viyar article",
  materialAddArticlePlaceholder: "Enter article and add",
  materialAddUrl: "Viyar product URL (optional)",
  materialAddUrlPlaceholder: "Paste direct product link if search fails",
  materialCategory: "Material type",
  materialImportSuccess: "Material added from Viyar",
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
  materialsCount: "Materials",
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
  materialAdd: "\u0414\u043e\u0434\u0430\u0442\u0438 \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b \u0437 Viyar",
  materialAddArticle: "\u0410\u0440\u0442\u0438\u043a\u0443\u043b Viyar",
  materialAddArticlePlaceholder:
    "\u0412\u0432\u0435\u0434\u0456\u0442\u044c \u0430\u0440\u0442\u0438\u043a\u0443\u043b \u0456 \u0434\u043e\u0434\u0430\u0439\u0442\u0435",
  materialAddUrl: "\u041f\u0440\u044f\u043c\u0435 \u043f\u043e\u0441\u0438\u043b\u0430\u043d\u043d\u044f Viyar (\u043d\u0435\u043e\u0431\u043e\u0432'\u044f\u0437\u043a\u043e\u0432\u043e)",
  materialAddUrlPlaceholder:
    "\u0412\u0441\u0442\u0430\u0432\u0442\u0435 \u043f\u0440\u044f\u043c\u0438\u0439 URL \u0442\u043e\u0432\u0430\u0440\u0443, \u044f\u043a\u0449\u043e \u043f\u043e\u0448\u0443\u043a \u043d\u0435 \u0441\u043f\u0440\u0430\u0446\u044e\u0432\u0430\u0432",
  materialCategory: "\u0422\u0438\u043f \u043c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0443",
  materialImportSuccess: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b \u0434\u043e\u0434\u0430\u043d\u043e \u0437 Viyar",
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
  materialsCount: "\u041c\u0430\u0442\u0435\u0440\u0456\u0430\u043b\u0438",
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

function buildProjectPayload(form) {
  return {
    metadata: {
      name: form.projectName || DEFAULT_PROJECT_NAME,
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

function buildMaterialImageCandidates(item, token = "") {
  const candidates = [];
  const article = String(item?.article || "").trim();
  const baseImage = String(item?.image || "").trim();
  const hasCachedImage = Boolean(item?.has_cached_image);
  const tokenQuery = token ? `?access_token=${encodeURIComponent(token)}` : "";

  if (baseImage) {
    candidates.push(baseImage);
  }

  if (article && hasCachedImage) {
    candidates.unshift(`${API_BASE_URL}/catalog/materials/${encodeURIComponent(article)}/image${tokenQuery}`);
  } else if (article) {
    candidates.push(`${API_BASE_URL}/catalog/materials/${encodeURIComponent(article)}/image${tokenQuery}`);
  }

  if (article) {
    candidates.push(`https://viyar.ua/upload/resize_cache/photos/512_512_1/ph${article}.jpg`);
    candidates.push(`https://www.viyar.ua/store/Items/photos/ph${article}.jpg`);
    candidates.push(`https://viyar.ua/store/Items/photos/ph${article}.jpg`);
    candidates.push(`https://www.viyar.ua/upload/resize_cache/photos/512_512_1/ph${article}.jpg`);
  }

  return [...new Set(candidates.filter(Boolean))];
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

function canManageMaterialCatalog(user) {
  return user?.role === "admin" || user?.role === "pro";
}

function canManageSystemFittings(user) {
  return user?.role === "admin";
}

function canManageOwnFittings(user) {
  return user?.role === "admin" || user?.role === "pro";
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

  if (user.role === "user" || user.role === "pro") {
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
  return user?.role === "admin" || user?.role === "user" || user?.role === "pro";
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
  const [language, setLanguage] = useState(
    () => localStorage.getItem(LANGUAGE_STORAGE_KEY) || "en",
  );
  const [token, setToken] = useState(
    () => localStorage.getItem(TOKEN_STORAGE_KEY) || "",
  );
  const [user, setUser] = useState(null);
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
    role: "user",
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
  const [materialSearch, setMaterialSearch] = useState("");
  const [materialCategoryFilter, setMaterialCategoryFilter] = useState("dsp");
  const [newMaterialArticle, setNewMaterialArticle] = useState("");
  const [newMaterialSourceUrl, setNewMaterialSourceUrl] = useState("");
  const [activeMaterialImportJobId, setActiveMaterialImportJobId] = useState("");
  const [activeMaterialImportJob, setActiveMaterialImportJob] = useState(null);
  const [openMaterialMenuId, setOpenMaterialMenuId] = useState("");
  const [openFittingMenuId, setOpenFittingMenuId] = useState("");
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
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
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
  const [newFittingForm, setNewFittingForm] = useState(DEFAULT_FITTING_FORM);
  const [autoRefreshStatus, setAutoRefreshStatus] = useState(null);
  const storedProjectId = localStorage.getItem(ACTIVE_PROJECT_ID_STORAGE_KEY) || "";
  const storedProjectTab = localStorage.getItem(ACTIVE_PROJECT_TAB_STORAGE_KEY) || "data";

  const t = TRANSLATIONS[language] || TRANSLATIONS.en;
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
        setStatus(t.materialImportSuccess);
        await loadMaterialsCatalog(token);
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
  const isCatalogValuesView = activeView === "catalogValues";
  const isCatalogViyarView = activeView === "catalogViyar";
  const isCatalogManualView = activeView === "catalogManual";
  const isCatalogHubView = activeView === "catalogHub";
  const isCatalogView =
    isCatalogHubView ||
    isCatalogMaterialsView ||
    isCatalogFittingsView ||
    isCatalogFastenersView ||
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
  const getFittingSourceMeta = (item) => {
    const sourceSite = item?.source_site || detectFittingSourceSite(item?.source_url);

    if (sourceSite === "viyar") {
      return {
        code: "viyar",
        label: "Viyar",
        shortLabel: "viyar",
      };
    }

    if (sourceSite === "blum") {
      return {
        code: "blum",
        label: "BLUM",
        shortLabel: "blum",
      };
    }

    if (sourceSite === "kronas") {
      return {
        code: "kronas",
        label: "Kronas",
        shortLabel: "kronas",
      };
    }

    return {
      code: "manual",
      label: t.fittingManualSource,
      shortLabel: t.fittingManualSource,
    };
  };

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

    if (!result.success) {
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
      setStatus(result.error || t.unableToLoadCatalog);
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
      setStatus(result.error || t.unableToLoadCatalog);
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
      setStatus(result.error || t.unableToLoadCatalog);
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

  async function handleMaterialCitySave(event) {
    event.preventDefault();

    if (!token) {
      return;
    }

    const profilePayload = {
      phone: ownProfileForm.phone.trim(),
      city: materialSelectedCity,
    };

    if (ownProfileForm.username.trim()) {
      profilePayload.username = ownProfileForm.username.trim();
    }

    setLoading(true);
    const result = await updateMyProfile(token, profilePayload);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadCatalog);
      return;
    }

    setUser(result.user);
    setOwnProfileForm((current) => ({
      ...current,
      city: result.user.city || "",
    }));
    setStatus(t.citySaved);
    await loadMaterialsCatalog(token, {
      category: materialCategoryFilter,
      city: result.user.city || "",
      search: materialSearch,
    });
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
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_VIEW_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_ID_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_PROJECT_TAB_STORAGE_KEY);
    setToken("");
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

    const profilePayload = {
      phone: ownProfileForm.phone.trim(),
      city: ownProfileForm.city.trim(),
    };

    if (ownProfileForm.username.trim()) {
      profilePayload.username = ownProfileForm.username.trim();
    }

    setLoading(true);
    const result = await updateMyProfile(token, profilePayload);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.usernameChangeWeekly);
      return;
    }

    setUser(result.user);
    setStatus(t.profileSaved);
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
    setStatus(t.viyarSavingCredentials);
    setLoading(true);
    const result = await updateMyViyarAuth(
      token,
      normalizedViyarEmail,
      viyarAuthForm.password || null,
    );
    setLoading(false);

    if (!result.success) {
      setViyarAction("");
      setStatus(result.error || t.unableToSaveViyarAuth);
      return;
    }

    setViyarAuth(result.viyar || null);
    setViyarAuthForm((current) => ({
      ...current,
      email: result.viyar?.email || current.email,
        password: "",
      }));
    setViyarAction("");
    setStatus(t.viyarCredentialsSaved);
  }

  async function handleRefreshViyarSession() {
    if (!normalizedViyarEmail) {
      setStatus(t.viyarStepSave);
      return;
    }

    if (viyarEmailChanged || viyarHasUnsavedPassword || !viyarHasSavedPassword) {
      setViyarAction("saving");
      setStatus(t.viyarSavingCredentials);
      setLoading(true);
      const saveResult = await updateMyViyarAuth(
        token,
        normalizedViyarEmail,
        viyarAuthForm.password || null,
      );
      setLoading(false);

      if (!saveResult.success) {
        setViyarAction("");
        setStatus(saveResult.error || t.unableToSaveViyarAuth);
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
    setStatus(t.viyarConnectingNow);
    setLoading(true);
    const result = await refreshMyViyarSession(token);
    setLoading(false);

    if (!result.success) {
      if (result.viyar) {
        setViyarAuth(result.viyar);
      }
      setViyarAction("");
      setStatus(result.error || t.unableToRefreshViyarSession);
      return;
    }

    setViyarAuth(result.viyar || null);
    setViyarAction("");
    setStatus(t.viyarConnected);
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
      role: "user",
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

    if (!ownProfileForm.city.trim()) {
      setStatus(t.cityRequiredForMaterialImport);
      return;
    }

    setLoading(true);
    const result = await importMaterialFromViyar(
      token,
      newMaterialArticle.trim(),
      materialCategoryFilter || "dsp",
      newMaterialSourceUrl.trim(),
    );
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadCatalog);
      return;
    }

    setNewMaterialArticle("");
    setNewMaterialSourceUrl("");

    if (result.item) {
      if (result.job) {
        setActiveMaterialImportJob(result.job);
      }
      setStatus(t.materialImportSuccess);
      await loadMaterialsCatalog(token);
      return;
    }

    if (result.job?.id) {
      setActiveMaterialImportJobId(result.job.id);
      setActiveMaterialImportJob(result.job);
      setStatus(t.materialImportQueued);
      return;
    }

    setStatus(result.error || t.materialImportQueued);
  }

  function openDeleteMaterialConfirm(item) {
    if (!item || item.is_default) {
      return;
    }

    setOpenMaterialMenuId("");
    setConfirmAction({
      type: "deleteMaterial",
      title: t.deleteMaterial,
      message: `${t.deleteMaterialConfirm}: ${item.name || item.article}?`,
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
      setStatus(result.error || t.deleteFailed);
      return;
    }

    setMaterialItems((current) => current.filter((item) => item.article !== article));
    setStatus(t.materialDeleted);
    closeConfirm();
  }

  async function handleRefreshMaterial(item) {
    if (!item?.article) {
      return;
    }

    setOpenMaterialMenuId("");
    setStatus(t.materialRefreshStarted);
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
      setStatus(result.error || t.unableToLoadCatalog);
      return;
    }

    if (result.job?.id) {
      setActiveMaterialImportJobId(result.job.id);
      setActiveMaterialImportJob(result.job);
      setStatus(t.materialRefreshQueued);
      return;
    }

    if (result.item) {
      setStatus(t.materialImportSuccess);
      await loadMaterialsCatalog(token);
    }
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
      setStatus(result.error || t.deleteFailed);
      return;
    }

    setFittingItems((current) => current.filter((item) => item.id !== itemId));
    setStatus(t.fittingDelete);
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
      setStatus(t.fittingImageSelected);
    } catch (error) {
      setStatus(error?.message || t.unableToLoadCatalog);
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
      setStatus(t.fittingTypePrompt);
      return;
    }

    if (!payload.article) {
      setStatus(t.fittingArticlePrompt);
      return;
    }

    if (isSystemFitting && !payload.source_url) {
      setStatus(t.fittingSourceUrlPrompt);
      return;
    }

    if (!isSystemFitting && !payload.name) {
      setStatus(t.fittingNamePrompt);
      return;
    }

    setLoading(true);
    const result = await createFitting(token, payload);
    setLoading(false);

    if (!result.success) {
      setStatus(result.error || t.unableToLoadCatalog);
      return;
    }

    setStatus(t.fittingCreateSuccess);
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
      setStatus(t.projectDeleteRestricted);
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
    setActiveProjectTab("history");
    await loadProjectHistory(selectedProjectId);
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
      return;
    }

    async function bootstrapAuthorizedApp() {
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
    }

    bootstrapAuthorizedApp();
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

  if (!token || !user) {
    return (
      <main className="auth-screen">
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
          <span>{user.email}</span>
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
                className={`nav-group-link${isCatalogHubView || isCatalogMaterialsView || isCatalogFittingsView || isCatalogFastenersView ? " active" : ""}`}
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

        {status ? <p className="status">{status}</p> : null}

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
                ) : null}

                {activeProjectTab === "production" ? (
                <section className="production-section">
                  <div className="history-header production-header">
                    <h3>{t.production}</h3>
                  </div>

                  <section className="production-assembly-workspace">
                    <article className="production-card production-card-sticky">
                      <h4>{t.productionAssembly3d}</h4>
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
                      <h4>{t.productionCutting}</h4>
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
                                    <th>{t.materialThickness}</th>
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

                </section>
                ) : null}

                {activeProjectTab === "partDetail" && selectedPartDetail ? (
                  <PartDetailWorkspace
                    canEdit={canEditSelectedProject}
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

                {activeProjectTab === "history" ? (
                <>
                <div className="history-header">
                  <History size={18} />
                  <h3>{t.history}</h3>
                </div>
                <div className="history-list">
                  {historyItems.map((item) => (
                    <article className="history-item" key={item.id}>
                      <div>
                        <strong>{formatDateTime(item.created_at, t)}</strong>
                        <span>
                          {item.width} x {item.height} x {item.depth}
                        </span>
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
                ) : null}
              </>
            ) : (
              <div className="empty-state">
                <Search size={22} />
                <p>{t.selectProject}</p>
              </div>
            )}
          </section>
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
                      {t.city}
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
                        {(materialCityOptions.length ? materialCityOptions : DEFAULT_CITY_OPTIONS).map((city) => (
                          <option key={city} value={city}>
                            {formatCatalogLabel(city, t)}
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

              <article className="settings-card">
                <div className="settings-card-header">
                  <h3>{t.viyarSettingsTitle}</h3>
                </div>
                <form className="settings-password-form" onSubmit={handleSaveViyarAuth}>
                  {viyarAuth?.has_password ? (
                    <div className="settings-inline-status success">
                      <strong>{t.viyarHasSavedPassword}:</strong> {t.viyarSavedState}
                    </div>
                  ) : null}
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
                  <div className="settings-info-grid viyar-status-grid">
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
                    <div className="settings-inline-status info">
                      {viyarNextStepLabel}
                    </div>
                    {viyarActionLabel ? (
                      <div className="settings-inline-status progress">
                        {viyarActionLabel}
                      </div>
                    ) : null}
                    <div className="settings-actions">
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
                  <option value="pro">pro</option>
                  <option value="user">user</option>
                  <option value="guest">guest</option>
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
                        <option value="pro">pro</option>
                        <option value="user">user</option>
                        <option value="guest">guest</option>
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
                    <button
                      className="primary-button"
                      disabled={loading || !newMaterialArticle.trim()}
                      type="submit"
                    >
                      <Plus size={16} />
                      {t.materialAdd}
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
                          <p>{activeMaterialImportJob.last_error}</p>
                        </div>
                      ) : null}
                      {Array.isArray(activeMaterialImportJob.debug_trace) && activeMaterialImportJob.debug_trace.length ? (
                        <div className="material-import-status-trace">
                          <span>{t.materialImportTrace || "Журнал спроб"}</span>
                          <ul>
                            {activeMaterialImportJob.debug_trace.map((entry, index) => (
                              <li key={`${entry.stage || "trace"}-${index}`}>
                                <b>{entry.stage || "step"}</b>
                                {entry.message ? `: ${entry.message}` : ""}
                                {!entry.message && entry.url ? `: ${entry.url}` : ""}
                                {!entry.message && !entry.url && entry.product_url ? `: ${entry.product_url}` : ""}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </>
              ) : null}

              {materialItems.length ? (
                <div className="material-card-grid">
                  {materialItems.map((item) => (
                    <article className="material-card" key={item.id}>
                      {canEditMaterialCatalog ? (
                        <div className="material-card-menu">
                          <button
                            aria-label={t.refreshFromViyar}
                            className="icon-button material-card-menu-trigger"
                            onClick={() =>
                              setOpenMaterialMenuId((current) =>
                                current === item.id ? "" : item.id,
                              )
                            }
                            type="button"
                          >
                            <MoreHorizontal size={16} />
                          </button>
                          {openMaterialMenuId === item.id ? (
                            <div className="material-card-menu-dropdown">
                              <button
                                className="material-card-menu-action"
                                onClick={() => handleRefreshMaterial(item)}
                                type="button"
                              >
                                <RefreshCw size={14} />
                                {t.refreshFromViyar}
                              </button>
                              {!item.is_default ? (
                              <button
                                className="material-card-menu-action danger"
                                onClick={() => openDeleteMaterialConfirm(item)}
                                type="button"
                              >
                                <Trash2 size={14} />
                                {t.deleteMaterial}
                              </button>
                              ) : null}
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
                          <span className="material-card-article">{item.article}</span>
                        </div>
                        <strong>{item.name || item.article}</strong>
                        <div className="material-card-price">
                          <span>
                            {item.current_price_exact === false && item.current_price_city
                              ? `${t.materialPriceFallback} (${formatCatalogLabel(item.current_price_city, t)})`
                              : t.materialPriceForCity}
                          </span>
                          <b>
                            {item.current_price !== null && item.current_price !== undefined
                              ? `${item.current_price} UAH`
                              : t.notSet}
                          </b>
                        </div>
                        <div className="material-card-meta">
                          <span
                            className={`service-tree-badge material-cache-badge ${item.has_cached_image ? "success" : "pending"}`}
                          >
                            {item.has_cached_image ? t.materialCacheReady : t.materialCachePending}
                          </span>
                        </div>
                      </div>
                    </article>
                  ))}
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
                                {item.image_url ? (
                                  <img alt={item.name || item.article || t.catalogFittings} loading="lazy" src={item.image_url} />
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
                                <span className={`service-tree-badge ${item.is_system ? "success" : "subtle"}`}>
                                  {item.is_system ? t.fittingSystemScope : t.fittingCustomScope}
                                </span>
                                <span className={`fitting-source-logo ${sourceMeta.code}`}>{sourceMeta.label}</span>
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
                                    {item.image_url ? (
                                      <img alt={item.name || item.article || t.catalogFittings} loading="lazy" src={item.image_url} />
                                    ) : (
                                      <Package size={18} />
                                    )}
                                  </div>
                                  <div className="fittings-table-name-copy">
                                    <strong>{item.name || item.code || item.article}</strong>
                                    <div className="fittings-table-badges">
                                      <span className={`service-tree-badge ${item.is_system ? "success" : "subtle"}`}>
                                        {item.is_system ? t.fittingSystemScope : t.fittingCustomScope}
                                      </span>
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
                              <span className={`fitting-source-logo ${sourceMeta.code}`}>{sourceMeta.label}</span>
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
