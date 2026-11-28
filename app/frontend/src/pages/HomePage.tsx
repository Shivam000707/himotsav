import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, ApiError, type Health } from '../api';
import { Alert } from '../components/icons';

type Mode = 'live' | 'cached' | 'scripted';

/** The product promise drawn once: a line on a lab slip, and the doctor's row it becomes. */
function Proof() {
  return (
    <figure className="proof">
      <div className="proof-paper" aria-hidden="true">
        <div className="proof-head">
          <strong>Valley Diagnostics</strong>
          <span>Date: 12 Aug 2026</span>
        </div>
        <div className="proof-line">
          <span>Test</span>
          <span>Result</span>
        </div>
        <div className="proof-line proof-target">
          <span className="proof-swipe">HbA1c</span>
          <span className="proof-swipe">8.9 %</span>
        </div>
        <div className="proof-line">
          <span>Fasting glucose</span>
          <span>176 mg/dL</span>
        </div>
      </div>
      <svg className="proof-link" viewBox="0 0 40 56" aria-hidden="true">
        <path d="M20 2 V46 M12 38 L20 48 L28 38" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="proof-row">
        <span className="proof-name">HbA1c</span>
        <span className="mark proof-mark">8.9 %</span>
        <span className="proof-meta">Valley Diagnostics, 12 Aug 2026</span>
      </div>
      <figcaption>
        On the doctor&rsquo;s page the value is highlighted. Clicking it opens the original paper with the same line
        marked. Ramesh ji is a made-up patient.
      </figcaption>
    </figure>
  );
}

export function HomePage() {
  const nav = useNavigate();
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState('');
  const [loading, setLoading] = useState<Mode | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e) => setHealthError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  const seed = async (mode: Mode) => {
    setLoading(mode);
    setError(null);
    try {
      const res = await api.seedDemo(mode);
      nav(`/doctor/${res.patient_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(null);
    }
  };

  const addPersonas = async () => {
    setError(null);
    try {
      await api.seedPersonas();
      nav('/doctor');
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  };

  const keyReady = !!health?.nvidia_key_present;
  const publicDemo = !!health?.public_demo;

  return (
    <main className="home">
      <section className="home-hero">
        <div className="home-copy">
          <h1>Every number the doctor sees points back to the paper it came from.</h1>
          <p className="home-lede">
            While a diabetes patient waits, MediKiosk-DM asks for their history in Hindi or English and reads their old
            reports. The doctor gets one page. Each value opens the original paper at the line it was read from.
          </p>
          <div className="home-doors">
            <Link className="door door-main" to="/kiosk">
              <span className="door-title">Start as a patient</span>
              <span className="door-sub">
                Answer 8 questions and add old reports. <span lang="hi">हिन्दी या English</span>
              </span>
            </Link>
            <Link className="door" to="/doctor">
              <span className="door-title">Open the doctor&rsquo;s desk</span>
              <span className="door-sub">See each patient&rsquo;s summary, trends and source papers.</span>
            </Link>
          </div>
        </div>
        <Proof />
      </section>

      <section className="home-lower">
        <div className="home-demo">
          <h2>Try it with a demo patient</h2>
          <p className="muted page-note">
            Ramesh ji is 58, takes metformin, and brings 7 old papers from 3 labs and 2 clinics. One lab reports sugar in
            mmol/L and one dose is smudged.
          </p>

          {publicDemo ? (
            <div className="demo-actions">
              <button className="btn btn-primary" disabled={!!loading} onClick={() => seed('cached')}>
                {loading === 'cached' ? 'Loading…' : 'Open the demo patient'}
              </button>
              <p className="small muted page-note">
                This public demo shows replies that NVIDIA&rsquo;s AI gave when it read these 7 papers. Live reading and
                uploads are switched off here so nobody can spend the project&rsquo;s API key. The patient kiosk still
                works: answer the questions, then open the doctor&rsquo;s desk to see them.
              </p>
            </div>
          ) : (
            <div className="demo-actions">
              <button className="btn btn-primary" disabled={!!loading || !keyReady} onClick={() => seed('live')}>
                {loading === 'live' ? 'Reading the 7 papers with NVIDIA AI…' : 'Read the 7 papers with NVIDIA AI'}
              </button>
              {loading === 'live' && (
                <p className="small muted">The first run takes up to 2 minutes. Later runs use the saved replies.</p>
              )}
              {!keyReady && health && (
                <p className="small muted">
                  This needs a key. Add <code>NVIDIA_API_KEY</code> to <code>app/backend/.env</code>, then restart the backend.
                </p>
              )}
              <div className="demo-alt">
                <button className="btn btn-quiet" disabled={!!loading} onClick={() => seed('cached')}>
                  {loading === 'cached' ? 'Loading…' : 'Use saved AI replies (offline)'}
                </button>
                <button className="btn btn-quiet" disabled={!!loading} onClick={() => seed('scripted')}>
                  {loading === 'scripted' ? 'Loading…' : 'Use backup values (no AI)'}
                </button>
                <button className="btn btn-quiet" disabled={!!loading} onClick={addPersonas}>
                  Add 2 more demo patients
                </button>
              </div>
              <p className="small muted page-note">
                Backup values come from the synthetic answer key, and the doctor&rsquo;s page says so. Use them only when
                there is no key or no internet. The 2 extra patients (Mohan Lal and Kavita Sharma) are made up and use
                backup values too: one has a medicine change and a falling HbA1c, the other a steady year and then a jump.
              </p>
            </div>
          )}

          {error && (
            <div className="banner banner-error" role="alert">
              <Alert size={20} />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="home-check">
          <h2>System check</h2>
          <ul className="checklist" aria-live="polite">
            {healthError && (
              <li className="check-bad">
                <span className="dot" />
                <span>
                  Backend not reachable. {healthError}
                </span>
              </li>
            )}
            {!health && !healthError && (
              <li>
                <span className="dot dot-wait" />
                <span>Checking…</span>
              </li>
            )}
            {health && (
              <>
                {publicDemo ? (
                  <li className="check-ok">
                    <span className="dot" />
                    <span>Public demo: saved AI replies, no live calls.</span>
                  </li>
                ) : (
                  <li className={keyReady ? 'check-ok' : 'check-bad'}>
                    <span className="dot" />
                    <span>{keyReady ? 'NVIDIA key is set.' : 'NVIDIA key is missing, so only the offline options work.'}</span>
                  </li>
                )}
                <li className={health.asr_configured ? 'check-ok' : 'check-wait'}>
                  <span className="dot" />
                  <span>
                    {health.asr_configured
                      ? 'Voice answers use NVIDIA speech-to-text.'
                      : 'Voice answers use the browser (Chrome or Edge), or the patient types.'}
                  </span>
                </li>
                <li className="check-ok">
                  <span className="dot" />
                  <span>
                    Rules are checked as of {health.today}
                    {health.demo_today_set ? ' (set by DEMO_TODAY).' : '.'}
                  </span>
                </li>
              </>
            )}
          </ul>
        </div>
      </section>
    </main>
  );
}
