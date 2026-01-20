import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Card, { CardBody } from '../components/Card';
import Button from '../components/Button';
import Input, { Checkbox } from '../components/Input';
import Badge from '../components/Badge';
import { crawlsApi, statsApi } from '../services/api';

function StatCard({ label, value, color = 'text-gray-900' }) {
  return (
    <Card>
      <CardBody className="text-center">
        <div className={`text-3xl font-bold ${color}`}>{value}</div>
        <div className="text-sm text-gray-500 mt-1">{label}</div>
      </CardBody>
    </Card>
  );
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [sitemapUrl, setSitemapUrl] = useState('');
  const [internalOnly, setInternalOnly] = useState(false);
  const [skipOk, setSkipOk] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [recentCrawls, setRecentCrawls] = useState([]);
  
  useEffect(() => {
    loadData();
  }, []);
  
  async function loadData() {
    try {
      const [statsData, crawlsData] = await Promise.all([
        statsApi.get(),
        crawlsApi.list(0, 5),
      ]);
      setStats(statsData);
      setRecentCrawls(crawlsData.crawls);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    }
  }
  
  async function handleQuickStart(e) {
    e.preventDefault();
    if (!sitemapUrl.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const crawl = await crawlsApi.create({
        sitemap_url: sitemapUrl,
        settings: {
          internal_only: internalOnly,
          skip_ok: skipOk,
        },
      });
      navigate(`/crawl/${crawl.id}/progress`);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }
  
  return (
    <div className="space-y-8">
      <Card>
        <CardBody>
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Start</h2>
          <form onSubmit={handleQuickStart} className="space-y-4">
            <Input
              type="url"
              placeholder="Enter website sitemap URL (e.g., https://example.com/sitemap.xml)"
              value={sitemapUrl}
              onChange={(e) => setSitemapUrl(e.target.value)}
              error={error}
              className="flex-1"
            />
            
            <div className="flex flex-wrap gap-4 items-center justify-between">
              <div className="flex gap-4">
                <Checkbox
                  label="Internal links only"
                  checked={internalOnly}
                  onChange={(e) => setInternalOnly(e.target.checked)}
                />
                <Checkbox
                  label="Skip OK links in report"
                  checked={skipOk}
                  onChange={(e) => setSkipOk(e.target.checked)}
                />
              </div>
              
              <Button type="submit" size="lg" loading={loading}>
                Start Crawl
              </Button>
            </div>
          </form>
        </CardBody>
      </Card>
      
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Total Crawls" value={stats.total_crawls} />
          <StatCard label="Critical Issues" value={stats.issues_by_type.critical} color="text-red-600" />
          <StatCard label="High Issues" value={stats.issues_by_type.high} color="text-orange-600" />
          <StatCard label="Medium Issues" value={stats.issues_by_type.medium} color="text-yellow-600" />
          <StatCard label="Low Issues" value={stats.issues_by_type.low} color="text-blue-600" />
        </div>
      )}
      
      <Card>
        <CardBody>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Recent Crawls</h2>
            <Link to="/reports" className="text-blue-600 hover:text-blue-800 text-sm font-medium">
              View All
            </Link>
          </div>
          
          {recentCrawls.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <p>No crawls yet. Start your first crawl above!</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Site</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Issues</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {recentCrawls.map((crawl) => (
                    <tr key={crawl.id} className="hover:bg-gray-50">
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="font-medium text-gray-900">{crawl.name}</div>
                        <div className="text-sm text-gray-500 truncate max-w-xs">{crawl.sitemap_url}</div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <Badge variant={crawl.status}>{crawl.status}</Badge>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(crawl.created_at)}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="flex gap-2">
                          {crawl.issues.critical > 0 && <Badge variant="critical">{crawl.issues.critical}</Badge>}
                          {crawl.issues.high > 0 && <Badge variant="high">{crawl.issues.high}</Badge>}
                          {crawl.issues.medium > 0 && <Badge variant="medium">{crawl.issues.medium}</Badge>}
                          {crawl.issues.low > 0 && <Badge variant="low">{crawl.issues.low}</Badge>}
                          {crawl.issues.total === 0 && <Badge variant="success">No issues</Badge>}
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-right text-sm">
                        {crawl.status === 'completed' && (
                          <Link
                            to={`/report/${crawl.id}`}
                            className="text-blue-600 hover:text-blue-900 font-medium"
                          >
                            View Report
                          </Link>
                        )}
                        {crawl.status === 'in_progress' && (
                          <Link
                            to={`/crawl/${crawl.id}/progress`}
                            className="text-blue-600 hover:text-blue-900 font-medium"
                          >
                            View Progress
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
