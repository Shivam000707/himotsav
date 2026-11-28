import { useState } from 'react';
import { api, ApiError, type PlanItem, type ScheduleRow } from '../api';
import { fmtDate, TEST_DISPLAY } from '../format';
import { Alert } from './icons';

const STATUS_STAMP: Record<ScheduleRow['status'], string> = {
  Completed: 'stamp-ok',
  Due: 'stamp-missing',
  Overdue: 'stamp-flag',
  'No record': 'stamp-check',
  'Interval not set': 'stamp-note',
};

const MONTH_DAYS = 30.4375;

function months(days: number | null): string {
  if (!days) return 'not set';
  const m = days / MONTH_DAYS;
  return `every ${Number.isInteger(Math.round(m * 10) / 10) ? Math.round(m) : (Math.round(m * 10) / 10).toString()} months`;
}

interface Props {
  patientId: number;
  plan: PlanItem[];
  schedule: ScheduleRow[];
  testsInRecords: string[];
  onChanged: () => Promise<void> | void;
}

const numOrNull = (s: string): number | null => (s.trim() === '' ? null : Number(s));

/** The doctor's own targets, review margins and test intervals for this patient, and the schedule they give.
 *  Nothing is pre-filled or suggested: every number on this panel was typed by the doctor. */
export function MonitoringPlan({ patientId, plan, schedule, testsInRecords, onChanged }: Props) {
  const tests = Object.keys(TEST_DISPLAY);
  const [test, setTest] = useState(testsInRecords[0] ?? 'hba1c');
  const existing = plan.find((p) => p.test === test);
  const [low, setLow] = useState(existing?.target_low?.toString() ?? '');
  const [high, setHigh] = useState(existing?.target_high?.toString() ?? '');
  const [margin, setMargin] = useState(existing?.review_margin?.toString() ?? '');
  const [interval, setInterval_] = useState(existing?.interval_days ? String(Math.round((existing.interval_days / MONTH_DAYS) * 10) / 10) : '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');

  const pick = (t: string) => {
    const p = plan.find((x) => x.test === t);
    setTest(t);
    setLow(p?.target_low?.toString() ?? '');
    setHigh(p?.target_high?.toString() ?? '');
    setMargin(p?.review_margin?.toString() ?? '');
    setInterval_(p?.interval_days ? String(Math.round((p.interval_days / MONTH_DAYS) * 10) / 10) : '');
    setError('');
    setSaved('');
  };

  const save = async (clear: boolean) => {
    setBusy(true);
    setError('');
    setSaved('');
    try {
      const intervalMonths = clear ? null : numOrNull(interval);
      await api.savePlanItem(patientId, test, {
        target_low: clear ? null : numOrNull(low),
        target_high: clear ? null : numOrNull(high),
        review_margin: clear ? null : numOrNull(margin),
        interval_days: intervalMonths === null ? null : Math.round(intervalMonths * MONTH_DAYS),
      });
      if (clear) pick(test);
      await onChanged();
      setSaved(clear ? 'Removed.' : 'Saved.');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="plan">
      <div className="table-wrap">
        <table className="results">
          <thead>
            <tr>
              <th scope="col">Test</th>
              <th scope="col">Last done</th>
              <th scope="col">Repeat</th>
              <th scope="col">Next due</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {schedule.map((r) => (
              <tr key={r.key}>
                <th scope="row">{r.label}</th>
                <td>{r.last_date ? fmtDate(r.last_date) : 'No record'}</td>
                <td>{r.interval_set_by_doctor ? months(r.interval_days) : 'not set by the doctor'}</td>
                <td>{r.due_date ? fmtDate(r.due_date) : '–'}</td>
                <td>
                  <span className={`stamp ${STATUS_STAMP[r.status]}`}>{r.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form
        className="plan-form no-print"
        onSubmit={(e) => {
          e.preventDefault();
          void save(false);
        }}
      >
        <h3>Set numbers for this patient</h3>
        <p className="muted small">
          These are the doctor&rsquo;s numbers. MediKiosk-DM suggests no targets or intervals, and a blank field means
          none is set. A review margin turns on a &ldquo;change from own baseline&rdquo; check for that test.
        </p>
        <div className="plan-grid">
          <label className="field">
            <span className="field-label">Test</span>
            <select className="input" value={test} onChange={(e) => pick(e.target.value)}>
              {tests.map((t) => (
                <option key={t} value={t}>
                  {TEST_DISPLAY[t]}
                  {plan.some((p) => p.test === t) ? ' (set)' : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Target from</span>
            <input className="input" inputMode="decimal" value={low} onChange={(e) => setLow(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Target to</span>
            <input className="input" inputMode="decimal" value={high} onChange={(e) => setHigh(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Review margin</span>
            <input className="input" inputMode="decimal" value={margin} onChange={(e) => setMargin(e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Repeat every (months)</span>
            <input className="input" inputMode="decimal" value={interval} onChange={(e) => setInterval_(e.target.value)} />
          </label>
        </div>
        <div className="plan-actions">
          <button className="btn btn-primary" type="submit" disabled={busy}>
            Save for this patient
          </button>
          {existing && (
            <button className="btn btn-quiet" type="button" disabled={busy} onClick={() => void save(true)}>
              Remove these numbers
            </button>
          )}
          {saved && (
            <span className="muted" role="status">
              {saved}
            </span>
          )}
        </div>
        {error && (
          <p className="form-error" role="alert">
            <Alert size={20} />
            {error}
          </p>
        )}
      </form>
    </div>
  );
}
