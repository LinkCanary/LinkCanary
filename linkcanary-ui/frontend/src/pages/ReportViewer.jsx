import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import Badge from '../components/Badge';
import Input from '../components/Input';
import { crawlsApi, reportsApi } from '../services/api';

// Change 1: Expanded issue type labels
const issueTypeLabels = {
  broken: 'Broken',
  broken_404: 'Not Found (404)',
  broken_410: 'Gone (410)',
  broken_5xx: 'Server Error (5xx)',
  mixed_content: 'Mixed Content',
  orphaned_page: 'Orphaned Page',
  weak_anchor: 'Weak Anchor Text',
  redirect_loop: 'Redirect Loop',
  redirect_chain: 'Redirect Chain',
  redirect: 'Redirect',
  canonical_redirect: 'Canonical',
  ok: 'OK',
  error: 'Error',
};

// Change 1: Expanded badge variants
const issueTypeBadgeVariants = {
  broken: 'critical',
  broken_404: 'critical',
  broken_410: 'high',
  broken_5xx: 'critical',
  mixed_content: 'high',
  orphaned_page: 'low',
  weak_anchor: 'medium',
  redirect_loop: 'critical',
  redirect_chain: 'high',
  redirect: 'medium',
  canonical_redirect: 'medium',
  ok: 'success',
  error: 'critical',
};

// Change 4 helper: truncate URL with middle ellipsis, max 60 chars
function truncateUrlMiddle(url, max = 60) {
  if (!url || url.length <= max) return url;
  const half = Math.floor((max - 3) / 2);
  return url.slice(0, half) + '...' + url.slice(url.length - half);
}

// Change 4 helper: determine badge variant for a status code within a redirect chain
function hopStatusVariant(code) {
  const n = parseInt(code, 10);
  if (isNaN(n)) return 'neutral';
  if (n >= 200 && n < 300) return 'success';
  if (n >= 300 && n < 400) return 'medium';
  if (n >= 400 || n >= 500) return 'critical';
  return 'neutral';
}

