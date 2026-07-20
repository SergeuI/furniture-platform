const TRIAL_EXCLUDED_PLANS = new Set([
  "admin",
  "premium",
  "pro",
  "business",
]);

const PLAN_LABELS = {
  en: {
    admin: "Admin",
    business: "Business",
    free: "Free",
    premium: "Premium",
    pro: "PRO",
    trial: "Trial",
  },
  uk: {
    admin: "Admin",
    business: "Business",
    free: "Free",
    premium: "Premium",
    pro: "PRO",
    trial: "Пробний доступ",
  },
};

function normalizePlanKey(user) {
  return String(user?.effective_plan || user?.role || "free").trim().toLowerCase();
}

function pluralizeCount(value, forms) {
  const absValue = Math.abs(value);
  const lastDigit = absValue % 10;
  const lastTwoDigits = absValue % 100;

  if (lastDigit === 1 && lastTwoDigits !== 11) {
    return forms[0];
  }

  if (lastDigit >= 2 && lastDigit <= 4 && (lastTwoDigits < 12 || lastTwoDigits > 14)) {
    return forms[1];
  }

  return forms[2];
}

export function parseUtcDateTime(value) {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : new Date(value.getTime());
  }

  if (typeof value === "number") {
    const parsedFromNumber = new Date(value);
    return Number.isNaN(parsedFromNumber.getTime()) ? null : parsedFromNumber;
  }

  const rawValue = String(value ?? "").trim();
  if (!rawValue) {
    return null;
  }

  const normalizedValue = rawValue.replace(/\s+/, "T");
  const hasTimezoneSuffix = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalizedValue);
  const parsedValue = new Date(
    hasTimezoneSuffix ? normalizedValue : `${normalizedValue}Z`,
  );

  return Number.isNaN(parsedValue.getTime()) ? null : parsedValue;
}

export function getSubscriptionLabel(user, language = "en") {
  const planKey = normalizePlanKey(user);
  const labels = PLAN_LABELS[language] || PLAN_LABELS.en;

  return labels[planKey] || labels.free;
}

export function buildTrialCountdown(user, now = Date.now()) {
  if (!user) {
    return null;
  }

  const planKey = normalizePlanKey(user);
  if (TRIAL_EXCLUDED_PLANS.has(planKey) || planKey !== "trial") {
    return null;
  }

  const endsAt = parseUtcDateTime(user.trial_ends_at);
  if (!endsAt) {
    return null;
  }

  const currentTime = now instanceof Date ? now : parseUtcDateTime(now);
  if (!currentTime) {
    return null;
  }

  const remainingMs = endsAt.getTime() - currentTime.getTime();
  const clippedMs = Math.max(0, remainingMs);
  const totalMinutes = Math.floor(clippedMs / 60000);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  return {
    days,
    hours,
    minutes,
    remainingMs: clippedMs,
    state: remainingMs > 0 ? "active" : "expired",
  };
}

export function formatTrialCountdown(countdown, language = "en") {
  if (!countdown) {
    return "";
  }

  const useUkrainian = language === "uk";
  const dayForms = useUkrainian ? ["день", "дні", "днів"] : ["day", "days", "days"];
  const hourForms = useUkrainian ? ["година", "години", "годин"] : ["hour", "hours", "hours"];
  const minuteForms = useUkrainian ? ["хвилина", "хвилини", "хвилин"] : ["minute", "minutes", "minutes"];

  if (countdown.state === "expired") {
    return useUkrainian
      ? "Пробний період завершено. Активний тариф — Free."
      : "Trial finished. Active plan is Free.";
  }

  const parts = [];
  if (countdown.days > 0) {
    parts.push(`${countdown.days} ${pluralizeCount(countdown.days, dayForms)}`);
    parts.push(`${countdown.hours} ${pluralizeCount(countdown.hours, hourForms)}`);
  } else {
    parts.push(`${countdown.hours} ${pluralizeCount(countdown.hours, hourForms)}`);
    parts.push(`${countdown.minutes} ${pluralizeCount(countdown.minutes, minuteForms)}`);
  }

  return useUkrainian
    ? `Залишилось ${parts.join(" ")}`
    : `${parts.join(" ")} left`;
}
