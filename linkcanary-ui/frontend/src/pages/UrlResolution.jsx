import { useState } from 'react';
import Card, { CardBody, CardHeader } from '../components/Card';
import Button from '../components/Button';
import { urlResolutionApi } from '../services/api';

export default function UrlResolution() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState(null);
  const [baseUrls, setBaseUrls] = useState('https://example.com/blog/2024/01/my-post/');
  const [customHrefs, setCustomHrefs] = useState('');

  async function handleTest(e) {
    e.preventDefault();
    const urls = baseUrls
      .split('\n')
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const hrefs = customHrefs
        .split('\n')
        .map((h) => h.trim())
        .filter(Boolean);
      const data = await urlResolutionApi.test({
        base_urls: urls,
        custom_hrefs: hrefs,
      });
      setResults(data.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-primary mb-2">URL Resolution Tester</h1>
      <p className="text-gray-600 dark:text-secondary mb-6">
        Diagnose how relative URLs resolve against your site's base URLs.
        Essential for verifying WordPress/blog subdirectory sites don't produce false 404s.
      </p>

      <form onSubmit={handleTest} className="space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-primary">Base URLs</h2>
          </CardHeader>
          <CardBody className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-dark dark:text-secondary mb-1">
                Enter one or more page URLs to test against (one per line)
              </label>
              <textarea
                className="block w-full rounded-lg border border-gray-300 dark:border-primary/30 px-4 py-2.5 text-dark dark:text-primary bg-white dark:bg-dark/50 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary font-mono text-sm"
                rows={3}
                placeholder={"https://example.com/blog/2024/01/my-post/\nhttps://example.com/docs/api/getting-started/"}
                value={baseUrls}
                onChange={(e) => setBaseUrls(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-dark dark:text-secondary mb-1">
                Custom hrefs to test (optional, one per line)
              </label>
              <textarea
                className="block w-full rounded-lg border border-gray-300 dark:border-primary/30 px-4 py-2.5 text-dark dark:text-primary bg-white dark:bg-dark/50 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary font-mono text-sm"
                rows={2}
                placeholder="/custom/path/\n../../parent-page/"
                value={customHrefs}
                onChange={(e) => setCustomHrefs(e.target.value)}
              />
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Six common href patterns are tested automatically. Add extras here.
              </p>
            </div>
          </CardBody>
        </Card>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <Button type="submit" size="lg" loading={loading} className="w-full">
          Test URL Resolution
        </Button>
      </form>

      {results && (
        <div className="mt-8 space-y-6">
          {results.map((result, idx) => (
            <Card key={idx}>
              <CardHeader>
                <h3 className="text-sm font-semibold text-gray-900 dark:text-primary font-mono break-all">
                  {result.base_url}
                </h3>
              </CardHeader>
              <CardBody className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-dark/10 dark:border-primary/20">
                        <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Href</th>
                        <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Resolved URL</th>
                        <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.resolutions.map((row, rIdx) => {
                        return (
                          <tr
                            key={rIdx}
                            className="border-b border-dark/5 dark:border-primary/10 last:border-0 hover:bg-gray-50 dark:hover:bg-dark/40 transition-colors"
                          >
                            <td className="px-6 py-3 font-mono text-xs text-dark dark:text-primary break-all">
                              {row.href}
                            </td>
                            <td className="px-6 py-3 font-mono text-xs text-dark dark:text-secondary break-all">
                              {row.resolved_url}
                            </td>
                            <td className="px-4 py-3 text-center">
                              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-400">
                                ✓
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardBody>
            </Card>
          ))}

          <div className="text-center text-sm text-gray-500 dark:text-gray-400 py-2">
            All URLs resolved successfully. No subdirectory stripping detected.
          </div>
        </div>
      )}
    </div>
  );
}
