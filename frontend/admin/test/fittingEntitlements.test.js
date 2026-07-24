import assert from "node:assert/strict";
import test from "node:test";

import {
  canCreateFittings,
  canDeleteFittingItem,
  canEditFittingItem,
  canManageSystemFittings,
  canViewFittings,
  getFittingEntitlementFlags,
  hasUserEntitlement,
} from "../src/fittingEntitlements.js";

test("fitting entitlement helper reads runtime snapshot only", () => {
  const user = {
    role: "admin",
    entitlements: {
      "fittings.view": { allowed: true },
      "fittings.create": { allowed: true },
      "fittings.edit": { allowed: true },
      "fittings.delete": { allowed: true },
    },
  };

  assert.equal(hasUserEntitlement(user, "fittings.view"), true);
  assert.equal(hasUserEntitlement(user, "fittings.create"), true);
  assert.equal(hasUserEntitlement(user, "fittings.edit"), true);
  assert.equal(hasUserEntitlement(user, "fittings.delete"), true);
  assert.equal(hasUserEntitlement({ role: "admin", entitlements: {} }, "fittings.view"), false);
  assert.equal(hasUserEntitlement({ role: "pro" }, "fittings.view"), false);
});

test("fitting entitlement flags stay separated by feature key", () => {
  const flags = getFittingEntitlementFlags({
    entitlements: {
      "fittings.view": { allowed: true },
      "fittings.create": { allowed: false },
      "fittings.edit": { allowed: true },
      "fittings.delete": { allowed: false },
    },
  });

  assert.deepEqual(flags, {
    view: true,
    create: false,
    edit: true,
    delete: false,
  });
});

test("view and create helpers depend only on their entitlement values", () => {
  assert.equal(
    canViewFittings({
      role: "admin",
      entitlements: { "fittings.view": { allowed: false } },
    }),
    false,
  );
  assert.equal(
    canCreateFittings({
      role: "admin",
      entitlements: { "fittings.create": { allowed: false } },
    }),
    false,
  );
});

test("admin system control still requires create entitlement", () => {
  assert.equal(
    canManageSystemFittings({
      role: "admin",
      entitlements: { "fittings.create": { allowed: true } },
    }),
    true,
  );
  assert.equal(
    canManageSystemFittings({
      role: "admin",
      entitlements: { "fittings.create": { allowed: false } },
    }),
    false,
  );
});

test("fitting item edit and delete checks respect ownership and system scope", () => {
  const user = {
    id: 10,
    role: "pro",
    entitlements: {
      "fittings.edit": { allowed: true },
      "fittings.delete": { allowed: true },
    },
  };

  assert.equal(canEditFittingItem(user, { owner_user_id: 10, is_system: false }), true);
  assert.equal(canDeleteFittingItem(user, { owner_user_id: 10, is_system: false }), true);
  assert.equal(canEditFittingItem(user, { owner_user_id: 11, is_system: false }), false);
  assert.equal(canDeleteFittingItem(user, { owner_user_id: 11, is_system: false }), false);
  assert.equal(canEditFittingItem(user, { owner_user_id: 10, is_system: true }), false);
  assert.equal(canDeleteFittingItem(user, { owner_user_id: 10, is_system: true }), false);
});

test("admin can manage system and foreign private fittings when entitlement is allowed", () => {
  const admin = {
    id: 1,
    role: "admin",
    entitlements: {
      "fittings.edit": { allowed: true },
      "fittings.delete": { allowed: true },
    },
  };

  assert.equal(canEditFittingItem(admin, { owner_user_id: 10, is_system: false }), true);
  assert.equal(canDeleteFittingItem(admin, { owner_user_id: 10, is_system: false }), true);
  assert.equal(canEditFittingItem(admin, { owner_user_id: 10, is_system: true }), true);
  assert.equal(canDeleteFittingItem(admin, { owner_user_id: 10, is_system: true }), true);
});

test("explicit false entitlement is never overridden by admin role", () => {
  const admin = {
    id: 1,
    role: "admin",
    entitlements: {
      "fittings.view": { allowed: false },
      "fittings.create": { allowed: false },
      "fittings.edit": { allowed: false },
      "fittings.delete": { allowed: false },
    },
  };

  assert.equal(canViewFittings(admin), false);
  assert.equal(canCreateFittings(admin), false);
  assert.equal(canManageSystemFittings(admin), false);
  assert.equal(canEditFittingItem(admin, { owner_user_id: 1, is_system: false }), false);
  assert.equal(canDeleteFittingItem(admin, { owner_user_id: 1, is_system: false }), false);
});
