import React, { useState } from 'react';
import Card, { CardBody, CardHeader } from '../components/Card';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

// ---------------------------------------------------------------------------
// Copy-to-clipboard button — rendered next to each code block title
// ---------------------------------------------------------------------------
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard API unavailable (non-HTTPS dev env, etc.) — fail silently
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="text-xs px-2 py-1 rounded bg-primary/20 text-primary hover:bg-primary/40 transition-colors font-mono"
      title="Copy to clipboard"
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Reusable labelled code block
// ---------------------------------------------------------------------------
function CodeBlock({ label, language = 'yaml', code }) {
  return (
    <div className="space-y-1">
      {label && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            {label}
          </span>
          <CopyButton text={code} />
        </div>
      )}
      <div className="rounded-lg overflow-hidden text-sm">
        <SyntaxHighlighter
          language={language}
          style={atomDark}
          customStyle={{ margin: 0, borderRadius: '0.5rem', fontSize: '0.8125rem' }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styled table helpers
// ---------------------------------------------------------------------------
function DocTable({ headers, rows }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-dark/10 dark:border-primary/20">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 dark:bg-dark/60">
            {headers.map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide border-b border-dark/10 dark:border-primary/20"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className={`border-b border-dark/5 dark:border-primary/10 last:border-0 ${
                i % 2 === 0 ? '' : 'bg-gray-50/50 dark:bg-dark/40'
              }`}
            >
              {row.map((cell, j) => (
                <td
                  key={j}
                  className="px-4 py-3 text-gray-700 dark:text-gray-300 align-top"
                >
                  {typeof cell === 'string' && cell.startsWith('`') ? (
                    <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">
                      {cell.replace(/`/g, '')}
                    </code>
                  ) : (
                    cell
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pill / badge for Required / Optional
// ---------------------------------------------------------------------------
function Pill({ required }) {
  return required ? (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400">
      Required
    </span>
  ) : (
    <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-dark/60 dark:text-gray-400">
      Optional
    </span>
  );
}

// ---------------------------------------------------------------------------
// Code snippets (defined as constants to keep JSX readable)
// ---------------------------------------------------------------------------

const MINIMAL_WORKFLOW = `name: LinkCanary Crawl

on:
  schedule:
    - cron: '0 6 * * 1'   # Every Monday at 06:00 UTC
  workflow_dispatch:
    inputs:
      sitemap-url:
        description: 'URL to sitemap.xml'
        required: false
        default: ''
      fail-on-priority:
        description: 'Minimum priority to fail build (critical/high/medium/low/any/none)'
        required: false
        default: 'high'

jobs:
  linkcanary:
    name: Run LinkCanary Crawl
    runs-on: ubuntu-latest
    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        cache: 'pip'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e .

    - name: Run LinkCanary crawl
      id: run-linkcanary
      continue-on-error: true
      run: |
        linkcheck '\${{ inputs.sitemap-url }}' \\
          --fail-on-priority '\${{ inputs.fail-on-priority }}' \\
          --skip-ok \\
          --ci

    - name: Upload link report artifact
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: linkcanary-report
        path: |
          link_report.*
          linkcanary-report.*
        retention-days: 30`;

const SITEMAP_MODE = `# .github/workflows/linkcanary.yml
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'   # Weekly Monday sweep
  workflow_dispatch:

jobs:
  linkcanary:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.11', cache: pip }
    - run: pip install -e .
    - name: Full-site crawl
      run: |
        linkcheck https://example.com/sitemap.xml \\
          --fail-on-priority high \\
          --skip-ok \\
          --format csv \\
          --delay 0.5 \\
          --ci`;

const SINGLE_URL_MODE = `# Triggered by a CMS publish webhook or PR comment
on:
  workflow_dispatch:
    inputs:
      url:
        description: 'Single URL to check'
        required: true

jobs:
  linkcanary:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.11', cache: pip }
    - run: pip install -e .
    - name: Single-URL check
      run: |
        linkcheck --url '\${{ inputs.url }}' \\
          --fail-on-priority high \\
          --skip-ok \\
          --ci`;

const CHANGED_PAGES_MODE = `# PR workflow: generate urls-to-check.txt from changed files,
# then pass it to LinkCanary
on:
  pull_request:
    branches: [main]

jobs:
  linkcanary:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
      with: { fetch-depth: 0 }

    - name: Collect changed page URLs
      run: |
        git diff --name-only origin/main...HEAD \\
          | grep -E '^(src|content|pages)/' \\
          | sed 's|^src/||; s|index.jsx||; s|\\.jsx||' \\
          | awk '{print "https://example.com/" $0}' \\
          > urls-to-check.txt
        cat urls-to-check.txt

    - uses: actions/setup-python@v5
      with: { python-version: '3.11', cache: pip }
    - run: pip install -e .

    - name: Check changed pages
      run: |
        linkcheck --urls-file urls-to-check.txt \\
          --fail-on-priority high \\
          --skip-ok \\
          --ci`;

const OUTPUTS_USAGE = `jobs:
  linkcanary:
    runs-on: ubuntu-latest
    outputs:
      total-issues: \${{ steps.run-linkcanary.outputs.total-issues }}
      broken:       \${{ steps.run-linkcanary.outputs.broken }}
      exit-code:    \${{ steps.run-linkcanary.outputs.exit-code }}
    steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.11', cache: pip }
    - run: pip install -e .
    - id: run-linkcanary
      continue-on-error: true
      run: linkcheck https://example.com/sitemap.xml --ci

  notify:
    needs: linkcanary
    runs-on: ubuntu-latest
    if: \${{ needs.linkcanary.outputs.broken > 0 }}
    steps:
    - name: Post summary
      run: |
        echo "Broken links: \${{ needs.linkcanary.outputs.broken }}"
        echo "Total issues: \${{ needs.linkcanary.outputs.total-issues }}"
        echo "Exit code:    \${{ needs.linkcanary.outputs.exit-code }}"`;

const WEBHOOK_API_CALL = `POST https://api.github.com/repos/{owner}/{repo}/actions/workflows/linkcanary.yml/dispatches
Authorization: Bearer {GITHUB_PAT}
Content-Type: application/json

{
  "ref": "main",
  "inputs": {
    "url": "https://example.com/blog/new-post",
    "fail-on-priority": "high"
  }
}`;

const CONTENTFUL_WEBHOOK = `# Contentful — Webhook settings → URL
# Event: Entry published

# URL: (your own relay function / GitHub App — see note below)
# Or use a simple serverless function that calls the GitHub API:

# curl example (run from Contentful Webhook or a relay):
curl -X POST \\
  https://api.github.com/repos/YOUR_ORG/YOUR_REPO/actions/workflows/linkcanary.yml/dispatches \\
  -H "Authorization: Bearer \$GITHUB_PAT" \\
  -H "Content-Type: application/json" \\
  -d '{
    "ref": "main",
    "inputs": {
      "url": "https://example.com/\${ payload.fields.slug['en-US'] }",
      "fail-on-priority": "high"
    }
  }'`;

const SANITY_WEBHOOK = `# sanity.io → API → Webhooks → Create webhook
# Trigger: document published
# HTTP method: POST
# URL: point to a serverless relay (e.g. Vercel edge function)

# In your relay function:
await fetch(
  'https://api.github.com/repos/YOUR_ORG/YOUR_REPO/actions/workflows/linkcanary.yml/dispatches',
  {
    method: 'POST',
    headers: {
      Authorization: \`Bearer \${process.env.GITHUB_PAT}\`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      ref: 'main',
      inputs: {
        url: \`https://example.com/\${body.slug.current}\`,
        'fail-on-priority': 'high',
      },
    }),
  }
);`;

const GHOST_WEBHOOK = `# Ghost Admin → Integrations → Custom integration → Webhooks
# Event: Post published
# Target URL: your relay endpoint (or direct GitHub API via a proxy)

# Ghost sends a POST with the post payload.
# Your relay extracts the URL and calls the GitHub API:

curl -X POST \\
  https://api.github.com/repos/YOUR_ORG/YOUR_REPO/actions/workflows/linkcanary.yml/dispatches \\
  -H "Authorization: Bearer \$GITHUB_PAT" \\
  -H "Content-Type: application/json" \\
  -d "{
    \\"ref\\": \\"main\\",
    \\"inputs\\": {
      \\"url\\": \\"https://example.com\${post.url}\\",
      \\"fail-on-priority\\": \\"high\\"
    }
  }"`;

const LOCAL_USAGE = `# Install
pip install linkcanary

# Full-site crawl
linkcheck https://example.com/sitemap.xml --fail-on-priority high --skip-ok

# Single URL
linkcheck --url https://example.com/blog/post --fail-on-priority high

# URL list from file
linkcheck --urls-file urls.txt --fail-on-priority high --skip-ok

# Export as JSON, limit to 100 pages, 0.5 s between requests
linkcheck https://example.com/sitemap.xml \\
  --format json \\
  --max-pages 100 \\
  --delay 0.5 \\
  --skip-ok`;

// ---------------------------------------------------------------------------
// Inputs reference data (sourced from linkcanary.yml)
// ---------------------------------------------------------------------------
const INPUT_ROWS = [
  ['`sitemap-url`', <Pill required={false} />, '`""`',          'URL to sitemap.xml. Used when neither url nor urls-file is provided.'],
  ['`url`',         <Pill required={false} />, '`""`',          'Check a single URL. Overrides sitemap-url. Useful for CMS publish webhooks.'],
  ['`urls-file`',   <Pill required={false} />, '`""`',          'Path to a newline-separated file of URLs to check.'],
  ['`fail-on-priority`', <Pill required={false} />, '`"high"`', 'Minimum priority level that causes the build to fail. Options: critical / high / medium / low / any / none.'],
  ['`max-pages`',   <Pill required={false} />, '`"0"`',         'Cap the number of pages crawled. 0 = unlimited.'],
  ['`skip-ok`',     <Pill required={false} />, '`"true"`',      'Exclude 200 OK responses from the report output. true / false.'],
  ['`delay`',       <Pill required={false} />, '`"0.5"`',       'Seconds to wait between requests. Increase to reduce server load.'],
  ['`timeout`',     <Pill required={false} />, '`"10"`',        'Per-request timeout in seconds.'],
  ['`format`',      <Pill required={false} />, '`"csv"`',       'Report export format. Options: csv / json / mdx / xlsx / pdf.'],
  ['`exclude-pattern`', <Pill required={false} />, '`""`',      'Newline-separated list of URL patterns to skip.'],
  ['`auth-user`',   <Pill required={false} />, '`""`',          'Username for HTTP basic auth. Use a GitHub secret — never hard-code.'],
  ['`auth-pass`',   <Pill required={false} />, '`""`',          'Password for HTTP basic auth. Use a GitHub secret.'],
  ['`webhook-url`', <Pill required={false} />, '`""`',          'Webhook URL for Slack or Discord notifications when the crawl finishes.'],
];

const OUTPUT_ROWS = [
  ['`total-issues`', 'Total number of issues found across all priority levels.'],
  ['`critical`',     'Count of critical-priority issues (e.g. 5xx server errors).'],
  ['`high`',         'Count of high-priority issues (e.g. 404 not found).'],
  ['`medium`',       'Count of medium-priority issues.'],
  ['`low`',          'Count of low-priority issues (e.g. redirects).'],
  ['`broken`',       'Total broken links detected (typically critical + high combined).'],
  ['`exit-code`',    'Raw process exit code. 0 = clean, non-zero = issues exceeded threshold.'],
];

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------
export default function CiDocs() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">

      {/* ------------------------------------------------------------------ */}
      {/* Page header                                                          */}
      {/* ------------------------------------------------------------------ */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          CI &amp; Integration Setup
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-400">
          Run LinkCanary automatically in your CI pipeline to catch broken links before they ship.
        </p>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Section 1 — GitHub Actions Quick Start                              */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm">1</span>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">GitHub Actions — Quick Start</h2>
          </div>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Drop the workflow file below into <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">.github/workflows/linkcanary.yml</code> and
            set the <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">LINKCANARY_SITEMAP</code> variable (or pass <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">sitemap-url</code> as a workflow input).
            The workflow runs on a weekly schedule and can also be triggered manually or via webhook.
          </p>
        </CardHeader>
        <CardBody>
          <CodeBlock label="Minimal linkcanary.yml" code={MINIMAL_WORKFLOW} />
        </CardBody>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Section 2 — Three modes                                             */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm">2</span>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Three Crawl Modes</h2>
          </div>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            LinkCanary supports three input modes. Choose the one that fits your workflow — or combine them across jobs.
          </p>
        </CardHeader>
        <CardBody className="space-y-8">

          {/* Sitemap mode */}
          <div className="space-y-3">
            <div>
              <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200">Sitemap mode</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                Full-site crawl. Best for scheduled sweeps or post-deploy verification on <code className="font-mono text-xs">main</code>.
              </p>
            </div>
            <CodeBlock label="sitemap-mode.yml" code={SITEMAP_MODE} />
          </div>

          <div className="border-t border-dark/10 dark:border-primary/10" />

          {/* Single URL mode */}
          <div className="space-y-3">
            <div>
              <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200">Single URL mode</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                Fast check for a specific page. Ideal for PR feedback loops or CMS publish webhooks where you know exactly which URL changed.
              </p>
            </div>
            <CodeBlock label="single-url-mode.yml" code={SINGLE_URL_MODE} />
          </div>

          <div className="border-t border-dark/10 dark:border-primary/10" />

          {/* Changed pages mode */}
          <div className="space-y-3">
            <div>
              <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200">Changed pages mode</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                Derives a URL list from files changed in a PR and passes them to LinkCanary via <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">--urls-file</code>. Faster than a full crawl and scoped to only what changed.
              </p>
            </div>
            <CodeBlock label="changed-pages-mode.yml" code={CHANGED_PAGES_MODE} />
          </div>

        </CardBody>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Section 3 — Inputs reference                                        */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm">3</span>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Inputs Reference</h2>
          </div>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            All workflow inputs are optional. Defaults are chosen for safe, low-noise CI runs. Pass them under <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">workflow_dispatch.inputs</code> or via the API <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">inputs</code> object.
          </p>
        </CardHeader>
        <CardBody>
          <DocTable
            headers={['Input', 'Required', 'Default', 'Description']}
            rows={INPUT_ROWS}
          />
        </CardBody>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Section 4 — Outputs reference                                       */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm">4</span>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Outputs Reference</h2>
          </div>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            When <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">--ci</code> flag is set, LinkCanary writes structured outputs to <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">$GITHUB_OUTPUT</code>. Reference them in downstream jobs using <code className="font-mono text-xs bg-gray-100 dark:bg-dark/60 px-1.5 py-0.5 rounded text-primary">needs.linkcanary.outputs.*</code>.
          </p>
        </CardHeader>
        <CardBody className="space-y-6">
          <DocTable
            headers={['Output', 'Description']}
            rows={OUTPUT_ROWS}
          />
          <CodeBlock label="Using outputs in a downstream job" code={OUTPUTS_USAGE} />
        </CardBody>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Section 5 — CMS Webhook Integration                                 */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm">5</span>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">CMS Webhook Integration</h2>
          </div>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Trigger a single-URL LinkCanary run the moment a page is published in your CMS.
            The pattern is: <strong className="text-gray-700 dark:text-gray-300">CMS publish event → webhook → relay (serverless function or proxy) → GitHub API → LinkCanary workflow runs</strong>.
            This catches broken links on the exact page that just went live, before anyone sees it.
          </p>
        </CardHeader>
        <CardBody className="space-y-8">

          {/* GitHub API call */}
          <div className="space-y-3">
            <h3 className="text-base font-semibold text-gray-800 dark:text-gray-200">GitHub API dispatch call</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Every CMS integration below ultimately makes this API call. Store your GitHub PAT as a secret in the CMS webhook config — never hard-code it.
            </p>
            <CodeBlock label="GitHub workflow dispatch — REST API" language="http" code={WEBHOOK_API_CALL} />
            <div className="rounded-lg border border-yellow-200 dark:border-yellow-800/50 bg-yellow-50 dark:bg-yellow-900/20 px-4 py-3 text-sm text-yellow-800 dark:text-yellow-300">
              <strong>PAT scopes required:</strong> your GitHub Personal Access Token needs the <code className="font-mono text-xs">workflow</code> scope. Create it at <em>GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens</em> and scope it to only the target repository.
            </div>
          </div>

          <div className="border-t border-dark/10 dark:border-primary/10" />

          {/* Contentful */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-gray-800 dark:text-gray-200">Contentful</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium">Webhook settings</span>
            </div>
            <ol className="text-sm text-gray-600 dark:text-gray-400 list-decimal list-inside space-y-1">
              <li>Open <em>Contentful → Space settings → Webhooks → Add webhook</em>.</li>
              <li>Set the trigger to <strong>Entry published</strong>.</li>
              <li>Point the URL to a small relay function (e.g. a Vercel or Cloudflare Worker) that calls the GitHub API below — Contentful cannot send the <code className="font-mono text-xs">Authorization</code> header directly with a secret injection.</li>
              <li>Store <code className="font-mono text-xs">GITHUB_PAT</code> as an environment variable in your relay function.</li>
            </ol>
            <CodeBlock label="Contentful relay example (bash / curl)" language="bash" code={CONTENTFUL_WEBHOOK} />
          </div>

          <div className="border-t border-dark/10 dark:border-primary/10" />

          {/* Sanity */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-gray-800 dark:text-gray-200">Sanity</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 font-medium">GROQ-powered webhook</span>
            </div>
            <ol className="text-sm text-gray-600 dark:text-gray-400 list-decimal list-inside space-y-1">
              <li>Go to <em>sanity.io/manage → your project → API → Webhooks → Create webhook</em>.</li>
              <li>Set trigger to <strong>document.published</strong> and filter to your page document type.</li>
              <li>Point the URL at a relay function (Next.js API route, Vercel function, etc.).</li>
              <li>Set <code className="font-mono text-xs">GITHUB_PAT</code> in your relay's environment variables.</li>
            </ol>
            <CodeBlock label="Sanity relay (Node.js / fetch)" language="javascript" code={SANITY_WEBHOOK} />
          </div>

          <div className="border-t border-dark/10 dark:border-primary/10" />

          {/* Ghost */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-base font-semibold text-gray-800 dark:text-gray-200">Ghost</span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-dark/60 text-gray-600 dark:text-gray-400 font-medium">Custom integration</span>
            </div>
            <ol className="text-sm text-gray-600 dark:text-gray-400 list-decimal list-inside space-y-1">
              <li>Go to <em>Ghost Admin → Integrations → Add custom integration</em>.</li>
              <li>Under <em>Webhooks</em>, add a webhook for the <strong>Post published</strong> event.</li>
              <li>Set the target URL to your relay endpoint. Ghost posts the full post payload as JSON.</li>
              <li>Extract <code className="font-mono text-xs">post.current.url</code> from the payload and dispatch the workflow.</li>
            </ol>
            <CodeBlock label="Ghost relay example (bash / curl)" language="bash" code={GHOST_WEBHOOK} />
          </div>

        </CardBody>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Section 6 — Local usage                                             */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-primary/20 text-primary font-bold text-sm">6</span>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Local Usage</h2>
          </div>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Run LinkCanary locally to debug issues or audit a site before adding CI.
            Requires Python 3.9+.
          </p>
        </CardHeader>
        <CardBody>
          <CodeBlock label="Install &amp; run" language="bash" code={LOCAL_USAGE} />
        </CardBody>
      </Card>

    </div>
  );
}
