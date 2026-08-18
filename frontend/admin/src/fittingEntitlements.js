export function hasUserEntitlement(user, featureKey) {
  return user?.entitlements?.[featureKey]?.allowed === true;
}

export const DEFAULT_FITTING_FORM = {
  article: "",
  brand: "",
  city: "",
  code: "",
  fitting_group: "fittings",
  fitting_type: "drawer_slides",
  image_url: "",
  image_urls: [],
  is_active: true,
  is_system: false,
  name: "",
  price: "",
  sort_order: 0,
  stock: "",
  source_url: "",
  supplier_offer: {
    offer_id: null,
    supplier_id: "",
    article: "",
    external_product_id: "",
    source_url: "",
    price: "",
    currency: "UAH",
    unit: "",
    stock: "",
    is_active: true,
    priority: 100,
  },
};

function normalizeFittingAvailabilityDraftValue(value) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();

  if (!text) {
    return "";
  }

  const normalized = text.toLowerCase();

  if (
    value === true ||
    value === 1 ||
    normalized === "наявність" ||
    normalized === "в наявності" ||
    normalized === "in stock" ||
    normalized === "true" ||
    normalized === "1" ||
    normalized === "yes"
  ) {
    return "in stock";
  }

  if (
    value === false ||
    value === 0 ||
    normalized === "немає в наявності" ||
    normalized === "нема в наявності" ||
    normalized === "out of stock" ||
    normalized === "false" ||
    normalized === "0" ||
    normalized === "no"
  ) {
    return "out of stock";
  }

  return text;
}

function normalizeFittingAvailabilityPayloadValue(value) {
  const normalized = normalizeFittingAvailabilityDraftValue(value);
  if (normalized === "in stock" || normalized === "out of stock") {
    return normalized;
  }

  return null;
}

export function getFittingAvailabilityCheckedValue(value) {
  return normalizeFittingAvailabilityDraftValue(value) === "in stock";
}

export function getFittingEntitlementFlags(user) {
  return {
    view: hasUserEntitlement(user, "fittings.view"),
    create: hasUserEntitlement(user, "fittings.create"),
    edit: hasUserEntitlement(user, "fittings.edit"),
    delete: hasUserEntitlement(user, "fittings.delete"),
  };
}

export function canViewFittings(user) {
  return user?.role === "admin" || getFittingEntitlementFlags(user).view;
}

export function canCreateFittings(user) {
  return user?.role === "admin" || getFittingEntitlementFlags(user).create;
}

export function canManageSystemFittings(user) {
  return user?.role === "admin";
}

export function canEditFittingItem(user, item) {
  if (!user || !item) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  if (!canEditFittings(user)) {
    return false;
  }

  if (item.is_system) {
    return false;
  }

  return String(item.owner_user_id || "") === String(user.id || "");
}

export function canDeleteFittingItem(user, item) {
  if (!user || !item) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  if (!canDeleteFittings(user)) {
    return false;
  }

  if (item.is_system) {
    return false;
  }

  return String(item.owner_user_id || "") === String(user.id || "");
}

export function canEditFittings(user) {
  return getFittingEntitlementFlags(user).edit;
}

export function canDeleteFittings(user) {
  return getFittingEntitlementFlags(user).delete;
}

export function canUseFittingHoles(user) {
  if (user?.role === "admin") {
    return true;
  }

  return hasUserEntitlement(user, "fitting_holes.use");
}

export function getFittingOwnershipScopeLabel(scope, language) {
  const labels = language === "en"
    ? {
        system: "System",
        mine: "My private",
        users: "Users' private",
        all: "All",
      }
    : {
        system: "Системні",
        mine: "Мої приватні",
        users: "Користувацькі",
        all: "Всі",
      };

  return labels[String(scope || "all")] || labels.all;
}

export function getFittingOwnershipTypeLabel(item, currentUser, language) {
  if (item?.is_system && !item?.owner_user_id) {
    return language === "en" ? "System" : "Системна";
  }

  if (item?.owner_user_id && String(item.owner_user_id) === String(currentUser?.id || "")) {
    return language === "en" ? "My private" : "Моя приватна";
  }

  if (item?.owner_user_id) {
    return language === "en" ? "Users' private" : "Користувацька";
  }

  return language === "en" ? "Invalid" : "Некоректна";
}

