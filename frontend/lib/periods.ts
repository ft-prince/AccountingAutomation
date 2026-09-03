// PROJECT_SPECS §3/§7 — Indian financial year: 1 April → 31 March.
// Pure date arithmetic on ISO strings; no Date-with-timezone surprises leak out.

export type PeriodPreset = "this_month" | "last_month" | "this_quarter" | "fy_to_date" | "last_fy" | "custom";

export interface Period {
  from: string; // YYYY-MM-DD
  to: string; // YYYY-MM-DD
  fy: string; // "2026-27"
  label: string;
}

export const PERIOD_PRESETS: readonly { value: PeriodPreset; label: string }[] = [
  { value: "this_month", label: "This month" },
  { value: "last_month", label: "Last month" },
  { value: "this_quarter", label: "This quarter" },
  { value: "fy_to_date", label: "FY to date" },
  { value: "last_fy", label: "Last FY" },
  { value: "custom", label: "Custom range" },
];

const FY_START_MONTH = 4; // April
const MONTHS_PER_QUARTER = 3;
const MONTHS_PER_YEAR = 12;

interface YearMonthDay {
  year: number;
  month: number; // 1–12
  day: number;
}

function parseIso(date: string): YearMonthDay {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) throw new Error(`Expected YYYY-MM-DD, got "${date}"`);
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function iso(year: number, month: number, day: number): string {
  return `${year}-${pad(month)}-${pad(day)}`;
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function monthBounds(year: number, month: number): { from: string; to: string } {
  return { from: iso(year, month, 1), to: iso(year, month, daysInMonth(year, month)) };
}

/** FY containing the date: starts 1 Apr of `startYear`, ends 31 Mar of `startYear + 1`. */
export function fiscalYearStartYear(date: string): number {
  const { year, month } = parseIso(date);
  return month >= FY_START_MONTH ? year : year - 1;
}

export function fiscalYearLabel(startYear: number): string {
  return `${startYear}-${pad((startYear + 1) % 100)}`;
}

export function fiscalYearBounds(startYear: number): { from: string; to: string; fy: string } {
  return {
    from: iso(startYear, FY_START_MONTH, 1),
    to: iso(startYear + 1, FY_START_MONTH - 1, daysInMonth(startYear + 1, FY_START_MONTH - 1)),
    fy: fiscalYearLabel(startYear),
  };
}

function quarterBounds(date: string): { from: string; to: string } {
  const { month } = parseIso(date);
  const startYear = fiscalYearStartYear(date);
  const monthsIntoFy = (month - FY_START_MONTH + MONTHS_PER_YEAR) % MONTHS_PER_YEAR;
  const quarterStartOffset = monthsIntoFy - (monthsIntoFy % MONTHS_PER_QUARTER);
  const startMonthIndex = FY_START_MONTH - 1 + quarterStartOffset; // 0-based, may exceed 11
  const startYearOfQuarter = startYear + Math.floor(startMonthIndex / MONTHS_PER_YEAR);
  const startMonth = (startMonthIndex % MONTHS_PER_YEAR) + 1;
  const endMonthIndex = startMonthIndex + MONTHS_PER_QUARTER - 1;
  const endYearOfQuarter = startYear + Math.floor(endMonthIndex / MONTHS_PER_YEAR);
  const endMonth = (endMonthIndex % MONTHS_PER_YEAR) + 1;
  return {
    from: iso(startYearOfQuarter, startMonth, 1),
    to: iso(endYearOfQuarter, endMonth, daysInMonth(endYearOfQuarter, endMonth)),
  };
}

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function monthLabel(year: number, month: number): string {
  return `${MONTH_NAMES[month - 1]} ${year}`;
}

/** Resolves a preset relative to `today` (ISO date). `custom` requires explicit bounds. */
export function resolvePeriod(preset: PeriodPreset, today: string, custom?: { from: string; to: string }): Period {
  const { year, month } = parseIso(today);
  switch (preset) {
    case "this_month": {
      const { from, to } = monthBounds(year, month);
      return { from, to, fy: fiscalYearLabel(fiscalYearStartYear(from)), label: monthLabel(year, month) };
    }
    case "last_month": {
      const lastYear = month === 1 ? year - 1 : year;
      const lastMonth = month === 1 ? MONTHS_PER_YEAR : month - 1;
      const { from, to } = monthBounds(lastYear, lastMonth);
      return { from, to, fy: fiscalYearLabel(fiscalYearStartYear(from)), label: monthLabel(lastYear, lastMonth) };
    }
    case "this_quarter": {
      const { from, to } = quarterBounds(today);
      const startYear = fiscalYearStartYear(today);
      const quarterNumber = Math.floor(((month - FY_START_MONTH + MONTHS_PER_YEAR) % MONTHS_PER_YEAR) / MONTHS_PER_QUARTER) + 1;
      return { from, to, fy: fiscalYearLabel(startYear), label: `Q${quarterNumber} FY${fiscalYearLabel(startYear)}` };
    }
    case "fy_to_date": {
      const { from, fy } = fiscalYearBounds(fiscalYearStartYear(today));
      return { from, to: today, fy, label: `FY${fy} to date` };
    }
    case "last_fy": {
      const { from, to, fy } = fiscalYearBounds(fiscalYearStartYear(today) - 1);
      return { from, to, fy, label: `FY${fy}` };
    }
    case "custom": {
      if (!custom) throw new Error("custom period requires from/to");
      const { from, to } = custom;
      if (from > to) throw new Error("period start must not be after its end");
      return { from, to, fy: fiscalYearLabel(fiscalYearStartYear(from)), label: `${from} → ${to}` };
    }
  }
}

export function todayIso(): string {
  const now = new Date();
  return iso(now.getFullYear(), now.getMonth() + 1, now.getDate());
}
