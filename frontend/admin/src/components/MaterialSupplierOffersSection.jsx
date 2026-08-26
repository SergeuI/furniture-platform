import { useEffect, useMemo, useRef, useState } from "react";
import { Pencil, Plus, Save, Trash2, X } from "lucide-react";

import {
  attachMaterialSupplierOfferFromSource,
  createMaterialSupplierOffer,
  deleteMaterialSupplierOffer,
  listFittingSuppliers,
  resolveAdminAssetUrl,
  updateMaterialSupplierOffer,
} from "../api.js";
import DeleteConfirmModal from "./DeleteConfirmModal.jsx";
import {
  shouldShowSupplierEmptyState,
  shouldShowSupplierErrorState,
  shouldShowSupplierLoadingState,
  shouldShowSupplierTabs,
} from "./materialDetailState.js";

function normalizeText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function buildOfferForm(item = null) {
  return {
    supplier_id: String(item?.supplier_id || ""),
    article: String(item?.article || ""),
    source_url: String(item?.source_url || ""),
    price: item?.price === null || item?.price === undefined ? "" : String(item.price),
    currency: String(item?.currency || ""),
    unit: String(item?.unit || ""),
    stock: String(item?.stock || ""),
    city: String(item?.city || ""),
    region: String(item?.region || ""),
    is_active: Boolean(item?.is_active ?? true),
  };
}

function getOfferAvailabilityLabel(value, language) {
  const normalized = normalizeText(value);
  if (!normalized) {
    return language === "en" ? "Not set" : "Не вказано";
  }
  return normalized;
}

function sortSupplierOffers(left, right) {
  const leftActive = Boolean(left?.is_active);
  const rightActive = Boolean(right?.is_active);

  if (leftActive !== rightActive) {
    return leftActive ? -1 : 1;
  }

  const leftPriority = Number(left?.priority ?? 0);
  const rightPriority = Number(right?.priority ?? 0);

  if (leftPriority !== rightPriority) {
    return leftPriority - rightPriority;
  }

  return Number(left?.id ?? 0) - Number(right?.id ?? 0);
}

function pickDefaultOfferId(offers) {
  const [firstOffer] = [...offers].sort(sortSupplierOffers);
  return firstOffer?.id ? String(firstOffer.id) : "";
}

function MaterialSupplierLogo({ name = "", logoUrl = "" }) {
  const [hasBrokenLogo, setHasBrokenLogo] = useState(false);
  const normalizedLogoUrl = normalizeText(logoUrl);
  const resolvedLogoUrl = resolveAdminAssetUrl(normalizedLogoUrl);
  const fallbackLabel = normalizeText(name) || "—";

  useEffect(() => {
    setHasBrokenLogo(false);
  }, [normalizedLogoUrl]);

  if (!normalizedLogoUrl || hasBrokenLogo) {
    return (
      <span className="fitting-source-logo material-supplier-offer-logo" title={fallbackLabel}>
        <span className="fitting-source-logo-text">{fallbackLabel.slice(0, 2).toUpperCase() || "—"}</span>
      </span>
    );
  }

  return (
    <span className="fitting-manufacturer-logo material-supplier-offer-logo" title={fallbackLabel}>
      <img
        alt={fallbackLabel}
        className="fitting-manufacturer-logo-image"
        loading="lazy"
        onError={() => setHasBrokenLogo(true)}
        src={resolvedLogoUrl}
      />
    </span>
  );
}

