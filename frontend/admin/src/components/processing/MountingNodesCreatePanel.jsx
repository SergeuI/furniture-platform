import { ArrowLeft, ChevronRight, LayoutGrid, List, Plus, Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import FittingHolesWorkspace from "./FittingHolesWorkspace.jsx";
import HolesMountingThreePreview from "./HolesMountingThreePreview.jsx";
import surfaceMountIcon from "../../assets/hole-mounting/surface_mount.png";
import angledTwoPlanesIcon from "../../assets/hole-mounting/angled_two_planes.png";
import faceToEdgeIcon from "../../assets/hole-mounting/face_to_edge.png";
import edgeToEdgeIcon from "../../assets/hole-mounting/edge_to_edge.png";
import drawerSlidesIcon from "../../assets/hole-mounting/drawer_slides.png";
import {
  MOUNTING_NODE_CREATE_ROLE_OPTIONS,
  addMountingNodeCreateDraftItem,
  addMountingNodeCreateDraftPoint,
  commitMountingNodeCreateDraftPoint,
  createMountingNodeCreateDraft,
  createMountingNodeCreateDraftItemFromFitting,
  createMountingNodeCreateDraftPointFromFitting,
  removeMountingNodeCreateDraftItem,
  removeMountingNodeCreateDraftPoint,
  prepareMountingNodeCreateDraftPointForm,
  updateMountingNodeCreateDraftItem,
  updateMountingNodeCreateDraftPoint,
} from "../../mountingNodesCreateDraft.js";
import { getProcessingTemplateMountingVariantLabel } from "../../processingTemplates.js";
import {
  getSurfaceMountPointFormPreset,
  shouldShowSurfaceMountPointTargetFields,
} from "../../surfaceMountThreePreview.js";
import { getAngledTwoPlanesPointFormPreset } from "../../angledTwoPlanesThreePreview.js";
import { buildHolePointFormFromPoint, createHolePointFormDefaults } from "../../holePointForm.js";

const MOUNTING_VARIANT_KEYS = [
  "surface_mount",
  "face_to_edge",
  "edge_to_edge",
  "angled_two_planes",
  "drawer_slides",
];

const POINT_PANEL_OPTIONS = [
  { value: "vertical_panel", label: "Vertical panel" },
  { value: "horizontal_panel", label: "Horizontal panel" },
];

const MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY = "mountingNodesCreateFittingSelectorView";

function normalizeText(value) {
  return String(value ?? "").trim();
}

function humanizeKey(value) {
  return normalizeText(value)
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function normalizeCategoryToken(value) {
  return normalizeText(value)
    .toLowerCase()
    .replace(/[^a-z0-9а-яіїєґ]+/giu, "");
}

function findMatchingFittingCategory(categoryCode, fittingCategories = []) {
  const normalizedCategoryToken = normalizeCategoryToken(categoryCode);

  if (!normalizedCategoryToken) {
    return null;
  }

  return (Array.isArray(fittingCategories) ? fittingCategories : []).find((category) => {
    const normalizedCode = normalizeCategoryToken(category?.code);
    const normalizedName = normalizeCategoryToken(category?.name);
    const normalizedHumanizedCode = normalizeCategoryToken(humanizeKey(category?.code));

    return (
      normalizedCategoryToken === normalizedCode ||
      normalizedCategoryToken === normalizedName ||
      normalizedCategoryToken === normalizedHumanizedCode
    );
  }) || null;
}

function getFittingId(item) {
  return normalizeText(item?.id || item?.fitting_id);
}

function getFittingName(item) {
  return normalizeText(item?.name || item?.article || item?.code || item?.fitting_name || item?.fitting_id);
}

function getFittingArticle(item) {
  return normalizeText(item?.article || item?.code);
}

function getFittingCategoryCode(item) {
  return normalizeText(
    item?.category_code || item?.categoryCode || item?.fitting_type || item?.type || item?.code || "",
  );
}

function getFittingCategoryLabel(item, language, t, fittingCategories = []) {
  const categoryCode = getFittingCategoryCode(item);
  const matchingCategory = findMatchingFittingCategory(categoryCode, fittingCategories);
  const localizedLabel = normalizeText(t?.[categoryCode]);

  return (
    normalizeText(matchingCategory?.name) ||
    localizedLabel ||
    normalizeText(item?.category_label || item?.categoryName || item?.category || item?.fitting_category || "") ||
    humanizeKey(categoryCode)
  );
}

function getFittingImageUrl(item) {
  return normalizeText(item?.image_url || item?.image || item?.thumbnail_url || "");
}

function getMountingVariantDescription(variantKey, language) {
  const descriptions = {
    angled_two_planes:
      language === "uk"
        ? "Кріплення між двома непаралельними площинами."
        : "Mounting between two non-parallel planes.",
    drawer_slides:
      language === "uk"
        ? "Напрямні для висувних елементів."
        : "Slides for pull-out elements.",
    edge_to_edge:
      language === "uk"
        ? "Установка фурнітури по торцях панелей."
        : "Hardware mounted on the edges of panels.",
    face_to_edge:
      language === "uk"
        ? "Установка на площині однієї та торця іншої панелі."
        : "Mounting on one panel face and another panel edge.",
    surface_mount:
      language === "uk"
        ? "Установка фурнітури на площині."
        : "Hardware mounted on a panel face.",
  };

  return descriptions[variantKey] || "";
}

function getMountingVariantIcon(variantKey) {
  const icons = {
    angled_two_planes: angledTwoPlanesIcon,
    drawer_slides: drawerSlidesIcon,
    edge_to_edge: edgeToEdgeIcon,
    face_to_edge: faceToEdgeIcon,
    surface_mount: surfaceMountIcon,
  };

  return icons[variantKey] || surfaceMountIcon;
}

function getMountingVariantOptions(language) {
  return MOUNTING_VARIANT_KEYS.map((key) => ({
    description: getMountingVariantDescription(key, language),
    icon: getMountingVariantIcon(key),
    key,
    label: getProcessingTemplateMountingVariantLabel(key, language) || humanizeKey(key),
  }));
}

function normalizeSelectorViewMode(value) {
  return value === "cards" ? "cards" : "list";
}

function readStoredSelectorViewMode() {
  if (typeof window === "undefined" || !window.localStorage) {
    return "list";
  }

  try {
    return normalizeSelectorViewMode(window.localStorage.getItem(MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY));
  } catch {
    return "list";
  }
}

function PointField({ children, label }) {
  return (
    <label className="mounting-node-create-field">
      <span>{label}</span>
      {children}
    </label>
  );
}

function getPointTargetPanelOptions(mountingVariantKey = "") {
  if (String(mountingVariantKey || "").trim() === "surface_mount") {
    return [{ value: "vertical_panel", label: "Панель" }];
  }

  return [
    { value: "vertical_panel", label: "Вертикальна панель" },
    { value: "horizontal_panel", label: "Горизонтальна панель" },
  ];
}

function getPointTargetSurfaceOptions(targetPanel, mountingVariantKey = "") {
  if (String(mountingVariantKey || "").trim() === "surface_mount") {
    return [{ value: "plane", label: "Площина панелі" }];
  }

  const panel = String(targetPanel || "").trim();

  if (panel === "horizontal_panel") {
    return [
      { value: "edge", label: "Торець" },
      { value: "plane", label: "Площина" },
    ];
  }

  return [
    { value: "plane", label: "Площина" },
    { value: "edge", label: "Торець" },
  ];
}

function getPointTargetSideOptions(targetPanel, targetSurface, currentValue, mountingVariantKey = "") {
  if (String(mountingVariantKey || "").trim() === "surface_mount") {
    return [{ value: "inner_face", label: "Всередину панелі" }];
  }

  const panel = String(targetPanel || "").trim();
  const surface = String(targetSurface || "").trim();
  const normalizedCurrentValue = String(currentValue || "").trim();

  const addCurrentValue = (options) => {
    if (normalizedCurrentValue && !options.some((option) => option.value === normalizedCurrentValue)) {
      return [...options, { value: normalizedCurrentValue, label: normalizedCurrentValue }];
    }

    return options;
  };

  if (panel === "vertical_panel") {
    if (surface === "edge") {
      return addCurrentValue([
        { value: "top_edge", label: "Верхній торець" },
        { value: "bottom_edge", label: "Нижній торець" },
      ]);
    }

    return addCurrentValue([
      { value: "inner_face", label: "Внутрішня площина" },
      { value: "outer_face", label: "Зовнішня / фасадна площина" },
      { value: "needs_clarification", label: "Потребує уточнення площини" },
    ]);
  }

  if (panel === "horizontal_panel") {
    if (surface === "edge") {
      return addCurrentValue([
        { value: "edge_near_vertical", label: "Торець біля вертикальної панелі" },
        { value: "edge_far_vertical", label: "Інший торець" },
      ]);
    }

    return addCurrentValue([
      { value: "top_face", label: "Верхня площина" },
      { value: "bottom_face", label: "Нижня площина" },
      { value: "needs_clarification", label: "Потребує уточнення площини" },
    ]);
  }

  return addCurrentValue([
    { value: "needs_clarification", label: "Потребує уточнення площини" },
  ]);
}

function MountingNodePointFields({
  disabled = false,
  form = {},
  language = "en",
  mountingVariantKey = "",
  onFieldChange = () => {},
  onNumericFieldChange = () => {},
  onToggle = () => {},
}) {
  const normalizedVariantKey = String(mountingVariantKey || "").trim();
  const isAngledTwoPlanesVariant = normalizedVariantKey === "angled_two_planes";
  const showSurfaceMountPointTargetFields = shouldShowSurfaceMountPointTargetFields(normalizedVariantKey);
  const showTargetFields = showSurfaceMountPointTargetFields && !isAngledTwoPlanesVariant;
  const selectedPanelKey = form.target_panel || form.panel_key || "vertical_panel";
  const selectedTargetSurface = form.target_surface || "plane";
  const selectedTargetSide = form.target_side || "inner_face";

  return (
    <div className="mounting-node-create-workspace-side">
      <PointField label={language === "uk" ? "Мітка" : "Label"}>
        <input
          disabled={disabled}
          onChange={(event) => onFieldChange("label", event.target.value)}
          type="text"
          value={form.label || ""}
        />
      </PointField>

      <div className="hole-template-form-grid">
        <PointField label="X">
          <input
            disabled={disabled}
            onChange={(event) => onNumericFieldChange("x_mm", event.target.value)}
            step="any"
            type="number"
            value={form.x_mm}
          />
        </PointField>
        <PointField label="Y">
          <input
            disabled={disabled}
            onChange={(event) => onNumericFieldChange("y_mm", event.target.value)}
            step="any"
            type="number"
            value={form.y_mm}
          />
        </PointField>
        <PointField label="Z">
          <input
            disabled={disabled}
            onChange={(event) => onNumericFieldChange("z_mm", event.target.value)}
            step="any"
            type="number"
            value={form.z_mm}
          />
        </PointField>
      </div>

      {isAngledTwoPlanesVariant ? (
        <div className="hole-template-form-grid">
          <PointField label={language === "uk" ? "Панель" : "Panel"}>
            <select
              disabled={disabled}
              onChange={(event) => onFieldChange("target_panel", event.target.value)}
              value={selectedPanelKey}
            >
              {getPointTargetPanelOptions(normalizedVariantKey).map((option, index) => (
                <option key={`point-target-panel-${index}-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </PointField>
        </div>
      ) : null}

      {showTargetFields ? (
        <div className="hole-template-form-grid">
          <PointField label={language === "uk" ? "Панель" : "Panel"}>
            <select
              disabled={disabled}
              onChange={(event) => onFieldChange("target_panel", event.target.value)}
              value={selectedPanelKey}
            >
              {getPointTargetPanelOptions(normalizedVariantKey).map((option, index) => (
                <option key={`point-target-panel-${index}-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </PointField>
          <PointField label={language === "uk" ? "Поверхня" : "Surface"}>
            <select
              disabled={disabled}
              onChange={(event) => onFieldChange("target_surface", event.target.value)}
              value={selectedTargetSurface}
            >
              {getPointTargetSurfaceOptions(selectedPanelKey, normalizedVariantKey).map((option, index) => (
                <option key={`point-target-surface-${index}-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </PointField>
          <PointField label={language === "uk" ? "Сторона" : "Side"}>
            <select
              disabled={disabled}
              onChange={(event) => onFieldChange("target_side", event.target.value)}
              value={selectedTargetSide}
            >
              {getPointTargetSideOptions(
                selectedPanelKey,
                selectedTargetSurface,
                selectedTargetSide,
                normalizedVariantKey,
              ).map((option, index) => (
                <option key={`point-target-side-${index}-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </PointField>
        </div>
      ) : null}

      <div className="hole-template-form-grid">
        <PointField label={language === "uk" ? "Діаметр" : "Diameter"}>
          <input
            disabled={disabled}
            min="0.01"
            onChange={(event) => onNumericFieldChange("diameter_mm", event.target.value)}
            step="any"
            type="number"
            value={form.diameter_mm}
          />
        </PointField>
        <PointField label={language === "uk" ? "Глибина" : "Depth"}>
          <input
            disabled={disabled || Boolean(form.is_through)}
            onChange={(event) => onNumericFieldChange("depth_mm", event.target.value)}
            step="any"
            type="number"
            value={form.depth_mm}
          />
        </PointField>
        <label className="material-inline-check">
          <input
            checked={Boolean(form.is_through)}
            disabled={disabled}
            onChange={(event) => onToggle("is_through", event.target.checked)}
            type="checkbox"
          />
          {language === "uk" ? "Наскрізний отвір" : "Through"}
        </label>
      </div>

      <div className="hole-template-checks">
        <label className="material-inline-check">
          <input
            checked={(form.operation || "drill") === "drill"}
            disabled={disabled}
            onChange={() => onFieldChange("operation", "drill")}
            type="radio"
            name={`point-operation-${form.client_key || "default"}`}
          />
          {language === "uk" ? "Свердління" : "Drill"}
        </label>
        <label className="material-inline-check">
          <input
            checked={form.operation === "counterbore"}
            disabled={disabled}
            onChange={() => onFieldChange("operation", "counterbore")}
            type="radio"
            name={`point-operation-${form.client_key || "default"}`}
          />
          {language === "uk" ? "Потай" : "Counterbore"}
        </label>
      </div>

      <label className="mounting-node-create-field">
        <span>{language === "uk" ? "Примітки" : "Notes"}</span>
        <textarea
          disabled={disabled}
          onChange={(event) => onFieldChange("notes", event.target.value)}
          rows="3"
          value={form.notes || ""}
        />
      </label>
    </div>
  );
}

function applyMountingNodePointFieldChange(current, field, value) {
  const next = { ...(current || {}), [field]: value };

  if (field === "target_panel" || field === "panel_key") {
    const targetPanel = String(value || "").trim() || "vertical_panel";
    const targetSurface = targetPanel === "horizontal_panel" ? "edge" : "plane";
    const targetSide = targetPanel === "horizontal_panel" ? "edge_near_vertical" : "inner_face";

    next.panel_key = targetPanel;
    next.target_panel = targetPanel;
    next.target_surface = targetSurface;
    next.target_side = targetSide;
    next.side = targetSide;
  }

  if (field === "target_surface") {
    const targetSurface = String(value || "").trim() || "plane";
    const targetPanel = String(next.target_panel || next.panel_key || "vertical_panel").trim() || "vertical_panel";
    const targetSide =
      targetPanel === "horizontal_panel"
        ? (targetSurface === "edge" ? "edge_near_vertical" : "top_face")
        : (targetSurface === "edge" ? "top_edge" : "inner_face");

    next.target_panel = targetPanel;
    next.panel_key = targetPanel;
    next.target_surface = targetSurface;
    next.target_side = targetSide;
    next.side = targetSide;
  }

  if (field === "target_side") {
    next.target_side = value;
    next.side = value;
  }

  if (field === "is_through") {
    next.is_through = Boolean(value);
    if (next.is_through) {
      next.depth_mm = "";
    }
  }

  return next;
}

export default function MountingNodesCreatePanel({
  fittingItems = [],
  fittingCategories = [],
  language = "en",
  onCancel = () => {},
  t = {},
}) {
  const [draft, setDraft] = useState(() =>
    createMountingNodeCreateDraft({
      mounting_variant_key: MOUNTING_VARIANT_KEYS[0],
    }),
  );
  const [selectedFittingId, setSelectedFittingId] = useState("");
  const [selectedPointKey, setSelectedPointKey] = useState("");
  const [hoveredPointKey, setHoveredPointKey] = useState("");
  const [pointCreateOpen, setPointCreateOpen] = useState(false);
  const [pointCreateForm, setPointCreateForm] = useState(() => createHolePointFormDefaults());
  const [pointCreateFittingId, setPointCreateFittingId] = useState("");
  const [pointCreateError, setPointCreateError] = useState("");
  const [pointCreateSubmitting, setPointCreateSubmitting] = useState(false);
  const [variantOpen, setVariantOpen] = useState(false);
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorSearch, setSelectorSearch] = useState("");
  const [selectorCategoryCode, setSelectorCategoryCode] = useState("");
  const [selectorViewMode, setSelectorViewMode] = useState(() => readStoredSelectorViewMode());
  const [selectorDraftItemIds, setSelectorDraftItemIds] = useState([]);
  const selectorSearchRef = useRef(null);
  const selectorStateSeededRef = useRef(false);

  const selectorTitle =
    language === "uk" ? "Вибір фурнітури для монтажного вузла" : "Choose fittings for the mounting node";

  useEffect(() => {
    if (selectorOpen) {
      selectorSearchRef.current?.focus();
    }
  }, [selectorOpen]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.localStorage) {
      return;
    }

    try {
      window.localStorage.setItem(MOUNTING_NODE_CREATE_SELECTOR_VIEW_MODE_STORAGE_KEY, selectorViewMode);
    } catch {
      // Ignore storage failures in private browsing or sandboxed environments.
    }
  }, [selectorViewMode]);

  const fittingCategoryOptions = useMemo(() => {
    const options = new Map();
    const categorySource =
      Array.isArray(fittingCategories) && fittingCategories.length
        ? fittingCategories
        : Array.isArray(fittingItems)
          ? fittingItems
          : [];

    for (const item of categorySource) {
      const code = getFittingCategoryCode(item);
      if (!code || options.has(code)) {
        continue;
      }

      options.set(code, {
        value: code,
        label: getFittingCategoryLabel(item, language, t, fittingCategories) || humanizeKey(code),
      });
    }

    return [
      {
        value: "",
        label: language === "uk" ? "Усі категорії" : "All categories",
      },
      ...Array.from(options.values()),
    ];
  }, [fittingCategories, fittingItems, language, t]);

  useEffect(() => {
    if (!selectorCategoryCode && fittingCategoryOptions.length > 1) {
      setSelectorCategoryCode("");
    }
  }, [fittingCategoryOptions, selectorCategoryCode]);

  const selectedItems = Array.isArray(draft.items) ? draft.items : [];
  const selectedVariantKey = normalizeText(draft.mounting_variant_key) || MOUNTING_VARIANT_KEYS[0];
  const mountingVariantOptions = useMemo(() => getMountingVariantOptions(language), [language]);
  const selectedVariantModel = useMemo(
    () => mountingVariantOptions.find((item) => item.key === selectedVariantKey) || mountingVariantOptions[0] || null,
    [mountingVariantOptions, selectedVariantKey],
  );

  const previewPoints = useMemo(
    () =>
      (Array.isArray(draft.points) ? draft.points : []).map((point, index) => {
        const pointId = normalizeText(point?.client_key || point?.id || `point-${index + 1}`);
        return {
          ...point,
          id: pointId,
          displayId: point?.id !== null && point?.id !== undefined && String(point.id).trim() ? String(point.id) : `P${index + 1}`,
        };
      }),
    [draft.points],
  );

  const selectedFitting =
    selectedItems.find((item) => getFittingId(item) === selectedFittingId) || selectedItems[0] || null;

  useEffect(() => {
    if (!selectedItems.length) {
      if (selectedFittingId) {
        setSelectedFittingId("");
      }
      return;
    }

    if (!selectedItems.some((item) => getFittingId(item) === selectedFittingId)) {
      setSelectedFittingId(getFittingId(selectedItems[0]));
    }
  }, [selectedFittingId, selectedItems]);

  const selectedPoint =
    previewPoints.find((point) => normalizeText(point.id) === normalizeText(selectedPointKey)) || previewPoints[0] || null;

  useEffect(() => {
    if (!previewPoints.length) {
      if (selectedPointKey) {
        setSelectedPointKey("");
      }
      return;
    }

    if (!previewPoints.some((point) => normalizeText(point.id) === normalizeText(selectedPointKey))) {
      setSelectedPointKey(normalizeText(previewPoints[0].id));
    }
  }, [previewPoints, selectedPointKey]);

  useEffect(() => {
    if (selectedPoint?.id) {
      setHoveredPointKey(selectedPoint.id);
    }
  }, [selectedPoint?.id]);

  const selectedPointForm = useMemo(() => {
    if (!selectedPoint) {
      return createHolePointFormDefaults();
    }

    return buildHolePointFormFromPoint(selectedPoint);
  }, [selectedPoint]);

  const visibleSelectorItems = useMemo(() => {
    const search = normalizeText(selectorSearch).toLowerCase();
    const categoryCode = normalizeText(selectorCategoryCode);

    return (Array.isArray(fittingItems) ? fittingItems : []).filter((item) => {
      const itemCategoryCode = getFittingCategoryCode(item);
      const haystack = [
        getFittingId(item),
        getFittingName(item),
        getFittingArticle(item),
        getFittingCategoryLabel(item, language, t, fittingCategories),
        itemCategoryCode,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      if (categoryCode && itemCategoryCode !== categoryCode) {
        return false;
      }

      return !search || haystack.includes(search);
    });
  }, [fittingCategories, fittingItems, selectorCategoryCode, selectorSearch, language, t]);

  const selectorSelectedCount = selectorDraftItemIds.length;

  const updateDraft = (updater) => {
    setDraft((current) => {
      const next = typeof updater === "function" ? updater(current) : updater;
      return next;
    });
  };

  const handleCancel = () => {
    onCancel?.();
  };

  const openSelector = () => {
    if (!selectorStateSeededRef.current) {
      setSelectorDraftItemIds(selectedItems.map((item) => getFittingId(item)).filter(Boolean));
      selectorStateSeededRef.current = true;
    }

    setSelectorOpen(true);
  };

  const closeSelector = () => {
    setSelectorOpen(false);
  };

  const handleVariantChange = (variantKey) => {
    updateDraft((current) => ({
      ...current,
      mounting_variant_key: variantKey,
      is_dirty: true,
    }));
    setVariantOpen(false);
  };

  const handleToggleSelectorFitting = (item) => {
    const fittingId = getFittingId(item);

    if (!fittingId) {
      return;
    }

    setSelectorDraftItemIds((current) =>
      current.includes(fittingId)
        ? current.filter((existingId) => existingId !== fittingId)
        : [...current, fittingId],
    );
  };

  const handleRemoveFitting = (fittingId) => {
    const nextDraft = removeMountingNodeCreateDraftItem(draft, fittingId);
    updateDraft(nextDraft);
    if (normalizeText(selectedFittingId) === normalizeText(fittingId)) {
      setSelectedFittingId(normalizeText(nextDraft.items?.[0]?.fitting_id || ""));
    }
  };

  const handleSelectedFittingPatch = (fittingId, patch) => {
    updateDraft(updateMountingNodeCreateDraftItem(draft, fittingId, patch));
  };

  const handleConfirmSelectedFittings = () => {
    const currentItems = Array.isArray(draft.items) ? draft.items : [];
    const currentItemsById = new Map(currentItems.map((item) => [getFittingId(item), item]));
    const selectedIds = selectorDraftItemIds.filter(Boolean);
    const selectedIdSet = new Set(selectedIds);
    const nextItems = [];

    selectedIds.forEach((fittingId) => {
      const existingItem = currentItemsById.get(fittingId);
      if (existingItem) {
        nextItems.push(existingItem);
        return;
      }

      const fitting = (Array.isArray(fittingItems) ? fittingItems : []).find((item) => getFittingId(item) === fittingId);
      if (!fitting) {
        return;
      }

      nextItems.push(createMountingNodeCreateDraftItemFromFitting(fitting));
    });

    const nextPoints = (Array.isArray(draft.points) ? draft.points : []).filter((point) =>
      selectedIdSet.has(getFittingId(point) || normalizeText(point.fitting_id)),
    );

    updateDraft({
      ...draft,
      items: nextItems,
      points: nextPoints,
      is_dirty: true,
    });

    if (!nextItems.some((item) => getFittingId(item) === selectedFittingId)) {
      setSelectedFittingId(getFittingId(nextItems[0]) || "");
    }

    closeSelector();
  };

  const handleCreatePoint = () => {
    if (!selectedFitting) {
      return;
    }

    const fitting = {
      id: selectedFitting.fitting_id,
      article: selectedFitting.article,
      name: selectedFitting.name,
      image_url: selectedFitting.image_url,
    };
    const nextPointForm = prepareMountingNodeCreateDraftPointForm(draft, fitting);

    setPointCreateFittingId(getFittingId(selectedFitting));
    setPointCreateForm(nextPointForm);
    setPointCreateError("");
    setPointCreateSubmitting(false);
    setPointCreateOpen(true);
  };

  const closePointCreateForm = () => {
    setPointCreateOpen(false);
    setPointCreateError("");
    setPointCreateForm(createHolePointFormDefaults());
    setPointCreateFittingId("");
    setPointCreateSubmitting(false);
  };

  const handlePointCreateFieldChange = (field, value) => {
    setPointCreateForm((current) => {
      if (!current) {
        return current;
      }

      return applyMountingNodePointFieldChange(current, field, value);
    });
  };

  const handlePointCreateNumericFieldChange = (field, value) => {
    handlePointCreateFieldChange(field, value);
  };

  const handlePointCreateToggle = (field, value) => {
    handlePointCreateFieldChange(field, value);
  };

  const handlePointCreateSubmit = (event) => {
    event.preventDefault();

    if (!pointCreateForm) {
      return;
    }

    const fitting =
      selectedItems.find((item) => getFittingId(item) === normalizeText(pointCreateFittingId)) || selectedFitting;

    if (!fitting) {
      setPointCreateError(language === "uk" ? "Спочатку виберіть фурнітуру." : "Select a fitting first.");
      return;
    }

    setPointCreateSubmitting(true);

    const nextPoint = createMountingNodeCreateDraftPointFromFitting(
      fitting,
      pointCreateForm,
      previewPoints.length,
      Math.max(previewPoints.length + 1, 1),
    );

    updateDraft(commitMountingNodeCreateDraftPoint(draft, nextPoint));
    setSelectedPointKey(normalizeText(nextPoint.client_key));
    closePointCreateForm();
  };

  const handleRemovePoint = (clientKey) => {
    const nextDraft = removeMountingNodeCreateDraftPoint(draft, clientKey);
    updateDraft(nextDraft);
    if (normalizeText(selectedPointKey) === normalizeText(clientKey)) {
      setSelectedPointKey(normalizeText(nextDraft.points?.[0]?.client_key || ""));
    }
  };

  const handlePointFieldChange = (field, value) => {
    if (!selectedPoint) {
      return;
    }

    updateDraft(updateMountingNodeCreateDraftPoint(draft, selectedPoint.id, applyMountingNodePointFieldChange(selectedPointForm, field, value)));
  };

  const handlePointNumericFieldChange = (field, value) => {
    handlePointFieldChange(field, value);
  };

  const handlePointToggle = (field, value) => {
    handlePointFieldChange(field, value);
  };

  const canShowSaveButton = selectedItems.length > 0;

  return (
    <section aria-label={selectorTitle} className="mounting-node-create-screen">
      <article className="catalog-card service-catalog-card service-catalog-card-full mounting-node-create-section">
        <div className="catalog-page-header mounting-node-create-header">
          <div className="service-catalog-title">
            <h3>{language === "uk" ? "Створення монтажного вузла" : "Create mounting node"}</h3>
          </div>
          <div className="service-catalog-header-actions">
            <span className="service-tree-badge subtle">
              {selectedItems.length} {language === "uk" ? "фурнітур" : "fittings"}
            </span>
            <button className="ghost-button compact-button" onClick={handleCancel} type="button">
              <ArrowLeft size={16} />
              {language === "uk" ? "Повернутися до монтажних вузлів" : "Back to mounting nodes"}
            </button>
          </div>
        </div>

        <div className="mounting-node-create-top-grid">
          <div className="mounting-node-create-field mounting-node-create-name-field">
            <span>{language === "uk" ? "Назва монтажного вузла" : "Mounting node name"}</span>
            <div className="mounting-node-create-name-row">
              <input
                onChange={(event) =>
                  updateDraft({
                    ...draft,
                    name: event.target.value,
                    is_dirty: true,
                  })
                }
                placeholder={language === "uk" ? "Наприклад, mn_confirmat_7x50" : "For example, mn_confirmat_7x50"}
                type="text"
                value={draft.name}
              />
              <button className="primary-button compact-button" onClick={openSelector} type="button">
                <Plus size={16} />
                {language === "uk" ? "Додати фурнітуру" : "Add fittings"}
              </button>
            </div>
          </div>
        </div>

        <FittingHolesWorkspace>
          <div className="holes-left-column">
            <div className="holes-workspace-top-zone">
              <section className="hole-template-fitting-info">
                <div className="hole-template-fitting-info-head">
                  <strong>{language === "uk" ? "Інформація про фурнітуру" : "Fitting info"}</strong>
                  {selectedItems.length ? (
                    <span className="service-tree-badge subtle">
                      {selectedItems.length} {language === "uk" ? "позицій" : "items"}
                    </span>
                  ) : null}
                </div>
                {selectedFitting ? (
                  <div className={`hole-template-fitting-info-body${getFittingImageUrl(selectedFitting) ? "" : " no-image"}`}>
                    {getFittingImageUrl(selectedFitting) ? (
                      <img
                        alt=""
                        className="hole-template-fitting-info-image"
                        loading="lazy"
                        src={getFittingImageUrl(selectedFitting)}
                      />
                    ) : (
                      <div className="hole-template-fitting-info-placeholder">
                        {language === "uk" ? "Немає фото" : "No image"}
                      </div>
                    )}
                    <div className="hole-template-fitting-info-copy">
                      <strong className="hole-template-fitting-info-title">
                        {getFittingName(selectedFitting)}
                      </strong>
                      <div className="hole-template-fitting-info-subtitle">
                        {[getFittingArticle(selectedFitting), getFittingCategoryLabel(selectedFitting, language, t, fittingCategories)]
                          .filter(Boolean)
                          .join(" · ") ||
                          (language === "uk" ? "Вибрано для локального draft" : "Selected for local draft")}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="empty-state compact-empty-state">
                    <span>{language === "uk" ? "Спершу виберіть фурнітуру зверху." : "Choose a fitting above."}</span>
                  </div>
                )}
              </section>

              <section className="holes-mounting-variant-dropdown">
                <div className="holes-mounting-variant-dropdown-head">
                  <div>
                    <strong>{language === "uk" ? "Варіант кріплення" : "Mounting variant"}</strong>
                  </div>
                </div>
                <div className={`holes-mounting-variant-dropdown-shell${variantOpen ? " is-open" : ""}`}>
                  <button
                    className="holes-mounting-variant-toggle"
                    onClick={() => setVariantOpen((current) => !current)}
                    type="button"
                  >
                                        <span className="holes-mounting-variant-toggle-mark" aria-hidden="true">
                      {selectedVariantModel?.icon ? <img alt="" src={selectedVariantModel.icon} /> : <span>⋯</span>}
                    </span>
                    <span className="holes-mounting-variant-toggle-copy">
                      <strong>{selectedVariantModel?.label || selectedVariantKey}</strong>
                      {selectedVariantModel?.description ? <span>{selectedVariantModel.description}</span> : null}
                    </span>
                    <ChevronRight className="holes-mounting-variant-toggle-arrow" size={16} />
                  </button>
                  {variantOpen ? (
                    <div className="holes-mounting-variant-menu" role="listbox">
                      {mountingVariantOptions.map((variant, index) => {
                        const isActive = selectedVariantKey === variant.key;

                        return (
                          <button
                            aria-pressed={isActive}
                            className={`holes-mounting-variant-option${isActive ? " active" : ""}`}
                            key={`variant-${index}-${variant.key}`}
                            onClick={() => handleVariantChange(variant.key)}
                            type="button"
                          >
                            <span className="holes-mounting-variant-option-mark" aria-hidden="true">
                              <img alt="" src={variant.icon} />
                            </span>
                            <span className="holes-mounting-variant-option-copy">
                              <strong>{variant.label}</strong>
                              {variant.description ? <span>{variant.description}</span> : null}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  ) : null}
                </div>
              </section>
            </div>

            <section className="holes-panel mounting-node-create-section">
              <div className="holes-panel-header">
                <h4>{language === "uk" ? "Вибрані фурнітури" : "Selected fittings"}</h4>
                <span className="service-tree-badge subtle">
                  {selectedItems.length} {language === "uk" ? "позицій" : "items"}
                </span>
              </div>

              {selectedItems.length ? (
                <div className="hole-bundle-selected-list">
                  <div className="hole-bundle-selected-items">
                    {selectedItems.map((item, index) => {
                      const fittingId = getFittingId(item);
                      const imageUrl = getFittingImageUrl(item);
                      const isActive = normalizeText(selectedFitting?.fitting_id) === normalizeText(fittingId);
                      const itemKey = `selected-item-${index}-${fittingId || getFittingArticle(item) || getFittingName(item) || "fallback"}`;

                      return (
                        <article
                          aria-label={getFittingName(item) || fittingId}
                          className={`hole-bundle-selected-item hole-bundle-selected-item-compact mounting-node-create-fitting-row${fittingId ? " is-clickable" : ""}${isActive ? " is-active" : ""}`}
                          key={itemKey}
                          onClick={() => setSelectedFittingId(fittingId)}
                          role="button"
                          tabIndex={0}
                        >
                          <div className="hole-bundle-selected-item-media">
                            {imageUrl ? (
                              <img alt="" loading="lazy" src={imageUrl} />
                            ) : (
                              <div className="hole-bundle-selected-item-placeholder">
                                {language === "uk" ? "Немає фото" : "No image"}
                              </div>
                            )}
                          </div>
                          <div className="hole-bundle-selected-item-copy">
                            <div className="hole-bundle-selected-item-copy-head">
                              <strong>{getFittingName(item) || fittingId}</strong>
                              {isActive ? (
                                <span className="hole-bundle-selected-item-active-badge">
                                  {language === "uk" ? "Вибрано" : "Selected"}
                                </span>
                              ) : null}
                            </div>
                            <span>
                              {language === "uk" ? "Артикул" : "Article"}: {getFittingArticle(item) || "—"} ·{" "}
                              {language === "uk" ? "Категорія" : "Category"}: {getFittingCategoryLabel(item, language, t, fittingCategories) || "—"}
                            </span>
                          </div>
                          <select
                            aria-label={language === "uk" ? "Роль" : "Role"}
                            className="mounting-node-create-fitting-role"
                            onClick={(event) => event.stopPropagation()}
                            onChange={(event) => handleSelectedFittingPatch(fittingId, { role: event.target.value })}
                            title={language === "uk" ? "Роль" : "Role"}
                            value={item.role}
                          >
                            {MOUNTING_NODE_CREATE_ROLE_OPTIONS.map((role, roleIndex) => (
                              <option key={`selected-role-${roleIndex}-${role}`} value={role}>
                                {role}
                              </option>
                            ))}
                          </select>
                          <input
                            aria-label={language === "uk" ? "Кількість" : "Quantity"}
                            className="mounting-node-create-fitting-quantity"
                            min="1"
                            onClick={(event) => event.stopPropagation()}
                            onChange={(event) => handleSelectedFittingPatch(fittingId, { quantity: event.target.value })}
                            title={language === "uk" ? "Кількість" : "Quantity"}
                            type="number"
                            value={item.quantity}
                          />
                          <button
                            aria-label={language === "uk" ? "Видалити" : "Remove fitting"}
                            className="ghost-button compact-button mounting-node-create-fitting-remove"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleRemoveFitting(fittingId);
                            }}
                            title={language === "uk" ? "Видалити" : "Remove fitting"}
                            type="button"
                          >
                            <X size={14} />
                          </button>
                        </article>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="empty-state compact-empty-state">
                  <span>
                    {language === "uk"
                      ? "Спершу виберіть хоча б одну фурнітуру через кнопку вище."
                      : "Pick at least one fitting using the button above."}
                  </span>
                </div>
              )}

            </section>

            <section className="holes-panel mounting-node-create-section">
              <div className="holes-panel-header">
                <h4>{language === "uk" ? "Точки" : "Points"}</h4>
                <span className="service-tree-badge subtle">
                  {previewPoints.length} {language === "uk" ? "точок" : "points"}
                </span>
                <button
                  className="ghost-button compact-button"
                  disabled={!selectedFitting}
                  onClick={handleCreatePoint}
                  type="button"
                >
                  <Plus size={14} />
                  {language === "uk" ? "Додати точку" : "Add point"}
                </button>
              </div>

              {previewPoints.length ? (
                <div className="holes-table-shell">
                  <div className="holes-points-table-header">
                    <span>ID</span>
                    <span>{language === "uk" ? "Фурнітура" : "Fitting"}</span>
                    <span>{language === "uk" ? "Мітка" : "Label"}</span>
                    <span>x</span>
                    <span>y</span>
                    <span>z</span>
                    <span>⌀</span>
                    <span>{language === "uk" ? "Глибина" : "Depth"}</span>
                    <span>{language === "uk" ? "Сторона" : "Side"}</span>
                  </div>
                  <div className="holes-table-list">
                    {previewPoints.map((point, index) => {
                      const isSelected = normalizeText(selectedPoint?.id) === normalizeText(point.id);
                      const isHovered = normalizeText(hoveredPointKey) === normalizeText(point.id);
                      const fittingLabel =
                        selectedItems.find((item) => normalizeText(item.fitting_id) === normalizeText(point.fitting_id))?.name ||
                        point.fitting_name ||
                        point.fitting_id;

                      return (
                        <article
                          className={`holes-points-table-row${isHovered ? " is-hovered" : ""}${isSelected ? " is-selected" : ""}`}
                          key={`point-${index}-${point.id}`}
                          onClick={() => setSelectedPointKey(point.id)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedPointKey(point.id);
                            }
                          }}
                          onMouseEnter={() => setHoveredPointKey(point.id)}
                          onMouseLeave={() => setHoveredPointKey("")}
                          role="button"
                          tabIndex={0}
                        >
                          <span className="holes-point-id-cell">
                            <span className="holes-point-id-value">{point.displayId}</span>
                          </span>
                          <span className="holes-point-label-cell" title={fittingLabel}>
                            {fittingLabel}
                          </span>
                          <span className="holes-point-label-cell" title={point.label}>
                            {point.label}
                          </span>
                          <span>{point.x_mm ?? point.x ?? "—"}</span>
                          <span>{point.y_mm ?? point.y ?? "—"}</span>
                          <span>{point.z_mm ?? point.z ?? "—"}</span>
                          <span>{point.diameter_mm ?? point.diameter ?? "—"}</span>
                          <span>{point.depth_mm ?? point.depth ?? "—"}</span>
                          <span>{point.side}</span>
                          <button
                            className="ghost-button compact-button"
                            onClick={(event) => {
                              event.stopPropagation();
                              handleRemovePoint(point.id);
                            }}
                            type="button"
                          >
                            <X size={14} />
                          </button>
                        </article>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="empty-state compact-empty-state">
                  <span>
                    {language === "uk"
                      ? "Поки що немає локальних точок. Додайте точку для вибраної фурнітури."
                      : "There are no local points yet. Add one for the selected fitting."}
                  </span>
                </div>
              )}
            </section>
          </div>

          <div>
            <section className="holes-preview-card holes-preview-3d-card mounting-node-preview-card">
              <div className="holes-preview-header">
                <div>
                  <h4>{language === "uk" ? "3D-прев’ю" : "3D preview"}</h4>
                </div>
                <span className="service-tree-badge subtle">
                  {previewPoints.length} {language === "uk" ? "точок" : "points"}
                </span>
              </div>
              <div className="holes-preview-stage">
                <HolesMountingThreePreview
                  hoveredHoleId={hoveredPointKey}
                  holes={previewPoints}
                  mountingVariantKey={selectedVariantKey}
                  onHoverHole={(holeId) => setHoveredPointKey(normalizeText(holeId))}
                  onLeaveHole={() => setHoveredPointKey("")}
                  onSelectHole={(holeId) => setSelectedPointKey(normalizeText(holeId))}
                  selectedHoleId={selectedPointKey}
                />
              </div>
              <div className="holes-preview-legend">
                <span>
                  {language === "uk" ? "Поточний варіант" : "Current variant"}: {selectedVariantModel?.label || selectedVariantKey}
                </span>
                <span>
                  {language === "uk" ? "Точок у прев’ю" : "Points in preview"}: {previewPoints.length}
                </span>
              </div>
            </section>

            <section
              aria-label={language === "uk" ? "Вибрана точка" : "Selected point"}
              className="holes-selected-point-panel mounting-node-selected-point-panel"
            >
              <div className="holes-selected-point-panel-header">
                <div>
                  <strong>{language === "uk" ? "Вибрана точка" : "Selected point"}</strong>
                </div>
                <span className="service-tree-badge subtle">
                  {selectedPoint?.displayId || (language === "uk" ? "Немає" : "None")}
                </span>
              </div>

              {selectedPoint ? (
                <>
                  <div className="holes-selected-point-grid">
                    <div className="holes-selected-point-row">
                      <span>{language === "uk" ? "Фурнітура" : "Fitting"}</span>
                      <strong>{selectedFitting?.name || selectedPoint?.fitting_id}</strong>
                    </div>
                    <div className="holes-selected-point-row">
                      <span>ID</span>
                      <strong>{selectedPoint.displayId}</strong>
                    </div>
                    <div className="holes-selected-point-row">
                      <span>{language === "uk" ? "Координати" : "Coordinates"}</span>
                      <strong>
                        x={selectedPoint.x_mm ?? selectedPoint.x}, y={selectedPoint.y_mm ?? selectedPoint.y}, z=
                        {selectedPoint.z_mm ?? selectedPoint.z}
                      </strong>
                    </div>
                    <div className="holes-selected-point-row">
                      <span>{language === "uk" ? "Варіант" : "Variant"}</span>
                      <strong>{selectedVariantModel?.label || selectedVariantKey}</strong>
                    </div>
                  </div>

                  <div className="mounting-node-create-workspace-side">
                    <PointField label={language === "uk" ? "Мітка" : "Label"}>
                      <input
                        onChange={(event) => handlePointFieldChange("label", event.target.value)}
                        type="text"
                        value={selectedPointForm.label}
                      />
                    </PointField>
                    <div className="hole-template-form-grid">
                      <PointField label="X">
                        <input
                          onChange={(event) => handlePointNumericFieldChange("x_mm", event.target.value)}
                          step="any"
                          type="number"
                          value={selectedPointForm.x_mm}
                        />
                      </PointField>
                      <PointField label="Y">
                        <input
                          onChange={(event) => handlePointNumericFieldChange("y_mm", event.target.value)}
                          step="any"
                          type="number"
                          value={selectedPointForm.y_mm}
                        />
                      </PointField>
                      <PointField label="Z">
                        <input
                          onChange={(event) => handlePointNumericFieldChange("z_mm", event.target.value)}
                          step="any"
                          type="number"
                          value={selectedPointForm.z_mm}
                        />
                      </PointField>
                    </div>
                    <div className="hole-template-form-grid">
                      <PointField label={language === "uk" ? "Панель" : "Panel"}>
                        <select
                          onChange={(event) => handlePointFieldChange("target_panel", event.target.value)}
                          value={selectedPointForm.target_panel || selectedPointForm.panel_key || "vertical_panel"}
                        >
                          {POINT_PANEL_OPTIONS.map((option, index) => (
                            <option key={`point-panel-${index}-${option.value}`} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </PointField>
                      <PointField label={language === "uk" ? "Поверхня" : "Surface"}>
                        <select
                          onChange={(event) => handlePointFieldChange("target_surface", event.target.value)}
                          value={selectedPointForm.target_surface || "plane"}
                        >
                          <option value="plane">{language === "uk" ? "Площина" : "Plane"}</option>
                          <option value="edge">{language === "uk" ? "Край" : "Edge"}</option>
                        </select>
                      </PointField>
                      <PointField label={language === "uk" ? "Сторона" : "Side"}>
                        <select
                          onChange={(event) => handlePointFieldChange("target_side", event.target.value)}
                          value={selectedPointForm.target_side || "inner_face"}
                        >
                          <option value="inner_face">inner_face</option>
                          <option value="outer_face">outer_face</option>
                          <option value="edge_near_vertical">edge_near_vertical</option>
                          <option value="edge_far_vertical">edge_far_vertical</option>
                          <option value="top_face">top_face</option>
                          <option value="bottom_face">bottom_face</option>
                        </select>
                      </PointField>
                    </div>
                    <div className="hole-template-form-grid">
                      <PointField label={language === "uk" ? "Діаметр" : "Diameter"}>
                        <input
                          min="0.01"
                          onChange={(event) => handlePointNumericFieldChange("diameter_mm", event.target.value)}
                          step="any"
                          type="number"
                          value={selectedPointForm.diameter_mm}
                        />
                      </PointField>
                      <PointField label={language === "uk" ? "Глибина" : "Depth"}>
                        <input
                          disabled={Boolean(selectedPointForm.is_through)}
                          onChange={(event) => handlePointNumericFieldChange("depth_mm", event.target.value)}
                          step="any"
                          type="number"
                          value={selectedPointForm.depth_mm}
                        />
                      </PointField>
                      <label className="material-inline-check">
                        <input
                          checked={Boolean(selectedPointForm.is_through)}
                          onChange={(event) => handlePointToggle("is_through", event.target.checked)}
                          type="checkbox"
                        />
                        {language === "uk" ? "Сквозна" : "Through"}
                      </label>
                    </div>
                    <div className="hole-template-checks">
                      <label className="material-inline-check">
                        <input
                          checked={(selectedPointForm.operation || "drill") === "drill"}
                          onChange={() => handlePointFieldChange("operation", "drill")}
                          type="radio"
                          name={`point-operation-${selectedPointForm.client_key || "default"}`}
                        />
                        {language === "uk" ? "Свердління" : "Drill"}
                      </label>
                      <label className="material-inline-check">
                        <input
                          checked={selectedPointForm.operation === "counterbore"}
                          onChange={() => handlePointFieldChange("operation", "counterbore")}
                          type="radio"
                          name={`point-operation-${selectedPointForm.client_key || "default"}`}
                        />
                        {language === "uk" ? "Потай" : "Counterbore"}
                      </label>
                    </div>
                    <label className="mounting-node-create-field">
                      <span>{language === "uk" ? "Примітки" : "Notes"}</span>
                      <textarea
                        onChange={(event) => handlePointFieldChange("notes", event.target.value)}
                        rows="3"
                        value={selectedPointForm.notes || ""}
                      />
                    </label>
                  </div>
                </>
              ) : (
                <div className="empty-state compact-empty-state">
                  <span>
                    {language === "uk"
                      ? "Виберіть точку зі списку або з 3D-прев’ю, щоб побачити її дані."
                      : "Select a point from the list or the 3D preview to see its data."}
                  </span>
                </div>
              )}
            </section>
          </div>
        </FittingHolesWorkspace>

        <div className="holes-workspace-save-panel">
          <div className="holes-workspace-save-panel-copy">
            <strong>{language === "uk" ? "Створення монтажного вузла" : "Create mounting node"}</strong>
          </div>
          <button className="primary-button" disabled={!canShowSaveButton} type="button">
            {language === "uk" ? "Створити монтажний вузол" : "Create mounting node"}
          </button>
        </div>

        {pointCreateOpen ? (
          <div className="modal-backdrop" onClick={closePointCreateForm} role="presentation">
            <article
              className="confirm-modal hole-template-modal mounting-node-point-modal"
              onClick={(event) => event.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-label={language === "uk" ? "Створення точки" : "Create point"}
            >
              <header className="confirm-header">
                <div>
                  <strong>{language === "uk" ? "Створення точки" : "Create point"}</strong>
                  <p>
                    {selectedFitting
                      ? `${getFittingName(selectedFitting) || pointCreateFittingId}${getFittingArticle(selectedFitting) ? ` · ${getFittingArticle(selectedFitting)}` : ""}`
                      : language === "uk"
                        ? "Виберіть фурнітуру."
                        : "Select a fitting first."}
                  </p>
                </div>
                <button
                  aria-label={language === "uk" ? "Закрити" : "Close"}
                  className="ghost-button compact-button detail-info-button"
                  onClick={closePointCreateForm}
                  type="button"
                >
                  <X size={16} />
                </button>
              </header>

              {pointCreateError ? <div className="hole-template-error">{pointCreateError}</div> : null}

              <form onSubmit={handlePointCreateSubmit}>
                <MountingNodePointFields
                  disabled={pointCreateSubmitting}
                  form={pointCreateForm}
                  language={language}
                  mountingVariantKey={selectedVariantKey}
                  onFieldChange={handlePointCreateFieldChange}
                  onNumericFieldChange={handlePointCreateNumericFieldChange}
                  onToggle={handlePointCreateToggle}
                />

                <div className="confirm-actions">
                  <button className="ghost-button" onClick={closePointCreateForm} type="button">
                    {language === "uk" ? "Скасувати" : "Cancel"}
                  </button>
                  <button className="primary-button" disabled={pointCreateSubmitting} type="submit">
                    {language === "uk" ? "Додати точку" : "Add point"}
                  </button>
                </div>
              </form>
            </article>
          </div>
        ) : null}

        {selectorOpen ? (
          <div className="modal-backdrop" onClick={closeSelector} role="presentation">
            <article
              className="confirm-modal hole-template-modal hole-bundle-modal"
              onClick={(event) => event.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-label={selectorTitle}
            >
              <header className="confirm-header">
                <div>
                  <strong>{selectorTitle}</strong>
                  <p>
                    {language === "uk"
                      ? "Виберіть потрібну фурнітуру та підтвердьте додавання."
                      : "Choose the fittings you want and confirm the selection."}
                  </p>
                </div>
                <button
                  aria-label={language === "uk" ? "Закрити" : "Close"}
                  className="ghost-button compact-button detail-info-button"
                  onClick={closeSelector}
                  type="button"
                >
                  <X size={16} />
                </button>
              </header>

              <div className="hole-bundle-modal-toolbar">
                <div
                  className="hole-bundle-modal-mode-switch mounting-nodes-display-toggle materials-mode-switch"
                  role="group"
                  aria-label={language === "uk" ? "Вигляд вибору фурнітури" : "Fitting selector view mode"}
                >
                  <button
                    aria-pressed={selectorViewMode === "list"}
                    className={`ghost-button compact-button${selectorViewMode === "list" ? " active" : ""}`}
                    onClick={() => setSelectorViewMode("list")}
                    title={language === "uk" ? "Список" : "List"}
                    type="button"
                  >
                    <List size={16} />
                    <span>{language === "uk" ? "Список" : "List"}</span>
                  </button>
                  <button
                    aria-pressed={selectorViewMode === "cards"}
                    className={`ghost-button compact-button${selectorViewMode === "cards" ? " active" : ""}`}
                    onClick={() => setSelectorViewMode("cards")}
                    title={language === "uk" ? "Картки" : "Cards"}
                    type="button"
                  >
                    <LayoutGrid size={16} />
                    <span>{language === "uk" ? "Картки" : "Cards"}</span>
                  </button>
                </div>
                <span className="service-tree-badge subtle">
                  {selectorSelectedCount} {language === "uk" ? "вибрано" : "selected"}
                </span>
              </div>

              <div className="hole-bundle-modal-toolbar">
                <label className="service-catalog-search hole-bundle-modal-search">
                  <Search size={16} />
                  <input
                    onChange={(event) => setSelectorSearch(event.target.value)}
                    placeholder={language === "uk" ? "Пошук фурнітури" : "Search fittings"}
                    ref={selectorSearchRef}
                    type="search"
                    value={selectorSearch}
                  />
                </label>
                <label className="holes-select">
                  <span>{language === "uk" ? "Категорія" : "Category"}</span>
                  <select onChange={(event) => setSelectorCategoryCode(event.target.value)} value={selectorCategoryCode}>
                    {fittingCategoryOptions.map((category, index) => (
                      <option key={`selector-category-${index}-${category.value}`} value={category.value}>
                        {category.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {visibleSelectorItems.length ? (
                <div className={`hole-bundle-modal-body${selectorViewMode === "cards" ? " is-cards" : " is-list"}`}>
                  {selectorViewMode === "list" ? (
                    <div className="hole-bundle-modal-list">
                      {visibleSelectorItems.map((item, index) => {
                        const fittingId = getFittingId(item);
                        const selected = selectorDraftItemIds.includes(fittingId);
                        const imageUrl = getFittingImageUrl(item);
                        const selectorItemKey = `selector-item-${index}-${fittingId || getFittingArticle(item) || "fallback"}`;

                        return (
                          <button
                            aria-pressed={selected}
                            className={`hole-bundle-modal-row${selected ? " is-selected" : ""}`}
                            key={selectorItemKey}
                            onClick={() => handleToggleSelectorFitting(item)}
                            type="button"
                          >
                            <span className="hole-bundle-modal-row-check" aria-hidden="true">
                              {selected ? "✓" : ""}
                            </span>
                            <span className="hole-bundle-modal-row-media">
                              {imageUrl ? (
                                <img alt="" loading="lazy" src={imageUrl} />
                              ) : (
                                <span>{language === "uk" ? "Немає фото" : "No image"}</span>
                              )}
                            </span>
                            <span className="hole-bundle-modal-row-copy">
                              <strong>{getFittingName(item)}</strong>
                              <span>
                                {language === "uk" ? "Артикул" : "Article"}: {getFittingArticle(item) || "—"}
                              </span>
                            </span>
                            <span className="hole-bundle-modal-row-meta">
                              {getFittingCategoryLabel(item, language, t, fittingCategories) || humanizeKey(getFittingCategoryCode(item))}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="hole-bundle-modal-cards">
                      {visibleSelectorItems.map((item, index) => {
                        const fittingId = getFittingId(item);
                        const selected = selectorDraftItemIds.includes(fittingId);
                        const imageUrl = getFittingImageUrl(item);
                        const selectorItemKey = `selector-item-${index}-${fittingId || getFittingArticle(item) || "fallback"}`;

                        return (
                          <button
                            aria-pressed={selected}
                            className={`hole-bundle-modal-card${selected ? " is-selected" : ""}`}
                            key={selectorItemKey}
                            onClick={() => handleToggleSelectorFitting(item)}
                            type="button"
                          >
                            <div className="hole-bundle-modal-card-media">
                              {imageUrl ? (
                                <img alt="" loading="lazy" src={imageUrl} />
                              ) : (
                                <span>{language === "uk" ? "Немає фото" : "No image"}</span>
                              )}
                            </div>
                            <div className="hole-bundle-modal-card-copy">
                              <strong>{getFittingName(item)}</strong>
                              <span>
                                {language === "uk" ? "Артикул" : "Article"}: {getFittingArticle(item) || "—"}
                              </span>
                              <div className="hole-bundle-modal-card-footer">
                                <span>
                                  {getFittingCategoryLabel(item, language, t, fittingCategories) || humanizeKey(getFittingCategoryCode(item))}
                                </span>
                                <span>
                                  {selected ? (language === "uk" ? "Вже вибрано" : "Selected") : language === "uk" ? "Додати" : "Add"}
                                </span>
                              </div>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <div className="empty-state compact-empty-state">
                  <strong>{language === "uk" ? "Немає результатів" : "No results"}</strong>
                  <span>{language === "uk" ? "Спробуйте інший пошук або категорію." : "Try another search or category."}</span>
                </div>
              )}

              <div className="confirm-actions hole-bundle-actions">
                <button className="ghost-button" onClick={closeSelector} type="button">
                  {language === "uk" ? "Скасувати" : "Cancel"}
                </button>
                <button
                  className="primary-button"
                  disabled={!selectorSelectedCount}
                  onClick={handleConfirmSelectedFittings}
                  type="button"
                >
                  <Plus size={16} />
                  {language === "uk" ? "Додати вибране" : "Add selected"}
                </button>
              </div>
            </article>
          </div>
        ) : null}
      </article>
    </section>
  );
}