// Change 4: Parse and render redirect chain hops
function RedirectChainDisplay({ chain }) {
  if (!chain) return null;

  // Expected format: "301: url1 → 302: url2 → 200: url3"
  const hops = chain.split(' → ').map((hop) => {
    const colonIdx = hop.indexOf(':');
    if (colonIdx !== -1) {
      const code = hop.slice(0, colonIdx).trim();
      const url = hop.slice(colonIdx + 1).trim();
      return { code, url };
    }
    return { code: null, url: hop.trim() };
  });

  return (
    <div>
      <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
        Redirect Chain
        <span className="ml-2 text-gray-400 normal-case font-normal">
          ({hops.length} hop{hops.length !== 1 ? 's' : ''})
        </span>
      </div>
      <div className="bg-gray-50 rounded-lg p-2 space-y-1.5">
        {hops.map((hop, i) => (
          <div key={i} className="flex items-center gap-2">
            {hop.code && (
              <Badge variant={hopStatusVariant(hop.code)} className="shrink-0 font-mono">
                {hop.code}
              </Badge>
            )}
            <span
              className="font-mono text-xs text-gray-700 break-all leading-snug"
              title={hop.url}
            >
              {truncateUrlMiddle(hop.url)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Change 6 helper: color class for response time
function responseTimeColor(ms) {
  if (ms < 500) return 'text-green-700';
  if (ms < 2000) return 'text-yellow-700';
  return 'text-red-700';
}

function IssueCard({ issue }) {
  const [expanded, setExpanded] = useState(false);

  const isBroken =
    issue.issue_type === 'broken' ||
    issue.issue_type === 'broken_404' ||
    issue.issue_type === 'broken_410' ||
    issue.issue_type === 'broken_5xx';

  const isRedirectLoop = issue.issue_type === 'redirect_loop';
  const isMixedContent = issue.issue_type === 'mixed_content';

  return (
    <Card
      className={`border-l-4 ${
        issue.priority === 'critical'
          ? 'border-l-red-500'
          : issue.priority === 'high'
          ? 'border-l-orange-500'
          : issue.priority === 'medium'
          ? 'border-l-yellow-500'
          : 'border-l-blue-500'
      }`}
    >
      <CardBody className="space-y-3">
        {/* Badge row */}
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

          {/* Change 2: element_type badge */}
          {issue.element_type && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-gray-100 text-gray-600 border border-gray-200">
              &lt;{issue.element_type}&gt;
            </span>
          )}
        </div>

        {/* Change 5: Redirect loop — prominent warning block */}
        {isRedirectLoop && (
          <div className="bg-red-50 border border-red-300 rounded-lg p-3 flex items-start gap-2">
            <span className="text-red-600 shrink-0 text-base leading-snug">⚠</span>
            <p className="text-red-800 text-sm font-medium leading-snug">
              Redirect Loop Detected — this link never resolves and will time out for users.
            </p>
          </div>
        )}

        {/* Change 8: Mixed content note */}
        {isMixedContent && (
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm text-orange-900">
            This{' '}
            {issue.element_type ? (
              <span className="font-mono bg-orange-100 px-1 rounded">&lt;{issue.element_type}&gt;</span>
            ) : (
              'resource'
            )}{' '}
            is loaded over HTTP on an HTTPS page. Browsers may block it.
          </div>
        )}

        {/* Broken link / URL row */}
        <div>
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            {isRedirectLoop ? 'Loop Origin' : isBroken ? 'Broken Link' : 'Link'}
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

        {/* Change 3: Anchor text display */}
        <div>
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
            Anchor Text
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {issue.link_text ? (
              <>
                <span className="text-sm text-gray-800">"{issue.link_text}"</span>
                {issue.anchor_quality === 'weak' && (
                  <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                    Weak anchor
                  </span>
                )}
              </>
            ) : (
              <span className="text-sm text-gray-400 italic">No anchor text</span>
            )}
          </div>
        </div>

        {/* Source page(s) */}
        {issue.source_page !== 'multiple' ? (
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Found on
            </div>
            <a
              href={issue.source_page}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline break-all text-sm"
            >
              {issue.source_page}
            </a>
          </div>
        ) : (
          issue.example_pages?.length > 0 && (
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
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
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
          )
        )}

        {/* Change 4: Redirect chain — per-hop display */}
        {issue.redirect_chain && <RedirectChainDisplay chain={issue.redirect_chain} />}

        {/* Final URL — only when not a redirect loop */}
        {issue.final_url && !issue.redirect_chain && !isRedirectLoop && (
          <div>
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
              Final Destination
            </div>
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

        {/* Change 6: Response time — only for non-broken issues */}
        {!isBroken &&
          issue.response_time_ms != null &&
          issue.response_time_ms > 0 && (
            <div className="text-xs text-gray-500">
              Response time:{' '}
              <span className={`font-medium ${responseTimeColor(issue.response_time_ms)}`}>
                {Math.round(issue.response_time_ms)}ms
              </span>
            </div>
          )}

        {issue.recommended_fix && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-3">
            <div className="text-xs font-medium text-green-800 uppercase tracking-wide mb-1">
              Recommended Fix
            </div>
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
  // Change 7: Status code filter state
  const [statusCodeFilter, setStatusCodeFilter] = useState('');

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

  // Change 7: Build sorted list of unique status codes for dropdown
  const availableStatusCodes = [
    ...new Set(report?.issues?.map((i) => i.status_code).filter(Boolean)),
  ].sort((a, b) => a - b);

  const filteredIssues =
    report?.issues?.filter((issue) => {
      if (priorityFilter && issue.priority !== priorityFilter) return false;
      if (issueTypeFilter && issue.issue_type !== issueTypeFilter) return false;
      // Change 7: apply status code filter
      if (statusCodeFilter && String(issue.status_code) !== String(statusCodeFilter)) return false;
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

  const hasActiveFilters = search || priorityFilter || issueTypeFilter || statusCodeFilter;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{crawl?.name}</h1>
          <p className="text-gray-500 text-sm">{crawl?.sitemap_url}</p>
        </div>
        <div className="flex gap-2">
          <a href={reportsApi.downloadCsvUrl(id)} download>
            <Button variant="secondary" size="sm">
              Download CSV
            </Button>
          </a>
          <a href={reportsApi.downloadHtmlUrl(id)} download>
            <Button variant="secondary" size="sm">
              Download HTML
            </Button>
          </a>
          <Link to="/reports">
            <Button variant="secondary" size="sm">
              Back
            </Button>
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
              <div
                className={`text-2xl font-bold ${
                  p === 'critical'
                    ? 'text-red-600'
                    : p === 'high'
                    ? 'text-orange-600'
                    : p === 'medium'
                    ? 'text-yellow-600'
                    : 'text-blue-600'
                }`}
              >
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
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>

            <select
              value={issueTypeFilter}
              onChange={(e) => setIssueTypeFilter(e.target.value)}
              className="rounded-lg border border-gray-300 px-4 py-2.5"
            >
              <option value="">All Types</option>
              {issueTypes.map((t) => (
                <option key={t} value={t}>
                  {issueTypeLabels[t] || t}
                </option>
              ))}
            </select>

            {/* Change 7: Status code dropdown */}
            {availableStatusCodes.length > 0 && (
              <select
                value={statusCodeFilter}
                onChange={(e) => setStatusCodeFilter(e.target.value)}
                className="rounded-lg border border-gray-300 px-4 py-2.5"
              >
                <option value="">All Status Codes</option>
                {availableStatusCodes.map((code) => (
                  <option key={code} value={code}>
                    {code}
                  </option>
                ))}
              </select>
            )}

            {hasActiveFilters && (
              <Button
                variant="secondary"
                onClick={() => {
                  setSearch('');
                  setPriorityFilter('');
                  setIssueTypeFilter('');
                  setStatusCodeFilter('');
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
