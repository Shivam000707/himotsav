import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, type Patient } from '../api';

export function DoctorListPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .listPatients()
      .then(setPatients)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="page-container">
      <div className="top-row">
        <h1>Doctor Dashboard — Patients</h1>
        <Link to="/" className="btn-secondary">
          Home
        </Link>
      </div>

      {loading ? (
        <p>Loading patients…</p>
      ) : patients.length === 0 ? (
        <div className="card">
          <p>No patients yet. Use the Kiosk or load the demo patient from Home.</p>
        </div>
      ) : (
        <div className="patient-list">
          {patients.map((p) => (
            <Link key={p.id} to={`/doctor/${p.id}`} className="patient-row card">
              <div>
                <strong>{p.display_name}</strong>
                <div className="muted">
                  Age {p.age} · Language: {p.language.toUpperCase()}
                </div>
              </div>
              <span className="btn-primary">Open summary →</span>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
