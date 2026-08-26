import { useEffect, useMemo, useRef, useState } from "react";
import { Pencil, Plus, RefreshCw, Save, Trash2, X } from "lucide-react";

import {
  createMaterialCategory,
  createMaterialManufacturer,
  deleteMaterialCategory,
  deleteMaterialManufacturer,
  listMaterialCategories,
  listMaterialManufacturers,
  resolveAdminAssetUrl,
  uploadMaterialManufacturerLogo,
  uploadMaterialCategoryImage,
  updateMaterialCategory,
  updateMaterialManufacturer,
} from "../api.js";
import DeleteConfirmModal from "./DeleteConfirmModal.jsx";

function buildCategoryForm(item = null) {
  return {
    name: String(item?.name || ""),
    description: String(item?.description || ""),
    image_url: String(item?.image_url || ""),
    sort_order: String(item?.sort_order ?? 0),
    is_active: Boolean(item?.is_active ?? true),
    is_system: Boolean(item?.is_system ?? false),
  };
}

function buildManufacturerForm(item = null) {
  return {
    logo_url: String(item?.logo_url || ""),
    name: String(item?.name || ""),
    website_url: String(item?.website_url || ""),
    is_active: Boolean(item?.is_active ?? true),
    is_system: Boolean(item?.is_system ?? false),
  };
}

function normalizeText(value) {
  return String(value || "").trim();
}

const MATERIAL_CATEGORY_IMAGE_ACCEPT = "image/png,image/jpeg,image/webp";
const MATERIAL_CATEGORY_IMAGE_ALLOWED_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
]);
const MATERIAL_CATEGORY_IMAGE_MAX_SIZE_BYTES = 12 * 1024 * 1024;
const MATERIAL_MANUFACTURER_LOGO_ACCEPT = MATERIAL_CATEGORY_IMAGE_ACCEPT;
const MATERIAL_MANUFACTURER_LOGO_ALLOWED_TYPES = MATERIAL_CATEGORY_IMAGE_ALLOWED_TYPES;
const MATERIAL_MANUFACTURER_LOGO_MAX_SIZE_BYTES = MATERIAL_CATEGORY_IMAGE_MAX_SIZE_BYTES;

function compareMaterialCategoryRows(left, right) {
  const leftIsSystem = Boolean(left?.is_system);
  const rightIsSystem = Boolean(right?.is_system);
  if (leftIsSystem !== rightIsSystem) {
    return leftIsSystem ? -1 : 1;
  }

  if (leftIsSystem) {
    const leftSort = Number(left?.sort_order ?? 0);
    const rightSort = Number(right?.sort_order ?? 0);
    if (leftSort !== rightSort) {
      return leftSort - rightSort;
    }
  } else {
    const leftCreatedAt = new Date(left?.created_at || 0).getTime();
    const rightCreatedAt = new Date(right?.created_at || 0).getTime();
    if (leftCreatedAt !== rightCreatedAt) {
      return leftCreatedAt - rightCreatedAt;
    }
  }

  const leftName = normalizeText(left?.name);
  const rightName = normalizeText(right?.name);
  if (leftName !== rightName) {
    return leftName.localeCompare(rightName, "uk");
  }

  const leftCode = normalizeText(left?.code);
  const rightCode = normalizeText(right?.code);
  if (leftCode !== rightCode) {
    return leftCode.localeCompare(rightCode, "uk");
  }

  return Number(left?.id ?? 0) - Number(right?.id ?? 0);
}

function MaterialCategoryThumbnail({ imageUrl = "", name = "" }) {
  const [hasBrokenImage, setHasBrokenImage] = useState(false);
  const normalizedImageUrl = normalizeText(imageUrl);
  const resolvedImageUrl = resolveAdminAssetUrl(normalizedImageUrl);
  const fallbackLabel = normalizeText(name) || "—";

  useEffect(() => {
    setHasBrokenImage(false);
  }, [normalizedImageUrl]);

  if (!normalizedImageUrl || hasBrokenImage) {
    return (
      <div
        aria-label={fallbackLabel}
        className="material-taxonomy-thumbnail material-taxonomy-thumbnail-placeholder"
        title={fallbackLabel}
      >
        <span className="material-taxonomy-thumbnail-placeholder-mark">—</span>
      </div>
    );
  }

  return (
    <div className="material-taxonomy-thumbnail" title={fallbackLabel}>
      <img
        alt={fallbackLabel}
        className="material-taxonomy-thumbnail-image"
        loading="lazy"
        onError={() => setHasBrokenImage(true)}
        src={resolvedImageUrl}
      />
    </div>
  );
}

function MaterialLogoPreview({ logoUrl = "", name = "" }) {
  const [hasBrokenImage, setHasBrokenImage] = useState(false);
  const normalizedLogoUrl = normalizeText(logoUrl);
  const resolvedLogoUrl = resolveAdminAssetUrl(normalizedLogoUrl);
  const fallbackLabel = normalizeText(name) || "—";

  useEffect(() => {
    setHasBrokenImage(false);
  }, [normalizedLogoUrl]);

  return (
    <div className="supplier-logo-preview supplier-logo-preview--contain">
      {normalizedLogoUrl && !hasBrokenImage ? (
        <img
          alt={fallbackLabel}
          className="supplier-logo-preview-mark"
          loading="lazy"
          onError={() => setHasBrokenImage(true)}
          src={resolvedLogoUrl}
        />
      ) : (
        <div className="supplier-logo-preview-placeholder">
          <span className="supplier-logo-fallback">{fallbackLabel}</span>
        </div>
      )}
    </div>
  );
}

