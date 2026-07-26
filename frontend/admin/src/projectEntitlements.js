export function hasUserEntitlement(user, featureKey) {
  return user?.entitlements?.[featureKey]?.allowed === true;
}

export function normalizeOwnerId(value) {
  return String(value ?? "").trim();
}

export function getProjectEntitlementFlags(user) {
  return {
    view: hasUserEntitlement(user, "projects.view"),
    create: hasUserEntitlement(user, "projects.create"),
    edit: hasUserEntitlement(user, "projects.edit"),
    delete: hasUserEntitlement(user, "projects.delete"),
  };
}

export function canViewProjects(user) {
  return user?.role === "admin" || getProjectEntitlementFlags(user).view;
}

export function canCreateProjects(user) {
  return user?.role === "admin" || getProjectEntitlementFlags(user).create;
}

export function canEditProjects(user, project) {
  if (!user || !project) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  if (!getProjectEntitlementFlags(user).edit) {
    return false;
  }

  return String(project.created_by_user_id || "") === String(user.id || "");
}

export function canDeleteProjects(user, project) {
  if (!user || !project) {
    return false;
  }

  if (user.role === "admin") {
    return true;
  }

  if (!getProjectEntitlementFlags(user).delete) {
    return false;
  }

  return String(project.created_by_user_id || "") === String(user.id || "");
}

export function isOwnProject(user, project) {
  if (!user || !project) {
    return false;
  }

  return normalizeOwnerId(user.id) === normalizeOwnerId(project.created_by_user_id);
}

export function getProjectOwnershipScopeLabel(scope, language) {
  const labels = language === "en"
    ? {
        all: "All projects",
        mine: "My projects",
        unowned: "Without owner",
        users: "Users' projects",
      }
    : {
        all: "Усі проєкти",
        mine: "Мої проєкти",
        unowned: "Без власника",
        users: "Проєкти користувачів",
      };

  return labels[String(scope || "all")] || labels.all;
}

function shortenOwnerId(ownerId) {
  const normalized = normalizeOwnerId(ownerId);
  if (!normalized) {
    return "";
  }

  if (normalized.length <= 12) {
    return normalized;
  }

  return `${normalized.slice(0, 8)}…${normalized.slice(-4)}`;
}

export function getProjectOwnerDisplayName(owner, language) {
  const primary = String(
    owner?.display_name ||
      owner?.name ||
      owner?.login ||
      owner?.username ||
      owner?.email ||
      "",
  ).trim();

  if (primary) {
    return primary;
  }

  const ownerId = shortenOwnerId(owner?.id);
  if (ownerId) {
    return ownerId;
  }

  return language === "en" ? "Unknown owner" : "Невідомий власник";
}

export function getProjectOwnerLabel(project, usersById, currentUser, language) {
  const ownerId = normalizeOwnerId(project?.created_by_user_id);

  if (!ownerId) {
    return language === "en" ? "No owner" : "Без власника";
  }

  const owner = typeof usersById?.get === "function" ? usersById.get(ownerId) : null;
  const currentOwner = ownerId === normalizeOwnerId(currentUser?.id) ? currentUser : null;
  const ownerDisplay = getProjectOwnerDisplayName(owner || currentOwner || { id: ownerId }, language);

  if (ownerId === normalizeOwnerId(currentUser?.id)) {
    return language === "en" ? `${ownerDisplay} (you)` : `${ownerDisplay} (ви)`;
  }

  return ownerDisplay;
}

export function filterProjectsByOwnershipScope(projects, scope, currentUser) {
  if (!Array.isArray(projects)) {
    return [];
  }

  const ownerId = normalizeOwnerId(currentUser?.id);
  const normalizedScope = String(scope || "all");

  if (normalizedScope === "mine") {
    return projects.filter((project) => normalizeOwnerId(project?.created_by_user_id) === ownerId);
  }

  if (normalizedScope === "unowned") {
    return projects.filter((project) => !normalizeOwnerId(project?.created_by_user_id));
  }

  if (normalizedScope === "users") {
    return projects.filter((project) => {
      const projectOwnerId = normalizeOwnerId(project?.created_by_user_id);
      return Boolean(projectOwnerId) && projectOwnerId !== ownerId;
    });
  }

  return [...projects];
}

export function isProjectCreationBlockedByQuota(projectOwnershipQuota) {
  return Boolean(projectOwnershipQuota && projectOwnershipQuota.can_create === false);
}

export function getProjectOwnershipQuotaLabel(projectOwnershipQuota, language) {
  if (!projectOwnershipQuota) {
    return "";
  }

  const usage = Number(projectOwnershipQuota.usage || 0);
  const limit = Number(projectOwnershipQuota.limit || 0);

  if (projectOwnershipQuota.is_unlimited) {
    return language === "en"
      ? `Own projects: ${usage} · unlimited`
      : `Власні проєкти: ${usage} · без обмежень`;
  }

  return language === "en"
    ? `Own projects: ${usage} · ${limit}`
    : `Власні проєкти: ${usage} · ${limit}`;
}
