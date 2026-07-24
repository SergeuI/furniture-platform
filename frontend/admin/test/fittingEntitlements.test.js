import assert from "node:assert/strict";
import test from "node:test";

import {
  buildFittingSubmissionPayload,
  canCreateFittings,
  canDeleteFittingItem,
  canEditFittingItem,
  canManageSystemFittings,
  canViewFittings,
  createFittingFormDraft,
  getFittingEntitlementFlags,
  DEFAULT_FITTING_FORM,
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

test("admin bypass keeps view and create available even when entitlements are false", () => {
  assert.equal(
    canViewFittings({
      role: "admin",
      entitlements: { "fittings.view": { allowed: false } },
    }),
    true,
  );
  assert.equal(
    canCreateFittings({
      role: "admin",
      entitlements: { "fittings.create": { allowed: false } },
    }),
    true,
  );
});

test("admin system control still requires create entitlement", () => {
  assert.equal(
    canManageSystemFittings({
      role: "admin",
      entitlements: { "fittings.create": { allowed: false } },
    }),
    true,
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

test("admin can manage system and foreign private fittings even when entitlements are false", () => {
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

  assert.equal(canViewFittings(admin), true);
  assert.equal(canCreateFittings(admin), true);
  assert.equal(canEditFittingItem(admin, { owner_user_id: 10, is_system: false }), true);
  assert.equal(canDeleteFittingItem(admin, { owner_user_id: 10, is_system: false }), true);
  assert.equal(canEditFittingItem(admin, { owner_user_id: 10, is_system: true }), true);
  assert.equal(canDeleteFittingItem(admin, { owner_user_id: 10, is_system: true }), true);
});

test("fitting form drafts preserve editable fields and keep protected scope out of edit payload", () => {
  assert.deepEqual(DEFAULT_FITTING_FORM, {
    article: "",
    brand: "",
    city: "",
    code: "",
    fitting_group: "fittings",
    fitting_type: "drawer_slides",
    image_url: "",
    is_active: true,
    is_system: false,
    name: "",
    price: "",
    sort_order: 0,
    stock: "",
    source_url: "",
  });

  const draft = createFittingFormDraft(
    {
      article: "A-100",
      brand: "BLUM",
      city: "Kyiv",
      code: "CODE-1",
      fitting_group: "fittings",
      fitting_type: "drawer_slides",
      image_url: "https://example.com/image.jpg",
      is_active: true,
      is_system: true,
      name: "Test fitting",
      price: 25.5,
      sort_order: 7,
      stock: "in stock",
      source_url: "https://example.com/product",
    },
    { city: "Lviv" },
  );

  assert.equal(draft.city, "Lviv");
  assert.equal(draft.brand, "BLUM");
  assert.equal(draft.code, "CODE-1");
  assert.equal(draft.sort_order, 7);

  const createPayload = buildFittingSubmissionPayload(
    {
      article: "A-100",
      brand: "BLUM",
      city: "Kyiv",
      code: "",
      fitting_group: "fittings",
      fitting_type: "drawer_slides",
      image_url: "https://example.com/image.jpg",
      is_active: true,
      is_system: false,
      name: "Test fitting",
      price: "25.50",
      sort_order: 7,
      stock: "in stock",
      source_url: "https://example.com/product",
    },
    { canEditSystemFittings: true, allowSystemToggle: true, mode: "create", fallbackSystemName: "System" },
  );

  assert.equal(createPayload.is_system, false);
  assert.deepEqual(createPayload.payload, {
    article: "A-100",
    brand: "BLUM",
    city: "Kyiv",
    code: null,
    fitting_group: "fittings",
    fitting_type: "drawer_slides",
    image_url: "https://example.com/image.jpg",
    is_system: false,
    source_url: "https://example.com/product",
    is_active: true,
    name: "Test fitting",
    price: 25.5,
    sort_order: 7,
    stock: "in stock",
  });

  const editPayload = buildFittingSubmissionPayload(
    {
      article: "A-200",
      brand: "Hettich",
      city: "Kyiv",
      code: "CODE-9",
      fitting_group: "fittings",
      fitting_type: "drawer_slides",
      image_url: "https://example.com/updated.jpg",
      is_active: false,
      is_system: true,
      name: "Updated fitting",
      price: "30",
      sort_order: 9,
      stock: "out of stock",
      source_url: "https://example.com/updated",
    },
    { currentItem: { is_system: true }, mode: "edit", fallbackSystemName: "System" },
  );

  assert.equal(editPayload.is_system, true);
  assert.equal(Object.prototype.hasOwnProperty.call(editPayload.payload, "is_system"), false);
  assert.equal(editPayload.payload.code, "CODE-9");
  assert.equal(editPayload.payload.brand, "Hettich");
  assert.equal(editPayload.payload.stock, "out of stock");
});
