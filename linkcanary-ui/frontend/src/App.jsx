import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/Layout';
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

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/share/:token" element={<ShareView />} />
          <Route path="/*" element={<Layout><Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/crawl/new" element={<NewCrawl />} />
            <Route path="/crawl/:id/progress" element={<CrawlProgress />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/report/:id" element={<ReportViewer />} />
            <Route path="/backlinks" element={<BacklinkChecker />} />
            <Route path="/url-resolution" element={<UrlResolution />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/integrations" element={<Integrations />} />
            <Route path="/ci-setup" element={<CiDocs />} />
          </Routes></Layout>} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
