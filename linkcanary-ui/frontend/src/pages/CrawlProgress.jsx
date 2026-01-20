import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import Badge from '../components/Badge';
import { crawlsApi, createCrawlWebSocket } from '../services/api';

function ProgressBar({ value, max, className = '' }) {
  const percent = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className={`h-3 bg-gray-200 rounded-full overflow-hidden ${className}`}>
      <div
        className="h-full bg-blue-600 transition-all duration-500"
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

function formatDuration(seconds) {
  if (!seconds) return '0s';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins > 0) {
    return `${mins}m ${secs}s`;
  }
  return `${secs}s`;
}

export default function CrawlProgress() {
  const { id } = useParams();
  const navigate = useNavigate();
  const wsRef = useRef(null);
  
  const [crawl, setCrawl] = useState(null);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [stopping, setStopping] = useState(false);
  
  useEffect(() => {
    loadCrawl();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [id]);
  
  async function loadCrawl() {
    try {
      const data = await crawlsApi.get(id);
      setCrawl(data);
      
      if (data.status === 'in_progress' || data.status === 'pending') {
        connectWebSocket();
      }
    } catch (err) {
      setError(err.message);
    }
  }
  
  function connectWebSocket() {
    wsRef.current = createCrawlWebSocket(
      id,
      (data) => {
        if (data.type === 'progress') {
          setProgress(data);
          setCrawl((prev) => prev ? { ...prev, status: data.status } : prev);
        } else if (data.type === 'complete') {
          setCrawl((prev) => prev ? { ...prev, status: data.status } : prev);
        } else if (data.type === 'error') {
          setError(data.message);
        }
      },
      (err) => {
        console.error('WebSocket error:', err);
      },
      () => {
        loadCrawl();
      }
    );
  }
  
  async function handleStop() {
    if (!confirm('Are you sure you want to stop this crawl?')) return;
    
    setStopping(true);
    try {
      await crawlsApi.stop(id);
      loadCrawl();
    } catch (err) {
      setError(err.message);
    } finally {
      setStopping(false);
    }
  }
  
  if (error && !crawl) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-4">{error}</p>
        <Button onClick={() => navigate('/')}>Back to Dashboard</Button>
      </div>
    );
  }
  
  if (!crawl) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
        <p className="mt-4 text-gray-600">Loading...</p>
      </div>
    );
  }
  
  const isRunning = crawl.status === 'in_progress' || crawl.status === 'pending';
  const isComplete = crawl.status === 'completed';
  const isFailed = crawl.status === 'failed' || crawl.status === 'cancelled';
  
  const pagesTotal = progress?.total_pages || crawl.total_pages || 0;
  const pagesCrawled = progress?.pages_crawled || crawl.pages_crawled || 0;
  const linksChecked = progress?.links_checked || crawl.links_checked || 0;
  const issuesFound = progress?.issues_found || crawl.issues?.total || 0;
  const elapsed = progress?.elapsed_seconds || crawl.duration_seconds || 0;
  const issues = progress?.issues || crawl.issues || {};
  
  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{crawl.name}</h1>
          <p className="text-gray-500 text-sm mt-1">{crawl.sitemap_url}</p>
        </div>
        <Badge variant={crawl.status} className="text-sm px-3 py-1">
          {crawl.status === 'in_progress' ? 'Crawling...' : crawl.status}
        </Badge>
      </div>
      
      <Card>
        <CardBody className="space-y-6">
          {isRunning && (
            <div>
              <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>Progress</span>
                <span>{pagesCrawled} / {pagesTotal || '?'} pages</span>
              </div>
              <ProgressBar value={pagesCrawled} max={pagesTotal || 100} />
            </div>
          )}
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{pagesCrawled}</div>
              <div className="text-sm text-gray-500">Pages Crawled</div>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{linksChecked}</div>
              <div className="text-sm text-gray-500">Links Checked</div>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{issuesFound}</div>
              <div className="text-sm text-gray-500">Issues Found</div>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-2xl font-bold text-gray-900">{formatDuration(elapsed)}</div>
              <div className="text-sm text-gray-500">Elapsed Time</div>
            </div>
          </div>
          
          {(issuesFound > 0 || !isRunning) && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Issues by Priority</h3>
              <div className="flex gap-4">
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-red-500 rounded-full" />
                  <span className="text-sm text-gray-600">Critical: {issues.critical || 0}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-orange-500 rounded-full" />
                  <span className="text-sm text-gray-600">High: {issues.high || 0}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-yellow-500 rounded-full" />
                  <span className="text-sm text-gray-600">Medium: {issues.medium || 0}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="w-3 h-3 bg-blue-500 rounded-full" />
                  <span className="text-sm text-gray-600">Low: {issues.low || 0}</span>
                </div>
              </div>
            </div>
          )}
          
          {crawl.error_message && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              <p className="font-medium">Error</p>
              <p className="text-sm">{crawl.error_message}</p>
            </div>
          )}
        </CardBody>
      </Card>
      
      <div className="flex gap-4">
        {isRunning && (
          <Button variant="danger" onClick={handleStop} loading={stopping}>
            Stop Crawl
          </Button>
        )}
        
        {isComplete && (
          <Link to={`/report/${crawl.id}`}>
            <Button size="lg">View Report</Button>
          </Link>
        )}
        
        {isFailed && (
          <Button
            variant="secondary"
            onClick={async () => {
              const newCrawl = await crawlsApi.rerun(id);
              navigate(`/crawl/${newCrawl.id}/progress`);
            }}
          >
            Retry Crawl
          </Button>
        )}
        
        <Link to="/">
          <Button variant="secondary">Back to Dashboard</Button>
        </Link>
      </div>
    </div>
  );
}