export function getFittingOwnerDisplayName(item, language) {
  const primary = String(item?.owner_display_name || item?.owner_login || item?.owner_email || "").trim();
  if (primary) {
    return primary;
  }

  return language === "en" ? "Unknown owner" : "Невідомий власник";
}

export function getFittingOwnerDisplay(item, currentUser, language) {
  if (!item || currentUser?.role !== "admin") {
    return null;
  }

  if (!item.owner_user_id || item.is_system) {
    return null;
  }

  const ownerText = String(
    item.owner_display_name ||
      item.owner_login ||
      item.owner_email ||
      item.owner_user_id ||
      "",
  ).trim();

  if (!ownerText) {
    return null;
  }

  return language === "en" ? `Owner: ${ownerText}` : `Власник: ${ownerText}`;
}

export function createFittingFormDraft(item = null, options = {}) {
  const primaryOffer = Array.isArray(item?.supplier_offers) && item.supplier_offers.length
    ? item.supplier_offers[0]
    : null;
  const base = {
    ...DEFAULT_FITTING_FORM,
    fitting_group: String(options.fitting_group || item?.fitting_group || DEFAULT_FITTING_FORM.fitting_group),
    fitting_type: String(options.fitting_type || item?.fitting_type || DEFAULT_FITTING_FORM.fitting_type),
    city: String(options.city || item?.city || ""),
  };

  if (!item) {
    return base;
  }

  return {
    ...base,
    article: String(item?.article || ""),
    brand: String(item?.brand || ""),
    code: String(item?.code || ""),
    image_url: String(item?.image_url || ""),
    image_urls: Array.isArray(item?.image_urls)
      ? item.image_urls.map((url) => String(url || "").trim()).filter(Boolean)
      : [],
    is_active: item?.is_active !== false,
    is_system: Boolean(item?.is_system),
    name: String(item?.name || ""),
    price: item?.price === null || item?.price === undefined ? "" : String(item.price),
    sort_order: Number(item?.sort_order || 0),
    stock: normalizeFittingAvailabilityDraftValue(item?.stock),
    source_url: String(item?.source_url || ""),
    supplier_offer: {
      ...DEFAULT_FITTING_FORM.supplier_offer,
      offer_id: primaryOffer?.id ?? null,
      supplier_id: primaryOffer?.supplier_id ?? "",
      article: String(primaryOffer?.article || ""),
      external_product_id: String(primaryOffer?.external_product_id || ""),
      source_url: String(primaryOffer?.source_url || ""),
      price: primaryOffer?.price === null || primaryOffer?.price === undefined ? "" : String(primaryOffer.price),
      currency: String(primaryOffer?.currency || DEFAULT_FITTING_FORM.supplier_offer.currency),
      unit: String(primaryOffer?.unit || ""),
      stock: normalizeFittingAvailabilityDraftValue(primaryOffer?.stock),
      is_active: primaryOffer?.is_active !== false,
      priority: Number(primaryOffer?.priority || DEFAULT_FITTING_FORM.supplier_offer.priority),
    },
  };
}

