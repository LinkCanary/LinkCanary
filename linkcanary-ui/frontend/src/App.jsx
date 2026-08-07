import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/Layout';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import NewCrawl from './pages/NewCrawl';
import CrawlProgress from './pages/CrawlProgress';
import Reports from './pages/Reports';
import ReportViewer from './pages/ReportViewer';
import Settings from './pages/Settings';
import BacklinkChecker from './pages/BacklinkChecker';
import UrlResolution from './pages/UrlResolution';
import Integrations from './pages/Integrations';
import CiDocs from './pages/CiDocs';
import ShareView from './pages/ShareView';
import Signup from './pages/Signup';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import Account from './pages/Account';
import Billing from './pages/Billing';

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/share/:token" element={<ShareView />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/login" element={<Login />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />

            {/* Protected routes */}
            <Route path="/*" element={
              <ProtectedRoute>
                <Layout><Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/crawl/new" element={<NewCrawl />} />
                  <Route path="/crawl/:id/progress" element={<CrawlProgress />} />
                  <Route path="/reports" element={<Reports />} />
                  <Route path="/report/:id" element={<ReportViewer />} />
                  <Route path="/backlinks" element={<BacklinkChecker />} />
                  <Route path="/url-resolution" element={<UrlResolution />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/integrations" element={<Integrations />} />
                  <Route path="/ci-setup" element={<CiDocs />} />
                  <Route path="/account" element={<Account />} />
                  <Route path="/account/billing" element={<Billing />} />
                </Routes></Layout>
              </ProtectedRoute>
            } />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
