export function hasUserEntitlement(user, featureKey) {
  return user?.entitlements?.[featureKey]?.allowed === true;
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
  return getFittingEntitlementFlags(user).view;
}

export function canCreateFittings(user) {
  return getFittingEntitlementFlags(user).create;
}

export function canManageSystemFittings(user) {
  return canCreateFittings(user) && user?.role === "admin";
}

export function canEditFittingItem(user, item) {
  if (!user || !item || !canEditFittings(user)) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  if (item.is_system) {
    return false;
  }

  return String(item.owner_user_id || "") === String(user.id || "");
}

export function canDeleteFittingItem(user, item) {
  if (!user || !item || !canDeleteFittings(user)) {
    return false;
  }

  if (user.role === "admin") {
    return true;
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