export function buildFittingSubmissionPayload(form, options = {}) {
  const mode = options.mode === "edit" ? "edit" : "create";
  const canEditSystemFittings = Boolean(options.canEditSystemFittings);
  const currentItem = options.currentItem || null;
  const normalizedArticle = String(form?.article || "").trim();
  const normalizedBrand = String(form?.brand || "").trim();
  const normalizedCity = String(form?.city || "").trim();
  const normalizedCode = String(form?.code || "").trim();
  const normalizedImageUrl = String(form?.image_url || "").trim();
  const normalizedImageUrls = Array.isArray(form?.image_urls)
    ? form.image_urls.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  const normalizedName = String(form?.name || "").trim();
  const normalizedSourceUrl = String(form?.source_url || "").trim();
  const normalizedStock = normalizeFittingAvailabilityPayloadValue(form?.stock);
  const supplierOffer = form?.supplier_offer || null;
  const normalizedSupplierId = String(supplierOffer?.supplier_id || "").trim();
  const normalizedSupplierArticle = String(supplierOffer?.article || "").trim();
  const normalizedSupplierExternalProductId = String(supplierOffer?.external_product_id || "").trim();
  const normalizedSupplierSourceUrl = String(supplierOffer?.source_url || "").trim();
  const normalizedSupplierCurrency = String(supplierOffer?.currency || "").trim();
  const normalizedSupplierUnit = String(supplierOffer?.unit || "").trim();
  const normalizedSupplierStock = normalizeFittingAvailabilityPayloadValue(supplierOffer?.stock);
  const inferredSourceUrl = normalizedSourceUrl || (looksLikeUrl(normalizedName) ? normalizedName : "");
  const inferredName = looksLikeUrl(normalizedName) && inferredSourceUrl === normalizedName ? "" : normalizedName;
  const fallbackSystemName = String(options.fallbackSystemName || "").trim();
  const allowSystemToggle = Boolean(options.allowSystemToggle);
  const currentIsSystem = Boolean(currentItem?.is_system);
  const isSystemFitting = mode === "edit"
    ? currentIsSystem
    : allowSystemToggle && canEditSystemFittings && Boolean(form?.is_system);

  const payload = {
    article: normalizedArticle || null,
    brand: normalizedBrand || null,
    city: normalizedCity || null,
    code: mode === "edit" ? normalizedCode || null : null,
    fitting_group: String(form?.fitting_group || DEFAULT_FITTING_FORM.fitting_group),
    fitting_type: String(form?.fitting_type || DEFAULT_FITTING_FORM.fitting_type),
    image_url: normalizedImageUrls[0] || normalizedImageUrl || null,
    image_urls: normalizedImageUrls.length ? normalizedImageUrls : (normalizedImageUrl ? [normalizedImageUrl] : null),
    source_url: inferredSourceUrl || null,
    is_active: Boolean(form?.is_active),
    name: inferredName || normalizedArticle || inferredSourceUrl || (isSystemFitting ? fallbackSystemName : ""),
    price:
      form?.price === "" || form?.price === null || form?.price === undefined
        ? null
        : Number(String(form.price).replace(",", ".")),
    sort_order: Number(form?.sort_order || 0),
    stock: normalizedStock || null,
  };

  const normalizedSupplierOffer = normalizedSupplierId
    ? {
        offer_id:
          supplierOffer?.offer_id === "" || supplierOffer?.offer_id === null || supplierOffer?.offer_id === undefined
            ? null
            : Number(supplierOffer.offer_id),
        supplier_id: Number(normalizedSupplierId),
        article: normalizedSupplierArticle || null,
        external_product_id: normalizedSupplierExternalProductId || null,
        source_url: normalizedSupplierSourceUrl || null,
        price:
          supplierOffer?.price === "" || supplierOffer?.price === null || supplierOffer?.price === undefined
            ? null
            : Number(String(supplierOffer.price).replace(",", ".")),
        currency: normalizedSupplierCurrency || null,
        unit: normalizedSupplierUnit || null,
        stock: normalizedSupplierStock || null,
        is_active: supplierOffer?.is_active !== false,
        priority: Number(supplierOffer?.priority || 0),
      }
    : null;

  if (mode === "create" && canEditSystemFittings) {
    payload.is_system = Boolean(form?.is_system);
  }

  const hasMeaningfulSupplierOffer = Boolean(
    normalizedSupplierOffer &&
      (
        normalizedSupplierOffer.offer_id !== null ||
        normalizedSupplierOffer.article ||
        normalizedSupplierOffer.external_product_id ||
        normalizedSupplierOffer.source_url ||
        normalizedSupplierOffer.price !== null ||
        normalizedSupplierOffer.currency ||
        normalizedSupplierOffer.unit ||
        normalizedSupplierOffer.stock ||
        normalizedSupplierOffer.is_active === false ||
        normalizedSupplierOffer.priority !== 100
      ),
  );

  payload.supplier_offer = hasMeaningfulSupplierOffer ? normalizedSupplierOffer : null;

  return {
    is_system: isSystemFitting,
    payload,
  };
}

function looksLikeUrl(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return false;
  }

  return /^(https?:\/\/|www\.)/i.test(normalized) || normalized.includes(".");
}
