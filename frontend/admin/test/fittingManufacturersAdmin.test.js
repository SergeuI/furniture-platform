import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("manufacturer admin workspace keeps a single header and a logo-aware compact form", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const workspacePath = fileURLToPath(new URL("../src/components/FittingTaxonomyAdminWorkspace.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const workspaceSource = readFileSync(workspacePath, "utf8");

  assert.match(appSource, /const isCatalogFittingManufacturersView = activeView === FITTING_TAXONOMY_VIEWS\.manufacturers;/);
  assert.match(appSource, /isCatalogFittingManufacturersView\s*\?\s*\(language === "uk" \? "Виробники фурнітури" : "Fitting manufacturers"\)/);
  assert.match(appSource, /if \(isCatalogFittingManufacturersView\) \{\s*return language === "uk"\s*\?\s*"Керування виробниками фурнітури\."\s*:\s*"Manage fitting manufacturers\.";/);
  assert.match(appSource, /<FittingTaxonomyAdminWorkspace[\s\S]*activeTab=\{\s*isCatalogFittingManufacturersView/);
  assert.doesNotMatch(workspaceSource, /dashboard-hero-card/);
  assert.doesNotMatch(workspaceSource, /Керування виробниками, серіями, категоріями та технічними товарами\./);
  assert.doesNotMatch(workspaceSource, /Active records are shown by default/);
  assert.match(workspaceSource, /manufacturer-logo-cell/);
  assert.match(workspaceSource, /<ManufacturerLogo name=\{item\.name\} logoUrl=\{item\.logo_url\} \/>/);
  assert.match(workspaceSource, /uploadFittingManufacturerLogo/);
  assert.match(workspaceSource, /MANUFACTURER_LOGO_ACCEPT/);
  assert.match(workspaceSource, /URL\.createObjectURL\(file\)/);
  assert.match(workspaceSource, /resolveAdminAssetUrl\(editorForm\.logo_url\)/);
  assert.match(workspaceSource, /supplier-confirm-modal/);
  assert.match(workspaceSource, /language === "uk" \? "Виробник фурнітури" : "Fitting manufacturer"/);
  assert.match(workspaceSource, /language === "uk" \? "Логотип" : "Logo"/);
  assert.match(workspaceSource, /language === "uk" \? "Вибрати зображення" : "Choose image"/);
  assert.match(workspaceSource, /language === "uk" \? "Замінити" : "Replace"/);
  assert.match(workspaceSource, /language === "uk" \? "Видалити" : "Remove"/);
  assert.match(workspaceSource, /accept=\{MANUFACTURER_LOGO_ACCEPT\}/);
  assert.match(workspaceSource, /className="supplier-logo-upload-panel"/);
  assert.match(workspaceSource, /className="supplier-logo-preview"/);
  assert.match(workspaceSource, /className="supplier-logo-file-input"/);
  assert.match(workspaceSource, /className="supplier-form-body"/);
  assert.match(workspaceSource, /className="supplier-form-options"/);
  assert.match(workspaceSource, /className="supplier-form-footer confirm-actions"/);
  assert.match(workspaceSource, /supplier-form-error/);

  const manufacturerTableStart = workspaceSource.indexOf('        {activeTab === "manufacturers" ? (');
  const manufacturerTableEnd = workspaceSource.indexOf('        ) : activeTab === "series" ? (', manufacturerTableStart);
  const manufacturerTableSource =
    manufacturerTableStart >= 0 && manufacturerTableEnd > manufacturerTableStart
      ? workspaceSource.slice(manufacturerTableStart, manufacturerTableEnd)
      : workspaceSource;
  assert.match(manufacturerTableSource, /language === "uk" \? "Логотип" : "Logo"/);
  assert.doesNotMatch(manufacturerTableSource, /language === "uk" \? "Код" : "Code"/);

  const manufacturerFormStart = workspaceSource.indexOf('{editorEntity === "manufacturers" ? (');
  const manufacturerFormEnd = workspaceSource.indexOf('              ) : editorEntity === "series" ? (', manufacturerFormStart);
  const manufacturerFormSource =
    manufacturerFormStart >= 0 && manufacturerFormEnd > manufacturerFormStart
      ? workspaceSource.slice(manufacturerFormStart, manufacturerFormEnd)
      : workspaceSource;
  assert.match(manufacturerFormSource, /language === "uk" \? "Назва" : "Name"/);
  assert.match(manufacturerFormSource, /language === "uk" \? "Країна" : "Country"/);
  assert.match(manufacturerFormSource, /language === "uk" \? "Активний" : "Active"/);
  assert.doesNotMatch(manufacturerFormSource, /language === "uk" \? "Код" : "Code"/);
  assert.doesNotMatch(manufacturerFormSource, /language === "uk" \? "Сайт" : "Website"/);
  assert.doesNotMatch(manufacturerFormSource, /language === "uk" \? "Логотип URL" : "Logo URL"/);
});
