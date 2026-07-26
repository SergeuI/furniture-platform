import assert from "node:assert/strict";
import test from "node:test";

import {
  canCreateProjects,
  canDeleteProjects,
  canEditProjects,
  canViewProjects,
  filterProjectsByOwnershipScope,
  getProjectOwnerLabel,
  getProjectOwnershipScopeLabel,
  getProjectEntitlementFlags,
  getProjectOwnershipQuotaLabel,
  hasUserEntitlement,
  normalizeOwnerId,
  isProjectCreationBlockedByQuota,
} from "../src/projectEntitlements.js";

test("project entitlement helper reads runtime snapshot only", () => {
  const user = {
    role: "admin",
    entitlements: {
      "projects.view": { allowed: true },
      "projects.create": { allowed: true },
      "projects.edit": { allowed: true },
      "projects.delete": { allowed: true },
    },
  };

  assert.equal(hasUserEntitlement(user, "projects.view"), true);
  assert.equal(hasUserEntitlement(user, "projects.create"), true);
  assert.equal(hasUserEntitlement(user, "projects.edit"), true);
  assert.equal(hasUserEntitlement(user, "projects.delete"), true);
  assert.equal(hasUserEntitlement({ role: "admin", entitlements: {} }, "projects.view"), false);
  assert.equal(hasUserEntitlement({ role: "pro" }, "projects.view"), false);
});

test("project entitlement flags stay separated by feature key", () => {
  const flags = getProjectEntitlementFlags({
    entitlements: {
      "projects.view": { allowed: true },
      "projects.create": { allowed: false },
      "projects.edit": { allowed: true },
      "projects.delete": { allowed: false },
    },
  });

  assert.deepEqual(flags, {
    view: true,
    create: false,
    edit: true,
    delete: false,
  });
});

test("admin bypass keeps project access available even when entitlements are false", () => {
  const admin = {
    role: "admin",
    id: 1,
    entitlements: {
      "projects.view": { allowed: false },
      "projects.create": { allowed: false },
      "projects.edit": { allowed: false },
      "projects.delete": { allowed: false },
    },
  };

  assert.equal(canViewProjects(admin), true);
  assert.equal(canCreateProjects(admin), true);
  assert.equal(canEditProjects(admin, { created_by_user_id: null }), true);
  assert.equal(canDeleteProjects(admin, { created_by_user_id: null }), true);
});

test("project ownership governs edit and delete for non-admins", () => {
  const user = {
    id: 10,
    role: "pro",
    entitlements: {
      "projects.view": { allowed: true },
      "projects.create": { allowed: true },
      "projects.edit": { allowed: true },
      "projects.delete": { allowed: true },
    },
  };

  assert.equal(canViewProjects(user), true);
  assert.equal(canCreateProjects(user), true);
  assert.equal(canEditProjects(user, { created_by_user_id: 10 }), true);
  assert.equal(canDeleteProjects(user, { created_by_user_id: 10 }), true);
  assert.equal(canEditProjects(user, { created_by_user_id: 11 }), false);
  assert.equal(canDeleteProjects(user, { created_by_user_id: 11 }), false);
  assert.equal(canEditProjects(user, { created_by_user_id: null }), false);
  assert.equal(canDeleteProjects(user, { created_by_user_id: null }), false);
  assert.equal(canViewProjects({ role: "pro" }), false);
  assert.equal(canCreateProjects({ role: "premium" }), false);
});

test("project ownership helpers label owners and scopes", () => {
  const usersById = new Map([
    ["10", { id: 10, display_name: "admin" }],
    ["11", { id: "11", email: "user@example.com" }],
  ]);
  const projects = [
    { id: "p1", created_by_user_id: 10 },
    { id: "p2", created_by_user_id: "11" },
    { id: "p3", created_by_user_id: null },
    { id: "p4", created_by_user_id: "1234567890abcdef" },
  ];
  const currentUser = { id: "10" };

  assert.equal(normalizeOwnerId(10), "10");
  assert.equal(getProjectOwnershipScopeLabel("all", "uk"), "Усі проєкти");
  assert.equal(getProjectOwnershipScopeLabel("mine", "uk"), "Мої проєкти");
  assert.equal(getProjectOwnershipScopeLabel("unowned", "uk"), "Без власника");
  assert.equal(getProjectOwnershipScopeLabel("users", "uk"), "Проєкти користувачів");
  assert.equal(getProjectOwnerLabel(projects[0], usersById, currentUser, "uk"), "admin (ви)");
  assert.equal(getProjectOwnerLabel(projects[1], usersById, currentUser, "uk"), "user@example.com");
  assert.equal(getProjectOwnerLabel(projects[2], usersById, currentUser, "uk"), "Без власника");
  assert.equal(
    getProjectOwnerLabel(projects[0], new Map(), { id: "10", email: "admin@example.com" }, "uk"),
    "admin@example.com (ви)",
  );
  assert.equal(getProjectOwnerLabel(projects[3], new Map(), currentUser, "en"), "12345678…cdef");

  assert.deepEqual(filterProjectsByOwnershipScope(projects, "all", currentUser).map((item) => item.id), [
    "p1",
    "p2",
    "p3",
    "p4",
  ]);
  assert.deepEqual(filterProjectsByOwnershipScope(projects, "mine", currentUser).map((item) => item.id), ["p1"]);
  assert.deepEqual(filterProjectsByOwnershipScope(projects, "unowned", currentUser).map((item) => item.id), ["p3"]);
  assert.deepEqual(filterProjectsByOwnershipScope(projects, "users", currentUser).map((item) => item.id), [
    "p2",
    "p4",
  ]);
});

test("project creation quota label and blocker reflect current usage", () => {
  assert.equal(
    getProjectOwnershipQuotaLabel({ usage: 3, limit: 5, is_unlimited: false }, "uk"),
    "Власні проєкти: 3 · 5",
  );
  assert.equal(
    getProjectOwnershipQuotaLabel({ usage: 3, limit: 5, is_unlimited: false }, "en"),
    "Own projects: 3 · 5",
  );
  assert.equal(
    getProjectOwnershipQuotaLabel({ usage: 7, limit: 0, is_unlimited: true }, "uk"),
    "Власні проєкти: 7 · без обмежень",
  );
  assert.equal(
    isProjectCreationBlockedByQuota({ usage: 7, limit: 7, can_create: false }),
    true,
  );
  assert.equal(
    isProjectCreationBlockedByQuota({ usage: 7, limit: 7, can_create: true }),
    false,
  );
  assert.equal(
    isProjectCreationBlockedByQuota({ usage: 7, is_unlimited: true }),
    false,
  );
});
