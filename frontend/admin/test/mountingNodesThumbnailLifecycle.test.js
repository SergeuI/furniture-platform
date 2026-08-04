import assert from "node:assert/strict";
import test from "node:test";

import {
  buildMountingNodeThumbnailLoadPlan,
  buildMountingNodeThumbnailState,
  isCurrentMountingNodeThumbnailRequest,
  shouldLoadMountingNodeThumbnail,
} from "../src/mountingNodesThumbnailLifecycle.js";

test("mounting node thumbnail lifecycle loads missing, error, and stale loading states", () => {
  const nodeDetailsById = {
    9: {
      items: [
        { fitting_id: 42 },
        { fitting_id: 42 },
        { fitting_id: 43 },
        { fitting_id: 44 },
      ],
    },
  };

  const fittingThumbnailStateById = {
    42: buildMountingNodeThumbnailState("loaded", 1, "data:image/png;base64,abc"),
    43: buildMountingNodeThumbnailState("no-image", 1),
    44: buildMountingNodeThumbnailState("loading", 1),
    45: buildMountingNodeThumbnailState("error", 1),
  };

  assert.deepEqual(
    buildMountingNodeThumbnailLoadPlan({
      currentGeneration: 2,
      fittingThumbnailStateById,
      nodeDetailsById,
    }),
    ["44"],
  );
});

test("mounting node thumbnail lifecycle keeps current loading and terminal states stable", () => {
  const currentGeneration = 3;

  assert.equal(shouldLoadMountingNodeThumbnail(null, currentGeneration), true);
  assert.equal(shouldLoadMountingNodeThumbnail(buildMountingNodeThumbnailState("error", 1), currentGeneration), true);
  assert.equal(shouldLoadMountingNodeThumbnail(buildMountingNodeThumbnailState("loading", 1), currentGeneration), true);
  assert.equal(shouldLoadMountingNodeThumbnail(buildMountingNodeThumbnailState("loading", 3), currentGeneration), false);
  assert.equal(shouldLoadMountingNodeThumbnail(buildMountingNodeThumbnailState("loaded", 3, "data:image/png;base64,abc"), currentGeneration), false);
  assert.equal(shouldLoadMountingNodeThumbnail(buildMountingNodeThumbnailState("no-image", 3), currentGeneration), false);
});

test("mounting node thumbnail lifecycle marks request freshness by generation", () => {
  assert.equal(isCurrentMountingNodeThumbnailRequest(3, 3, false), true);
  assert.equal(isCurrentMountingNodeThumbnailRequest(3, 4, false), false);
  assert.equal(isCurrentMountingNodeThumbnailRequest(3, 3, true), false);
});