function MaterialManufacturerLogo({ logoUrl = "", name = "" }) {
  const [hasBrokenLogo, setHasBrokenLogo] = useState(false);
  const normalizedLogoUrl = normalizeText(logoUrl);
  const resolvedLogoUrl = resolveAdminAssetUrl(normalizedLogoUrl);
  const fallbackLabel = normalizeText(name) || "—";

  useEffect(() => {
    setHasBrokenLogo(false);
  }, [normalizedLogoUrl]);

  if (!normalizedLogoUrl || hasBrokenLogo) {
    return (
      <span className="fitting-source-logo fitting-manufacturer-badge material-taxonomy-manufacturer-logo" title={fallbackLabel}>
        <span className="fitting-source-logo-text">{fallbackLabel}</span>
      </span>
    );
  }

  return (
    <span className="fitting-manufacturer-logo material-taxonomy-manufacturer-logo" title={fallbackLabel}>
      <img
        alt={fallbackLabel}
        className="fitting-manufacturer-logo-image"
        onError={() => setHasBrokenLogo(true)}
        src={resolvedLogoUrl}
      />
    </span>
  );
}

const ENTITY_CONFIG = {
  categories: {
    breadcrumb: {
      uk: "Категорії",
      en: "Categories",
    },
    title: {
      uk: "Категорії матеріалів",
      en: "Material categories",
    },
    description: {
      uk: "Керування категоріями матеріалів.",
      en: "Manage material categories.",
    },
    list: listMaterialCategories,
    create: createMaterialCategory,
    update: updateMaterialCategory,
    buildForm: buildCategoryForm,
    columns: {
      name: { uk: "Назва", en: "Name" },
      image: { uk: "Зображення", en: "Image" },
      order: { uk: "Порядок", en: "Order" },
      status: { uk: "Статус / тип", en: "Status / type" },
      active: { uk: "Активність", en: "Active" },
    },
  },
  manufacturers: {
    breadcrumb: {
      uk: "Виробники",
      en: "Manufacturers",
    },
    title: {
      uk: "Виробники матеріалів",
      en: "Material manufacturers",
    },
    description: {
      uk: "Простий список виробників матеріалів.",
      en: "Simple list of material manufacturers.",
    },
    list: listMaterialManufacturers,
    create: createMaterialManufacturer,
    update: updateMaterialManufacturer,
    buildForm: buildManufacturerForm,
    columns: {
      name: { uk: "Назва", en: "Name" },
      logo: { uk: "Логотип", en: "Logo" },
      ownership: { uk: "Власність", en: "Ownership" },
      website_url: { uk: "Сайт", en: "Website" },
      active: { uk: "Активність", en: "Active" },
    },
  },
};

