import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import {
  api,
  ApiError,
  type Medication,
  type Observation,
  type PatientSummary,
  type RuleResult,
  type RuleStatus,
  type SummaryDocument,
  type TimelineData,
} from '../api';
import { Alert, Back, Check, Info, Print } from '../components/icons';
import { SourceViewer, type SourceTarget } from '../components/SourceViewer';
import {
  daysBetween,
  fmtDate,
  fmtMonth,
  medDose,
  medKey,
  medName,
  obsDisplay,
  rawDisplay,
  testName,
} from '../format';

const STATUS_STAMP: Record<RuleStatus, { cls: string; label: string }> = {
  flag: { cls: 'stamp-flag', label: 'Doctor to review' },
  missing: { cls: 'stamp-missing', label: 'Missing' },
  check: { cls: 'stamp-check', label: 'To confirm' },
  note: { cls: 'stamp-note', label: 'Note' },
  ok: { cls: 'stamp-ok', label: 'Nothing to report' },
};
const RANK: Record<RuleStatus, number> = { flag: 0, missing: 1, check: 2, note: 3, ok: 4 };

interface Point {
  date: string;
  label: string;
  value: number | null;
  obs: Observation;
}

function series(obs: Observation[] | undefined): Point[] {
  return (obs ?? [])
    .filter((o) => o.obs_date && (o.value_std ?? o.value_num) != null)
    .map((o) => ({ date: o.obs_date as string, label: fmtMonth(o.obs_date), value: o.value_std ?? o.value_num, obs: o }));
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="chart-tip">
      <strong>{obsDisplay(p.obs)}</strong>
      <div>{fmtDate(p.date)}</div>
      <div className="muted">{p.obs.source_org ?? 'unknown lab'}</div>
      {p.obs.converted && <div className="muted">converted from {rawDisplay(p.obs)}</div>}
      <div className="chart-tip-hint">Click the point to open the paper</div>
    </div>
  );
}

interface TrendProps {
  title: string;
  unit: string;
  points: Point[];
  step: number;
  notes: string[];
  onOpen: (o: Observation) => void;
  emptyText: string;
}

