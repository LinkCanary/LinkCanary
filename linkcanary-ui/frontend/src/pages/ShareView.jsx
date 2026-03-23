import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { crawlsApi } from '../services/api';

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

const priorityColors = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  low: 'bg-blue-100 text-blue-800 border-blue-200',
};

const borderColors = {
  critical: 'border-l-red-500',
  high: 'border-l-orange-500',
  medium: 'border-l-yellow-500',
  low: 'border-l-blue-500',
};

export default function ShareView() {
  const { token } = useParams();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');

  useEffect(() => {
    crawlsApi.getShared(token)
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full" />
          <p className="mt-4 text-gray-500">Loading shared report…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-2">
          <p className="text-2xl font-bold text-gray-800">Report not found</p>
          <p className="text-gray-500">This link may have expired or the report was deleted.</p>
        </div>
      </div>
    );
  }

  const priorities = ['critical', 'high', 'medium', 'low'];

  const filtered = report?.issues?.filter((issue) => {
    if (priorityFilter && issue.priority !== priorityFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (
        issue.link_url?.toLowerCase().includes(s) ||
        issue.source_page?.toLowerCase().includes(s)
      );
    }
    return true;
  }) || [];

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-gray-900">LinkCanary</span>
          <span className="text-gray-300">|</span>
          <span className="text-gray-500 text-sm">Shared Report</span>
        </div>
        <span className="text-xs text-gray-400">Read-only view</span>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        {/* Summary */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
            <div className="text-2xl font-bold text-gray-900">{report?.total || 0}</div>
            <div className="text-xs text-gray-500 mt-1">Total Issues</div>
          </div>
          {priorities.map((p) => (
            <div key={p} className="bg-white rounded-xl border border-gray-200 p-4 text-center">
              <div className={`text-2xl font-bold ${
                p === 'critical' ? 'text-red-600' :
                p === 'high' ? 'text-orange-600' :
                p === 'medium' ? 'text-yellow-600' : 'text-blue-600'
              }`}>
                {report?.issues?.filter((i) => i.priority === p).length || 0}
              </div>
              <div className="text-xs text-gray-500 mt-1 capitalize">{p}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-wrap gap-3">
          <input
            type="text"
            placeholder="Search URLs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="flex-1 min-w-[180px] border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none"
          >
            <option value="">All Priorities</option>
            {priorities.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          {(search || priorityFilter) && (
            <button
              onClick={() => { setSearch(''); setPriorityFilter(''); }}
              className="text-sm text-gray-500 hover:text-gray-800 px-2"
            >
              Clear
            </button>
          )}
          <span className="text-sm text-gray-400 self-center ml-auto">
            {filtered.length} of {report?.total || 0} issues
          </span>
        </div>

        {/* Issues */}
        <div className="grid md:grid-cols-2 gap-4">
          {filtered.map((issue, i) => (
            <div
              key={i}
              className={`bg-white rounded-xl border border-gray-200 border-l-4 ${borderColors[issue.priority] || 'border-l-gray-300'} p-4 space-y-3`}
            >
              <div className="flex flex-wrap gap-2">
                <span className={`text-xs font-medium px-2 py-0.5 rounded border ${priorityColors[issue.priority] || 'bg-gray-100 text-gray-600'}`}>
                  {issue.priority}
                </span>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {issueTypeLabels[issue.issue_type] || issue.issue_type}
                </span>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded font-mono">
                  {issue.status_code}
                </span>
              </div>

              <div>
                <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Broken Link</div>
                <a
                  href={issue.link_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline break-all text-sm font-mono"
                >
                  {issue.link_url}
                </a>
              </div>

              <div>
                <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">Found On</div>
                <p className="text-sm text-gray-700 break-all">{issue.source_page}</p>
              </div>

              {issue.recommended_fix && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <div className="text-xs font-medium text-green-800 uppercase tracking-wide mb-1">Fix</div>
                  <p className="text-green-900 text-sm">{issue.recommended_fix}</p>
                </div>
              )}
            </div>
          ))}
        </div>

        {filtered.length === 0 && (
          <div className="text-center py-12 text-gray-400">No issues match your filters.</div>
        )}

        <footer className="text-center text-xs text-gray-400 pt-4 border-t border-gray-200">
          Generated by <a href="https://github.com/LinkCanary/LinkCanary" className="hover:underline">LinkCanary</a>
        </footer>
      </main>
    </div>
  );
}
