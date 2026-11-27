import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  api,
  type Medication,
  type Observation,
  type PatientSummary,
  type RuleResult,
  type TimelineData,
} from '../api';
import { SourceViewer, type SourceTarget } from '../components/SourceViewer';

const STATUS_BADGE: Record<RuleResult['status'], { cls: string; label: string }> = {
  flag: { cls: 'badge-flag', label: 'Doctor to review' },
  missing: { cls: 'badge-missing', label: 'Missing' },
  check: { cls: 'badge-check', label: 'To confirm' },
  note: { cls: 'badge-note', label: 'Note' },
  ok: { cls: 'badge-ok', label: 'All good' },
};

const TEST_DISPLAY: Record<string, string> = {
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

function obsDisplay(o: Observation): string {
  if (o.edited_value) return o.edited_value;
  if (o.value_std != null && o.unit_std) return `${o.value_std} ${o.unit_std}`;
  return `${o.value_raw}${o.unit_raw ? ` ${o.unit_raw}` : ''}`;
}

export function DoctorDashboardPage() {
  const { id } = useParams();
  const patientId = Number(id);

  const [summary, setSummary] = useState<PatientSummary | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [note, setNote] = useState('');
  const [noteStatus, setNoteStatus] = useState('');
  const [sourceTarget, setSourceTarget] = useState<SourceTarget | null>(null);

  const loadData = useCallback(async () => {
    const [sum, tl] = await Promise.all([
      api.getSummary(patientId),
      api.getTimeline(patientId),
    ]);
    setSummary(sum);
    setTimeline(tl);
    setNote(sum.doctor_note || '');
  }, [patientId]);

  useEffect(() => {
    if (!Number.isNaN(patientId)) {
      loadData();
    }
  }, [patientId, loadData]);

  useEffect(() => {
    if (!summary) return;
    if (note === (summary.doctor_note || '')) return;
    const t = setTimeout(async () => {
      setNoteStatus('Saving…');
      await api.saveDoctorNote(patientId, note);
      setNoteStatus('Saved');
    }, 500);
    return () => clearTimeout(t);
  }, [note, patientId, summary]);

  const openObsSource = (o: Observation) => {
    setSourceTarget({
      kind: 'observation',
      id: o.id,
      title: TEST_DISPLAY[o.test] ?? o.label_as_written,
      valueDisplay: obsDisplay(o),
      documentId: o.document_id,
      pageNo: o.page_no ?? 1,
      bbox: o.bbox ?? null,
      unverified: o.unverified,
      verifiedByClinician: o.verified_by_clinician,
      editedValue: o.edited_value,
      sourceOrg: o.source_org ?? null,
    });
  };

  const openMedSource = (m: Medication) => {
    if (!m.document_id) return;
    setSourceTarget({
      kind: 'medication',
      id: m.id,
      title: m.generic_name ? `${m.generic_name} (${m.name_as_written})` : m.name_as_written,
      valueDisplay: m.edited_value ?? `${m.strength ?? ''} ${m.frequency ?? ''}`.trim(),
      documentId: m.document_id,
      pageNo: m.page_no ?? 1,
      bbox: m.bbox ?? null,
      unverified: m.unverified,
      verifiedByClinician: m.verified_by_clinician,
      editedValue: m.edited_value,
      sourceOrg: m.source_org ?? null,
    });
  };

  const handleVerify = async (target: SourceTarget) => {
    if (target.kind === 'observation') {
      await api.patchObservation(target.id, { verified_by_clinician: true });
    } else {
      await api.patchMedication(target.id, { verified_by_clinician: true });
    }
    await loadData();
    setSourceTarget(null);
  };

  const handleSaveEdit = async (target: SourceTarget, edited: string) => {
    if (target.kind === 'observation') {
      await api.patchObservation(target.id, { edited_value: edited, verified_by_clinician: true });
    } else {
      await api.patchMedication(target.id, { edited_value: edited, verified_by_clinician: true });
    }
    await loadData();
    setSourceTarget(null);
  };

  if (!summary || !timeline) {
    return <main className="page-container">Loading doctor summary…</main>;
  }

  const orderedRules = [...summary.rules].sort((a, b) => {
    const rank = { flag: 0, missing: 1, check: 2, note: 3, ok: 4 };
    return rank[a.status] - rank[b.status];
  });

  const hba1cSeries = (timeline.observations_by_test['hba1c'] || []).map((o) => ({
    date: o.obs_date ?? 'Unknown',
    value: o.value_std ?? o.value_num,
    lab: o.source_org ?? '',
    converted: o.converted,
  }));

  const fbsSeries = (timeline.observations_by_test['fasting_glucose'] || []).map((o) => ({
    date: o.obs_date ?? 'Unknown',
    value: o.value_std ?? o.value_num,
    lab: o.source_org ?? '',
    converted: o.converted,
  }));

  // Check >12 month HbA1c gaps
  const hba1cGaps: string[] = [];
  for (let i = 1; i < hba1cSeries.length; i++) {
    const d1 = new Date(hba1cSeries[i - 1].date);
    const d2 = new Date(hba1cSeries[i].date);
    const months = (d2.getTime() - d1.getTime()) / (1000 * 60 * 60 * 24 * 30.4);
    if (months > 12) {
      hba1cGaps.push(`No HbA1c from ${hba1cSeries[i - 1].date} to ${hba1cSeries[i].date}`);
    }
  }

  const rxMeds = summary.medications.filter((m) => m.source === 'rx');

  return (
    <main className="page-container">
      <header className="doc-header card">
        <div>
          <div className="muted no-print">
            <Link to="/doctor">← All patients</Link>
          </div>
          <h1>
            {summary.patient.display_name} · {summary.patient.age} yrs
          </h1>
          <p className="muted">
            Preferred language: {summary.patient.language.toUpperCase()} · {summary.disclaimer}
          </p>
        </div>
        <div className="no-print">
          <button className="btn-primary" onClick={() => window.print()}>
            Print A4 summary
          </button>
        </div>
      </header>

      <section className="card">
        <h2>Needs attention (deterministic rules)</h2>
        <div className="rules-grid">
          {orderedRules.map((r) => {
            const b = STATUS_BADGE[r.status];
            return (
              <div key={r.rule_id} className={`rule-card status-${r.status}`}>
                <div className="rule-top">
                  <strong>{r.name}</strong>
                  <span className={`badge ${b.cls}`}>{b.label}</span>
                </div>
                <p className="rule-ev">{r.evidence_text}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="grid-2">
        <div className="card">
          <h2>HbA1c trend (%)</h2>
          {hba1cGaps.map((g) => (
            <p key={g} className="gap-note">
              {g}
            </p>
          ))}
          <div style={{ width: '100%', height: 220 }}>
            <ResponsiveContainer>
              <LineChart data={hba1cSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={['auto', 'auto']} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#5243C2" strokeWidth={2.5} dot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h2>Fasting glucose trend (mg/dL)</h2>
          <div style={{ width: '100%', height: 220 }}>
            <ResponsiveContainer>
              <LineChart data={fbsSeries}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis domain={['auto', 'auto']} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#0B6E66"
                  strokeWidth={2.5}
                  dot={(props: { cx?: number; cy?: number; payload?: { converted?: boolean } }) => {
                    const { cx = 0, cy = 0, payload } = props;
                    return payload?.converted ? (
                      <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={6} fill="#fff" stroke="#0B6E66" strokeWidth={3} />
                    ) : (
                      <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={4} fill="#0B6E66" />
                    );
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>Latest lab results (click any source chip to verify)</h2>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Test</th>
                <th>Value</th>
                <th>Date</th>
                <th>Lab</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {summary.latest_results.map((o) => (
                <tr key={o.id}>
                  <td>{TEST_DISPLAY[o.test] ?? o.label_as_written}</td>
                  <td>
                    <strong>{obsDisplay(o)}</strong>
                    {o.converted && (
                      <div className="muted small">
                        converted from {o.value_raw} {o.unit_raw}
                      </div>
                    )}
                    {o.uncertain && <span className="badge badge-check">uncertain</span>}
                  </td>
                  <td>{o.obs_date ?? '—'}</td>
                  <td>{o.source_org ?? '—'}</td>
                  <td>
                    <button className="source-chip" onClick={() => openObsSource(o)}>
                      {o.verified_by_clinician ? '✓ Verified' : 'View source'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>Medicines</h2>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Medicine</th>
                <th>Strength</th>
                <th>Frequency</th>
                <th>Status</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {rxMeds.map((m) => (
                <tr key={m.id}>
                  <td>
                    <strong>{m.generic_name ?? m.name_as_written}</strong>
                    {m.generic_name && <span className="muted"> ({m.name_as_written})</span>}
                  </td>
                  <td>{m.edited_value ?? m.strength ?? '—'}</td>
                  <td>{m.frequency ?? '—'}</td>
                  <td>
                    <span className={`badge ${m.intake_status === 'confirmed today' ? 'badge-ok' : 'badge-check'}`}>
                      {m.intake_status}
                    </span>
                  </td>
                  <td>
                    {m.document_id ? (
                      <button className="source-chip" onClick={() => openMedSource(m)}>
                        {m.verified_by_clinician ? '✓ Verified' : 'View source'}
                      </button>
                    ) : (
                      'Intake'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid-2">
        <div className="card">
          <h2>Patient said (confirmed intake)</h2>
          <ul className="intake-list">
            {summary.answers.map((a) => (
              <li key={a.id}>
                <strong>{a.question_id}:</strong> {a.raw_text || a.value_json}
              </li>
            ))}
          </ul>
          {summary.unanswered_questions.length > 0 && (
            <p className="muted small">
              Unanswered: {summary.unanswered_questions.join(', ')}
            </p>
          )}
        </div>

        <div className="card">
          <div className="note-head">
            <h2>Doctor note</h2>
            <span className="muted small">{noteStatus}</span>
          </div>
          <textarea
            className="doc-note-area"
            rows={6}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add consultation notes…"
          />
        </div>
      </section>

      <SourceViewer
        target={sourceTarget}
        onClose={() => setSourceTarget(null)}
        onVerify={handleVerify}
        onSaveEdit={handleSaveEdit}
      />
    </main>
  );
}
