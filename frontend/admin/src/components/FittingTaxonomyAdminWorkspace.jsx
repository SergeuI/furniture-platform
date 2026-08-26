import { useEffect, useMemo, useRef, useState } from "react";
import { Pencil, Plus, RefreshCw, Save, Trash2, X } from "lucide-react";

import {
  buildCategoryForm,
  buildCategoryParentOptions,
  buildManufacturerForm,
  buildManufacturerOptions,
  buildProductTaxonomyForm,
  buildProductTaxonomyPayload,
  buildSeriesForm,
  buildSeriesOptions,
  FITTING_TAXONOMY_VIEWS,
  getCompatibleSeriesId,
  parseNullableId,
  sortFittingTaxonomyItems,
} from "../fittingTaxonomyAdmin.js";
import {
  createFittingCategory,
  createFittingManufacturer,
  createFittingSeries,
  deleteFittingCategory,
  deleteFittingManufacturer,
  deleteFittingSeries,
  listFittingCategories,
  listFittingManufacturers,
  listFittingProducts,
  listFittingSeries,
  updateFittingCategory,
  updateFittingManufacturer,
  updateFittingProductTaxonomy,
  updateFittingSeries,
  resolveAdminAssetUrl,
  uploadFittingManufacturerLogo,
} from "../api.js";

const ENTITY_LABELS = {
  manufacturers: { uk: "Виробники фурнітури", en: "Fitting manufacturers" },
  series: { uk: "Серії фурнітури", en: "Fitting series" },
  categories: { uk: "Категорії фурнітури", en: "Fitting categories" },
  products: { uk: "Технічні товари", en: "Technical products" },
};

function pickLabel(language, labels) {
  return labels?.[language] || labels?.uk || labels?.en || "";
}

function entityToLabel(entity, language) {
  return pickLabel(language, ENTITY_LABELS[entity]);
}

function emptyStateFor(entity) {
  if (entity === "manufacturers") {
    return buildManufacturerForm();
  }

  if (entity === "series") {
    return buildSeriesForm();
  }

  if (entity === "categories") {
    return buildCategoryForm();
  }

  return buildProductTaxonomyForm();
}

function sortProducts(items = []) {
  return [...items].sort((left, right) => {
    const leftLabel = String(left?.name || left?.article || left?.code || "").trim();
    const rightLabel = String(right?.name || right?.article || right?.code || "").trim();
    return leftLabel.localeCompare(rightLabel, "uk");
  });
}

function normalizeManufacturerCode(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9а-яіїєґ]+/gi, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

const MANUFACTURER_LOGO_ACCEPT = "image/png,image/jpeg,image/webp";
const MANUFACTURER_LOGO_ALLOWED_TYPES = new Set(["image/png", "image/jpeg", "image/webp"]);
const MANUFACTURER_LOGO_MAX_SIZE_BYTES = 12 * 1024 * 1024;

function ManufacturerLogo({ name = "", logoUrl = "", className = "" }) {
  const [hasBrokenImage, setHasBrokenImage] = useState(false);
  const normalizedLogoUrl = String(logoUrl || "").trim();
  const resolvedLogoUrl = resolveAdminAssetUrl(normalizedLogoUrl);
  const fallbackLabel = String(name || "").trim() || "—";

  useEffect(() => {
    setHasBrokenImage(false);
  }, [normalizedLogoUrl]);

  const rootClassName = ["fitting-manufacturer-logo", "material-taxonomy-manufacturer-logo", className]
    .filter(Boolean)
    .join(" ");

  if (!normalizedLogoUrl || hasBrokenImage) {
    return (
      <span className={rootClassName} title={fallbackLabel}>
        <span className="fitting-source-logo-text">{fallbackLabel}</span>
      </span>
    );
  }

  return (
    <span className={rootClassName} title={fallbackLabel}>
      <img
        alt={fallbackLabel}
        className="fitting-manufacturer-logo-image"
        loading="lazy"
        onError={() => setHasBrokenImage(true)}
        src={resolvedLogoUrl}
      />
    </span>
  );
}

