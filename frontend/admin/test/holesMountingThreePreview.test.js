import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import test from "node:test";

test("holes mounting three preview is extracted into a reusable component", () => {
  const componentPath = fileURLToPath(
    new URL("../src/components/processing/HolesMountingThreePreview.jsx", import.meta.url),
  );
  const componentSource = readFileSync(componentPath, "utf8");
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");

  assert.equal(componentSource.includes("export default function HolesMountingThreePreview({"), true);
  assert.equal(componentSource.includes("renderSchematicPreview,"), true);
  assert.equal(componentSource.includes("holes"), true);
  assert.equal(componentSource.includes("mountingVariantKey"), true);
  assert.equal(componentSource.includes("hoveredHoleId"), true);
  assert.equal(componentSource.includes("selectedHoleId"), true);
  assert.equal(componentSource.includes("onHoverHole"), true);
  assert.equal(componentSource.includes("onLeaveHole"), true);
  assert.equal(componentSource.includes("onSelectHole"), true);
  assert.equal(componentSource.includes("Canvas"), true);
  assert.equal(componentSource.includes("OrbitControls"), true);
  assert.equal(componentSource.includes("function getSafeHolePointLabel("), true);
  assert.equal(componentSource.includes("buildSurfaceMountThreePreviewHoleVolumes"), true);
  assert.equal(componentSource.includes("buildAngledTwoPlanesThreePreviewHoleVolumes"), true);
  assert.equal(componentSource.includes('case "face_to_edge":'), true);
  assert.equal(componentSource.includes("normalizeAngledTwoPlanesPreviewThicknessMm(faceToEdgeVerticalPreviewThicknessMm) * 0.01"), true);
  assert.equal(componentSource.includes('normalizedVariantKey === "face_to_edge"'), true);
  assert.equal(componentSource.includes("getFaceToEdgeHolePlacement(baseLayout, hole, index)"), true);
  assert.equal(componentSource.includes('isAngledTwoPlanesPreview || normalizedVariantKey === "face_to_edge"'), true);
  assert.equal(componentSource.includes("normalizedFaceToEdgeVerticalPreviewThicknessMm"), true);
  assert.equal(componentSource.includes("normalizedFaceToEdgeHorizontalPreviewThicknessMm"), true);
  assert.equal(componentSource.includes("const hasDepth = Number.isFinite(depthValue) && depthValue > 0"), true);
  assert.equal(componentSource.includes("const throughHoleLength = isHorizontalEdge || isHorizontalPlane ? panelBThickness : panelAThickness"), true);
  assert.equal(componentSource.includes("const depthScene = hasDepth ? Math.abs(depthValue) * mmToScene : holeLength"), true);
  assert.equal(componentSource.includes('color: "#b9ffb9"'), true);
  assert.equal(componentSource.includes("opacity: 0.28"), true);

  assert.equal(
    appSource.includes('import HolesMountingThreePreview from "./components/processing/HolesMountingThreePreview.jsx";'),
    true,
  );
  assert.equal(appSource.includes("renderSchematicPreview={renderHolesSceneSchematicPreview}"), true);
  assert.equal(appSource.includes("function renderHoleWorkspaceFittingInfo("), true);
  assert.equal(appSource.includes("function renderHoleWorkspaceMountingVariantDropdown("), true);
  assert.equal(appSource.includes("memo(function HolesMountingThreePreview"), false);
  assert.equal(appSource.includes("const HolesMountingThreePreview = useMemo"), false);
});

test("app keeps panel metadata in hole preview points so legacy angled_two_planes points stay renderable", () => {
  const appPath = fileURLToPath(new URL("../src/App.jsx", import.meta.url));
  const appSource = readFileSync(appPath, "utf8");

  assert.equal(appSource.includes("const panelKey = String("), true);
  assert.equal(appSource.includes("point?.target_panel || point?.targetPanel || \"\""), true);
  assert.equal(appSource.includes("panelKey,"), true);
  assert.equal(appSource.includes("panel_key: panelKey,"), true);
  assert.equal(appSource.includes("target_panel: targetPanel,"), true);
  assert.equal(appSource.includes("target_surface: targetSurface,"), true);
  assert.equal(appSource.includes("target_side: targetSide,"), true);
});
