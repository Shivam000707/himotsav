import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, type Patient } from '../api';
import { Alert } from '../components/icons';
import { fmtDate } from '../format';

export function DoctorListPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api
      .listPatients()
      .then(setPatients)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="desk desk-narrow">
      <header className="desk-head">
        <div>
          <h1>Patients</h1>
          <p className="desk-meta">Everyone who has used the kiosk, newest first.</p>
        </div>
      </header>

      {loading ? (
        <p className="muted" role="status">
          Loading patients…
        </p>
      ) : error ? (
        <div className="banner banner-error" role="alert">
          <Alert size={20} />
          <span>Could not load the patient list. {error}</span>
        </div>
      ) : patients.length === 0 ? (
        <div className="empty">
          <h2>No patients yet</h2>
          <p className="muted page-note">
            A patient appears here after they finish the kiosk. To see the doctor&rsquo;s page right away, load the demo
            patient from the home page.
          </p>
          <div className="empty-actions">
            <Link to="/" className="btn btn-primary">
              Load the demo patient
            </Link>
            <Link to="/kiosk" className="btn btn-quiet">
              Open the patient kiosk
            </Link>
          </div>
        </div>
      ) : (
        <ul className="register">
          {patients.map((p) => (
            <li key={p.id}>
              <Link to={`/doctor/${p.id}`} className="reg-row">
                <span className="reg-name">{p.display_name}</span>
                <span className="reg-meta">
                  Age {p.age}, {p.language === 'hi' ? 'Hindi' : 'English'}
                </span>
                <span className="reg-date">Checked in {fmtDate(p.created_at)}</span>
                <span className="reg-open">Open summary</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
