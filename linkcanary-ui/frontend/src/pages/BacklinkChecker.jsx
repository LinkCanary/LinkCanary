import { useState } from 'react';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import Input from '../components/Input';
import Badge from '../components/Badge';
import { backlinksApi } from '../services/api';

export default function BacklinkChecker() {
  const [targetUrl, setTargetUrl] = useState('');
  const [sitemapUrl, setSitemapUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  
  async function handleCheck(e) {
    e.preventDefault();
    
    if (!targetUrl.trim() || !sitemapUrl.trim()) {
      setError('Please enter both target URL and sitemap URL');
      return;
    }
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    try {
      const response = await backlinksApi.check({
        target_url: targetUrl,
        sitemap_url: sitemapUrl,
      });
      setResult(response);
    } catch (err) {
      setError(err.message || 'Failed to check backlinks');
    } finally {
      setLoading(false);
    }
  }
  
  function getDomain(url) {
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  }
  
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <h1 className="text-2xl font-bold text-dark dark:text-primary">Backlink Checker</h1>
          <p className="text-sm text-gray-500 dark:text-secondary/70 mt-1">
            Check if pages from a sitemap contain links to a target URL
          </p>
        </CardHeader>
        <CardBody>
          <form onSubmit={handleCheck} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark dark:text-primary mb-2">
                Target URL
              </label>
              <Input
                type="url"
                placeholder="https://example.com/page-to-check"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                error={error}
                className="w-full"
              />
              <p className="text-xs text-gray-500 dark:text-secondary/60 mt-1">
                The URL you want to find backlinks to
              </p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-dark dark:text-primary mb-2">
                Sitemap URL
              </label>
              <Input
                type="url"
                placeholder="https://example.com/sitemap.xml"
                value={sitemapUrl}
                onChange={(e) => setSitemapUrl(e.target.value)}
                className="w-full"
              />
              <p className="text-xs text-gray-500 dark:text-secondary/60 mt-1">
                The sitemap containing pages to check for backlinks
              </p>
            </div>
            
            <Button type="submit" size="lg" loading={loading} className="w-full">
              Check for Backlinks
            </Button>
          </form>
        </CardBody>
      </Card>
      
      {result && (
        <>
          <Card>
            <CardHeader>
              <h2 className="text-xl font-semibold text-dark dark:text-primary">Results</h2>
            </CardHeader>
            <CardBody>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-secondary dark:bg-dark/50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-dark dark:text-primary">
                    {result.pages_checked}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-secondary/70">Pages Checked</div>
                </div>
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-4">
                  <div className="text-2xl font-bold text-green-600 dark:text-green-400">
                    {result.backlinks_found}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-secondary/70">Backlinks Found</div>
                </div>
                <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                    {((result.backlinks_found / result.pages_checked) * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-gray-500 dark:text-secondary/70">Backlink Rate</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-900/20 rounded-lg p-4">
                  <div className="text-2xl font-bold text-dark dark:text-primary">
                    {result.total_pages}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-secondary/70">Pages in Sitemap</div>
                </div>
              </div>
            </CardBody>
          </Card>
          
          <Card>
            <CardHeader>
              <h2 className="text-xl font-semibold text-dark dark:text-primary">
                Page Details ({result.sources.length})
              </h2>
            </CardHeader>
            <CardBody>
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {result.sources
                  .filter((source) => source.found)
                  .map((source, index) => (
                    <div
                      key={index}
                      className="bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-900/30 rounded-lg p-3"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="success">Found</Badge>
                        <a
                          href={source.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-dark dark:text-primary hover:underline truncate"
                        >
                          {source.source_url}
                        </a>
                      </div>
                      {source.link_text && (
                        <div className="mt-2 text-sm text-gray-600 dark:text-secondary/80">
                          <span className="font-medium">Link text:</span> {source.link_text}
                        </div>
                      )}
                    </div>
                  ))}
                
                {result.sources.filter((s) => s.found).length === 0 && (
                  <div className="text-center py-8 text-gray-500 dark:text-secondary/70">
                    <p>No backlinks found</p>
                  </div>
                )}
                
                {result.sources
                  .filter((source) => !source.found)
                  .map((source, index) => (
                    <div
                      key={`not-found-${index}`}
                      className="bg-gray-50 dark:bg-dark/50 border border-gray-200 dark:border-primary/20 rounded-lg p-3"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="low">Not Found</Badge>
                        <a
                          href={source.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-gray-600 dark:text-secondary/80 hover:underline truncate"
                        >
                          {source.source_url}
                        </a>
                      </div>
                      {source.error && (
                        <div className="mt-2 text-sm text-red-600 dark:text-red-400">
                          <span className="font-medium">Error:</span> {source.error}
                        </div>
                      )}
                    </div>
                  ))}
              </div>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}