export default function MaterialSupplierOffersSection({
  language = "uk",
  token = "",
  materialDetail = null,
  supplierOffers = [],
  canEdit = false,
  status = "idle",
  selectedOfferId = "",
  onSelectedOfferChange = null,
  onSelectedOfferActionsChange = null,
  onRefreshMaterialDetail = null,
}) {
  const article = String(materialDetail?.article || "").trim();
  const [offers, setOffers] = useState(() => (Array.isArray(materialDetail?.supplier_offers) ? materialDetail.supplier_offers : []));
  const [selectedSupplierOfferId, setSelectedSupplierOfferId] = useState("");
  const [supplierItems, setSupplierItems] = useState([]);
  const [supplierLoading, setSupplierLoading] = useState(false);
  const [supplierError, setSupplierError] = useState("");
  const [offerModalOpen, setOfferModalOpen] = useState(false);
  const [offerModalMode, setOfferModalMode] = useState("create");
  const [offerCreateMode, setOfferCreateMode] = useState("manual");
  const [offerModalItem, setOfferModalItem] = useState(null);
  const [offerModalForm, setOfferModalForm] = useState(() => buildOfferForm());
  const [offerModalError, setOfferModalError] = useState("");
  const [offerModalErrorDetails, setOfferModalErrorDetails] = useState("");
  const [offerModalSaving, setOfferModalSaving] = useState(false);
  const [offerActionError, setOfferActionError] = useState("");
  const [busyOfferId, setBusyOfferId] = useState("");
  const [deleteOfferItem, setDeleteOfferItem] = useState(null);
  const supplierLoadRequestRef = useRef(0);
  const previousArticleRef = useRef(article);
  const isSelectionControlled = typeof onSelectedOfferChange === "function";
  const effectiveSelectedSupplierOfferId = isSelectionControlled
    ? String(selectedOfferId || "").trim()
    : selectedSupplierOfferId;

  function setEffectiveSelectedSupplierOfferId(nextSelectedId) {
    const normalizedNextSelectedId = String(nextSelectedId || "").trim();
    if (isSelectionControlled) {
      onSelectedOfferChange(normalizedNextSelectedId);
      return;
    }
    setSelectedSupplierOfferId(normalizedNextSelectedId);
  }

  useEffect(() => {
    const nextOffers = Array.isArray(supplierOffers) && supplierOffers.length
      ? supplierOffers
      : Array.isArray(materialDetail?.supplier_offers)
        ? materialDetail.supplier_offers
        : [];

    if (previousArticleRef.current === article) {
      setOffers(nextOffers);
      const currentSelectedId = String(effectiveSelectedSupplierOfferId || "").trim();
      if (currentSelectedId && nextOffers.some((offer) => String(offer?.id || "") === String(currentSelectedId))) {
        setEffectiveSelectedSupplierOfferId(currentSelectedId);
      } else {
        setEffectiveSelectedSupplierOfferId(pickDefaultOfferId(nextOffers));
      }
      return;
    }

    previousArticleRef.current = article;
    setOffers(nextOffers);
    setEffectiveSelectedSupplierOfferId(pickDefaultOfferId(nextOffers));
    setOfferModalOpen(false);
    setOfferModalItem(null);
    setOfferModalForm(buildOfferForm());
    setOfferModalError("");
    setOfferModalErrorDetails("");
    setOfferModalSaving(false);
    setOfferActionError("");
    setBusyOfferId("");
    setDeleteOfferItem(null);
  }, [article, materialDetail?.supplier_offers, supplierOffers]);

  useEffect(() => {
    if (!offers.length) {
      setEffectiveSelectedSupplierOfferId("");
      return;
    }

    if (effectiveSelectedSupplierOfferId && offers.some((offer) => String(offer?.id || "") === String(effectiveSelectedSupplierOfferId))) {
      return;
    }

    setEffectiveSelectedSupplierOfferId(pickDefaultOfferId(offers));
  }, [effectiveSelectedSupplierOfferId, offers]);

  useEffect(() => {
    if (!offerModalOpen || !token || (offerModalMode === "create" && offerCreateMode === "link")) {
      return undefined;
    }

    let isActive = true;
    const requestId = supplierLoadRequestRef.current + 1;
    supplierLoadRequestRef.current = requestId;

    async function loadSuppliers() {
      setSupplierLoading(true);
      setSupplierError("");

      try {
        const result = await listFittingSuppliers(token, true);

        if (!isActive || supplierLoadRequestRef.current !== requestId) {
          return;
        }

        if (!result.success) {
          throw new Error(result.error || (language === "en" ? "Unable to load suppliers" : "Не вдалося завантажити постачальників"));
        }

        setSupplierItems(Array.isArray(result.items) ? result.items : []);
      } catch (error) {
        if (!isActive || supplierLoadRequestRef.current !== requestId) {
          return;
        }

        setSupplierItems([]);
        setSupplierError(error?.message || (language === "en" ? "Unable to load suppliers" : "Не вдалося завантажити постачальників"));
      } finally {
        if (isActive && supplierLoadRequestRef.current === requestId) {
          setSupplierLoading(false);
        }
      }
    }

    void loadSuppliers();

    return () => {
      isActive = false;
    };
  }, [language, offerCreateMode, offerModalMode, offerModalOpen, token]);

  const detailOffers = Array.isArray(supplierOffers) && supplierOffers.length
    ? supplierOffers
    : Array.isArray(materialDetail?.supplier_offers)
      ? materialDetail.supplier_offers
      : [];
  const sourceOffers = detailOffers.length ? detailOffers : offers;
  const visibleOffers = useMemo(() => [...sourceOffers].sort(sortSupplierOffers), [sourceOffers]);
  const hasVisibleOffers = visibleOffers.length > 0;
  const selectedOffer = useMemo(() => {
    if (!hasVisibleOffers) {
      return null;
    }

    const selected = visibleOffers.find((offer) => String(offer?.id || "") === String(effectiveSelectedSupplierOfferId));
    return selected || visibleOffers[0] || null;
  }, [effectiveSelectedSupplierOfferId, hasVisibleOffers, visibleOffers]);

  const selectedOfferActionHandlersRef = useRef({
    onEdit: null,
    onToggleActive: null,
    onDelete: null,
  });

  const activeSupplierItems = useMemo(
    () => supplierItems.filter((item) => Boolean(item?.is_active)),
    [supplierItems],
  );

  const selectedSupplierId = String(offerModalForm.supplier_id || "").trim();
  const selectedSupplier = useMemo(() => {
    if (!selectedSupplierId) {
      return null;
    }

    return supplierItems.find((item) => String(item?.id || "") === selectedSupplierId) || null;
  }, [selectedSupplierId, supplierItems]);

  const visibleSupplierItems = useMemo(() => {
    const nextItems = [...activeSupplierItems];
    if (offerModalMode === "edit" && selectedSupplier && !selectedSupplier.is_active) {
      nextItems.unshift(selectedSupplier);
    }

    return nextItems
      .filter((item, index, array) =>
        array.findIndex((candidate) => String(candidate?.id || "") === String(item?.id || "")) === index,
      )
      .sort((left, right) => normalizeText(left?.name).localeCompare(normalizeText(right?.name), "uk"));
  }, [activeSupplierItems, offerModalMode, selectedSupplier]);

  const canCreateOffer = canEdit && Boolean(article);

  function openOfferModal(item = null) {
    setOfferModalMode(item ? "edit" : "create");
    setOfferCreateMode(item ? "manual" : "link");
    setOfferModalItem(item);
    setOfferModalForm(buildOfferForm(item));
    setOfferModalError("");
    setOfferModalErrorDetails("");
    setSupplierError("");
    setOfferModalOpen(true);
  }

  function closeOfferModal(force = false) {
    if (offerModalSaving && force !== true) {
      return;
    }

    setOfferModalOpen(false);
    setOfferModalMode("create");
    setOfferCreateMode("link");
    setOfferModalItem(null);
    setOfferModalForm(buildOfferForm());
    setOfferModalError("");
    setOfferModalErrorDetails("");
    setSupplierError("");
  }

  function updateOfferForm(field, value) {
    setOfferModalForm((current) => ({
      ...current,
      [field]: value,
    }));
  }

  async function refreshMaterialDetail() {
    if (typeof onRefreshMaterialDetail === "function") {
      await onRefreshMaterialDetail();
    }
  }

  function applyOfferPatch(nextOffer) {
    if (!nextOffer?.id) {
      return;
    }

    setOffers((current) => {
      const nextItems = current.filter((item) => String(item?.id || "") !== String(nextOffer.id));
      nextItems.push(nextOffer);
      return nextItems;
    });
  }

  function removeOfferFromState(offerId) {
    setOffers((current) => {
      const nextItems = current.filter((item) => String(item?.id || "") !== String(offerId || ""));
      return nextItems;
    });
    if (String(effectiveSelectedSupplierOfferId || "") === String(offerId || "")) {
      setEffectiveSelectedSupplierOfferId("");
    }
  }

  async function handleOfferSubmit(event) {
    event.preventDefault();

    if (!token || !article) {
      return;
    }

    const normalizedSupplierId = String(offerModalForm.supplier_id || "").trim();
    const normalizedArticle = normalizeText(offerModalForm.article);
    const normalizedSourceUrl = normalizeText(offerModalForm.source_url);

    setOfferModalError("");
    setOfferModalErrorDetails("");

    const isSourceAttachFlow = offerModalMode === "create" && offerCreateMode === "link";

    if (isSourceAttachFlow && !normalizedSourceUrl) {
      setOfferModalError(language === "en" ? "Source URL is required" : "Потрібно вказати посилання на товар");
      return;
    }

    setOfferModalSaving(true);
    setSupplierError("");

    try {
      const result = isSourceAttachFlow
        ? await attachMaterialSupplierOfferFromSource(token, article, normalizedSourceUrl)
        : await (async () => {
            if (!normalizedSupplierId || !Number.isFinite(Number(normalizedSupplierId))) {
              setOfferModalError(language === "en" ? "Supplier is required" : "Потрібно вибрати постачальника");
              return null;
            }

            if (!normalizedArticle) {
              setOfferModalError(language === "en" ? "Supplier article is required" : "Потрібно вказати артикул постачальника");
              return null;
            }

            const normalizedPriceText = normalizeText(offerModalForm.price);
            const normalizedCurrency = normalizeText(offerModalForm.currency);
            const normalizedUnit = normalizeText(offerModalForm.unit);
            const normalizedStock = normalizeText(offerModalForm.stock);
            const normalizedCity = normalizeText(offerModalForm.city);
            const normalizedRegion = normalizeText(offerModalForm.region);

            const priceValue = normalizedPriceText === "" ? null : Number(normalizedPriceText);
            if (normalizedPriceText !== "" && (!Number.isFinite(priceValue) || priceValue < 0)) {
              setOfferModalError(language === "en" ? "Price must be non-negative" : "Ціна має бути додатною");
              return null;
            }

            const payload = {
              supplier_id: Number(normalizedSupplierId),
              article: normalizedArticle,
              price: priceValue,
              currency: normalizedCurrency || null,
              unit: normalizedUnit || null,
              stock: normalizedStock || null,
              city: normalizedCity || null,
              region: normalizedRegion || null,
              is_active: Boolean(offerModalForm.is_active),
            };

            return offerModalMode === "edit" && offerModalItem?.id
              ? updateMaterialSupplierOffer(token, offerModalItem.id, payload)
              : createMaterialSupplierOffer(token, article, payload);
          })();

      if (!result) {
        return;
      }

      if (!result?.success) {
        setOfferModalError(language === "en" ? "Unable to save offer" : "Не вдалося зберегти пропозицію");
        setOfferModalErrorDetails(result?.error || "");
        return;
      }

      if (result.item) {
        applyOfferPatch(result.item);
        setEffectiveSelectedSupplierOfferId(String(result.item.id));
      }

      closeOfferModal(true);
      await refreshMaterialDetail();
    } catch (error) {
      setOfferModalError(language === "en" ? "Unable to save offer" : "Не вдалося зберегти пропозицію");
      setOfferModalErrorDetails(error?.message || "");
    } finally {
      setOfferModalSaving(false);
    }
  }

  async function toggleOfferActive(item) {
    if (!token || !item?.id || busyOfferId) {
      return;
    }

    setBusyOfferId(String(item.id));
    setOfferActionError("");

    try {
      const result = await updateMaterialSupplierOffer(token, item.id, {
        is_active: !Boolean(item.is_active),
      });

      if (!result?.success) {
        setOfferActionError(result?.error || (language === "en" ? "Unable to update offer" : "Не вдалося оновити пропозицію"));
        return;
      }

      if (result.item) {
        applyOfferPatch(result.item);
      }

      await refreshMaterialDetail();
    } catch (error) {
      setOfferActionError(error?.message || (language === "en" ? "Unable to update offer" : "Не вдалося оновити пропозицію"));
    } finally {
      setBusyOfferId("");
    }
  }

  function openDeleteConfirm(item) {
    if (!item) {
      return;
    }

    setOfferActionError("");
    setDeleteOfferItem(item);
  }

  selectedOfferActionHandlersRef.current = {
    onEdit: selectedOffer ? () => openOfferModal(selectedOffer) : null,
    onToggleActive: selectedOffer ? () => toggleOfferActive(selectedOffer) : null,
    onDelete: selectedOffer ? () => openDeleteConfirm(selectedOffer) : null,
  };

  useEffect(() => {
    if (typeof onSelectedOfferActionsChange !== "function") {
      return undefined;
    }

    if (!selectedOffer) {
      onSelectedOfferActionsChange(null);
      return undefined;
    }

    onSelectedOfferActionsChange({
      offerId: String(selectedOffer.id || ""),
      canEdit: canCreateOffer,
      busy: Boolean(busyOfferId),
      error: offerActionError || "",
      onEdit: selectedOfferActionHandlersRef.current.onEdit,
      onToggleActive: selectedOfferActionHandlersRef.current.onToggleActive,
      onDelete: selectedOfferActionHandlersRef.current.onDelete,
    });
  }, [busyOfferId, canCreateOffer, offerActionError, onSelectedOfferActionsChange, selectedOffer]);

  function closeDeleteConfirm() {
    setDeleteOfferItem(null);
  }

  async function performDelete(item) {
    if (!token || !item?.id) {
      return;
    }

    const result = await deleteMaterialSupplierOffer(token, item.id);
    if (!result?.success) {
      throw new Error(result?.error || (language === "en" ? "Unable to delete offer" : "Не вдалося видалити пропозицію"));
    }

    removeOfferFromState(item.id);
    await refreshMaterialDetail();
  }

  const emptyStateLabel = language === "en"
    ? "No supplier offers yet."
    : "Пропозицій постачальників поки немає.";
  const errorStateLabel = language === "en"
    ? "Unable to load supplier offers."
    : "Не вдалося завантажити пропозиції постачальників.";
  const addOfferLabel = language === "en" ? "Add offer" : "Додати пропозицію";
  const tabsLabel = language === "en" ? "Supplier tabs" : "Вкладки постачальників";
  const normalizedStatus = hasVisibleOffers && shouldShowSupplierLoadingState(status) ? "loaded" : status;
  const showLoadingState = shouldShowSupplierLoadingState(normalizedStatus) && !hasVisibleOffers;
  const showTabs = shouldShowSupplierTabs(normalizedStatus, visibleOffers) || (shouldShowSupplierLoadingState(normalizedStatus) && hasVisibleOffers);
  const showEmptyState = shouldShowSupplierEmptyState(normalizedStatus, visibleOffers);
  const showErrorState = shouldShowSupplierErrorState(normalizedStatus);

  return (
    <>
      <div className="material-supplier-offers-topbar">
        {offerActionError ? <p className="status-message error">{offerActionError}</p> : null}
        {showLoadingState ? (
          <div className="material-supplier-offers-empty material-supplier-offers-empty-top">
            <p className="fitting-details-empty fitting-details-empty-compact">
              {language === "en" ? "Loading supplier offers..." : "Завантаження пропозицій постачальників..."}
            </p>
          </div>
        ) : showTabs ? (
          <div className="material-supplier-offers-tabs" role="tablist" aria-label={tabsLabel}>
            {visibleOffers.map((offer) => {
              const isSelected = String(selectedOffer?.id || "") === String(offer.id || "");
              const supplierName = offer.supplier_name || `Supplier ${offer.supplier_id}`;

              return (
                <button
                  aria-selected={isSelected}
                  aria-label={supplierName}
                  className={`material-supplier-offer-tab material-supplier-offer-tab-logo${isSelected ? " is-active" : ""}`}
                  key={offer.id}
                  onClick={() => setEffectiveSelectedSupplierOfferId(String(offer.id))}
                  role="tab"
                  type="button"
                >
                  <MaterialSupplierLogo
                    logoUrl={offer.supplier_logo_url}
                    name={supplierName}
                  />
                </button>
              );
            })}
            {canCreateOffer ? (
              <button
                aria-label={addOfferLabel}
                className="material-supplier-offer-tab material-supplier-offer-tab-add"
                onClick={() => openOfferModal()}
                type="button"
              >
                <Plus size={14} />
              </button>
            ) : null}
          </div>
        ) : showEmptyState ? (
          <div className="material-supplier-offers-empty material-supplier-offers-empty-top">
            {canCreateOffer ? (
              <button
                className="primary-button compact-button"
                onClick={() => openOfferModal()}
                type="button"
              >
                <Plus size={14} />
                {language === "en" ? "Add supplier offer" : "Додати постачальника"}
              </button>
            ) : (
              <p className="fitting-details-empty fitting-details-empty-compact">{emptyStateLabel}</p>
            )}
          </div>
        ) : showErrorState ? (
          <div className="material-supplier-offers-empty material-supplier-offers-empty-top">
            <p className="fitting-details-empty fitting-details-empty-compact">{errorStateLabel}</p>
          </div>
        ) : (
          <div className="material-supplier-offers-empty material-supplier-offers-empty-top">
            <p className="fitting-details-empty fitting-details-empty-compact">
              {language === "en" ? "Loading supplier offers..." : "Завантаження пропозицій постачальників..."}
            </p>
          </div>
        )}
      </div>

      {offerModalOpen ? (
        <div aria-modal="true" className="modal-backdrop" onClick={closeOfferModal} role="dialog">
          <section
            className="confirm-modal material-details-modal material-supplier-offer-modal"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="confirm-header">
              <div>
                <strong>
                  {offerModalMode === "edit"
                    ? (language === "en" ? "Edit supplier offer" : "Редагувати пропозицію")
                    : (language === "en" ? "Add supplier offer" : "Додати пропозицію")}
                </strong>
                <p>{materialDetail?.name || materialDetail?.article || (language === "en" ? "Material" : "Матеріал")}</p>
              </div>
              <button
                aria-label={language === "en" ? "Close" : "Закрити"}
                className="ghost-button compact-button detail-info-button"
                disabled={offerModalSaving}
                onClick={closeOfferModal}
                type="button"
              >
                <X size={16} />
              </button>
            </header>

            <form className="hole-template-form material-supplier-offer-form" onSubmit={handleOfferSubmit}>
              {offerModalError ? <p className="status-message error">{offerModalError}</p> : null}
              {offerModalErrorDetails ? <p className="material-supplier-offer-form-note">{offerModalErrorDetails}</p> : null}
              <div className="fitting-source-mode-switch" role="tablist" aria-label={language === "en" ? "Offer mode" : "Режим пропозиції"}>
                <button
                  aria-pressed={offerCreateMode === "link"}
                  className={`ghost-button compact-button${offerCreateMode === "link" ? " active" : ""}`}
                  disabled={offerModalSaving}
                  onClick={() => setOfferCreateMode("link")}
                  type="button"
                >
                  {language === "en" ? "By link" : "За посиланням"}
                </button>
                <button
                  aria-pressed={offerCreateMode === "manual"}
                  className={`ghost-button compact-button${offerCreateMode === "manual" ? " active" : ""}`}
                  disabled={offerModalSaving}
                  onClick={() => setOfferCreateMode("manual")}
                  type="button"
                >
                  {language === "en" ? "Manual" : "Вручну"}
                </button>
              </div>
              {offerModalMode === "create" && offerCreateMode === "link" ? (
                <div className="material-supplier-offer-link-flow">
                  <p className="material-supplier-offer-form-note">
                    {language === "en"
                      ? "Supplier and product data will be detected automatically."
                      : "Постачальник і дані товару будуть визначені автоматично."}
                  </p>
                  <label className="material-supplier-offer-link-input">
                    {language === "en" ? "Source URL" : "Посилання на товар"}
                    <input
                      autoComplete="off"
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("source_url", event.target.value)}
                      placeholder="https://..."
                      type="url"
                      value={offerModalForm.source_url}
                    />
                  </label>
                </div>
              ) : (
                <div className="hole-template-form-grid material-supplier-offer-form-grid">
                  <label>
                    {language === "en" ? "Supplier" : "Постачальник"}
                    <select
                      disabled={offerModalSaving || supplierLoading}
                      onChange={(event) => updateOfferForm("supplier_id", event.target.value)}
                      value={offerModalForm.supplier_id}
                    >
                      <option value="">{language === "en" ? "Select supplier" : "Оберіть постачальника"}</option>
                      {visibleSupplierItems.map((supplier) => (
                        <option key={supplier.id} value={supplier.id}>
                          {supplier.name}
                          {supplier.is_active ? "" : (language === "en" ? " (inactive)" : " (неактивний)")}
                        </option>
                      ))}
                    </select>
                    {selectedSupplier ? (
                      <div className="material-supplier-offer-selected-supplier">
                        <MaterialSupplierLogo
                          logoUrl={selectedSupplier.logo_url}
                          name={selectedSupplier.name}
                        />
                      </div>
                    ) : null}
                    {supplierError ? <span className="material-supplier-offer-form-note">{supplierError}</span> : null}
                  </label>
                  <label>
                    {language === "en" ? "Supplier article" : "Артикул постачальника"}
                    <input
                      autoComplete="off"
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("article", event.target.value)}
                      type="text"
                      value={offerModalForm.article}
                    />
                  </label>
                  <label>
                    {language === "en" ? "Price" : "Ціна"}
                    <input
                      disabled={offerModalSaving}
                      min="0"
                      onChange={(event) => updateOfferForm("price", event.target.value)}
                      step="0.01"
                      type="number"
                      value={offerModalForm.price}
                    />
                  </label>
                  <label>
                    {language === "en" ? "Currency" : "Валюта"}
                    <input
                      autoComplete="off"
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("currency", event.target.value)}
                      type="text"
                      value={offerModalForm.currency}
                    />
                  </label>
                  <label>
                    {language === "en" ? "Unit" : "Одиниця"}
                    <input
                      autoComplete="off"
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("unit", event.target.value)}
                      type="text"
                      value={offerModalForm.unit}
                    />
                  </label>
                  <label>
                    {language === "en" ? "Availability" : "Наявність"}
                    <input
                      autoComplete="off"
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("stock", event.target.value)}
                      type="text"
                      value={offerModalForm.stock}
                    />
                  </label>
                  <label>
                    {language === "en" ? "City" : "Місто"}
                    <input
                      autoComplete="off"
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("city", event.target.value)}
                      type="text"
                      value={offerModalForm.city}
                    />
                  </label>
                  <label>
                    {language === "en" ? "Region" : "Регіон"}
                    <input
                      autoComplete="off"
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("region", event.target.value)}
                      type="text"
                      value={offerModalForm.region}
                    />
                  </label>
                  <label className="toggle-label material-supplier-offer-active-toggle">
                    <input
                      checked={Boolean(offerModalForm.is_active)}
                      disabled={offerModalSaving}
                      onChange={(event) => updateOfferForm("is_active", event.target.checked)}
                      type="checkbox"
                    />
                    {language === "en" ? "Active" : "Активний"}
                  </label>
                </div>
              )}

              <div className="confirm-actions">
                <button className="ghost-button" disabled={offerModalSaving} onClick={closeOfferModal} type="button">
                  {language === "en" ? "Cancel" : "Скасувати"}
                </button>
                <button className="primary-button" disabled={offerModalSaving || supplierLoading} type="submit">
                  <Save size={16} />
                  {offerModalSaving
                    ? (language === "en" ? "Saving..." : "Збереження...")
                    : (language === "en" ? "Save" : "Зберегти")}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      <DeleteConfirmModal
        cancelLabel={language === "en" ? "Cancel" : "Скасувати"}
        confirmLabel={language === "en" ? "Delete" : "Видалити"}
        loadingLabel={language === "en" ? "Deleting..." : "Видалення..."}
        message={
          deleteOfferItem
            ? `${language === "en" ? "Delete supplier offer" : "Видалити пропозицію"} «${deleteOfferItem.supplier_name || deleteOfferItem.article || deleteOfferItem.id}»?`
            : ""
        }
        open={Boolean(deleteOfferItem)}
        title={language === "en" ? "Delete supplier offer" : "Видалити пропозицію"}
        onCancel={closeDeleteConfirm}
        onConfirm={deleteOfferItem ? () => performDelete(deleteOfferItem) : undefined}
      />
    </>
  );
}