export default function FittingTaxonomyAdminWorkspace({
  activeTab = "manufacturers",
  language = "uk",
  token = "",
  onNavigate = null,
}) {
  const [manufacturers, setManufacturers] = useState([]);
  const [series, setSeries] = useState([]);
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorEntity, setEditorEntity] = useState("manufacturers");
  const [editorMode, setEditorMode] = useState("create");
  const [editorItemId, setEditorItemId] = useState("");
  const [editorError, setEditorError] = useState("");
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorForm, setEditorForm] = useState(emptyStateFor("manufacturers"));
  const [editorLogoFile, setEditorLogoFile] = useState(null);
  const [editorLogoPreviewUrl, setEditorLogoPreviewUrl] = useState("");
  const [editorLogoRemoved, setEditorLogoRemoved] = useState(false);
  const [search, setSearch] = useState("");
  const logoFileInputRef = useRef(null);

  const manufacturersById = useMemo(() => new Map(manufacturers.map((item) => [String(item.id), item])), [manufacturers]);
  const seriesById = useMemo(() => new Map(series.map((item) => [String(item.id), item])), [series]);
  const categoriesById = useMemo(() => new Map(categories.map((item) => [String(item.id), item])), [categories]);

  const visibleManufacturers = useMemo(
    () => {
      const items = showInactive ? manufacturers : manufacturers.filter((item) => item.is_active);
      const normalizedSearch = search.trim().toLowerCase();
      const filtered = normalizedSearch
        ? items.filter((item) =>
            [item.name, item.code, item.country_code, item.description]
              .filter(Boolean)
              .join(" ")
              .toLowerCase()
              .includes(normalizedSearch),
          )
        : items;
      return sortFittingTaxonomyItems(filtered);
    },
    [manufacturers, search, showInactive],
  );

  const visibleSeries = useMemo(
    () => {
      const items = showInactive ? series : series.filter((item) => item.is_active);
      const normalizedSearch = search.trim().toLowerCase();
      const filtered = normalizedSearch
        ? items.filter((item) =>
            [item.name, item.code, manufacturersById.get(String(item.manufacturer_id))?.name, item.description]
              .filter(Boolean)
              .join(" ")
              .toLowerCase()
              .includes(normalizedSearch),
          )
        : items;
      return [...filtered].sort((left, right) => {
        const leftManufacturer = manufacturersById.get(String(left.manufacturer_id))?.name || "";
        const rightManufacturer = manufacturersById.get(String(right.manufacturer_id))?.name || "";
        const manufacturerCompare = leftManufacturer.localeCompare(rightManufacturer, "uk");
        if (manufacturerCompare) {
          return manufacturerCompare;
        }

        const leftLabel = String(left.name || left.code || "");
        const rightLabel = String(right.name || right.code || "");
        return leftLabel.localeCompare(rightLabel, "uk");
      });
    },
    [manufacturersById, search, series, showInactive],
  );

  const visibleCategories = useMemo(
    () => {
      const items = showInactive ? categories : categories.filter((item) => item.is_active);
      const normalizedSearch = search.trim().toLowerCase();
      const filtered = normalizedSearch
        ? items.filter((item) =>
            [item.name, item.code, categoriesById.get(String(item.parent_id))?.name, item.description]
              .filter(Boolean)
              .join(" ")
              .toLowerCase()
              .includes(normalizedSearch),
          )
        : items;
      return sortFittingTaxonomyItems(filtered);
    },
    [categories, categoriesById, search, showInactive],
  );

  const visibleProducts = useMemo(
    () => {
      const items = showInactive ? products : products.filter((item) => item.is_active);
      const normalizedSearch = search.trim().toLowerCase();
      const filtered = normalizedSearch
        ? items.filter((item) =>
            [item.name, item.article, item.code, item.brand]
              .filter(Boolean)
              .join(" ")
              .toLowerCase()
              .includes(normalizedSearch),
          )
        : items;
      return sortProducts(filtered);
    },
    [products, search, showInactive],
  );

  const activeManufacturerOptions = useMemo(
    () => buildManufacturerOptions(manufacturers, editorEntity === "series" ? editorForm.manufacturer_id : null),
    [editorEntity, editorForm.manufacturer_id, manufacturers],
  );
  const activeSeriesOptions = useMemo(
    () => buildSeriesOptions(series, editorForm.manufacturer_id, editorForm.series_id),
    [editorForm.manufacturer_id, editorForm.series_id, series],
  );
  const activeCategoryParentOptions = useMemo(
    () => buildCategoryParentOptions(categories, editorForm.parent_id, editorItemId),
    [categories, editorForm.parent_id, editorItemId],
  );

  useEffect(() => {
    return () => {
      if (editorLogoPreviewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(editorLogoPreviewUrl);
      }
    };
  }, [editorLogoPreviewUrl]);

  async function loadAllData() {
    if (!token) {
      return;
    }

    setLoading(true);
    setPageError("");
    try {
      const [manufacturersResult, seriesResult, categoriesResult, productsResult] = await Promise.all([
        listFittingManufacturers(token, true),
        listFittingSeries(token, true),
        listFittingCategories(token, true),
        listFittingProducts(token, { active_only: false }),
      ]);

      if (manufacturersResult.success) {
        setManufacturers(Array.isArray(manufacturersResult.items) ? manufacturersResult.items : []);
      } else {
        throw new Error(manufacturersResult.error || "Unable to load manufacturers");
      }

      if (seriesResult.success) {
        setSeries(Array.isArray(seriesResult.items) ? seriesResult.items : []);
      } else {
        throw new Error(seriesResult.error || "Unable to load series");
      }

      if (categoriesResult.success) {
        setCategories(Array.isArray(categoriesResult.items) ? categoriesResult.items : []);
      } else {
        throw new Error(categoriesResult.error || "Unable to load categories");
      }

      if (productsResult.success) {
        setProducts(Array.isArray(productsResult.items) ? productsResult.items : []);
      } else {
        throw new Error(productsResult.error || "Unable to load products");
      }
    } catch (error) {
      setPageError(error?.message || "Unable to load taxonomy data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAllData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    setSearch("");
  }, [activeTab]);

  function openEditor(entity, item = null) {
    setEditorEntity(entity);
    setEditorMode(item ? "edit" : "create");
    setEditorItemId(String(item?.id || ""));
    setEditorForm(
      entity === "manufacturers"
        ? buildManufacturerForm(item)
        : entity === "series"
          ? buildSeriesForm(item)
          : entity === "categories"
            ? buildCategoryForm(item)
            : buildProductTaxonomyForm(item),
    );
    setEditorError("");
    setEditorOpen(true);

    if (logoFileInputRef.current) {
      logoFileInputRef.current.value = "";
    }
    if (editorLogoPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(editorLogoPreviewUrl);
    }
    setEditorLogoFile(null);
    setEditorLogoPreviewUrl("");
    setEditorLogoRemoved(false);
  }

  function closeEditor() {
    if (logoFileInputRef.current) {
      logoFileInputRef.current.value = "";
    }
    if (editorLogoPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(editorLogoPreviewUrl);
    }
    setEditorOpen(false);
    setEditorItemId("");
    setEditorError("");
    setEditorForm(emptyStateFor(editorEntity));
    setEditorLogoFile(null);
    setEditorLogoPreviewUrl("");
    setEditorLogoRemoved(false);
  }

  function openLogoFilePicker() {
    if (logoFileInputRef.current) {
      logoFileInputRef.current.click();
    }
  }

  function handleLogoFileChange(event) {
    const file = event.target.files?.[0] || null;
    if (!file) {
      return;
    }

    const normalizedType = String(file.type || "").toLowerCase();
    if (!MANUFACTURER_LOGO_ALLOWED_TYPES.has(normalizedType)) {
      setEditorError(
        language === "uk"
          ? "Дозволені тільки PNG, JPG, JPEG або WEBP"
          : "Only PNG, JPG, JPEG, or WEBP files are allowed",
      );
      event.target.value = "";
      return;
    }

    if (file.size > MANUFACTURER_LOGO_MAX_SIZE_BYTES) {
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
  }

  async function submitEditor(event) {
    event.preventDefault();

    if (!token) {
      return;
    }

    setEditorSaving(true);
    setEditorError("");

    try {
      let result = null;

      if (editorEntity === "manufacturers") {
        let logoUrl = editorLogoRemoved ? null : String(editorForm.logo_url || "").trim() || null;

        if (editorLogoFile) {
          const uploadResult = await uploadFittingManufacturerLogo(token, editorLogoFile);
          if (!uploadResult?.success) {
            setEditorError(uploadResult?.error || (language === "uk" ? "Не вдалося завантажити логотип" : "Unable to upload logo"));
            return;
          }

          logoUrl = String(uploadResult.logo_url || "").trim() || null;
        }

        const nextCode = editorMode === "edit"
          ? String(editorForm.code || "").trim()
          : normalizeManufacturerCode(editorForm.name || "");
        const payload = {
          code: nextCode,
          name: String(editorForm.name || ""),
          description: String(editorForm.description || "") || null,
          website_url: String(editorForm.website_url || "") || null,
          logo_url: logoUrl,
          country_code: String(editorForm.country_code || "") || null,
          is_active: Boolean(editorForm.is_active),
          sort_order: Number(editorForm.sort_order || 0),
        };
        result = editorMode === "edit"
          ? await updateFittingManufacturer(token, editorItemId, payload)
          : await createFittingManufacturer(token, payload);
      } else if (editorEntity === "series") {
        const payload = {
          manufacturer_id: Number(editorForm.manufacturer_id || 0),
          code: String(editorForm.code || ""),
          name: String(editorForm.name || ""),
          description: String(editorForm.description || "") || null,
          is_active: Boolean(editorForm.is_active),
          sort_order: Number(editorForm.sort_order || 0),
        };
        result = editorMode === "edit"
          ? await updateFittingSeries(token, editorItemId, payload)
          : await createFittingSeries(token, payload);
      } else if (editorEntity === "categories") {
        const payload = {
          code: String(editorForm.code || ""),
          name: String(editorForm.name || ""),
          parent_id: parseNullableId(editorForm.parent_id),
          description: String(editorForm.description || "") || null,
          is_active: Boolean(editorForm.is_active),
          sort_order: Number(editorForm.sort_order || 0),
        };
        result = editorMode === "edit"
          ? await updateFittingCategory(token, editorItemId, payload)
          : await createFittingCategory(token, payload);
      } else if (editorEntity === "products") {
        const payload = buildProductTaxonomyPayload(editorForm);
        result = await updateFittingProductTaxonomy(token, editorItemId, payload);
      }

      if (!result?.success) {
        setEditorError(result?.error || "Unable to save");
        return;
      }

      closeEditor();
      await loadAllData();
    } catch (error) {
      setEditorError(error?.message || "Unable to save");
    } finally {
      setEditorSaving(false);
    }
  }

  async function handleDelete(entity, item) {
    if (!token || !item?.id) {
      return;
    }

    if (!window.confirm(language === "uk" ? "Видалити запис?" : "Delete this record?")) {
      return;
    }

    setLoading(true);
    try {
      let result = null;
      if (entity === "manufacturers") {
        result = await deleteFittingManufacturer(token, item.id);
      } else if (entity === "series") {
        result = await deleteFittingSeries(token, item.id);
      } else if (entity === "categories") {
        result = await deleteFittingCategory(token, item.id);
      }

      if (!result?.success) {
        setPageError(result?.error || "Unable to delete");
        return;
      }

      await loadAllData();
    } finally {
      setLoading(false);
    }
  }

  async function toggleActive(entity, item) {
    if (!token || !item?.id) {
      return;
    }

    setLoading(true);
    try {
      let result = null;
      const nextIsActive = !Boolean(item.is_active);

      if (entity === "manufacturers") {
        result = await updateFittingManufacturer(token, item.id, {
          code: item.code,
          name: item.name,
          description: item.description,
          website_url: item.website_url,
          logo_url: item.logo_url,
          country_code: item.country_code,
          is_active: nextIsActive,
          sort_order: item.sort_order || 0,
        });
      } else if (entity === "series") {
        result = await updateFittingSeries(token, item.id, {
          manufacturer_id: item.manufacturer_id,
          code: item.code,
          name: item.name,
          description: item.description,
          is_active: nextIsActive,
          sort_order: item.sort_order || 0,
        });
      } else if (entity === "categories") {
        result = await updateFittingCategory(token, item.id, {
          code: item.code,
          name: item.name,
          parent_id: item.parent_id,
          description: item.description,
          is_active: nextIsActive,
          sort_order: item.sort_order || 0,
        });
      } else if (entity === "products") {
        result = await updateFittingProductTaxonomy(token, item.id, {
          manufacturer_id: item.manufacturer_id,
          series_id: item.series_id,
          category_id: item.category_id,
          is_active: nextIsActive,
        });
      }

      if (!result?.success) {
        setPageError(result?.error || "Unable to update status");
        return;
      }

      await loadAllData();
    } finally {
      setLoading(false);
    }
  }

  function handleManufacturerNameChange(value) {
    setEditorForm((current) => ({
      ...current,
      code: editorEntity === "manufacturers" && editorMode === "create"
        ? normalizeManufacturerCode(value)
        : current.code,
      name: value,
    }));
  }

  function handleManufacturerFieldChange(nextManufacturerId) {
    setEditorForm((current) => {
      if (editorEntity !== "products") {
        return current;
      }

      const compatibleSeriesId = getCompatibleSeriesId({
        manufacturerId: nextManufacturerId,
        seriesId: current.series_id,
        seriesItems: series,
      });

      return {
        ...current,
        manufacturer_id: nextManufacturerId,
        series_id: compatibleSeriesId === null ? "" : String(compatibleSeriesId),
      };
    });
  }

  useEffect(() => {
    if (editorEntity !== "products") {
      return;
    }

    setEditorForm((current) => {
      const compatibleSeriesId = getCompatibleSeriesId({
        manufacturerId: current.manufacturer_id,
        seriesId: current.series_id,
        seriesItems: series,
      });

      if (compatibleSeriesId === null && String(current.series_id || "").trim()) {
        return {
          ...current,
          series_id: "",
        };
      }

      return current;
    });
  }, [editorEntity, series]);

  const editorLogoPreviewSource = editorLogoPreviewUrl || (!editorLogoRemoved ? resolveAdminAssetUrl(editorForm.logo_url) : "");
  const editorHasLogo = Boolean(editorLogoPreviewSource);
  const editorLogoFileName = editorLogoFile?.name || "";
  const visibleCountLabel = language === "uk"
    ? `${visibleManufacturers.length} записів`
    : `${visibleManufacturers.length} records`;

  return (
    <section className={activeTab === "manufacturers" ? "table-panel full-panel fitting-taxonomy-page-shell" : "dashboard-layout"}>
      {activeTab === "manufacturers" ? (
        <>
          <div className="catalog-page-header fitting-taxonomy-page-header">
            <div className="service-catalog-title fitting-taxonomy-page-title">
              {typeof onNavigate === "function" ? (
                <div className="fitting-category-breadcrumb fitting-category-breadcrumb-top">
                  <button className="fitting-breadcrumb-link" onClick={() => onNavigate("catalogFittings")} type="button">
                    {language === "uk" ? "Фурнітура" : "Fittings"}
                  </button>
                  <span className="fitting-breadcrumb-separator">/</span>
                  <strong>{language === "uk" ? "Виробники" : "Manufacturers"}</strong>
                </div>
              ) : null}
              <p>{language === "uk" ? "Керування виробниками фурнітури." : "Manage fitting manufacturers."}</p>
            </div>
            <div className="service-catalog-header-actions fitting-taxonomy-page-actions">
              <span className="service-tree-badge subtle">{visibleCountLabel}</span>
              <label className="materials-filter">
                <span>{language === "uk" ? "Пошук" : "Search"}</span>
                <input
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={language === "uk" ? "Фільтр..." : "Filter..."}
                  type="search"
                  value={search}
                />
              </label>
              <label className="toggle-label">
                <input
                  checked={showInactive}
                  onChange={(event) => setShowInactive(event.target.checked)}
                  type="checkbox"
                />
                {language === "uk" ? "Показати неактивні" : "Show inactive"}
              </label>
              <button className="ghost-button" disabled={loading} onClick={loadAllData} type="button">
                <RefreshCw size={16} />
                {language === "uk" ? "Оновити" : "Refresh"}
              </button>
              <button
                className="primary-button"
                onClick={() => openEditor(activeTab)}
                type="button"
              >
                <Plus size={16} />
                {language === "uk" ? "Додати" : "Add"}
              </button>
            </div>
          </div>

          {pageError ? <p className="status-message error">{pageError}</p> : null}

          <article className="catalog-card service-catalog-card service-catalog-card-full fitting-taxonomy-page-content">
            <div className="table-panel full-panel">
              <div className="fittings-table-header fitting-manufacturers-table">
                <span>{language === "uk" ? "Назва" : "Name"}</span>
                <span>{language === "uk" ? "Логотип" : "Logo"}</span>
                <span>{language === "uk" ? "Країна" : "Country"}</span>
                <span>{language === "uk" ? "Активна" : "Active"}</span>
              </div>
              <div className="fittings-table-list">
                {visibleManufacturers.map((item) => (
                  <article className="fittings-table-row fitting-manufacturers-table" key={item.id}>
                    <div>{item.name}</div>
                    <div className="manufacturer-logo-cell">
                      <ManufacturerLogo name={item.name} logoUrl={item.logo_url} />
                    </div>
                    <div>{item.country_code || "—"}</div>
                    <div>{item.is_active ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No")}</div>
                    <div className="catalog-actions">
                      <button className="icon-button" onClick={() => openEditor("manufacturers", item)} type="button">
                        <Pencil size={14} />
                      </button>
                      <button className="ghost-button compact-button" onClick={() => toggleActive("manufacturers", item)} type="button">
                        {item.is_active
                          ? (language === "uk" ? "Деактивувати" : "Deactivate")
                          : (language === "uk" ? "Активувати" : "Activate")}
                      </button>
                      {!item.is_active ? (
                        <button className="ghost-button compact-button danger-button" onClick={() => handleDelete("manufacturers", item)} type="button">
                          <Trash2 size={14} />
                          {language === "uk" ? "Видалити" : "Delete"}
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </article>
        </>
      ) : (
        <article className="catalog-card service-catalog-card service-catalog-card-full">
          <div className="service-catalog-header">
            <div className="service-catalog-header-actions">
              <label className="materials-filter">
                <span>{language === "uk" ? "Пошук" : "Search"}</span>
                <input
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={language === "uk" ? "Фільтр..." : "Filter..."}
                  type="search"
                  value={search}
                />
              </label>
              <label className="toggle-label">
                <input
                  checked={showInactive}
                  onChange={(event) => setShowInactive(event.target.checked)}
                  type="checkbox"
                />
                {language === "uk" ? "Показати неактивні" : "Show inactive"}
              </label>
              <button className="ghost-button" disabled={loading} onClick={loadAllData} type="button">
                <RefreshCw size={16} />
                {language === "uk" ? "Оновити" : "Refresh"}
              </button>
              <button
                className="primary-button"
                onClick={() => openEditor(activeTab)}
                type="button"
              >
                <Plus size={16} />
                {language === "uk" ? "Додати" : "Add"}
              </button>
            </div>
          </div>

          {pageError ? <p className="status-message error">{pageError}</p> : null}

          {activeTab === "series" ? (
          <div className="table-panel full-panel">
            <div className="fittings-table-header">
              <span>{language === "uk" ? "Назва" : "Name"}</span>
              <span>{language === "uk" ? "Код" : "Code"}</span>
              <span>{language === "uk" ? "Виробник" : "Manufacturer"}</span>
              <span>{language === "uk" ? "Активна" : "Active"}</span>
            </div>
            <div className="fittings-table-list">
              {visibleSeries.map((item) => (
                <article className="fittings-table-row" key={item.id}>
                  <div>{item.name}</div>
                  <div>{item.code}</div>
                  <div>{manufacturersById.get(String(item.manufacturer_id))?.name || item.manufacturer_id}</div>
                  <div>{item.is_active ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No")}</div>
                  <div className="catalog-actions">
                    <button className="icon-button" onClick={() => openEditor("series", item)} type="button">
                      <Pencil size={14} />
                    </button>
                    <button className="icon-button" onClick={() => toggleActive("series", item)} type="button">
                      {item.is_active ? "↘" : "↗"}
                    </button>
                    <button className="icon-button danger" onClick={() => handleDelete("series", item)} type="button">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
        ) : activeTab === "categories" ? (
          <div className="table-panel full-panel">
            <div className="fittings-table-header">
              <span>{language === "uk" ? "Назва" : "Name"}</span>
              <span>{language === "uk" ? "Код" : "Code"}</span>
              <span>{language === "uk" ? "Батьківська" : "Parent"}</span>
              <span>{language === "uk" ? "Активна" : "Active"}</span>
            </div>
            <div className="fittings-table-list">
              {visibleCategories.map((item) => (
                <article className="fittings-table-row" key={item.id}>
                  <div>{item.name}</div>
                  <div>{item.code}</div>
                  <div>{categoriesById.get(String(item.parent_id))?.name || "—"}</div>
                  <div>{item.is_active ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No")}</div>
                  <div className="catalog-actions">
                    <button className="icon-button" onClick={() => openEditor("categories", item)} type="button">
                      <Pencil size={14} />
                    </button>
                    <button className="icon-button" onClick={() => toggleActive("categories", item)} type="button">
                      {item.is_active ? "↘" : "↗"}
                    </button>
                    <button className="icon-button danger" onClick={() => handleDelete("categories", item)} type="button">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
          ) : (
          <div className="table-panel full-panel">
            <div className="fittings-table-header">
              <span>{language === "uk" ? "Назва" : "Name"}</span>
              <span>{language === "uk" ? "Артикул" : "Article"}</span>
              <span>{language === "uk" ? "Виробник" : "Manufacturer"}</span>
              <span>{language === "uk" ? "Серія" : "Series"}</span>
              <span>{language === "uk" ? "Категорія" : "Category"}</span>
              <span>{language === "uk" ? "Активний" : "Active"}</span>
            </div>
            <div className="fittings-table-list">
              {visibleProducts.map((item) => (
                <article className="fittings-table-row" key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <div className="fitting-form-note">
                      {language === "uk" ? `ID: ${item.id}` : `ID: ${item.id}`}
                    </div>
                  </div>
                  <div>{item.article || "—"}</div>
                  <div>{manufacturersById.get(String(item.manufacturer_id))?.name || "—"}</div>
                  <div>{seriesById.get(String(item.series_id))?.name || "—"}</div>
                  <div>{categoriesById.get(String(item.category_id))?.name || "—"}</div>
                  <div>{item.is_active ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No")}</div>
                  <div className="catalog-actions">
                    <button className="icon-button" onClick={() => openEditor("products", item)} type="button">
                      <Pencil size={14} />
                    </button>
                    <button className="icon-button" onClick={() => toggleActive("products", item)} type="button">
                      {item.is_active ? "↘" : "↗"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>
          )}
        </article>
      )}

      {editorOpen ? (
        <div aria-modal="true" className="modal-backdrop" onClick={closeEditor} role="dialog">
          <section className="confirm-modal supplier-confirm-modal" onClick={(event) => event.stopPropagation()}>
            <header className="confirm-header">
              <div>
                <strong>{language === "uk" ? "Виробник фурнітури" : "Fitting manufacturer"}</strong>
                <p>{editorMode === "edit" ? (language === "uk" ? "Редагування" : "Edit") : (language === "uk" ? "Створення" : "Create")}</p>
              </div>
              <button aria-label="Close" className="ghost-button compact-button detail-info-button" onClick={closeEditor} type="button">
                <X size={16} />
              </button>
            </header>
            <form className="catalog-form" onSubmit={submitEditor}>
              {editorEntity === "manufacturers" ? (
                <>
                  <div className="supplier-form-body">
                    <label className="supplier-form-field">
                      <span>{language === "uk" ? "Назва" : "Name"}</span>
                      <input
                        onChange={(event) => handleManufacturerNameChange(event.target.value)}
                        value={editorForm.name}
                      />
                    </label>

                    <label className="supplier-form-field supplier-logo-field">
                      <span>{language === "uk" ? "Логотип" : "Logo"}</span>
                      <input
                        accept={MANUFACTURER_LOGO_ACCEPT}
                        className="supplier-logo-file-input"
                        onChange={handleLogoFileChange}
                        ref={logoFileInputRef}
                        type="file"
                      />
                      <div className="supplier-logo-upload-panel">
                        <div className="supplier-logo-preview">
                          {editorHasLogo ? (
                            <ManufacturerLogo
                              className="supplier-logo-preview-mark"
                              name={editorForm.name}
                              logoUrl={editorLogoPreviewSource}
                            />
                          ) : (
                            <div className="supplier-logo-preview-placeholder">
                              <span className="supplier-logo-fallback">{String(editorForm.name || "").trim() || "—"}</span>
                            </div>
                          )}
                        </div>
                        <div className="supplier-logo-input-row">
                          <button className="ghost-button compact-button" onClick={openLogoFilePicker} type="button">
                            {editorLogoFile || editorLogoRemoved || editorForm.logo_url
                              ? (language === "uk" ? "Замінити" : "Replace")
                              : (language === "uk" ? "Вибрати зображення" : "Choose image")}
                          </button>
                          <button
                            className="ghost-button compact-button"
                            disabled={!editorHasLogo}
                            onClick={removeEditorLogo}
                            type="button"
                          >
                            {language === "uk" ? "Видалити" : "Remove"}
                          </button>
                        </div>
                        {editorLogoFileName ? <p className="supplier-logo-file-name">{editorLogoFileName}</p> : null}
                      </div>
                    </label>

                    <div className="supplier-form-options">
                      <label className="supplier-form-field">
                        <span>{language === "uk" ? "Країна" : "Country"}</span>
                        <input
                          onChange={(event) => setEditorForm((current) => ({ ...current, country_code: event.target.value }))}
                          value={editorForm.country_code}
                        />
                      </label>
                      <label className="toggle-label supplier-toggle">
                        <input
                          checked={Boolean(editorForm.is_active)}
                          onChange={(event) => setEditorForm((current) => ({ ...current, is_active: event.target.checked }))}
                          type="checkbox"
                        />
                        {language === "uk" ? "Активний" : "Active"}
                      </label>
                    </div>
                  </div>
                </>
              ) : editorEntity === "series" ? (
                <>
                  <label>
                    <span>{language === "uk" ? "Виробник" : "Manufacturer"}</span>
                    <select value={editorForm.manufacturer_id} onChange={(event) => setEditorForm((current) => ({ ...current, manufacturer_id: event.target.value }))}>
                      <option value="">{language === "uk" ? "Оберіть виробника" : "Choose manufacturer"}</option>
                      {activeManufacturerOptions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} ({item.code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>{language === "uk" ? "Назва" : "Name"}</span>
                    <input value={editorForm.name} onChange={(event) => setEditorForm((current) => ({ ...current, name: event.target.value }))} />
                  </label>
                  <label>
                    <span>{language === "uk" ? "Код" : "Code"}</span>
                    <input value={editorForm.code} onChange={(event) => setEditorForm((current) => ({ ...current, code: event.target.value }))} />
                  </label>
                  <label>
                    <span>{language === "uk" ? "Опис" : "Description"}</span>
                    <textarea value={editorForm.description} onChange={(event) => setEditorForm((current) => ({ ...current, description: event.target.value }))} />
                  </label>
                  <label>
                    <span>{language === "uk" ? "Порядок" : "Sort order"}</span>
                    <input type="number" value={editorForm.sort_order} onChange={(event) => setEditorForm((current) => ({ ...current, sort_order: event.target.value }))} />
                  </label>
                </>
              ) : editorEntity === "categories" ? (
                <>
                  <label>
                    <span>{language === "uk" ? "Назва" : "Name"}</span>
                    <input value={editorForm.name} onChange={(event) => setEditorForm((current) => ({ ...current, name: event.target.value }))} />
                  </label>
                  <label>
                    <span>{language === "uk" ? "Код" : "Code"}</span>
                    <input value={editorForm.code} onChange={(event) => setEditorForm((current) => ({ ...current, code: event.target.value }))} />
                  </label>
                  <label>
                    <span>{language === "uk" ? "Батьківська категорія" : "Parent category"}</span>
                    <select value={editorForm.parent_id} onChange={(event) => setEditorForm((current) => ({ ...current, parent_id: event.target.value }))}>
                      <option value="">{language === "uk" ? "Без батька" : "No parent"}</option>
                      {activeCategoryParentOptions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} ({item.code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>{language === "uk" ? "Опис" : "Description"}</span>
                    <textarea value={editorForm.description} onChange={(event) => setEditorForm((current) => ({ ...current, description: event.target.value }))} />
                  </label>
                  <label>
                    <span>{language === "uk" ? "Порядок" : "Sort order"}</span>
                    <input type="number" value={editorForm.sort_order} onChange={(event) => setEditorForm((current) => ({ ...current, sort_order: event.target.value }))} />
                  </label>
                </>
              ) : (
                <>
                  <div className="fitting-form-note">
                    {language === "uk"
                      ? "Зміни застосовуються до технічного товару та пов'язаних записів."
                      : "Changes apply to the technical product and its linked records."}
                  </div>
                  <label>
                    <span>{language === "uk" ? "Виробник" : "Manufacturer"}</span>
                    <select value={editorForm.manufacturer_id} onChange={(event) => handleManufacturerFieldChange(event.target.value)}>
                      <option value="">{language === "uk" ? "Без виробника" : "No manufacturer"}</option>
                      {buildManufacturerOptions(manufacturers, editorForm.manufacturer_id).map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} ({item.code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>{language === "uk" ? "Серія" : "Series"}</span>
                    <select value={editorForm.series_id} onChange={(event) => setEditorForm((current) => ({ ...current, series_id: event.target.value }))}>
                      <option value="">{language === "uk" ? "Без серії" : "No series"}</option>
                      {buildSeriesOptions(series, editorForm.manufacturer_id, editorForm.series_id).map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} ({item.code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>{language === "uk" ? "Категорія" : "Category"}</span>
                    <select value={editorForm.category_id} onChange={(event) => setEditorForm((current) => ({ ...current, category_id: event.target.value }))}>
                      <option value="">{language === "uk" ? "Без категорії" : "No category"}</option>
                      {buildCategoryParentOptions(categories, editorForm.category_id).map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.name} ({item.code})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="toggle-label">
                    <input
                      checked={Boolean(editorForm.is_active)}
                      onChange={(event) => setEditorForm((current) => ({ ...current, is_active: event.target.checked }))}
                      type="checkbox"
                    />
                    {language === "uk" ? "Активний" : "Active"}
                  </label>
                </>
              )}

              {editorError ? <p className="status-message error supplier-form-error">{editorError}</p> : null}

              <div className="supplier-form-footer confirm-actions">
                <button className="ghost-button" disabled={editorSaving} onClick={closeEditor} type="button">
                  {language === "uk" ? "Скасувати" : "Cancel"}
                </button>
                <button className="primary-button" disabled={editorSaving} type="submit">
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