export default function MaterialTaxonomyAdminWorkspace({
  entity = "categories",
  language = "uk",
  token = "",
  currentUser = null,
  canCreate = false,
  onNavigate = null,
}) {
  const config = ENTITY_CONFIG[entity] || ENTITY_CONFIG.categories;
  const isAdmin = currentUser?.role === "admin";
  const canCreateEntity = canCreate;
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [categoryScope, setCategoryScope] = useState("system");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState("create");
  const [editorItemId, setEditorItemId] = useState("");
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorError, setEditorError] = useState("");
  const [editorForm, setEditorForm] = useState(config.buildForm());
  const [editorImageUploading, setEditorImageUploading] = useState(false);
  const [editorLogoUploading, setEditorLogoUploading] = useState(false);
  const [editorLogoFile, setEditorLogoFile] = useState(null);
  const [editorLogoPreviewUrl, setEditorLogoPreviewUrl] = useState("");
  const [editorLogoRemoved, setEditorLogoRemoved] = useState(false);
  const [manufacturerDeleteConfirmItem, setManufacturerDeleteConfirmItem] = useState(null);
  const imageFileInputRef = useRef(null);
  const logoFileInputRef = useRef(null);

  const visibleItems = useMemo(() => {
    const filtered = showInactive ? items : items.filter((item) => item.is_active);
    if (entity === "categories") {
      const scopedItems = isAdmin
        ? filtered.filter((item) => {
            if (categoryScope === "system") {
              return Boolean(item?.is_system);
            }

            if (categoryScope === "private") {
              return !Boolean(item?.is_system);
            }

            return true;
          })
        : filtered;

      return [...scopedItems].sort(compareMaterialCategoryRows);
    }

    const scopedItems = isAdmin
      ? filtered.filter((item) => {
          if (categoryScope === "system") {
            return Boolean(item?.is_system);
          }

          if (categoryScope === "private") {
            return !Boolean(item?.is_system);
          }

          return true;
        })
      : filtered;

    return [...scopedItems].sort((left, right) => normalizeText(left?.name).localeCompare(normalizeText(right?.name), "uk"));
  }, [categoryScope, entity, isAdmin, items, showInactive]);
  const includePrivateCategories = entity === "categories";

  useEffect(() => {
    return () => {
      if (editorLogoPreviewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(editorLogoPreviewUrl);
      }
    };
  }, [editorLogoPreviewUrl]);

  async function loadItems() {
    if (!token) {
      setItems([]);
      return;
    }

    setLoading(true);
    setPageError("");
    try {
      const result = await config.list(token, showInactive, includePrivateCategories);
      if (!result?.success) {
        throw new Error(result?.error || (language === "uk" ? "Не вдалося завантажити список" : "Unable to load list"));
      }

      setItems(Array.isArray(result.items) ? result.items : []);
    } catch (error) {
      setPageError(error?.message || (language === "uk" ? "Не вдалося завантажити список" : "Unable to load list"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entity, includePrivateCategories, showInactive, token]);

  function openEditor(item = null) {
    setEditorMode(item ? "edit" : "create");
    setEditorItemId(String(item?.id || ""));
    setEditorForm(
      config.buildForm(
        item || (entity === "categories" || entity === "manufacturers" ? { is_system: isAdmin } : null),
      ),
    );
    setEditorImageUploading(false);
    setEditorLogoUploading(false);
    if (imageFileInputRef.current) {
      imageFileInputRef.current.value = "";
    }
    if (logoFileInputRef.current) {
      logoFileInputRef.current.value = "";
    }
    if (editorLogoPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(editorLogoPreviewUrl);
    }
    setEditorLogoFile(null);
    setEditorLogoPreviewUrl("");
    setEditorLogoRemoved(false);
    setEditorError("");
    setEditorOpen(true);
  }

  function closeEditor() {
    setEditorImageUploading(false);
    setEditorLogoUploading(false);
    if (imageFileInputRef.current) {
      imageFileInputRef.current.value = "";
    }
    if (logoFileInputRef.current) {
      logoFileInputRef.current.value = "";
    }
    if (editorLogoPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(editorLogoPreviewUrl);
    }
    setEditorOpen(false);
    setEditorItemId("");
    setEditorError("");
    setEditorForm(config.buildForm());
    setEditorLogoFile(null);
    setEditorLogoPreviewUrl("");
    setEditorLogoRemoved(false);
  }

  function openImageFilePicker() {
    if (imageFileInputRef.current) {
      imageFileInputRef.current.click();
    }
  }

  function openLogoFilePicker() {
    if (logoFileInputRef.current) {
      logoFileInputRef.current.click();
    }
  }

  function removeEditorImage() {
    if (imageFileInputRef.current) {
      imageFileInputRef.current.value = "";
    }

    setEditorForm((current) => ({ ...current, image_url: "" }));
  }

  function removeEditorLogo() {
    if (logoFileInputRef.current) {
      logoFileInputRef.current.value = "";
    }

    if (editorLogoPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(editorLogoPreviewUrl);
    }

    setEditorLogoFile(null);
    setEditorLogoPreviewUrl("");
    setEditorLogoRemoved(true);
    setEditorForm((current) => ({ ...current, logo_url: "" }));
  }

  function canManageCategoryRow(item) {
    if (entity !== "categories" || !item) {
      return false;
    }

    if (isAdmin) {
      return true;
    }

    return !item.is_system && String(item.owner_user_id || "") === String(currentUser?.id || "");
  }

  function canDeleteCategoryRow(item) {
    if (entity !== "categories" || !item) {
      return false;
    }

    if (isAdmin) {
      return !item.is_system;
    }

    return canManageCategoryRow(item);
  }

  function canManageManufacturerRow(item) {
    if (entity !== "manufacturers" || !item) {
      return false;
    }

    if (isAdmin) {
      return true;
    }

    return !item.is_system && String(item.owner_user_id || "") === String(currentUser?.id || "");
  }

  function canDeleteManufacturerRow(item) {
    if (!canManageManufacturerRow(item)) {
      return false;
    }

    return !item?.is_active;
  }

  function openDeleteManufacturerConfirm(item) {
    if (!canDeleteManufacturerRow(item)) {
      return;
    }

    setPageError("");
    setManufacturerDeleteConfirmItem(item);
  }

  function closeDeleteManufacturerConfirm() {
    setManufacturerDeleteConfirmItem(null);
  }

  function getCategoryOwnershipLabel(item) {
    if (item?.is_system) {
      return language === "uk" ? "Системна" : "System";
    }

    if (String(item?.owner_user_id || "") === String(currentUser?.id || "")) {
      return language === "uk" ? "Моя" : "My";
    }

    return language === "uk" ? "Користувацька" : "User";
  }

  function getCategoryActiveLabel(item) {
    return item?.is_active ? (language === "uk" ? "Активна" : "Active") : (language === "uk" ? "Неактивна" : "Inactive");
  }

  function getCategoryOwnerDisplayLabel(item, language) {
    if (item?.is_system) {
      return language === "uk" ? "Система" : "System";
    }

    const primary = String(
      item?.owner_display_name ||
        item?.owner_login ||
        item?.owner_email ||
        "",
    ).trim();
    if (primary) {
      return primary;
    }

    const ownerId = String(item?.owner_user_id || "").trim();
    if (!ownerId) {
      return language === "uk" ? "Невідомо" : "Unknown";
    }

    if (ownerId.length <= 14) {
      return ownerId;
    }

    return `${ownerId.slice(0, 8)}…${ownerId.slice(-4)}`;
  }

  function getManufacturerOwnershipLabel(item) {
    if (item?.is_system) {
      return language === "uk" ? "Системний" : "System";
    }

    if (String(item?.owner_user_id || "") === String(currentUser?.id || "")) {
      return language === "uk" ? "Мій" : "Mine";
    }

    return language === "uk" ? "Користувацький" : "Private";
  }

  function getManufacturerOwnerDisplayLabel(item) {
    if (item?.is_system) {
      return language === "uk" ? "Система" : "System";
    }

    const primary = String(
      item?.owner_display_name ||
        item?.owner_login ||
        item?.owner_email ||
        "",
    ).trim();
    if (primary) {
      return primary;
    }

    const ownerId = String(item?.owner_user_id || "").trim();
    if (!ownerId) {
      return language === "uk" ? "Невідомо" : "Unknown";
    }

    if (ownerId.length <= 14) {
      return ownerId;
    }

    return `${ownerId.slice(0, 8)}…${ownerId.slice(-4)}`;
  }

  async function handleEditorImageFileChange(event) {
    const file = event.target.files?.[0] || null;
    if (!file || !token || entity !== "categories") {
      if (event.target) {
        event.target.value = "";
      }
      return;
    }

    const normalizedType = String(file.type || "").toLowerCase();
    if (!MATERIAL_CATEGORY_IMAGE_ALLOWED_TYPES.has(normalizedType)) {
      setEditorError(language === "uk" ? "Дозволені тільки PNG, JPG, JPEG або WEBP" : "Only PNG, JPG, JPEG, or WEBP files are allowed");
      event.target.value = "";
      return;
    }

    if (file.size > MATERIAL_CATEGORY_IMAGE_MAX_SIZE_BYTES) {
      setEditorError(language === "uk" ? "Файл занадто великий" : "File is too large");
      event.target.value = "";
      return;
    }

    setEditorImageUploading(true);
    setEditorError("");
    try {
      const result = await uploadMaterialCategoryImage(token, file);
      if (!result?.success || !result?.image_url) {
        throw new Error(result?.error || (language === "uk" ? "Не вдалося завантажити зображення" : "Unable to upload image"));
      }

      setEditorForm((current) => ({
        ...current,
        image_url: String(result.image_url || ""),
      }));
    } catch (error) {
      setEditorError(error?.message || (language === "uk" ? "Не вдалося завантажити зображення" : "Unable to upload image"));
    } finally {
      setEditorImageUploading(false);
      event.target.value = "";
    }
  }

  async function handleEditorLogoFileChange(event) {
    const file = event.target.files?.[0] || null;
    if (!file || !token || entity !== "manufacturers") {
      if (event.target) {
        event.target.value = "";
      }
      return;
    }

    const normalizedType = String(file.type || "").toLowerCase();
    if (!MATERIAL_MANUFACTURER_LOGO_ALLOWED_TYPES.has(normalizedType)) {
      setEditorError(language === "uk" ? "Дозволені тільки PNG, JPG, JPEG або WEBP" : "Only PNG, JPG, JPEG, or WEBP files are allowed");
      event.target.value = "";
      return;
    }

    if (file.size > MATERIAL_MANUFACTURER_LOGO_MAX_SIZE_BYTES) {
      setEditorError(language === "uk" ? "Файл занадто великий" : "File is too large");
      event.target.value = "";
      return;
    }

    if (editorLogoPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(editorLogoPreviewUrl);
    }

    setEditorLogoFile(file);
    setEditorLogoPreviewUrl(URL.createObjectURL(file));
    setEditorLogoRemoved(false);
    setEditorError("");
    event.target.value = "";
  }

  async function submitEditor(event) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setEditorSaving(true);
    setEditorError("");
    try {
      let payload;
      if (entity === "categories") {
        payload = {
          name: normalizeText(editorForm.name),
          description: normalizeText(editorForm.description) || null,
          image_url: normalizeText(editorForm.image_url) || null,
          sort_order: isAdmin ? Number(editorForm.sort_order || 0) : 0,
          is_active: Boolean(editorForm.is_active),
          is_system: isAdmin ? Boolean(editorForm.is_system) : false,
        };
      } else if (entity === "manufacturers") {
        let logoUrl = editorLogoRemoved ? null : normalizeText(editorForm.logo_url) || null;
        if (editorLogoFile) {
          setEditorLogoUploading(true);
          try {
            const uploadResult = await uploadMaterialManufacturerLogo(token, editorLogoFile);
            if (!uploadResult?.success || !uploadResult?.logo_url) {
              throw new Error(uploadResult?.error || (language === "uk" ? "Не вдалося завантажити логотип" : "Unable to upload logo"));
            }

            logoUrl = String(uploadResult.logo_url || "").trim() || null;
          } finally {
            setEditorLogoUploading(false);
          }
        }

        payload = {
          name: normalizeText(editorForm.name),
          website_url: normalizeText(editorForm.website_url) || null,
          logo_url: logoUrl,
          is_active: Boolean(editorForm.is_active),
          is_system: isAdmin ? Boolean(editorForm.is_system) : false,
        };
      } else {
        payload = {};
      }

      const result = editorMode === "edit"
        ? await config.update(token, editorItemId, payload)
        : await config.create(token, payload);

      if (!result?.success) {
        throw new Error(result?.error || (language === "uk" ? "Не вдалося зберегти запис" : "Unable to save item"));
      }

      closeEditor();
      await loadItems();
    } catch (error) {
      setEditorError(error?.message || (language === "uk" ? "Не вдалося зберегти запис" : "Unable to save item"));
    } finally {
      setEditorSaving(false);
    }
  }

  async function toggleActive(item) {
    if (!token) {
      return;
    }

    setPageError("");
    try {
      const payload = entity === "categories"
        ? {
            name: item.name,
            description: item.description || null,
            image_url: item.image_url || null,
            sort_order: Number(item.sort_order || 0),
            is_active: !Boolean(item.is_active),
            is_system: Boolean(item.is_system),
          }
        : {
            name: item.name,
            website_url: item.website_url || null,
            logo_url: item.logo_url || null,
            is_active: !Boolean(item.is_active),
            is_system: Boolean(item.is_system),
          };

      const result = await config.update(token, item.id, payload);
      if (!result?.success) {
        throw new Error(result?.error || (language === "uk" ? "Не вдалося оновити запис" : "Unable to update item"));
      }

      await loadItems();
    } catch (error) {
      setPageError(error?.message || (language === "uk" ? "Не вдалося оновити запис" : "Unable to update item"));
    }
  }

  async function handleDeleteCategory(item) {
    if (!token || entity !== "categories" || !item) {
      return;
    }

    const confirmationMessage = language === "uk"
      ? `Видалити категорію "${item.name}"?`
      : `Delete category "${item.name}"?`;

    if (!window.confirm(confirmationMessage)) {
      return;
    }

    setPageError("");
    try {
      const result = await deleteMaterialCategory(token, item.id);
      if (!result?.success) {
        throw new Error(result?.error || (language === "uk" ? "Не вдалося видалити категорію" : "Unable to delete category"));
      }

      await loadItems();
    } catch (error) {
      setPageError(error?.message || (language === "uk" ? "Не вдалося видалити категорію" : "Unable to delete category"));
    }
  }

  async function performDeleteManufacturer(item) {
    if (!token || entity !== "manufacturers" || !item) {
      return;
    }

    const result = await deleteMaterialManufacturer(token, item.id);
    if (!result?.success) {
      throw new Error(result?.error || (language === "uk" ? "Не вдалося видалити виробника" : "Unable to delete manufacturer"));
    }

    await loadItems();
  }

  const visibleCountLabel = language === "uk"
    ? `${visibleItems.length} записів`
    : `${visibleItems.length} records`;
  const editorManufacturerLogoPreviewSource = editorLogoPreviewUrl || (!editorLogoRemoved ? editorForm.logo_url : "");

  return (
    <section className="table-panel full-panel">
      <div className="catalog-page-header material-taxonomy-page-header">
        <div className="service-catalog-title material-taxonomy-page-title">
          {typeof onNavigate === "function" ? (
            <div className="fitting-category-breadcrumb fitting-category-breadcrumb-top">
              <button className="fitting-breadcrumb-link" onClick={() => onNavigate("catalogMaterials")} type="button">
                {language === "uk" ? "Матеріали" : "Materials"}
              </button>
              <span className="fitting-breadcrumb-separator">/</span>
              <strong>{config.breadcrumb[language] || config.breadcrumb.uk}</strong>
            </div>
          ) : null}
          <p>{config.description[language] || config.description.uk}</p>
        </div>
        <div className="service-catalog-header-actions material-taxonomy-page-actions">
          <span className="service-tree-badge subtle">{visibleCountLabel}</span>
          {isAdmin && (entity === "categories" || entity === "manufacturers") ? (
            <label className="toggle-label supplier-toggle">
              <span>{language === "uk" ? "Показати" : "Show"}</span>
              <select
                onChange={(event) => setCategoryScope(event.target.value)}
                value={categoryScope}
              >
                <option value="system">{language === "uk" ? "Системні" : "System"}</option>
                <option value="private">{language === "uk" ? "Користувацькі" : "User-owned"}</option>
                <option value="all">{language === "uk" ? "Всі" : "All"}</option>
              </select>
            </label>
          ) : null}
          <label className="toggle-label supplier-toggle">
            <input
              checked={showInactive}
              onChange={(event) => setShowInactive(event.target.checked)}
              type="checkbox"
            />
            {language === "uk" ? "Показати неактивні" : "Show inactive"}
          </label>
          <button className="ghost-button" disabled={loading} onClick={loadItems} type="button">
            <RefreshCw size={16} />
            {language === "uk" ? "Оновити" : "Refresh"}
          </button>
          {canCreateEntity ? (
            <button className="primary-button" onClick={() => openEditor()} type="button">
              <Plus size={16} />
              {language === "uk" ? "Додати" : "Add"}
            </button>
          ) : null}
        </div>
      </div>

      <article className="catalog-card service-catalog-card service-catalog-card-full">
        {pageError ? <p className="status-message error">{pageError}</p> : null}

        <div className="table-panel full-panel">
          <div
            className={`fittings-table-header${entity === "categories"
              ? ` material-taxonomy-table material-taxonomy-table--${isAdmin ? "admin" : "user"}`
              : entity === "manufacturers"
                ? " material-taxonomy-table material-taxonomy-table--manufacturers"
                : ""}`}
          >
            <span>{config.columns.name[language] || config.columns.name.uk}</span>
            {entity === "categories" ? <span>{config.columns.image[language] || config.columns.image.uk}</span> : null}
            {entity === "categories" ? (
              <>
                {isAdmin ? <span>{config.columns.order[language] || config.columns.order.uk}</span> : null}
                <span>{config.columns.status[language] || config.columns.status.uk}</span>
                {isAdmin ? <span>{language === "uk" ? "Власник" : "Owner"}</span> : null}
                <span>{config.columns.active[language] || config.columns.active.uk}</span>
              </>
            ) : null}
            {entity === "manufacturers" ? (
              <>
                <span>{config.columns.logo[language] || config.columns.logo.uk}</span>
                <span>{config.columns.ownership[language] || config.columns.ownership.uk}</span>
                <span>{config.columns.website_url[language] || config.columns.website_url.uk}</span>
                <span>{config.columns.active[language] || config.columns.active.uk}</span>
              </>
            ) : null}
            <span>{language === "uk" ? "Дії" : "Actions"}</span>
          </div>

          <div className="fittings-table-list">
            {visibleItems.map((item) => {
              return (
                <article
                  className={`fittings-table-row${entity === "categories"
                    ? ` material-taxonomy-table material-taxonomy-table--${isAdmin ? "admin" : "user"}`
                    : entity === "manufacturers"
                      ? " material-taxonomy-table material-taxonomy-table--manufacturers"
                      : ""}`}
                  key={item.id}
                >
                  <div className="material-taxonomy-name-cell">{item?.name || "—"}</div>
                  {entity === "categories" ? (
                    <div className="material-taxonomy-thumbnail-cell">
                      <MaterialCategoryThumbnail imageUrl={item?.image_url} name={item?.name} />
                    </div>
                  ) : null}
                  {entity === "categories" ? (
                    <>
                      {isAdmin ? <div>{Number(item?.sort_order ?? 0)}</div> : null}
                      <div>{getCategoryOwnershipLabel(item)}</div>
                      {isAdmin ? (
                        <div className="material-taxonomy-owner-cell" title={String(item?.owner_user_id || "")}>
                          {getCategoryOwnerDisplayLabel(item, language)}
                        </div>
                      ) : null}
                      <div>{getCategoryActiveLabel(item)}</div>
                    </>
                  ) : null}
                  {entity === "manufacturers" ? (
                    <>
                      <div className="manufacturer-logo-cell">
                        <MaterialManufacturerLogo logoUrl={item?.logo_url} name={item?.name} />
                      </div>
                      <div className="material-taxonomy-manufacturer-scope-cell" title={String(item?.owner_user_id || "")}>
                        <strong>{getManufacturerOwnershipLabel(item)}</strong>
                        {!item?.is_system ? <span>{getManufacturerOwnerDisplayLabel(item)}</span> : null}
                      </div>
                      <div>{item?.website_url || "—"}</div>
                      <div>{item?.is_active ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No")}</div>
                    </>
                  ) : null}
                  <div className="catalog-actions">
                    {entity === "categories" ? (
                      <>
                        {canManageCategoryRow(item) ? (
                          <button className="icon-button" onClick={() => openEditor(item)} type="button">
                            <Pencil size={14} />
                          </button>
                        ) : null}
                        {canDeleteCategoryRow(item) ? (
                          <button className="ghost-button compact-button danger-button" onClick={() => handleDeleteCategory(item)} type="button">
                            {language === "uk" ? "Видалити" : "Delete"}
                          </button>
                        ) : null}
                        {canManageCategoryRow(item) ? (
                          <button className="ghost-button compact-button" onClick={() => toggleActive(item)} type="button">
                            {item.is_active
                              ? (language === "uk" ? "Деактивувати" : "Deactivate")
                              : (language === "uk" ? "Активувати" : "Activate")}
                          </button>
                        ) : null}
                      </>
                    ) : entity === "manufacturers" ? (
                      <>
                        {canManageManufacturerRow(item) ? (
                          <button className="icon-button" onClick={() => openEditor(item)} type="button">
                            <Pencil size={14} />
                          </button>
                        ) : null}
                        {canManageManufacturerRow(item) ? (
                          <button className="ghost-button compact-button" onClick={() => toggleActive(item)} type="button">
                            {item.is_active
                              ? (language === "uk" ? "Деактивувати" : "Deactivate")
                              : (language === "uk" ? "Активувати" : "Activate")}
                          </button>
                        ) : null}
                        {canDeleteManufacturerRow(item) ? (
                          <button className="ghost-button compact-button danger-button" onClick={() => openDeleteManufacturerConfirm(item)} type="button">
                            <Trash2 size={14} />
                            {language === "uk" ? "Видалити" : "Delete"}
                          </button>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <button className="icon-button" onClick={() => openEditor(item)} type="button">
                          <Pencil size={14} />
                        </button>
                        <button className="ghost-button compact-button" onClick={() => toggleActive(item)} type="button">
                          {item.is_active
                            ? (language === "uk" ? "Деактивувати" : "Deactivate")
                            : (language === "uk" ? "Активувати" : "Activate")}
                        </button>
                      </>
                    )}
                  </div>
                </article>
              );
            })}
            {!loading && visibleItems.length === 0 ? (
              <div className="fittings-table-row">
                <div>{language === "uk" ? "Немає записів" : "No records"}</div>
              </div>
            ) : null}
          </div>
        </div>
      </article>

      <DeleteConfirmModal
        cancelLabel={language === "uk" ? "Скасувати" : "Cancel"}
        confirmLabel={language === "uk" ? "Видалити" : "Delete"}
        loadingLabel={language === "uk" ? "Видалення..." : "Deleting..."}
        message={language === "uk"
          ? `Видалити виробника «${manufacturerDeleteConfirmItem?.name || ""}»?`
          : `Delete manufacturer "${manufacturerDeleteConfirmItem?.name || ""}"?`}
        open={Boolean(manufacturerDeleteConfirmItem)}
        onCancel={closeDeleteManufacturerConfirm}
        onConfirm={async () => {
          if (!manufacturerDeleteConfirmItem) {
            return;
          }

          await performDeleteManufacturer(manufacturerDeleteConfirmItem);
        }}
        title={language === "uk" ? "Видалити виробника" : "Delete manufacturer"}
      />

      {editorOpen ? (
        <div aria-modal="true" className="modal-backdrop" onClick={closeEditor} role="dialog">
          <section className="confirm-modal supplier-confirm-modal" onClick={(event) => event.stopPropagation()}>
            <header className="confirm-header">
              <div>
                <strong>{config.title[language] || config.title.uk}</strong>
                <p>{editorMode === "edit" ? (language === "uk" ? "Редагування" : "Edit") : (language === "uk" ? "Створення" : "Create")}</p>
              </div>
              <button aria-label="Close" className="ghost-button compact-button detail-info-button" onClick={closeEditor} type="button">
                <X size={16} />
              </button>
            </header>

            <form className="catalog-form" onSubmit={submitEditor}>
              <div className="supplier-form-body">
                <label className="supplier-form-field">
                  <span>{language === "uk" ? "Назва" : "Name"}</span>
                  <input
                    onChange={(event) => setEditorForm((current) => ({ ...current, name: event.target.value }))}
                    value={editorForm.name}
                  />
                </label>

                {entity === "categories" ? (
                  <>
                    <label className="supplier-form-field supplier-form-field-wide">
                      <span>{language === "uk" ? "Опис" : "Description"}</span>
                      <textarea
                        onChange={(event) => setEditorForm((current) => ({ ...current, description: event.target.value }))}
                        rows={3}
                        value={editorForm.description}
                      />
                    </label>

                    <div className="supplier-form-field supplier-form-field-wide">
                      <span>{language === "uk" ? "Зображення" : "Image"}</span>
                      <input
                        ref={imageFileInputRef}
                        accept={MATERIAL_CATEGORY_IMAGE_ACCEPT}
                        className="supplier-logo-file-input"
                        onChange={handleEditorImageFileChange}
                        type="file"
                      />
                      <div className="supplier-logo-upload-panel">
                        <div className="supplier-logo-preview">
                          {editorForm.image_url ? (
                            <img
                              alt={editorForm.name || (language === "uk" ? "Зображення категорії" : "Category image")}
                              className="supplier-logo-preview-mark"
                              loading="lazy"
                              src={resolveAdminAssetUrl(editorForm.image_url)}
                            />
                          ) : (
                            <div className="supplier-logo-preview-placeholder">
                              <span className="supplier-logo-fallback">{language === "uk" ? "Немає зображення" : "No image"}</span>
                            </div>
                          )}
                        </div>
                        <div className="supplier-logo-input-row">
                          <button
                            className="ghost-button compact-button"
                            disabled={editorSaving || editorImageUploading}
                            onClick={openImageFilePicker}
                            type="button"
                          >
                            {editorImageUploading
                              ? (language === "uk" ? "Завантаження..." : "Uploading...")
                              : (language === "uk" ? "Завантажити файл" : "Upload file")}
                          </button>
                          <button
                            className="ghost-button compact-button"
                            disabled={editorSaving || editorImageUploading || !editorForm.image_url}
                            onClick={removeEditorImage}
                            type="button"
                          >
                            {language === "uk" ? "Прибрати" : "Remove"}
                          </button>
                        </div>
                        <label className="supplier-form-field supplier-form-field-wide">
                          <span>{language === "uk" ? "URL зображення" : "Image URL"}</span>
                          <input
                            onChange={(event) => setEditorForm((current) => ({ ...current, image_url: event.target.value }))}
                            placeholder="https://..."
                            value={editorForm.image_url}
                          />
                        </label>
                      </div>
                    </div>
                    {isAdmin ? (
                      <label className="supplier-form-field">
                        <span>{language === "uk" ? "Порядок" : "Sort order"}</span>
                        <input
                          onChange={(event) => setEditorForm((current) => ({ ...current, sort_order: event.target.value }))}
                          type="number"
                          value={editorForm.sort_order}
                        />
                      </label>
                    ) : null}
                    {isAdmin ? (
                      <label className="toggle-label supplier-toggle">
                        <input
                          checked={Boolean(editorForm.is_system)}
                          onChange={(event) => setEditorForm((current) => ({ ...current, is_system: event.target.checked }))}
                          type="checkbox"
                        />
                        {language === "uk" ? "Системна" : "System"}
                      </label>
                    ) : null}
                  </>
                ) : entity === "manufacturers" ? (
                  <>
                    <div className="supplier-form-field supplier-form-field-wide">
                      <span>{language === "uk" ? "Логотип" : "Logo"}</span>
                      <input
                        ref={logoFileInputRef}
                        accept={MATERIAL_MANUFACTURER_LOGO_ACCEPT}
                        className="supplier-logo-file-input"
                        onChange={handleEditorLogoFileChange}
                        type="file"
                      />
                      <div className="supplier-logo-upload-panel">
                        <MaterialLogoPreview
                          logoUrl={editorManufacturerLogoPreviewSource}
                          name={editorForm.name}
                        />
                        <div className="supplier-logo-input-row">
                          <button
                            className="ghost-button compact-button"
                            disabled={editorSaving || editorLogoUploading}
                            onClick={openLogoFilePicker}
                            type="button"
                          >
                            {editorLogoUploading
                              ? (language === "uk" ? "Завантаження..." : "Uploading...")
                              : (language === "uk" ? "Завантажити файл" : "Upload file")}
                          </button>
                          <button
                            className="ghost-button compact-button"
                            disabled={editorSaving || editorLogoUploading || !editorForm.logo_url}
                            onClick={removeEditorLogo}
                            type="button"
                          >
                            {language === "uk" ? "Прибрати" : "Remove"}
                          </button>
                        </div>
                        <label className="supplier-form-field supplier-form-field-wide">
                          <span>{language === "uk" ? "URL логотипа" : "Logo URL"}</span>
                          <input
                            onChange={(event) => {
                              if (editorLogoPreviewUrl.startsWith("blob:")) {
                                URL.revokeObjectURL(editorLogoPreviewUrl);
                              }

                              setEditorLogoFile(null);
                              setEditorLogoPreviewUrl("");
                              setEditorLogoRemoved(false);
                              setEditorForm((current) => ({ ...current, logo_url: event.target.value }));
                            }}
                            placeholder="https://..."
                            value={editorForm.logo_url}
                          />
                        </label>
                      </div>
                    </div>
                    <label className="supplier-form-field">
                      <span>{language === "uk" ? "Сайт" : "Website"}</span>
                      <input
                        onChange={(event) => setEditorForm((current) => ({ ...current, website_url: event.target.value }))}
                        value={editorForm.website_url}
                      />
                    </label>
                    {isAdmin ? (
                      <label className="toggle-label supplier-toggle">
                        <input
                          checked={Boolean(editorForm.is_system)}
                          onChange={(event) => setEditorForm((current) => ({ ...current, is_system: event.target.checked }))}
                          type="checkbox"
                        />
                        {language === "uk" ? "Системний" : "System"}
                      </label>
                    ) : null}
                  </>
                ) : (
                  <label className="supplier-form-field">
                    <span>{language === "uk" ? "Сайт" : "Website"}</span>
                    <input
                      onChange={(event) => setEditorForm((current) => ({ ...current, website_url: event.target.value }))}
                      value={editorForm.website_url}
                    />
                  </label>
                )}

                <label className="toggle-label supplier-toggle">
                  <input
                    checked={Boolean(editorForm.is_active)}
                    onChange={(event) => setEditorForm((current) => ({ ...current, is_active: event.target.checked }))}
                    type="checkbox"
                  />
                  {language === "uk" ? "Активний" : "Active"}
                </label>
              </div>

              {editorError ? <p className="status-message error supplier-form-error">{editorError}</p> : null}

              <div className="supplier-form-footer confirm-actions">
                <button className="ghost-button" disabled={editorSaving} onClick={closeEditor} type="button">
                  {language === "uk" ? "Скасувати" : "Cancel"}
                </button>
                <button className="primary-button" disabled={editorSaving || editorImageUploading || editorLogoUploading} type="submit">
                  <Save size={16} />
                  {language === "uk" ? "Зберегти" : "Save"}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}