/** One lab value over time. Every point is labelled and opens its source paper. */
function Trend({ title, unit, points, step, notes, onOpen, emptyText }: TrendProps) {
  const INK = '#17211e';
  const BOARD = '#0b5b4b';
  return (
    <div className="trend">
      <h3>
        {title} <span className="trend-unit">{unit}</span>
      </h3>
      {points.length === 0 ? (
        <p className="muted">{emptyText}</p>
      ) : (
        <>
          {notes.map((n) => (
            <p key={n} className="trend-note">
              <Info size={16} />
              {n}
            </p>
          ))}
          <div className="trend-chart">
            <ResponsiveContainer>
              <LineChart data={points} margin={{ top: 32, right: 28, bottom: 4, left: 0 }}>
                <CartesianGrid vertical={false} stroke="#d4d9d0" strokeDasharray="2 5" />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 13, fill: '#44524d' }}
                  tickLine={false}
                  axisLine={{ stroke: '#aeb6ac' }}
                  padding={{ left: 24, right: 24 }}
                />
                <YAxis
                  width={40}
                  tick={{ fontSize: 12, fill: '#62706a' }}
                  tickLine={false}
                  axisLine={false}
                  domain={[
                    (min: number) => Math.floor((min - step * 0.4) / step) * step,
                    (max: number) => Math.ceil((max + step * 0.4) / step) * step,
                  ]}
                />
                <Tooltip content={<ChartTooltip />} cursor={false} />
                <Line
                  type="linear"
                  dataKey="value"
                  stroke={BOARD}
                  strokeWidth={3}
                  isAnimationActive={false}
                  activeDot={false}
                  dot={(props: { cx?: number; cy?: number; index?: number; payload?: Point; value?: number }) => {
                    const { cx = 0, cy = 0, index = 0, payload, value } = props;
                    if (!payload) return <g key={index} />;
                    const label = `${obsDisplay(payload.obs)}, ${fmtDate(payload.date)}. Open the source paper.`;
                    return (
                      <g
                        key={index}
                        className="pt"
                        role="button"
                        tabIndex={0}
                        aria-label={label}
                        onClick={() => onOpen(payload.obs)}
                        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onOpen(payload.obs)}
                      >
                        <circle cx={cx} cy={cy} r={18} fill="transparent" />
                        <circle
                          cx={cx}
                          cy={cy}
                          r={payload.obs.converted ? 6.5 : 6}
                          fill={payload.obs.converted ? '#ffffff' : BOARD}
                          stroke={BOARD}
                          strokeWidth={3}
                        />
                        <text
                          x={cx}
                          y={cy - 15}
                          textAnchor="middle"
                          fontSize={15}
                          fontWeight={800}
                          fill={INK}
                          stroke="#f2f3ee"
                          strokeWidth={4}
                          paintOrder="stroke"
                        >
                          {value}
                        </text>
                      </g>
                    );
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}

/** Groups prescription rows by medicine, newest first, so repeated prescriptions show once. */
function groupMeds(meds: Medication[]) {
  const groups = new Map<string, Medication[]>();
  for (const m of meds.filter((x) => x.source === 'rx')) {
    const k = medKey(m);
    groups.set(k, [...(groups.get(k) ?? []), m]);
  }
  return [...groups.values()].map((rows) =>
    rows.sort((a, b) => (b.rx_date ?? '').localeCompare(a.rx_date ?? '') || b.id - a.id),
  );
}

export function DoctorDashboardPage() {
  const { id } = useParams();
  const patientId = Number(id);

  const [summary, setSummary] = useState<PatientSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [loadError, setLoadError] = useState('');
  const [note, setNote] = useState('');
  const [noteStatus, setNoteStatus] = useState('');
  const savedNote = useRef<string | null>(null);
  const [sourceTarget, setSourceTarget] = useState<SourceTarget | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [sum, tl] = await Promise.all([api.getSummary(patientId), api.getTimeline(patientId)]);
      setSummary(sum);
      setTimeline(tl);
      if (savedNote.current === null) {
        savedNote.current = sum.doctor_note || '';
        setNote(sum.doctor_note || '');
      }
      setLoadError('');
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : String(e));
    }
  }, [patientId]);

  useEffect(() => {
    savedNote.current = null;
    if (Number.isInteger(patientId)) void loadData();
    else setLoadError('Not a valid patient id.');
  }, [patientId, loadData]);

  // Autosave the note half a second after typing stops.
  useEffect(() => {
    if (savedNote.current === null || note === savedNote.current) return;
    setNoteStatus('Unsaved…');
    const timer = setTimeout(async () => {
      try {
        await api.saveDoctorNote(patientId, note);
        savedNote.current = note;
        setNoteStatus('Saved');
      } catch (e) {
        setNoteStatus(`Not saved: ${e instanceof Error ? e.message : e}`);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [note, patientId]);

  const allObs = useMemo(() => Object.values(timeline?.observations_by_test ?? {}).flat(), [timeline]);
  const closeSource = useCallback(() => setSourceTarget(null), []);

  if (loadError) {
    return (
      <main className="desk">
        <div className="banner banner-error" role="alert">
          <Alert size={20} />
          <span>Could not load this patient. {loadError}</span>
        </div>
        <p style={{ marginTop: 16 }}>
          <Link to="/doctor">Back to all patients</Link>
        </p>
      </main>
    );
  }
  if (!summary || !timeline) {
    return (
      <main className="desk">
        <p className="muted" role="status">
          Loading the summary…
        </p>
      </main>
    );
  }

  const obsTarget = (o: Observation): SourceTarget => ({
    kind: 'observation',
    id: o.id,
    title: `${testName(o)} · ${fmtDate(o.obs_date)}`,
    valueDisplay: obsDisplay(o),
    rawDisplay: rawDisplay(o),
    documentId: o.document_id,
    pageNo: o.page_no ?? 1,
    pageW: o.page_w,
    pageH: o.page_h,
    bbox: o.bbox ?? null,
    blockText: o.block_text,
    unverified: o.unverified,
    uncertain: o.uncertain,
    note: o.note,
    verifiedByClinician: o.verified_by_clinician,
    editedValue: o.edited_value,
    sourceOrg: o.source_org ?? null,
    sourceMode: o.source_mode,
  });

  const medTarget = (m: Medication): SourceTarget | null =>
    m.document_id
      ? {
          kind: 'medication',
          id: m.id,
          title: `${medName(m)} (${m.name_as_written}) · ${fmtDate(m.rx_date)}`,
          valueDisplay: medDose(m),
          documentId: m.document_id,
          pageNo: m.page_no ?? 1,
          pageW: m.page_w,
          pageH: m.page_h,
          bbox: m.bbox ?? null,
          blockText: m.block_text,
          unverified: m.unverified,
          uncertain: m.uncertain,
          note: m.note,
          verifiedByClinician: m.verified_by_clinician,
          editedValue: m.edited_value,
          sourceOrg: m.source_org ?? null,
          sourceMode: m.source_mode,
        }
      : null;

  const docTarget = (d: SummaryDocument): SourceTarget => ({
    kind: 'document',
    id: d.id,
    title: d.source_org ?? d.original_filename ?? `Document ${d.id}`,
    valueDisplay: '',
    documentId: d.id,
    pageNo: 1,
    bbox: null,
    unverified: false,
    verifiedByClinician: false,
    editedValue: null,
    sourceOrg: d.source_org,
    sourceMode: d.source_mode,
  });

  const openRef = (ref: string) => {
    const [kind, idStr] = ref.split(':');
    const refId = Number(idStr);
    if (kind === 'obs') {
      const o = allObs.find((x) => x.id === refId);
      if (o) setSourceTarget(obsTarget(o));
    } else if (kind === 'med') {
      const m = summary.medications.find((x) => x.id === refId);
      const t = m && medTarget(m);
      if (t) setSourceTarget(t);
    }
  };
  const refLabel = (ref: string): string | null => {
    const [kind, idStr] = ref.split(':');
    const refId = Number(idStr);
    if (kind === 'obs') {
      const o = allObs.find((x) => x.id === refId);
      return o ? `${testName(o)} ${obsDisplay(o)}` : null;
    }
    if (kind === 'med') {
      const m = summary.medications.find((x) => x.id === refId);
      return m && m.document_id ? `${m.name_as_written} ${fmtMonth(m.rx_date)}` : null;
    }
    return null;
  };

  const patch = async (target: SourceTarget, body: { edited_value?: string; verified_by_clinician?: boolean }) => {
    if (target.kind === 'observation') await api.patchObservation(target.id, body);
    else if (target.kind === 'medication') await api.patchMedication(target.id, body);
    await loadData();
    setSourceTarget(null);
  };

  const rules = [...summary.rules].sort((a, b) => RANK[a.status] - RANK[b.status]);
  const attention = rules.filter((r) => r.status !== 'ok');
  const allGood = rules.filter((r) => r.status === 'ok');

  const hba1c = series(timeline.observations_by_test['hba1c']);
  const fbs = series(timeline.observations_by_test['fasting_glucose']);
  const hba1cNotes: string[] = [];
  for (let i = 1; i < hba1c.length; i++) {
    if (daysBetween(hba1c[i - 1].date, hba1c[i].date) > 365) {
      hba1cNotes.push(`No HbA1c in the papers from ${fmtMonth(hba1c[i - 1].date)} to ${fmtMonth(hba1c[i].date)}.`);
    }
  }
  const fbsNotes = fbs.some((p) => p.obs.converted)
    ? ['Hollow point: the paper gave mmol/L, converted here to mg/dL (× 18.016). Both values are kept.']
    : [];

  const medGroups = groupMeds(summary.medications);
  const rxKeys = new Set(medGroups.map((g) => medKey(g[0])));
  const intakeOnly = summary.medications.filter((m) => m.source === 'intake' && !rxKeys.has(medKey(m)));

  const failedDocs = summary.documents.filter((d) => d.status === 'failed');
  const scripted = summary.documents.some((d) => d.source_mode === 'scripted');
  const cap = (x: string) => (x ? x.charAt(0).toUpperCase() + x.slice(1) : x);

  const renderRule = (r: RuleResult) => {
    const st = STATUS_STAMP[r.status];
    const chips = r.evidence_refs.map((ref) => ({ ref, label: refLabel(ref) })).filter((c) => c.label);
    return (
      <li key={r.rule_id} className="flag">
        <div className="flag-tag">
          <span className={`stamp ${st.cls}`}>{st.label}</span>
        </div>
        <div className="flag-body">
          <h3>{r.name}</h3>
          <p className="flag-q">{r.question}</p>
          <p className="flag-ev">{r.evidence_text}</p>
          {chips.length > 0 && (
            <p className="flag-src">
              {chips.map((c) => (
                <button key={c.ref} className="mark" onClick={() => openRef(c.ref)}>
                  {c.label}
                </button>
              ))}
            </p>
          )}
        </div>
      </li>
    );
  };

  return (
    <main className="desk">
      <header className="desk-head">
        <div>
          <Link to="/doctor" className="crumb no-print">
            <Back size={18} />
            All patients
          </Link>
          <h1>
            {summary.patient.display_name}
            <span className="desk-age">, {summary.patient.age} years</span>
          </h1>
          <p className="desk-meta">
            Answered the kiosk in {summary.patient.language === 'hi' ? 'Hindi' : 'English'}. Rules checked as of{' '}
            {fmtDate(summary.today)}.
          </p>
          <p className="desk-disclaimer">{summary.disclaimer}</p>
        </div>
        <button className="btn btn-quiet no-print" onClick={() => window.print()}>
          <Print size={20} />
          Print this page
        </button>
      </header>

      {(scripted || failedDocs.length > 0) && (
        <div className="desk-banners">
          {scripted && (
            <div className="banner banner-info">
              <Info size={20} />
              <span>
                Offline demo data. The report values on this page were entered from the synthetic answer key, not read
                by AI. Load the demo with NVIDIA to see real extraction.
              </span>
            </div>
          )}
          {failedDocs.length > 0 && (
            <div className="banner banner-warn">
              <Alert size={20} />
              <span>
                {failedDocs.length === 1
                  ? '1 paper could not be read, so its values are missing below.'
                  : `${failedDocs.length} papers could not be read, so their values are missing below.`}{' '}
                Check them by hand in the list of papers.
              </span>
            </div>
          )}
        </div>
      )}

      <div className="desk-grid">
        <div className="desk-main">
          <section className="sec" aria-labelledby="h-attn">
            <h2 id="h-attn">Needs attention</h2>
            <p className="sec-note">
              {attention.length === 0 ? 'Nothing was flagged. ' : `${attention.length} of ${rules.length} checks. `}
              These are fixed rules in plain code, not AI. Thresholds are drafts that a doctor must review.
            </p>
            {attention.length > 0 && <ul className="flags">{attention.map(renderRule)}</ul>}
            {allGood.length > 0 && (
              <details className="clear">
                <summary>
                  <Check size={18} strokeWidth={3} />
                  {allGood.length} {allGood.length > 1 ? 'checks have' : 'check has'} nothing to report
                </summary>
                <ul className="flags flags-quiet">{allGood.map(renderRule)}</ul>
              </details>
            )}
          </section>

          <section className="sec" aria-labelledby="h-trend">
            <h2 id="h-trend">Trends</h2>
            <p className="sec-note no-print">Click any point to open the paper it came from.</p>
            <div className="trends">
              <Trend
                title="HbA1c"
                unit="%"
                step={1}
                points={hba1c}
                notes={hba1cNotes}
                onOpen={(o) => setSourceTarget(obsTarget(o))}
                emptyText="No HbA1c was found in the papers."
              />
              <Trend
                title="Fasting glucose"
                unit="mg/dL"
                step={20}
                points={fbs}
                notes={fbsNotes}
                onOpen={(o) => setSourceTarget(obsTarget(o))}
                emptyText="No fasting glucose was found in the papers."
              />
            </div>
          </section>

          <section className="sec" aria-labelledby="h-latest">
            <h2 id="h-latest">Latest results</h2>
            <p className="sec-note no-print">
              A highlighted value opens the original paper with the line marked. A dotted red line means the AI could not
              find the exact place.
            </p>
            {summary.latest_results.length === 0 ? (
              <p className="muted">No test results were read from the papers.</p>
            ) : (
              <div className="table-wrap">
                <table className="results">
                  <thead>
                    <tr>
                      <th scope="col">Test</th>
                      <th scope="col">Result</th>
                      <th scope="col">Date</th>
                      <th scope="col">Lab</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.latest_results.map((o) => (
                      <tr key={o.id}>
                        <th scope="row">{testName(o)}</th>
                        <td>
                          <button
                            className={`mark res-val ${o.unverified && !o.verified_by_clinician ? 'mark-loose' : ''}`}
                            onClick={() => setSourceTarget(obsTarget(o))}
                          >
                            {obsDisplay(o)}
                          </button>
                          {o.edited_value && (
                            <div className="res-note">Corrected by the doctor. The AI read {rawDisplay(o)}.</div>
                          )}
                          {!o.edited_value && o.converted && <div className="res-note">Converted from {rawDisplay(o)}</div>}
                          <div className="res-stamps">
                            {o.uncertain && !o.verified_by_clinician && <span className="stamp stamp-check">Unsure reading</span>}
                            {o.unverified && !o.verified_by_clinician && <span className="stamp stamp-missing">No exact source</span>}
                            {o.verified_by_clinician && <span className="stamp stamp-ok">Checked by doctor</span>}
                          </div>
                        </td>
                        <td>{fmtDate(o.obs_date)}</td>
                        <td>{o.source_org ?? 'Unknown'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="sec" aria-labelledby="h-meds">
            <h2 id="h-meds">Medicines</h2>
            <p className="sec-note">From the prescriptions, compared with what the patient named today.</p>
            {medGroups.length === 0 && intakeOnly.length === 0 ? (
              <p className="muted">No medicines were found on the papers or named by the patient.</p>
            ) : (
              <ul className="meds">
                {medGroups.map((rows) => {
                  const latest = rows[0];
                  const target = medTarget(latest);
                  const status = latest.intake_status ?? '';
                  return (
                    <li key={latest.id} className="med">
                      <div className="med-main">
                        <h3>
                          {medName(latest)}
                          {latest.generic_name && <span className="med-brand"> ({latest.name_as_written})</span>}
                        </h3>
                        <p>
                          {target ? (
                            <button className="mark" onClick={() => setSourceTarget(target)}>
                              {medDose(latest)}
                            </button>
                          ) : (
                            medDose(latest)
                          )}
                          <span className="muted">
                            {' '}
                            Last prescribed {fmtDate(latest.rx_date)}
                            {latest.source_org ? ` by ${latest.source_org}` : ''}.
                          </span>
                        </p>
                        {rows.length > 1 && (
                          <p className="muted small">
                            Also on prescriptions from {rows.slice(1).map((r) => fmtMonth(r.rx_date)).join(', ')}.
                          </p>
                        )}
                        {latest.note && <p className="muted small">Note: {latest.note}</p>}
                      </div>
                      <span className={`stamp med-stamp ${status === 'confirmed today' ? 'stamp-ok' : 'stamp-check'}`}>
                        {cap(status)}
                      </span>
                    </li>
                  );
                })}
                {intakeOnly.map((m) => (
                  <li key={m.id} className="med">
                    <div className="med-main">
                      <h3>
                        {medName(m)}
                        {m.generic_name && <span className="med-brand"> ({m.name_as_written})</span>}
                      </h3>
                      <p className="muted">{m.frequency ?? 'Frequency not given'}. Named by the patient today.</p>
                    </div>
                    <span className="stamp stamp-check med-stamp">No prescription found</span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="sec" aria-labelledby="h-docs">
            <h2 id="h-docs">Papers ({summary.documents.length})</h2>
            {summary.documents.length === 0 ? (
              <p className="muted">No reports or prescriptions were uploaded.</p>
            ) : (
              <ul className="papers">
                {summary.documents.map((d) => (
                  <li key={d.id} className="paper-row">
                    <button className="mark" onClick={() => setSourceTarget(docTarget(d))}>
                      {d.source_org ?? d.original_filename ?? `Document ${d.id}`}
                    </button>
                    <span className="muted">
                      {d.kind === 'rx' ? 'Prescription' : d.kind === 'lab' ? 'Lab report' : 'Document'}, {fmtDate(d.doc_date)}
                    </span>
                    <span className="paper-state">
                      {d.status === 'done' && `${d.n_observations} results, ${d.n_medications} medicines`}
                      {d.status === 'failed' && <span className="paper-fail">Could not be read: {d.error}</span>}
                      {d.status === 'pending' && 'Still being read…'}
                      {d.source_mode === 'scripted' && ' (offline demo values)'}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <aside className="desk-rail" aria-label="The patient's words and your notes">
          <section className="rail-sec" aria-labelledby="h-said">
            <h2 id="h-said">What the patient said</h2>
            <p className="sec-note">Confirmed by the patient at the kiosk.</p>
            {summary.answers_display.length === 0 ? (
              <p className="muted">The patient has not answered any questions yet.</p>
            ) : (
              <dl className="said">
                {summary.answers_display.map((a) => (
                  <div key={a.question_id} className="said-row">
                    <dt>{a.topic}</dt>
                    <dd>
                      {a.answer}
                      {a.patient_words && <span className="said-words hand">&ldquo;{a.patient_words}&rdquo;</span>}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
            {summary.unanswered_topics.length > 0 && (
              <p className="muted small said-missing">Not answered: {summary.unanswered_topics.join(', ')}.</p>
            )}
          </section>

          <section className="rail-sec" aria-labelledby="h-note">
            <div className="note-head">
              <h2 id="h-note">Your notes</h2>
              <span className="note-status no-print" role="status">
                {noteStatus}
              </span>
            </div>
            <label className="visually-hidden" htmlFor="doctor-note">
              Consultation notes
            </label>
            <textarea
              id="doctor-note"
              className="note-area no-print"
              rows={8}
              value={note}
              maxLength={10000}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Type consultation notes here. They save as you type."
            />
            <p className="print-only note-print">{note}</p>
          </section>
        </aside>
      </div>

      <SourceViewer
        target={sourceTarget}
        onClose={closeSource}
        onVerify={(t) => patch(t, { verified_by_clinician: true })}
        onSaveEdit={(t, edited) => patch(t, { edited_value: edited, verified_by_clinician: true })}
      />
    </main>
  );
}
