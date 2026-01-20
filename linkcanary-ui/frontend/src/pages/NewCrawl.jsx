import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import Input, { Checkbox, Select } from '../components/Input';
import { crawlsApi } from '../services/api';

export default function NewCrawl() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState(null);
  const [sitemapValid, setSitemapValid] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  
  const [form, setForm] = useState({
    sitemap_url: '',
    name: '',
    internal_only: false,
    external_only: false,
    skip_ok: true,
    expand_duplicates: false,
    include_subdomains: false,
    delay: 0.5,
    timeout: 10,
    max_pages: '',
    since: '',
    user_agent: 'LinkCanary/1.0',
  });
  
  function updateForm(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (field === 'sitemap_url') {
      setSitemapValid(null);
    }
  }
  
  async function validateSitemap() {
    if (!form.sitemap_url.trim()) return;
    
    setValidating(true);
    try {
      const result = await crawlsApi.validateSitemap(form.sitemap_url);
      setSitemapValid(result);
    } catch (err) {
      setSitemapValid({ valid: false, error: err.message });
    } finally {
      setValidating(false);
    }
  }
  
  async function handleSubmit(e) {
    e.preventDefault();
    if (!form.sitemap_url.trim()) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const crawl = await crawlsApi.create({
        sitemap_url: form.sitemap_url,
        name: form.name || undefined,
        settings: {
          internal_only: form.internal_only,
          external_only: form.external_only,
          skip_ok: form.skip_ok,
          expand_duplicates: form.expand_duplicates,
          include_subdomains: form.include_subdomains,
          delay: parseFloat(form.delay),
          timeout: parseInt(form.timeout),
          max_pages: form.max_pages ? parseInt(form.max_pages) : null,
          since: form.since || null,
          user_agent: form.user_agent,
        },
      });
      navigate(`/crawl/${crawl.id}/progress`);
    } catch (err) {
      setError(err.message);
      setLoading(false);
    }
  }
  
  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Crawl</h1>
      
      <form onSubmit={handleSubmit} className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">Basic Settings</h2>
          </CardHeader>
          <CardBody className="space-y-4">
            <div>
              <Input
                label="Sitemap URL"
                type="url"
                placeholder="https://example.com/sitemap.xml"
                value={form.sitemap_url}
                onChange={(e) => updateForm('sitemap_url', e.target.value)}
                required
              />
              <div className="mt-2 flex items-center gap-2">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={validateSitemap}
                  loading={validating}
                  disabled={!form.sitemap_url.trim()}
                >
                  Test URL
                </Button>
                {sitemapValid && (
                  <span className={sitemapValid.valid ? 'text-green-600 text-sm' : 'text-red-600 text-sm'}>
                    {sitemapValid.valid 
                      ? `Valid sitemap with ${sitemapValid.page_count} pages`
                      : sitemapValid.error}
                  </span>
                )}
              </div>
            </div>
            
            <Input
              label="Crawl Name (optional)"
              type="text"
              placeholder="Auto-generated from domain if empty"
              value={form.name}
              onChange={(e) => updateForm('name', e.target.value)}
            />
          </CardBody>
        </Card>
        
        <Card>
          <CardHeader>
            <button
              type="button"
              className="flex items-center justify-between w-full text-left"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <h2 className="text-lg font-semibold text-gray-900">Advanced Options</h2>
              <svg
                className={`w-5 h-5 text-gray-500 transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </CardHeader>
          
          {showAdvanced && (
            <CardBody className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Link Scope</label>
                <div className="space-y-2">
                  <Checkbox
                    label="Internal links only"
                    checked={form.internal_only}
                    onChange={(e) => {
                      updateForm('internal_only', e.target.checked);
                      if (e.target.checked) updateForm('external_only', false);
                    }}
                  />
                  <Checkbox
                    label="External links only"
                    checked={form.external_only}
                    onChange={(e) => {
                      updateForm('external_only', e.target.checked);
                      if (e.target.checked) updateForm('internal_only', false);
                    }}
                  />
                  <Checkbox
                    label="Include subdomains as internal"
                    checked={form.include_subdomains}
                    onChange={(e) => updateForm('include_subdomains', e.target.checked)}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Delay between requests (seconds)
                  </label>
                  <input
                    type="range"
                    min="0.1"
                    max="5"
                    step="0.1"
                    value={form.delay}
                    onChange={(e) => updateForm('delay', e.target.value)}
                    className="w-full"
                  />
                  <div className="text-sm text-gray-500 text-center">{form.delay}s</div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Request timeout (seconds)
                  </label>
                  <input
                    type="range"
                    min="5"
                    max="60"
                    step="5"
                    value={form.timeout}
                    onChange={(e) => updateForm('timeout', e.target.value)}
                    className="w-full"
                  />
                  <div className="text-sm text-gray-500 text-center">{form.timeout}s</div>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="Max pages to crawl"
                  type="number"
                  min="1"
                  placeholder="No limit"
                  value={form.max_pages}
                  onChange={(e) => updateForm('max_pages', e.target.value)}
                />
                
                <Input
                  label="Only pages modified after"
                  type="date"
                  value={form.since}
                  onChange={(e) => updateForm('since', e.target.value)}
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Report Options</label>
                <div className="space-y-2">
                  <Checkbox
                    label="Skip OK links in report (recommended)"
                    checked={form.skip_ok}
                    onChange={(e) => updateForm('skip_ok', e.target.checked)}
                  />
                  <Checkbox
                    label="Expand duplicates (show all occurrences)"
                    checked={form.expand_duplicates}
                    onChange={(e) => updateForm('expand_duplicates', e.target.checked)}
                  />
                </div>
              </div>
              
              <Input
                label="User-Agent"
                type="text"
                value={form.user_agent}
                onChange={(e) => updateForm('user_agent', e.target.value)}
              />
            </CardBody>
          )}
        </Card>
        
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}
        
        <div className="flex gap-4">
          <Button type="submit" size="lg" loading={loading} className="flex-1">
            Start Crawl
          </Button>
          <Button type="button" variant="secondary" size="lg" onClick={() => navigate('/')}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
