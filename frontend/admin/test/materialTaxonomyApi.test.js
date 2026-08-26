import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("material taxonomy api helpers point at the new catalog routes", () => {
  const apiPath = fileURLToPath(new URL("../src/api.js", import.meta.url));
  const source = readFileSync(apiPath, "utf8");

  assert.match(source, /export async function listMaterialCategories\(token, includeInactive = false, includePrivateCategories = false\)/);
  assert.match(source, /\/catalog\/material-categories/);
  assert.match(source, /export async function getMaterialCategory\(token, itemId\)/);
  assert.match(source, /export async function createMaterialCategory\(token, payload\)/);
  assert.match(source, /export async function updateMaterialCategory\(token, itemId, payload\)/);
  assert.match(source, /export async function deleteMaterialCategory\(token, itemId\)/);
  assert.match(source, /export async function listMaterialManufacturers\(token, includeInactive = false\)/);
  assert.match(source, /\/catalog\/material-manufacturers/);
  assert.match(source, /export async function getMaterialManufacturer\(token, itemId\)/);
  assert.match(source, /export async function createMaterialManufacturer\(token, payload\)/);
  assert.match(source, /export async function updateMaterialManufacturer\(token, itemId, payload\)/);
  assert.match(source, /export async function uploadMaterialManufacturerLogo\(token, file, timeoutMs = 30000\)/);
  assert.match(source, /\/catalog\/material-manufacturers\/logo/);
  assert.match(source, /active_only", "false"/);
  assert.match(source, /include_private_categories/);
});
