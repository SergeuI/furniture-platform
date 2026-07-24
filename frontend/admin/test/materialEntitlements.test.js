import assert from "node:assert/strict";
import test from "node:test";

import {
  getMaterialEntitlementFlags,
  hasUserEntitlement,
  isMaterialCreationBlockedByQuota,
} from "../src/materialEntitlements.js";

test("material entitlement helper reads runtime snapshot only", () => {
  const user = {
    role: "admin",
    entitlements: {
      "materials.view": { allowed: true },
      "materials.create": { allowed: true },
      "materials.edit": { allowed: true },
      "materials.delete": { allowed: true },
    },
  };

  assert.equal(hasUserEntitlement(user, "materials.view"), true);
  assert.equal(hasUserEntitlement(user, "materials.create"), true);
  assert.equal(hasUserEntitlement(user, "materials.edit"), true);
  assert.equal(hasUserEntitlement(user, "materials.delete"), true);
  assert.equal(hasUserEntitlement({ role: "admin", entitlements: {} }, "materials.view"), false);
  assert.equal(hasUserEntitlement({ role: "pro" }, "materials.view"), false);
});

test("material entitlement flags stay separated by feature key", () => {
  const flags = getMaterialEntitlementFlags({
    entitlements: {
      "materials.view": { allowed: true },
      "materials.create": { allowed: false },
      "materials.edit": { allowed: true },
      "materials.delete": { allowed: false },
    },
  });

  assert.deepEqual(flags, {
    view: true,
    create: false,
    edit: true,
    delete: false,
  });
});

test("quota blocks new material creation without replacing entitlement checks", () => {
  assert.equal(
    isMaterialCreationBlockedByQuota({ can_create: false, is_unlimited: false }, true),
    true,
  );
  assert.equal(
    isMaterialCreationBlockedByQuota({ can_create: false, is_unlimited: false }, false),
    false,
  );
  assert.equal(
    isMaterialCreationBlockedByQuota({ can_create: true, is_unlimited: false }, true),
    false,
  );
  assert.equal(
    isMaterialCreationBlockedByQuota({ is_unlimited: true }, true),
    false,
  );
});
