import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import Input, { Checkbox } from '../components/Input';
import Badge from '../components/Badge';
import { crawlsApi, statsApi } from '../services/api';

function StatCard({ label, value, color = 'text-dark dark:text-primary' }) {
  return (
    <Card>
      <CardBody className="text-center">
        <div className={`text-3xl font-bold ${color}`}>{value}</div>
        <div className="text-sm text-gray-500 dark:text-secondary/70 mt-1">{label}</div>
      </CardBody>
    </Card>
  );
}

function PriorityGuide() {
  const [expanded, setExpanded] = useState(null);
  
  const priorities = [
    {
      id: 'critical',
      emoji: '🔴',
      name: 'CRITICAL',
      color: 'border-red-500',
      bgColor: 'bg-red-50 dark:bg-red-900/20',
      textColor: 'text-red-700 dark:text-red-400',
      definition: 'Issues that completely break user experience or create infinite loops that waste crawler resources.',
      meaning: [
        'Users clicking these links will encounter serious problems',
        'Search engine crawlers may get stuck',
        'These issues should be fixed IMMEDIATELY',
      ],
      issueTypes: [
        {
          name: 'Redirect Loops',
          desc: 'Link creates an infinite redirect chain that never resolves',
          example: 'Link A → Link B → Link C → Link A (repeats forever)',
          impact: 'Users see error pages, crawlers waste resources, terrible UX',
          action: 'Remove the link or replace with working destination',
        },
        {
          name: 'Excessive Redirect Chains (3+ redirects)',
          desc: 'Link goes through 3 or more redirects before reaching destination',
          example: 'Link → 308 → 302 → 308 → Final page',
          impact: 'Very slow page loads, poor SEO, wastes resources',
          action: 'Update link to point directly to final destination',
        },
      ],
    },
    {
      id: 'high',
      emoji: '🟠',
      name: 'HIGH',
      color: 'border-orange-500',
      bgColor: 'bg-orange-50 dark:bg-orange-900/20',
      textColor: 'text-orange-700 dark:text-orange-400',
      definition: 'Issues that significantly impact user experience and should be fixed soon.',
      meaning: [
        'Links are completely broken (404 errors)',
        'Links go through multiple unnecessary redirects',
        'Affects multiple pages on your site',
        'Damages SEO and user trust',
      ],
      issueTypes: [
        {
          name: 'Broken Links (404 - Not Found)',
          desc: 'Link points to page that doesn\'t exist',
          example: 'Status code: 404',
          impact: 'Poor user experience, damages credibility, negative SEO signal',
          action: 'Remove link or update to correct page',
        },
        {
          name: 'Redirect Chains (2 redirects)',
          desc: 'Link goes through 2 redirects before reaching destination',
          example: 'Link → 301 → 301 → Final page',
          impact: 'Slower page loads, diluted SEO value, poor UX',
          action: 'Update link to point directly to final URL',
        },
      ],
    },
    {
      id: 'medium',
      emoji: '🟡',
      name: 'MEDIUM',
      color: 'border-yellow-500',
      bgColor: 'bg-yellow-50 dark:bg-yellow-900/20',
      textColor: 'text-yellow-700 dark:text-yellow-400',
      definition: 'Issues that create minor inefficiencies but don\'t break functionality.',
      meaning: [
        'Links work but take an extra step',
        'Small SEO impact',
        'Worth fixing when you have time',
        'Improves site performance and polish',
      ],
      issueTypes: [
        {
          name: 'Simple Redirects (1 redirect)',
          desc: 'Link redirects once before reaching destination',
          example: 'Link → 301 → Final page',
          impact: 'Minor delay, slightly diluted SEO value',
          action: 'Update link to point directly to final destination',
        },
        {
          name: 'Canonical Redirects (Missing Trailing Slash)',
          desc: 'Link is missing trailing slash, causing automatic redirect',
          example: '/blog/post → /blog/post/',
          impact: 'Very minor - one extra redirect per click',
          action: 'Add trailing slash to links for consistency',
        },
      ],
    },
    {
      id: 'low',
      emoji: '🔵',
      name: 'LOW',
      color: 'border-blue-500',
      bgColor: 'bg-blue-50 dark:bg-blue-900/20',
      textColor: 'text-blue-700 dark:text-blue-400',
      definition: 'Informational issues or links that work fine but have minor quirks.',
      meaning: [
        'Links are working correctly',
        'No user impact',
        'No action required unless you want perfection',
        'Often just documentation of link status',
      ],
      issueTypes: [
        {
          name: 'OK Links (200 - Success)',
          desc: 'Links that work perfectly',
          example: 'Status code: 200',
          impact: 'None - these are good!',
          action: 'No action needed',
        },
        {
          name: 'Minor Access Issues (403, 410)',
          desc: 'External links with access restrictions',
          example: '403 Forbidden, 410 Gone, 999 (LinkedIn)',
          impact: 'May be intentional or expected behavior',
          action: 'Review individually - some may need fixing',
        },
        {
          name: 'Connection Errors',
          desc: 'Couldn\'t connect to external link',
          example: 'Timeout, DNS failure',
          impact: 'Might be temporary, verify manually',
          action: 'Test link manually, may be site temporarily down',
        },
      ],
    },
  ];

  return (
    <Card>
      <CardHeader>
        <h2 className="text-xl font-semibold text-dark dark:text-primary">Understanding Issue Priorities</h2>
        <p className="text-sm text-gray-500 dark:text-secondary/70 mt-1">
          Click each priority level to learn what issues it contains and how to fix them
        </p>
      </CardHeader>
      <CardBody className="space-y-4">
        {priorities.map((priority) => (
          <div
            key={priority.id}
            className={`border-l-4 ${priority.color} ${priority.bgColor} rounded-r-lg overflow-hidden`}
          >
            <button
              onClick={() => setExpanded(expanded === priority.id ? null : priority.id)}
              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">{priority.emoji}</span>
                <div>
                  <span className={`font-bold ${priority.textColor}`}>{priority.name} Priority</span>
                  <p className="text-sm text-gray-600 dark:text-secondary/80 mt-0.5">{priority.definition}</p>
                </div>
              </div>
              <svg
                className={`w-5 h-5 text-gray-400 transition-transform ${expanded === priority.id ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            
            {expanded === priority.id && (
              <div className="px-4 pb-4 space-y-4">
                <div>
                  <h4 className="font-medium text-dark dark:text-primary mb-2">What This Means:</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-gray-600 dark:text-secondary/80">
                    {priority.meaning.map((item, i) => (
                      <li key={i}>{item}</li>
                    ))}
                  </ul>
                </div>
                
                <div>
                  <h4 className="font-medium text-dark dark:text-primary mb-2">Issue Types:</h4>
                  <div className="space-y-3">
                    {priority.issueTypes.map((issue, i) => (
                      <div key={i} className="bg-white dark:bg-dark/50 rounded-lg p-3 text-sm">
                        <div className="font-medium text-dark dark:text-primary">{issue.name}</div>
                        <p className="text-gray-600 dark:text-secondary/80 mt-1">{issue.desc}</p>
                        <div className="mt-2 space-y-1 text-xs">
                          <div><span className="font-medium text-gray-500 dark:text-secondary/60">Example:</span> <span className="text-gray-600 dark:text-secondary/80">{issue.example}</span></div>
                          <div><span className="font-medium text-gray-500 dark:text-secondary/60">Impact:</span> <span className="text-gray-600 dark:text-secondary/80">{issue.impact}</span></div>
                          <div><span className="font-medium text-primary dark:text-primary">Action:</span> <span className="text-gray-600 dark:text-secondary/80">{issue.action}</span></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
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
          <h2 className="text-xl font-semibold text-dark dark:text-primary mb-4">Quick Start</h2>
          <form onSubmit={handleQuickStart} className="space-y-4">
            <Input
              type="url"
              placeholder="Enter website URL (e.g., https://example.com)"
              value={sitemapUrl}
              onChange={(e) => setSitemapUrl(e.target.value)}
              error={error}
              className="flex-1"
            />
            <p className="text-xs text-gray-500 dark:text-secondary/60 -mt-2">
              We'll automatically find your sitemap.xml
            </p>
            
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
            <h2 className="text-xl font-semibold text-dark dark:text-primary">Recent Crawls</h2>
            <Link to="/reports" className="text-dark dark:text-primary hover:underline text-sm font-medium">
              View All
            </Link>
          </div>
          
          {recentCrawls.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-secondary/70">
              <p>No crawls yet. Start your first crawl above!</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-primary/20">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-secondary/70 uppercase tracking-wider">Site</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-secondary/70 uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-secondary/70 uppercase tracking-wider">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-secondary/70 uppercase tracking-wider">Issues</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-secondary/70 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 dark:divide-primary/20">
                  {recentCrawls.map((crawl) => (
                    <tr key={crawl.id} className="hover:bg-gray-50 dark:hover:bg-primary/5">
                      <td className="px-4 py-4 whitespace-nowrap">
                        <div className="font-medium text-dark dark:text-primary">{crawl.name}</div>
                        <div className="text-sm text-gray-500 dark:text-secondary/70 truncate max-w-xs">{crawl.sitemap_url}</div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        <Badge variant={crawl.status}>{crawl.status}</Badge>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-secondary/70">
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
                            className="text-dark dark:text-primary hover:underline font-medium"
                          >
                            View Report
                          </Link>
                        )}
                        {crawl.status === 'in_progress' && (
                          <Link
                            to={`/crawl/${crawl.id}/progress`}
                            className="text-dark dark:text-primary hover:underline font-medium"
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
      
      <PriorityGuide />
    </div>
  );
}
