import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const appSource = fs.readFileSync(
  path.resolve("frontend/admin/src/App.jsx"),
  "utf8",
);

test("project page contract keeps quota banner and owner column on the projects view", () => {
  assert.match(appSource, /getProjectOwnershipScopeLabel/);
  assert.match(appSource, /project-quota-banner/);
  assert.match(appSource, /getProjectOwnerLabel\(project, projectOwnerMap, user, language\)/);
  assert.match(appSource, /language === "uk" \? "Власник" : "Owner"/);
});

test("project filters use owner scope dropdown instead of the old checkbox", () => {
  const quotaBlockStart = appSource.indexOf('className="project-quota-banner"');
  const filterBlockStart = appSource.indexOf('className="project-filter-form"');
  const quotaBlock = appSource.slice(quotaBlockStart, filterBlockStart);
  const filterBlock = appSource.slice(
    filterBlockStart,
    appSource.indexOf('{canCreateNewProject ? (', filterBlockStart),
  );

  assert.ok(quotaBlockStart > -1 && filterBlockStart > quotaBlockStart);
  assert.doesNotMatch(quotaBlock, /<strong>/);
  assert.match(quotaBlock, /projectOwnershipQuotaLabel/);
  assert.match(appSource, /user\?\.role === "admin" \? \(/);
  assert.match(filterBlock, /ownership_scope/);
  assert.match(filterBlock, /getProjectOwnershipScopeLabel\(scope, language\)/);
  assert.doesNotMatch(filterBlock, /only_mine/);
});

test("ownership dropdown applies immediately without the Apply button", () => {
  assert.match(appSource, /function handleProjectOwnershipScopeChange\(event\)/);
  assert.match(appSource, /setAppliedProjectFilters\(nextAppliedProjectFilters\)/);
  assert.match(appSource, /await loadProjects\(token, 0, nextAppliedProjectFilters, user\)/);
});

test("create project contract keeps only short quota messages", () => {
  const createBlockStart = appSource.indexOf('className="project-form-caption"');
  const createBlockEnd = appSource.indexOf('<div className="project-start-grid">');
  const createBlock = appSource.slice(createBlockStart, createBlockEnd);

  assert.ok(createBlockStart > -1 && createBlockEnd > createBlockStart);
  assert.match(appSource, /projectOwnershipQuotaError/);
  assert.match(appSource, /isProjectCreationBlockedByQuotaHelper\(projectOwnershipQuota\)/);
  assert.doesNotMatch(createBlock, /projectOwnershipQuotaLabel/);
});
