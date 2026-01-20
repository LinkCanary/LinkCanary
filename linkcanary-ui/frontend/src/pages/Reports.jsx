import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Card, { CardBody } from '../components/Card';
import Button from '../components/Button';
import Input from '../components/Input';
import Badge from '../components/Badge';
import { crawlsApi, reportsApi } from '../services/api';

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDuration(seconds) {
  if (!seconds) return '-';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

export default function Reports() {
  const [crawls, setCrawls] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(0);
  const pageSize = 10;
  
  useEffect(() => {
    loadCrawls();
  }, [page, statusFilter]);
  
  async function loadCrawls() {
    setLoading(true);
    try {
      const data = await crawlsApi.list(page * pageSize, pageSize, statusFilter || null);
      setCrawls(data.crawls);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to load crawls:', err);
    } finally {
      setLoading(false);
    }
  }
  
  async function handleDelete(id) {
    if (!confirm('Are you sure you want to delete this crawl and its report?')) return;
    
    try {
      await crawlsApi.delete(id);
      loadCrawls();
    } catch (err) {
      alert('Failed to delete: ' + err.message);
    }
  }
  
  const filteredCrawls = search
    ? crawls.filter((c) =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.sitemap_url.toLowerCase().includes(search.toLowerCase())
      )
    : crawls;
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
        <Link to="/crawl/new">
          <Button>New Crawl</Button>
        </Link>
      </div>
      
      <Card>
        <CardBody>
          <div className="flex flex-wrap gap-4 mb-6">
            <Input
              type="text"
              placeholder="Search by domain or URL..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 min-w-[200px]"
            />
            
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(0);
              }}
              className="rounded-lg border border-gray-300 px-4 py-2.5 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="in_progress">In Progress</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
            </div>
          ) : filteredCrawls.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <p>No reports found.</p>
              <Link to="/crawl/new" className="text-blue-600 hover:text-blue-800 mt-2 inline-block">
                Start your first crawl
              </Link>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead>
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Site</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Pages</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Issues</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {filteredCrawls.map((crawl) => (
                      <tr key={crawl.id} className="hover:bg-gray-50">
                        <td className="px-4 py-4">
                          <div className="font-medium text-gray-900">{crawl.name}</div>
                          <div className="text-sm text-gray-500 truncate max-w-xs">{crawl.sitemap_url}</div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <Badge variant={crawl.status}>{crawl.status}</Badge>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDate(crawl.created_at)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDuration(crawl.duration_seconds)}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {crawl.pages_crawled}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <div className="flex gap-1">
                            {crawl.issues.critical > 0 && <Badge variant="critical">{crawl.issues.critical}</Badge>}
                            {crawl.issues.high > 0 && <Badge variant="high">{crawl.issues.high}</Badge>}
                            {crawl.issues.medium > 0 && <Badge variant="medium">{crawl.issues.medium}</Badge>}
                            {crawl.issues.low > 0 && <Badge variant="low">{crawl.issues.low}</Badge>}
                            {crawl.issues.total === 0 && crawl.status === 'completed' && (
                              <Badge variant="success">None</Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-right text-sm">
                          <div className="flex gap-2 justify-end">
                            {crawl.status === 'completed' && (
                              <>
                                <Link
                                  to={`/report/${crawl.id}`}
                                  className="text-blue-600 hover:text-blue-900 font-medium"
                                >
                                  View
                                </Link>
                                <a
                                  href={reportsApi.downloadCsvUrl(crawl.id)}
                                  className="text-gray-600 hover:text-gray-900"
                                  download
                                >
                                  CSV
                                </a>
                                <a
                                  href={reportsApi.downloadHtmlUrl(crawl.id)}
                                  className="text-gray-600 hover:text-gray-900"
                                  download
                                >
                                  HTML
                                </a>
                              </>
                            )}
                            {crawl.status === 'in_progress' && (
                              <Link
                                to={`/crawl/${crawl.id}/progress`}
                                className="text-blue-600 hover:text-blue-900 font-medium"
                              >
                                Progress
                              </Link>
                            )}
                            <button
                              onClick={() => handleDelete(crawl.id)}
                              className="text-red-600 hover:text-red-900"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {total > pageSize && (
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
                  <p className="text-sm text-gray-500">
                    Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, total)} of {total} results
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={page === 0}
                      onClick={() => setPage((p) => p - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      disabled={(page + 1) * pageSize >= total}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
