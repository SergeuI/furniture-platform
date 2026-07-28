import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  buildProcessingTemplateEditorContext,
  filterProcessingTemplates,
  getProcessingTemplateDefaultLabel,
  getProcessingFittingDisplayLabel,
  getProcessingTemplateDimensionsLabel,
  getProcessingTemplateCardSubtitle,
  getProcessingTemplateCardTitle,
  getProcessingTemplateFutureCategories,
  getProcessingTemplateMountingVariantLabel,
  getProcessingTemplatePreviewCountLabel,
  getProcessingTemplateStatusLabel,
  getProcessingTemplateTypeLabel,
  getProcessingTemplateVariantOptions,
} from "../src/processingTemplates.js";

test("processing templates helpers expose readable labels and future categories", () => {
  const categories = getProcessingTemplateFutureCategories("uk");

  assert.ok(categories.length >= 4);
  assert.equal(categories[0].title, "Мийки");
  assert.equal(categories.some((category) => category.title === "surface_mount"), false);

  assert.equal(getProcessingTemplateMountingVariantLabel("surface_mount", "uk"), "Установка фурнітури на площині");
  assert.equal(getProcessingTemplateMountingVariantLabel("face_to_edge", "uk"), "Площина до торця");
  assert.equal(getProcessingTemplateTypeLabel("manual", "uk"), "Ручний шаблон");
  assert.equal(getProcessingTemplateStatusLabel({ is_active: true }, "uk"), "Активний");
  assert.equal(getProcessingTemplateStatusLabel({ is_active: false }, "uk"), "Неактивний");
  assert.equal(getProcessingTemplateDefaultLabel({ is_default: true }, "uk"), "За замовчуванням");
  assert.equal(getProcessingTemplatePreviewCountLabel(3, "uk"), "3 операцій");
  assert.equal(getProcessingTemplateDimensionsLabel({ width: 500, height: 300, thickness: 18 }, "uk"), "500 × 300 × 18 мм");
  assert.deepEqual(
    buildProcessingTemplateEditorContext(
      { id: 7428, fitting_id: 19, mounting_variant_key: "face_to_edge", bundle_key: "confirmat_7x50" },
      { id: 19 },
    ),
    {
      templateId: "7428",
      fittingId: "19",
      mountingVariantKey: "face_to_edge",
      bundleKey: "confirmat_7x50",
    },
  );
});

test("processing templates helpers build readable titles and filters", () => {
  const fitting = {
    article: "A-1",
    code: "F-1",
    name: "Hinge",
  };
  const template = {
    bundle_name: "Bundle A",
    is_active: true,
    is_default: true,
    mounting_variant_key: "surface_mount",
    name: "",
    template_type: "manual",
  };

  assert.equal(getProcessingFittingDisplayLabel(fitting, "uk"), "Hinge · A-1 · F-1");
  assert.equal(
    getProcessingTemplateCardTitle(template, fitting, "uk"),
    "Bundle A",
  );
  assert.equal(
    getProcessingTemplateCardSubtitle(template, fitting, "uk"),
    "Hinge · A-1 · F-1 · Bundle A · Установка фурнітури на площині · Ручний шаблон",
  );

  const filtered = filterProcessingTemplates(
    [
      { id: 1, name: "Alpha", is_active: true, mounting_variant_key: "surface_mount", template_type: "manual" },
      { id: 2, name: "Beta", is_active: false, mounting_variant_key: "face_to_edge", template_type: "bundle" },
      { id: 3, name: "Gamma", is_active: true, mounting_variant_key: "face_to_edge", template_type: "bundle" },
    ],
    fitting,
    {
      search: "beta",
      status: "inactive",
      mountingVariantKey: "face_to_edge",
    },
  );

  assert.deepEqual(filtered.map((item) => item.id), [2]);

  const variants = getProcessingTemplateVariantOptions(
    [
      { mounting_variant_key: "face_to_edge" },
      { mounting_variant_key: "surface_mount" },
      { mounting_variant_key: "surface_mount" },
    ],
    "uk",
  );

  assert.deepEqual(
    variants,
    [
      { value: "face_to_edge", label: "Площина до торця" },
      { value: "surface_mount", label: "Установка фурнітури на площині" },
    ],
  );
  assert.equal(getProcessingTemplateCardTitle({}, {}, "uk"), "Фурнітура");
});

test("processing templates render preview next to the selected card only once", () => {
  const sourcePath = fileURLToPath(new URL("../src/components/processing/ProcessingTemplates.jsx", import.meta.url));
  const source = readFileSync(sourcePath, "utf8");
  const previewMatches = source.match(/<TemplatePreviewPanel/g) || [];

  assert.equal(source.includes("selectedTemplatePreviewRef"), true);
  assert.equal(source.includes("isSelected ? ("), true);
  assert.equal(previewMatches.length, 1);
});
