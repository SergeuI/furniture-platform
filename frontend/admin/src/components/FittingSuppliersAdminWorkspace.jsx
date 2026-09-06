import { useEffect, useMemo, useRef, useState } from "react";
import { Pencil, Plus, RefreshCw, Save, Trash2, X } from "lucide-react";

import {
  createFittingSupplier,
  deleteFittingSupplier,
  listFittingSuppliers,
  resolveAdminAssetUrl,
  updateFittingSupplier,
  uploadSupplierLogo,
} from "../api.js";
import CatalogBreadcrumbTrail from "./CatalogBreadcrumbTrail.jsx";
import DeleteConfirmModal from "./DeleteConfirmModal.jsx";

function normalizeSupplierText(value) {
  return String(value || "").trim();
}

function normalizeSupplierLogoUrl(value) {
  return String(value || "").trim();
}

const SUPPLIER_LOGO_ACCEPT = "image/png,image/jpeg,image/webp";
const SUPPLIER_LOGO_ALLOWED_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/webp",
]);
const SUPPLIER_LOGO_MAX_SIZE_BYTES = 12 * 1024 * 1024;

function buildSupplierForm(item = null) {
  return {
    logo_url: String(item?.logo_url || ""),
    name: String(item?.name || ""),
    is_active: Boolean(item?.is_active ?? true),
    is_system: Boolean(item?.is_system ?? false),
  };
}

