import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';

export function HomePage() {
  const nav = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSeed = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.seedDemo('cached');
      nav(`/doctor/${res.patient_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load demo patient');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="home-wrap">
      <div className="home-card">
        <h1>MediKiosk-DM</h1>
        <p className="muted">
          Type 2 diabetes OPD intake &amp; source-linked report summary. Synthetic demo data only.
        </p>

        <div className="home-actions">
          <button className="btn-kiosk-big" onClick={() => nav('/kiosk')}>
            Patient Kiosk (मरीज़ कियोस्क)
          </button>
          <button className="btn-doc-big" onClick={() => nav('/doctor')}>
            Doctor Dashboard (डॉक्टर डैशबोर्ड)
          </button>
        </div>

        <div className="home-demo">
          <button className="btn-secondary" disabled={loading} onClick={handleSeed}>
            {loading ? 'Loading Ramesh ji…' : 'Load demo patient (Ramesh ji · cached)'}
          </button>
          {error && <p className="err-text">{error}</p>}
        </div>
      </div>
    </main>
  );
}
