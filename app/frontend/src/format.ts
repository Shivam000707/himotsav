import type { Medication, Observation } from './api';

export const TEST_DISPLAY: Record<string, string> = {
  hba1c: 'HbA1c',
  fasting_glucose: 'Fasting glucose',
  postprandial_glucose: 'Post-meal glucose',
  random_glucose: 'Random glucose',
  creatinine: 'Creatinine',
  egfr: 'eGFR',
  uacr: 'Urine albumin / creatinine',
  total_cholesterol: 'Total cholesterol',
  ldl: 'LDL cholesterol',
  hdl: 'HDL cholesterol',
  triglycerides: 'Triglycerides',
};

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "2026-08-12" -> "12 Aug 2026". Parsed by hand so the browser's time zone cannot shift the day. */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return 'date unknown';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
}

/** "2026-08-12" -> "Aug 2026" */
export function fmtMonth(iso: string | null | undefined): string {
  if (!iso) return '?';
  const m = /^(\d{4})-(\d{2})/.exec(iso);
  return m ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : iso;
}

/** Days between two ISO dates (b - a). */
export function daysBetween(a: string, b: string): number {
  const da = Date.UTC(Number(a.slice(0, 4)), Number(a.slice(5, 7)) - 1, Number(a.slice(8, 10)));
  const db = Date.UTC(Number(b.slice(0, 4)), Number(b.slice(5, 7)) - 1, Number(b.slice(8, 10)));
  return Math.round((db - da) / 86_400_000);
}

export function testName(o: Observation): string {
  return TEST_DISPLAY[o.test] ?? o.label_as_written;
}

/** Value as the doctor should read it: the doctor's correction first, then the standard unit. */
export function obsDisplay(o: Observation): string {
  if (o.edited_value) return o.edited_value;
  if (o.value_std != null && o.unit_std) return `${o.value_std} ${o.unit_std}`;
  return `${o.value_raw}${o.unit_raw ? ` ${o.unit_raw}` : ''}`;
}

export function rawDisplay(o: Observation): string {
  return `${o.value_raw}${o.unit_raw ? ` ${o.unit_raw}` : ''}`;
}

export function medName(m: Medication): string {
  if (!m.generic_name) return m.name_as_written;
  return m.generic_name.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function medDose(m: Medication): string {
  if (m.edited_value) return m.edited_value;
  return [m.strength, m.frequency].filter(Boolean).join(' · ') || 'dose not stated';
}

export function medKey(m: Medication): string {
  return (m.generic_name || m.name_as_written).trim().toLowerCase();
}
