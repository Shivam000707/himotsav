import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { DoctorDashboardPage } from './pages/DoctorDashboardPage';
import { DoctorListPage } from './pages/DoctorListPage';
import { HomePage } from './pages/HomePage';
import { KioskPage } from './pages/KioskPage';

export function App() {
  return (
    <BrowserRouter>
      <div className="disclaimer-bar">
        Documentation aid only. Not a diagnosis or treatment advice.
      </div>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/kiosk" element={<KioskPage />} />
        <Route path="/doctor" element={<DoctorListPage />} />
        <Route path="/doctor/:id" element={<DoctorDashboardPage />} />
      </Routes>
    </BrowserRouter>
  );
}
