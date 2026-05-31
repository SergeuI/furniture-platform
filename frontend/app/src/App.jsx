import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  RotateCcw,
  Download,
  Eye,
  LogOut,
  Plus,
  RefreshCw,
  Save,
  Search,
} from "lucide-react";
import { Suspense, lazy, useEffect, useMemo, useState } from "react";

import {
  generateProject,
  getCuttingExportFormats,
  getCuttingJsonExport,
  getCurrentUser,
  getProject,
  getProjectBom,
  getProjectCutting,
  getProjectPartDetail,
  getSpecificationCatalog,
  listProjects,
  login,
  updateProjectPartEdges,
  updateProjectPartMachining,
} from "./api";
const PartThreeViewer = lazy(() => import("./components/PartThreeViewer"));
const ProjectThreeViewer = lazy(() => import("./components/ProjectThreeViewer"));


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
    app: "Застосунок",
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
  const [cuttingExportFormats, setCuttingExportFormats] = useState([]);
  const [cuttingJsonExport, setCuttingJsonExport] = useState(null);
  const [selectedPartDetail, setSelectedPartDetail] = useState(null);
  const [selectedCuttingPartCode, setSelectedCuttingPartCode] = useState(null);
  const [selectedEdgeSide, setSelectedEdgeSide] = useState(null);
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
    setCuttingExportFormats([]);
    setCuttingJsonExport(null);
    setSelectedPartDetail(null);
    setSelectedCuttingPartCode(null);
    setSelectedEdgeSide(null);
    setActiveProjectTab("general");
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
          <div className="auth-brand">
            <img
              alt={t.furniturePlatform}
              className="brand-logo"
              src="/brand/mproject-logo-flat.svg"
            />
            <div className="auth-heading">
              <p>{t.brandTagline}</p>
              <h1>{t.app}</h1>
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
        <div className="brand-block brand-lockup">
          <img alt="" className="brand-mark" src="/brand/mp-symbol-flat.svg" />
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
                      <h3>{t.productionAssembly3d}</h3>
                      {cuttingItems.length > 0 ? (
                        <Suspense fallback={<div className="part-three-viewer part-three-viewer-loading">Loading 3D assembly...</div>}>
                          <ProjectThreeViewer
                            items={cuttingItems}
                            onClearSelection={handleClearCuttingPartSelection}
                            onOpenPart={handleSelectCuttingPart}
                            onSelectPart={handlePreviewCuttingPart}
                            selectedPartDetail={selectedPartDetail}
                            selectedPartCode={selectedCuttingPartCode || selectedPartDetail?.part?.export_code}
                            t={t}
                          />
                        </Suspense>
                      ) : (
                        <p>{t.noCuttingItems}</p>
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
                              <tr
                                className={
                                selectedPartDetail?.part?.export_code === item.export_code
                                  || selectedCuttingPartCode === item.export_code
                                  ? "selected"
                                  : ""
                              }
                              key={item.export_code}
                              onClick={() => handlePreviewCuttingPart(item.export_code)}
                            >
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
                    canEdit={user?.role !== "viewer"}
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
