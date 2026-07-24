export function hasUserEntitlement(user, featureKey) {
  return user?.entitlements?.[featureKey]?.allowed === true;
}

export function getMaterialEntitlementFlags(user) {
  return {
    view: hasUserEntitlement(user, "materials.view"),
    create: hasUserEntitlement(user, "materials.create"),
    edit: hasUserEntitlement(user, "materials.edit"),
    delete: hasUserEntitlement(user, "materials.delete"),
  };
}

export function isMaterialCreationBlockedByQuota(materialOwnershipQuota, isNewMaterialSubmission) {
  return Boolean(
    materialOwnershipQuota &&
      materialOwnershipQuota.can_create === false &&
      isNewMaterialSubmission,
  );
}