function SupplierLogo({ name = "", logoUrl = "", className = "" }) {
  const [hasBrokenImage, setHasBrokenImage] = useState(false);
  const normalizedLogoUrl = normalizeSupplierLogoUrl(logoUrl);
  const resolvedLogoUrl = resolveAdminAssetUrl(normalizedLogoUrl);
  const fallbackLabel = normalizeSupplierText(name) || "—";

  useEffect(() => {
    setHasBrokenImage(false);
  }, [normalizedLogoUrl]);

  const rootClassName = [
    "fitting-manufacturer-logo",
    "material-taxonomy-manufacturer-logo",
    className,
  ]
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

export default function FittingSuppliersAdminWorkspace({
  language = "uk",
  token = "",
  currentUserId = "",
  currentUserRole = "admin",
  breadcrumbCatalogLabel = "",
  breadcrumbRootLabel = "",
  breadcrumbCurrentLabel = "",
  onBreadcrumbCatalogClick = null,
  onBreadcrumbRootClick = null,
  title = language === "uk" ? "Постачальники" : "Suppliers",
  description = language === "uk"
    ? "Керування системними та власними постачальниками фурнітури."
    : "Manage system and personal fitting suppliers.",
}) {
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [pageError, setPageError] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [search, setSearch] = useState("");
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorMode, setEditorMode] = useState("create");
  const [editorItemId, setEditorItemId] = useState("");
  const [editorError, setEditorError] = useState("");
  const [editorSaving, setEditorSaving] = useState(false);
  const [editorForm, setEditorForm] = useState(buildSupplierForm());
  const [editorLogoFile, setEditorLogoFile] = useState(null);
  const [editorLogoPreviewUrl, setEditorLogoPreviewUrl] = useState("");
  const [editorLogoRemoved, setEditorLogoRemoved] = useState(false);
  const [deleteConfirmItem, setDeleteConfirmItem] = useState(null);
  const logoFileInputRef = useRef(null);

  const visibleSuppliers = useMemo(() => {
    const items = showInactive ? suppliers : suppliers.filter((item) => item.is_active);
    const normalizedSearch = search.trim().toLowerCase();
    if (!normalizedSearch) {
      return [...items].sort((left, right) => {
        const leftLabel = normalizeSupplierText(left?.name);
        const rightLabel = normalizeSupplierText(right?.name);
        return leftLabel.localeCompare(rightLabel, "uk");
      });
    }

    return [...items]
      .filter((item) =>
        [item.name, item.owner_user_id, item.is_system ? "system" : "own"]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(normalizedSearch),
      )
      .sort((left, right) => {
        const leftLabel = normalizeSupplierText(left?.name);
        const rightLabel = normalizeSupplierText(right?.name);
        return leftLabel.localeCompare(rightLabel, "uk");
      });
  }, [search, showInactive, suppliers]);

  const pageLabel = useMemo(() => {
    const visibleCount = visibleSuppliers.length;
    return language === "uk"
      ? `${visibleCount} записів`
      : `${visibleCount} records`;
  }, [language, visibleSuppliers.length]);

  async function loadSuppliers() {
    if (!token) {
      setSuppliers([]);
      return;
    }

    setLoading(true);
    setPageError("");
    try {
      const result = await listFittingSuppliers(token, true);
      if (!result.success) {
        throw new Error(result.error || (language === "uk" ? "Не вдалося завантажити постачальників" : "Unable to load suppliers"));
      }

      setSuppliers(Array.isArray(result.items) ? result.items : []);
    } catch (error) {
      setPageError(error?.message || (language === "uk" ? "Не вдалося завантажити постачальників" : "Unable to load suppliers"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSuppliers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    return () => {
      if (editorLogoPreviewUrl.startsWith("blob:")) {
        URL.revokeObjectURL(editorLogoPreviewUrl);
      }
    };
  }, [editorLogoPreviewUrl]);

  function openEditor(item = null) {
    setEditorMode(item ? "edit" : "create");
    setEditorItemId(String(item?.id || ""));
    setEditorForm(buildSupplierForm(item));
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
    if (logoFileInputRef.current) {
      logoFileInputRef.current.value = "";
    }
    if (editorLogoPreviewUrl.startsWith("blob:")) {
      URL.revokeObjectURL(editorLogoPreviewUrl);
    }
    setEditorOpen(false);
    setEditorItemId("");
    setEditorError("");
    setEditorForm(buildSupplierForm());
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
    if (!SUPPLIER_LOGO_ALLOWED_TYPES.has(normalizedType)) {
      setEditorError(language === "uk" ? "Дозволені тільки PNG, JPG, JPEG або WEBP" : "Only PNG, JPG, JPEG, or WEBP files are allowed");
      event.target.value = "";
      return;
    }

    if (file.size > SUPPLIER_LOGO_MAX_SIZE_BYTES) {
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
      let logoUrl = editorLogoRemoved ? null : String(editorForm.logo_url || "").trim() || null;

      if (editorLogoFile) {
        const uploadResult = await uploadSupplierLogo(token, editorLogoFile);
        if (!uploadResult?.success) {
          setEditorError(uploadResult?.error || (language === "uk" ? "Не вдалося завантажити логотип" : "Unable to upload logo"));
          return;
        }

        logoUrl = String(uploadResult.logo_url || "").trim() || null;
      }

      const payload = {
        name: String(editorForm.name || "").trim(),
        logo_url: logoUrl,
        is_active: Boolean(editorForm.is_active),
        is_system: currentUserRole === "admin" ? Boolean(editorForm.is_system) : false,
      };

      const result = editorMode === "edit"
        ? await updateFittingSupplier(token, editorItemId, payload)
        : await createFittingSupplier(token, payload);

      if (!result?.success) {
        setEditorError(result?.error || (language === "uk" ? "Не вдалося зберегти" : "Unable to save"));
        return;
      }

      closeEditor();
      await loadSuppliers();
    } catch (error) {
      setEditorError(error?.message || (language === "uk" ? "Не вдалося зберегти" : "Unable to save"));
    } finally {
      setEditorSaving(false);
    }
  }

  function openDeleteConfirm(item) {
    if (!item) {
      return;
    }

    setPageError("");
    setDeleteConfirmItem(item);
  }

  function closeDeleteConfirm() {
    setDeleteConfirmItem(null);
  }

  async function performDelete(item) {
    if (!token || !item?.id) {
      return;
    }

    const result = await deleteFittingSupplier(token, item.id);
    if (!result?.success) {
      throw new Error(result?.error || (language === "uk" ? "Не вдалося видалити" : "Unable to delete"));
    }

    await loadSuppliers();
  }

  async function toggleActive(item) {
    if (!token || !item?.id) {
      return;
    }

    setLoading(true);
    setPageError("");
    try {
      const result = await updateFittingSupplier(token, item.id, {
        name: item.name,
        is_active: !Boolean(item.is_active),
        is_system: Boolean(item.is_system),
      });

      if (!result?.success) {
        setPageError(result?.error || (language === "uk" ? "Не вдалося оновити статус" : "Unable to update status"));
        return;
      }

      await loadSuppliers();
    } finally {
      setLoading(false);
    }
  }

  const canEditSystemSupplier = currentUserRole === "admin";
  const editorLogoPreviewSource = editorLogoPreviewUrl || (!editorLogoRemoved ? resolveAdminAssetUrl(editorForm.logo_url) : "");
  const editorHasLogo = Boolean(editorLogoPreviewSource);
  const editorLogoFileName = editorLogoFile?.name || "";

  return (
    <section className="table-panel full-panel">
      {breadcrumbRootLabel && breadcrumbCurrentLabel ? (
        <header className="catalog-page-header material-taxonomy-page-header supplier-page-header">
          <div className="service-catalog-title material-taxonomy-page-title">
            <CatalogBreadcrumbTrail
              items={[
                ...(breadcrumbCatalogLabel
                  ? [{
                      label: breadcrumbCatalogLabel,
                      onClick: onBreadcrumbCatalogClick,
                      title: breadcrumbCatalogLabel,
                    }]
                  : []),
                {
                  label: breadcrumbRootLabel,
                  onClick: onBreadcrumbRootClick,
                  title: breadcrumbRootLabel,
                },
                {
                  current: true,
                  label: breadcrumbCurrentLabel,
                  title: breadcrumbCurrentLabel,
                },
              ]}
            />
            <p>{description}</p>
          </div>
          <div className="service-catalog-header-actions material-taxonomy-page-actions supplier-page-actions">
            <span className="service-tree-badge subtle">{pageLabel}</span>
            <label className="materials-filter supplier-search">
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
            <button className="ghost-button" disabled={loading} onClick={loadSuppliers} type="button">
              <RefreshCw size={16} />
              {language === "uk" ? "Оновити" : "Refresh"}
            </button>
            <button className="primary-button" onClick={() => openEditor()} type="button">
              <Plus size={16} />
              {language === "uk" ? "Додати" : "Add"}
            </button>
          </div>
        </header>
      ) : (
        <header className="supplier-page-header">
          <h1>{title}</h1>
          <p>{description}</p>
        </header>
      )}

      <article className="catalog-card service-catalog-card service-catalog-card-full">
        {pageError ? <p className="status-message error">{pageError}</p> : null}

        <div className="table-panel full-panel suppliers-table">
          <div className="fittings-table-header">
            <span>{language === "uk" ? "Назва" : "Name"}</span>
            <span>{language === "uk" ? "Логотип" : "Logo"}</span>
            <span>{language === "uk" ? "Власність" : "Scope"}</span>
            <span>{language === "uk" ? "Активний" : "Active"}</span>
            <span>{language === "uk" ? "Дії" : "Actions"}</span>
          </div>
          <div className="fittings-table-list">
            {visibleSuppliers.map((item) => {
              const isOwnSupplier = !item.is_system && String(item.owner_user_id || "").trim() === String(currentUserId || "").trim();
              const scopeLabel = item.is_system
                ? (language === "uk" ? "Системний" : "System")
                : isOwnSupplier
                  ? (language === "uk" ? "Мій" : "Mine")
                  : (language === "uk" ? "Власний" : "Personal");
              const canManageItem = currentUserRole === "admin" || isOwnSupplier || !item.is_system;

              return (
                <article className="fittings-table-row" key={item.id}>
                  <div className="material-taxonomy-name-cell">{item.name}</div>
                  <div className="manufacturer-logo-cell">
                    <SupplierLogo name={item.name} logoUrl={item.logo_url} />
                  </div>
                  <div className="material-taxonomy-manufacturer-scope-cell">{scopeLabel}</div>
                  <div>{item.is_active ? (language === "uk" ? "Так" : "Yes") : (language === "uk" ? "Ні" : "No")}</div>
                  <div className="catalog-actions">
                    <button
                      className="icon-button"
                      disabled={!canManageItem || (item.is_system && !canEditSystemSupplier)}
                      onClick={() => openEditor(item)}
                      type="button"
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      className="ghost-button compact-button"
                      disabled={!canManageItem || (item.is_system && !canEditSystemSupplier)}
                      onClick={() => toggleActive(item)}
                      type="button"
                    >
                      {item.is_active
                        ? (language === "uk" ? "Деактивувати" : "Deactivate")
                        : (language === "uk" ? "Активувати" : "Activate")}
                    </button>
                    {!item.is_active ? (
                      <button
                        className="ghost-button compact-button danger-button"
                        disabled={!canManageItem || (item.is_system && !canEditSystemSupplier)}
                        onClick={() => openDeleteConfirm(item)}
                        type="button"
                      >
                        <Trash2 size={14} />
                        {language === "uk" ? "Видалити" : "Delete"}
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        </div>

      </article>

      <DeleteConfirmModal
        cancelLabel={language === "uk" ? "Скасувати" : "Cancel"}
        confirmLabel={language === "uk" ? "Видалити" : "Delete"}
        loadingLabel={language === "uk" ? "Видалення..." : "Deleting..."}
        message={language === "uk"
          ? `Видалити постачальника «${deleteConfirmItem?.name || ""}»?`
          : `Delete supplier "${deleteConfirmItem?.name || ""}"?`}
        open={Boolean(deleteConfirmItem)}
        onCancel={closeDeleteConfirm}
        onConfirm={async () => {
          if (!deleteConfirmItem) {
            return;
          }

          await performDelete(deleteConfirmItem);
        }}
        title={language === "uk" ? "Видалити постачальника" : "Delete supplier"}
      />

      {editorOpen ? (
        <div aria-modal="true" className="modal-backdrop" onClick={closeEditor} role="dialog">
          <section className="confirm-modal supplier-confirm-modal" onClick={(event) => event.stopPropagation()}>
            <header className="confirm-header">
              <div>
                <strong>{language === "uk" ? "Постачальник" : "Supplier"}</strong>
                <p>{editorMode === "edit" ? (language === "uk" ? "Редагування" : "Edit") : (language === "uk" ? "Створення" : "Create")}</p>
              </div>
              <button
                aria-label="Close"
                className="ghost-button compact-button detail-info-button"
                onClick={closeEditor}
                type="button"
              >
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

                <label className="supplier-form-field supplier-logo-field">
                  <span>{language === "uk" ? "Логотип" : "Logo"}</span>
                  <input
                    accept={SUPPLIER_LOGO_ACCEPT}
                    className="supplier-logo-file-input"
                    onChange={handleLogoFileChange}
                    ref={logoFileInputRef}
                    type="file"
                  />
                  <div className="supplier-logo-upload-panel">
                    <div className="supplier-logo-preview">
                      {editorHasLogo ? (
                        <SupplierLogo className="supplier-logo-preview-mark" name={editorForm.name} logoUrl={editorLogoPreviewSource} />
                      ) : (
                        <div className="supplier-logo-preview-placeholder">
                          <span className="supplier-logo-fallback">{normalizeSupplierText(editorForm.name) || "—"}</span>
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
                  {currentUserRole === "admin" ? (
                    <label className="toggle-label supplier-toggle">
                      <input
                        checked={Boolean(editorForm.is_system)}
                        onChange={(event) => setEditorForm((current) => ({ ...current, is_system: event.target.checked }))}
                        type="checkbox"
                      />
                      {language === "uk" ? "Системний постачальник" : "System supplier"}
                    </label>
                  ) : null}

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
