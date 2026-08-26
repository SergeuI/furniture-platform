import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("fitting manufacturers workspace uses the shared page shell and a logo-aware compact form", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const workspacePath = fileURLToPath(new URL("../src/components/FittingTaxonomyAdminWorkspace.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");
  const workspaceSource = readFileSync(workspacePath, "utf8");

  assert.match(appSource, /const isCatalogFittingManufacturersView = activeView === FITTING_TAXONOMY_VIEWS\.manufacturers;/);
  assert.match(appSource, /isCatalogFittingManufacturersView\s*\?\s*\(language === "uk" \? "Виробники фурнітури" : "Fitting manufacturers"\)/);
  assert.match(appSource, /if \(isCatalogFittingManufacturersView\) \{\s*return language === "uk"\s*\?\s*"Керування виробниками фурнітури\."\s*:\s*"Manage fitting manufacturers\.";/);
  assert.match(appSource, /<FittingTaxonomyAdminWorkspace[\s\S]*activeTab=\{\s*isCatalogFittingManufacturersView/);
  assert.match(appSource, /!isMaterialCleanupView && !isCatalogFittingManufacturersView \?\s*\(/);
  assert.match(appSource, /isCatalogView && !isCatalogFittingManufacturersView \?\s*\(/);
  assert.doesNotMatch(workspaceSource, /dashboard-hero-card/);
  assert.doesNotMatch(workspaceSource, /Керування виробниками, серіями, категоріями та технічними товарами\./);
  assert.doesNotMatch(workspaceSource, /Active records are shown by default/);
  assert.match(workspaceSource, /className={activeTab === "manufacturers" \? "table-panel full-panel fitting-taxonomy-page-shell" : "dashboard-layout"}/);
  assert.match(workspaceSource, /className="catalog-page-header fitting-taxonomy-page-header"/);
  assert.match(workspaceSource, /className="service-catalog-title fitting-taxonomy-page-title"/);
  assert.match(workspaceSource, /className="service-catalog-header-actions fitting-taxonomy-page-actions"/);
  assert.match(workspaceSource, /onClick=\{\(\) => onNavigate\("catalogFittings"\)\}/);
  assert.match(workspaceSource, /className="service-tree-badge subtle"/);
  assert.match(workspaceSource, /manufacturer-logo-cell/);
  assert.match(workspaceSource, /<ManufacturerLogo name=\{item\.name\} logoUrl=\{item\.logo_url\} \/>/);
  assert.match(workspaceSource, /className="fittings-table-row fitting-manufacturers-table"/);
  assert.match(workspaceSource, /const rootClassName = \[\s*"fitting-manufacturer-logo",\s*"material-taxonomy-manufacturer-logo",\s*className\s*\]/);
  assert.match(workspaceSource, /className="fitting-source-logo-text"/);
  assert.match(workspaceSource, /className="fitting-manufacturer-logo-image"/);
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

  const manufacturerTableStart = workspaceSource.indexOf('activeTab === "manufacturers" ? (');
  const manufacturerTableEnd = workspaceSource.indexOf('      ) : (', manufacturerTableStart);
  const manufacturerShellSource =
    manufacturerTableStart >= 0 && manufacturerTableEnd > manufacturerTableStart
      ? workspaceSource.slice(manufacturerTableStart, manufacturerTableEnd)
      : workspaceSource;
  assert.doesNotMatch(manufacturerShellSource, /className="service-catalog-header"/);
  assert.doesNotMatch(manufacturerShellSource, /className="service-catalog-header-actions"/);

  const manufacturerTableSource = manufacturerShellSource;
  assert.match(manufacturerTableSource, /language === "uk" \? "Логотип" : "Logo"/);
  assert.match(manufacturerTableSource, /className="ghost-button compact-button" onClick=\{\(\) => toggleActive\("manufacturers", item\)\}/);
  assert.match(manufacturerTableSource, /className="ghost-button compact-button danger-button" onClick=\{\(\) => handleDelete\("manufacturers", item\)\}/);
  assert.doesNotMatch(manufacturerTableSource, /↘|↗/);
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

  const stylesPath = fileURLToPath(new URL("../src/styles.css", import.meta.url));
  const stylesSource = readFileSync(stylesPath, "utf8");
  assert.match(stylesSource, /\.fitting-taxonomy-page-shell \{\s*display: block;[\s\S]*overflow: visible;/);
  assert.match(stylesSource, /\.fitting-taxonomy-page-header \{\s*align-items: center;/);
  assert.match(stylesSource, /\.fitting-taxonomy-page-actions \{\s*align-items: center;[\s\S]*flex-wrap: nowrap;[\s\S]*margin-left: auto;/);
  assert.match(stylesSource, /\.fitting-taxonomy-page-actions \.materials-filter \{\s*min-width: 180px;/);
  assert.match(stylesSource, /\.fitting-manufacturers-table \{\s*grid-template-columns:[\s\S]*minmax\(120px, 0\.85fr\);/);
  assert.match(stylesSource, /\.fitting-manufacturers-table \.manufacturer-logo-cell \{\s*align-items: center;[\s\S]*justify-content: center;/);
  assert.match(stylesSource, /\.fitting-manufacturers-table \.catalog-actions \{\s*gap: 8px;[\s\S]*min-width: 0;/);
  assert.match(stylesSource, /\.fitting-manufacturer-logo \{\s*align-items: center;[\s\S]*display: inline-flex;[\s\S]*overflow: hidden;/);
  assert.match(stylesSource, /\.fitting-manufacturer-logo-image \{\s*display: block;[\s\S]*height: 22px;[\s\S]*max-width: 85px;[\s\S]*object-fit: contain;/);
});
