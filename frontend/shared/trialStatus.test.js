import assert from "node:assert/strict";
import test from "node:test";

import {
  buildTrialCountdown,
  formatTrialCountdown,
  parseUtcDateTime,
} from "./trialStatus.js";


test("parseUtcDateTime treats naive backend datetimes as UTC", () => {
  const startedAt = parseUtcDateTime("2026-07-20 23:24:05.164954");
  const endsAt = parseUtcDateTime("2026-07-27 23:24:05.164954");

  assert.ok(startedAt);
  assert.ok(endsAt);
  assert.equal(startedAt.toISOString(), "2026-07-20T23:24:05.164Z");
  assert.equal(endsAt.toISOString(), "2026-07-27T23:24:05.164Z");
  assert.equal((endsAt.getTime() - startedAt.getTime()) / 3_600_000, 168);
});

test("parseUtcDateTime keeps explicit timezone suffixes unchanged", () => {
  const withZ = parseUtcDateTime("2026-07-27 23:24:05.164954Z");
  const withUtcOffset = parseUtcDateTime("2026-07-27 23:24:05.164954+00:00");
  const withPositiveOffset = parseUtcDateTime("2026-07-27 23:24:05.164954+03:00");

  assert.ok(withZ);
  assert.ok(withUtcOffset);
  assert.ok(withPositiveOffset);
  assert.equal(withZ.toISOString(), "2026-07-27T23:24:05.164Z");
  assert.equal(withUtcOffset.toISOString(), "2026-07-27T23:24:05.164Z");
  assert.equal(withPositiveOffset.toISOString(), "2026-07-27T20:24:05.164Z");
});

test("parseUtcDateTime returns null for empty or invalid values", () => {
  assert.equal(parseUtcDateTime(""), null);
  assert.equal(parseUtcDateTime("   "), null);
  assert.equal(parseUtcDateTime(null), null);
  assert.equal(parseUtcDateTime(undefined), null);
  assert.equal(parseUtcDateTime("not-a-date"), null);
});

test("buildTrialCountdown and formatTrialCountdown keep the correct remaining days and hours", () => {
  const countdown = buildTrialCountdown(
    {
      effective_plan: "trial",
      trial_ends_at: "2026-07-27 23:24:05.164954",
    },
    new Date(Date.UTC(2026, 6, 20, 23, 27, 5, 164)),
  );

  assert.ok(countdown);
  assert.equal(countdown.days, 6);
  assert.equal(countdown.hours, 23);
  assert.equal(countdown.minutes, 57);
  assert.equal(formatTrialCountdown(countdown, "en"), "6 days 23 hours left");
});

test("buildTrialCountdown returns null for invalid dates", () => {
  assert.equal(
    buildTrialCountdown(
      {
        effective_plan: "trial",
        trial_ends_at: "",
      },
      Date.now(),
    ),
    null,
  );
  assert.equal(
    buildTrialCountdown(
      {
        effective_plan: "trial",
        trial_ends_at: "not-a-date",
      },
      Date.now(),
    ),
    null,
  );
});
