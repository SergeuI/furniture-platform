import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingSchemePayload,
  buildMountingSchemesRouteUrl,
  collectDistinctGroupKeys,
  normalizeMountingSchemesRoute,
  parseMountingSchemesRoute,
  syncPlacementRulesWithGroupKeys,
  validateMountingSchemeDraft,
} from "../src/mountingSchemesWorkspace.js";

test("mounting-schemes route roundtrips through query params", () => {
  const parsed = parseMountingSchemesRoute("?section=mounting-schemes&mode=detail&scheme=42");
  assert.deepEqual(parsed, {
    mode: "detail",
    schemeId: "42",
  });

  const url = buildMountingSchemesRouteUrl(parsed, "?foo=bar");
  assert.equal(url, "?foo=bar&section=mounting-schemes&mode=detail&scheme=42");
});

test("mounting-schemes payload normalizes nested nodes and rules", () => {
  const payload = buildMountingSchemePayload({
    code: "  demo-scheme  ",
    name: "  Demo scheme  ",
    description: "  ",
    is_active: false,
    nodes: [
      {
        node_id: "12",
        group_key: "primary",
        quantity_per_group: "2",
        role_code: "",
        order_index: "3",
        is_required: 1,
      },
    ],
    placement_rules: [
      {
        group_key: "primary",
        distribution_mode: "equal",
        min_group_count: "2",
        max_group_count: "",
        fixed_group_count: "",
        start_offset_mm: "50",
        end_offset_mm: "",
        max_spacing_mm: "400",
        fixed_spacing_mm: "",
      },
    ],
  });

  assert.equal(payload.code, "demo-scheme");
  assert.equal(payload.name, "Demo scheme");
  assert.equal(payload.description, undefined);
  assert.equal(payload.is_active, false);
  assert.deepEqual(payload.nodes[0], {
    node_id: 12,
    group_key: "primary",
    quantity_per_group: 2,
    role_code: undefined,
    order_index: 3,
    is_required: true,
  });
  assert.equal(payload.placement_rules[0].group_key, "primary");
  assert.equal(payload.placement_rules[0].start_offset_mm, 50);
  assert.equal(payload.placement_rules[0].end_offset_mm, undefined);
});

test("mounting-schemes validation catches obvious frontend mistakes", () => {
  const errors = validateMountingSchemeDraft({
    name: "",
    nodes: [
      {
        node_id: "",
        group_key: "",
        quantity_per_group: 0,
      },
    ],
    placement_rules: [
      {
        group_key: "missing",
        distribution_mode: "bogus",
        min_group_count: 0,
      },
    ],
  });

  assert(errors.some((message) => message.includes("Name is required")));
  assert(errors.some((message) => message.includes("node is required")));
  assert(errors.some((message) => message.includes("group key is required")));
  assert(errors.some((message) => message.includes("quantity per group must be greater than 0")));
  assert(errors.some((message) => message.includes("distribution mode is invalid")));
});

test("mounting-schemes helper keeps placement rules aligned with node groups", () => {
  const synced = syncPlacementRulesWithGroupKeys(
    [{ group_key: "secondary", distribution_mode: "equal" }],
    ["primary", "joint"],
  );

  assert.deepEqual(collectDistinctGroupKeys([{ group_key: "joint" }, { group_key: "primary" }, { group_key: "primary" }]), ["joint", "primary"]);
  assert.deepEqual(
    synced.map((rule) => rule.group_key),
    ["primary", "joint"],
  );
});

test("mounting-schemes route normalization defaults to list", () => {
  assert.deepEqual(normalizeMountingSchemesRoute({}), {
    mode: "list",
    schemeId: "",
  });
});
