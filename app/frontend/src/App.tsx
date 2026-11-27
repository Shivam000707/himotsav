import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { Logo } from './components/icons';
import { DoctorDashboardPage } from './pages/DoctorDashboardPage';
import { DoctorListPage } from './pages/DoctorListPage';
import { HomePage } from './pages/HomePage';
import { KioskPage } from './pages/KioskPage';

const DISCLAIMER = 'Documentation aid only. Not a diagnosis or treatment advice.';

/** The kiosk draws its own signboard, so the staff bar and footer are hidden there. */
function Shell() {
  const { pathname } = useLocation();
  const isKiosk = pathname.startsWith('/kiosk');

  return (
    <>
      {!isKiosk && (
        <header className="appbar no-print">
          <div className="appbar-inner">
            <Link to="/" className="brand">
              <Logo />
              MediKiosk-DM
            </Link>
            <nav className="appnav" aria-label="Main">
              <NavLink to="/kiosk">Patient kiosk</NavLink>
              <NavLink to="/doctor">Doctor&rsquo;s desk</NavLink>
            </nav>
          </div>
        </header>
      )}

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/kiosk" element={<KioskPage />} />
        <Route path="/doctor" element={<DoctorListPage />} />
        <Route path="/doctor/:id" element={<DoctorDashboardPage />} />
        <Route
          path="*"
          element={
            <main className="not-found">
              <h1>This page does not exist</h1>
              <p className="muted">Check the address, or start again from the home page.</p>
              <Link className="btn btn-primary" to="/">
                Go to the home page
              </Link>
            </main>
          }
        />
      </Routes>

      {!isKiosk && <footer className="site-foot">{DISCLAIMER} Synthetic demo data only.</footer>}
    </>
  );
}

export function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Shell />
    </BrowserRouter>
  );
}
