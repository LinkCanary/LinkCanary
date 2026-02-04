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

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/crawl/new" element={<NewCrawl />} />
            <Route path="/crawl/:id/progress" element={<CrawlProgress />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/report/:id" element={<ReportViewer />} />
            <Route path="/backlinks" element={<BacklinkChecker />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </ThemeProvider>
  );
}
