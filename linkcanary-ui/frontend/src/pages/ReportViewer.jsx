import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import Badge from '../components/Badge';
import Input from '../components/Input';
import { crawlsApi, reportsApi } from '../services/api';

const issueTypeLabels = {
  broken: 'Broken',
  redirect_loop: 'Redirect Loop',
  redirect_chain: 'Redirect Chain',
  redirect: 'Redirect',
  canonical_redirect: 'Canonical',
  ok: 'OK',
  error: 'Error',
};

const issueTypeBadgeVariants = {
  broken: 'critical',
  redirect_loop: 'critical',
  redirect_chain: 'high',
  redirect: 'medium',
  canonical_redirect: 'medium',
  ok: 'success',
  error: 'critical',
};

function IssueCard({ issue }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <Card className={`border-l-4 ${
      issue.priority === 'critical' ? 'border-l-red-500' :
      issue.priority === 'high' ? 'border-l-orange-500' :
      issue.priority === 'medium' ? 'border-l-yellow-500' :
      'border-l-blue-500'
    }`}>
      <CardBody className="space-y-3">
        <div className="flex flex-wrap gap-2 items-center">
          <Badge variant={issueTypeBadgeVariants[issue.issue_type] || 'neutral'}>
            {issueTypeLabels[issue.issue_type] || issue.issue_type}
          </Badge>
          <Badge variant={issue.priority}>{issue.priority}</Badge>
          {issue.occurrence_count > 1 && (
            <Badge variant="neutral">{issue.occurrence_count}x</Badge>
          )}
          <Badge variant="neutral">{issue.link_type}</Badge>
          <Badge variant="neutral">{issue.status_code}</Badge>
        </div>
        
        <div>
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Broken Link {issue.link_text && `("${issue.link_text.substring(0, 50)}")`}
          </div>
          <a
            href={issue.link_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline break-all font-mono text-sm"
          >
            {issue.link_url}
          </a>
        </div>
        
        {issue.source_page !== 'multiple' ? (
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Found on</div>
            <a
              href={issue.source_page}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline break-all text-sm"
            >
              {issue.source_page}
            </a>
          </div>
        ) : issue.example_pages?.length > 0 && (
          <div>
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1 flex items-center gap-1"
            >
              Found on {issue.occurrence_count} pages
              <svg
                className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {expanded && (
              <div className="bg-gray-50 rounded-lg p-2 max-h-32 overflow-y-auto">
                {issue.example_pages.map((page, i) => (
                  <a
                    key={i}
                    href={page}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block text-blue-600 hover:underline text-sm py-0.5 break-all"
                  >
                    {page}
                  </a>
                ))}
              </div>
            )}
          </div>
        )}
        
        {issue.redirect_chain && (
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Redirect Chain</div>
            <div className="bg-gray-50 rounded-lg p-2 font-mono text-xs overflow-x-auto">
              {issue.redirect_chain.split(' → ').map((hop, i, arr) => (
                <span key={i}>
                  {hop}
                  {i < arr.length - 1 && <span className="text-gray-400"> → </span>}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {issue.final_url && !issue.redirect_chain && (
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Final Destination</div>
            <a
              href={issue.final_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline break-all text-sm"
            >
              {issue.final_url}
            </a>
          </div>
        )}
        
        {issue.recommended_fix && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <div className="text-xs font-medium text-green-800 uppercase tracking-wide mb-1">Recommended Fix</div>
            <p className="text-green-900 text-sm">{issue.recommended_fix}</p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

export default function ReportViewer() {
  const { id } = useParams();
  const [crawl, setCrawl] = useState(null);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [search, setSearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [issueTypeFilter, setIssueTypeFilter] = useState('');
  
  useEffect(() => {
    loadData();
  }, [id]);
  
  async function loadData() {
    try {
      const [crawlData, reportData] = await Promise.all([
        crawlsApi.get(id),
        crawlsApi.getReport(id),
      ]);
      setCrawl(crawlData);
      setReport(reportData);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }
  
  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="animate-spin inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
        <p className="mt-4 text-gray-600">Loading report...</p>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600 mb-4">{error}</p>
        <Link to="/reports">
          <Button variant="secondary">Back to Reports</Button>
        </Link>
      </div>
    );
  }
  
  const filteredIssues = report?.issues?.filter((issue) => {
    if (priorityFilter && issue.priority !== priorityFilter) return false;
    if (issueTypeFilter && issue.issue_type !== issueTypeFilter) return false;
    if (search) {
      const searchLower = search.toLowerCase();
      return (
        issue.link_url.toLowerCase().includes(searchLower) ||
        issue.source_page?.toLowerCase().includes(searchLower) ||
        issue.link_text?.toLowerCase().includes(searchLower)
      );
    }
    return true;
  }) || [];
  
  const priorities = ['critical', 'high', 'medium', 'low'];
  const issueTypes = [...new Set(report?.issues?.map((i) => i.issue_type) || [])];
  
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{crawl?.name}</h1>
          <p className="text-gray-500 text-sm">{crawl?.sitemap_url}</p>
        </div>
        <div className="flex gap-2">
          <a href={reportsApi.downloadCsvUrl(id)} download>
            <Button variant="secondary" size="sm">Download CSV</Button>
          </a>
          <a href={reportsApi.downloadHtmlUrl(id)} download>
            <Button variant="secondary" size="sm">Download HTML</Button>
          </a>
          <Link to="/reports">
            <Button variant="secondary" size="sm">Back</Button>
          </Link>
        </div>
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card>
          <CardBody className="text-center py-3">
            <div className="text-2xl font-bold">{report?.total || 0}</div>
            <div className="text-xs text-gray-500">Total Issues</div>
          </CardBody>
        </Card>
        {priorities.map((p) => (
          <Card key={p}>
            <CardBody className="text-center py-3">
              <div className={`text-2xl font-bold ${
                p === 'critical' ? 'text-red-600' :
                p === 'high' ? 'text-orange-600' :
                p === 'medium' ? 'text-yellow-600' :
                'text-blue-600'
              }`}>
                {report?.issues?.filter((i) => i.priority === p).length || 0}
              </div>
              <div className="text-xs text-gray-500 capitalize">{p}</div>
            </CardBody>
          </Card>
        ))}
      </div>
      
      <Card>
        <CardBody>
          <div className="flex flex-wrap gap-4 mb-4">
            <Input
              type="text"
              placeholder="Search by URL..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 min-w-[200px]"
            />
            
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded-lg border border-gray-300 px-4 py-2.5"
            >
              <option value="">All Priorities</option>
              {priorities.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            
            <select
              value={issueTypeFilter}
              onChange={(e) => setIssueTypeFilter(e.target.value)}
              className="rounded-lg border border-gray-300 px-4 py-2.5"
            >
              <option value="">All Types</option>
              {issueTypes.map((t) => (
                <option key={t} value={t}>{issueTypeLabels[t] || t}</option>
              ))}
            </select>
            
            {(search || priorityFilter || issueTypeFilter) && (
              <Button
                variant="secondary"
                onClick={() => {
                  setSearch('');
                  setPriorityFilter('');
                  setIssueTypeFilter('');
                }}
              >
                Clear Filters
              </Button>
            )}
          </div>
          
          <p className="text-sm text-gray-500 mb-4">
            Showing {filteredIssues.length} of {report?.total || 0} issues
          </p>
        </CardBody>
      </Card>
      
      <div className="grid md:grid-cols-2 gap-4">
        {filteredIssues.map((issue, i) => (
          <IssueCard key={i} issue={issue} />
        ))}
      </div>
      
      {filteredIssues.length === 0 && (
        <Card>
          <CardBody className="text-center py-12 text-gray-500">
            No issues match your filters.
          </CardBody>
        </Card>
      )}
    </div>
  );
}
