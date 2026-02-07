<p align="center">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/version-0.3-green" alt="Version 0.3">
  <img src="https://img.shields.io/badge/license-MIT-orange" alt="MIT License">
</p>

# LinkCanary

**Find broken links and redirect chains before your visitors do.**

LinkCanary is an open-source site auditing tool built out of a messy website migration. It crawls your site via sitemap, checks every link on every page, and — crucially — maps each broken link or redirect back to **every page where it appears**. So you don't just get a list of problems, you get an actionable fix list.

Use it from the command line for quick audits, or spin up the included web UI for a dashboard experience with real-time progress and a reports library.

---

## The Story

LinkCanary was born out of a real disaster. After migrating a live business website from Squarespace to Ghost.io, the result was a mess — hundreds of 404 errors, broken internal links, and redirect chains that looped back on themselves. The site looked fine on the surface, but underneath, visitors and search engines were hitting dead ends everywhere.

Existing tools would tell you *that* a link was broken, but not *where it lived on your site* — which pages actually contained the bad link. When you're staring at 200+ broken URLs, knowing the destination is broken isn't enough. You need to know every page that links to it so you can actually fix the problem.

So LinkCanary was built to solve that specific pain: crawl the entire site, check every link, and for each broken or redirecting URL, show you **exactly which pages it appears on** and how many times. That's the difference between a list of problems and an actionable fix list.

## What It Does

LinkCanary crawls your website via sitemap, checks every link on every page, and generates a report that maps each issue back to its source pages. Here's what it catches:

- **Broken links (4xx, 5xx)** — dead ends for users and search engines, mapped to every page where they appear
- **Redirect chains** — traces the full hop path (e.g., `301:url1 → 302:url2 → 200:url3`) so you can update links to point directly to the final destination
- **Redirect loops** — catches infinite redirect cycles before your visitors hit them
- **Canonical URL mismatches** — identifies pages where the canonical tag doesn't match the served URL
- **Priority classification** — issues ranked as critical, high, medium, or low so you fix what matters first
- **Actionable fix recommendations** — each issue includes a suggested resolution
- **Occurrence tracking** — shows how many pages contain each bad link, so you can prioritize the most widespread problems
- **CSV + interactive HTML reports** — share with your team or clients, or plug into your workflow
- **Web-based UI** — run audits without touching the terminal

---

## Quick Start

```bash
# Clone and install
git clone https://github.com/LinkCanary/LinkCanary.git
cd LinkCanary
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scriptsctivate
pip install -e .

# Run your first audit
linkcheck https://yoursite.com/sitemap.xml --skip-ok --html-report report.html --open
```

That's it. LinkCanary will crawl every page in your sitemap, check every link on every page, and open an interactive HTML report in your browser when it's done.

---

## Usage

### Command Line

```bash
# Basic audit — outputs link_report.csv
linkcheck https://example.com/sitemap.xml

# Internal links only, skip healthy links
linkcheck https://example.com/sitemap.xml --internal-only --skip-ok

# Slower crawl rate to be polite to the server
linkcheck https://example.com/sitemap.xml -o report.csv --delay 2.0

# Quick test on first 10 pages with verbose output
linkcheck https://example.com/sitemap.xml --max-pages 10 --verbose

# Treat subdomains (blog.example.com) as internal
linkcheck https://example.com/sitemap.xml --include-subdomains

# Only check pages modified since a specific date
linkcheck https://example.com/sitemap.xml --since 2025-01-01

# Full audit with HTML report
linkcheck https://example.com/sitemap.xml --html-report report.html --open
```

### Generate HTML Report from Existing CSV

Already have a CSV from a previous run? Convert it to an interactive HTML report:

```bash
linkcheck-report link_report.csv -o report.html --open
```

### Web UI

For teams or non-technical users, LinkCanary includes a web-based dashboard.

```bash
cd linkcanary-ui
pip install -e .
linkcanary-ui --open
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

For production workloads, enable Celery/Redis for background task management:

```bash
pip install -e ".[celery]"
export LINKCANARY_USE_CELERY=true
redis-server &
celery -A backend.tasks.celery_app worker &
linkcanary-ui
```

**Web UI features:**

- Dashboard with one-click crawl launch
- Advanced configuration options
- Real-time progress monitoring
- Reports library with search and filtering
- Interactive report viewer
- CSV and HTML report downloads

---

## CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `link_report.csv` | Output file path |
| `-d, --delay` | `0.5` | Seconds between requests |
| `-t, --timeout` | `10` | Request timeout in seconds |
| `--internal-only` | `false` | Only check internal links |
| `--external-only` | `false` | Only check external links |
| `--skip-ok` | `false` | Exclude 200 OK links from report |
| `--max-pages` | none | Limit pages to crawl (useful for testing) |
| `-v, --verbose` | `false` | Show detailed progress |
| `--user-agent` | `LinkCanary/1.0` | Custom User-Agent string |
| `--expand-duplicates` | `false` | Show all occurrences instead of aggregating |
| `--include-subdomains` | `false` | Treat subdomains as internal links |
| `--since` | none | Only crawl pages modified after date (YYYY-MM-DD) |
| `--html-report` | none | Generate HTML report at specified path |
| `--open` | `false` | Open HTML report in browser after generation |

---

## Understanding the Report

LinkCanary outputs a CSV (and optionally an interactive HTML report) with the following columns:

| Column | Description |
|--------|-------------|
| `source_page` | The page where the problematic link was found |
| `occurrence_count` | Number of pages containing this link |
| `link_url` | The broken or redirecting URL |
| `status_code` | HTTP response code |
| `issue_type` | `broken` · `redirect` · `redirect_chain` · `canonical_redirect` · `redirect_loop` · `ok` |
| `priority` | `critical` · `high` · `medium` · `low` |
| `redirect_chain` | Full redirect path with status codes (e.g., `301:url1 → 302:url2 → 200:url3`) |
| `final_url` | Where the link ultimately resolves |
| `recommended_fix` | Suggested action to resolve the issue |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No issues found |
| `1` | Broken links or redirects detected |
| `2` | Crawl failure (couldn't fetch sitemap or fatal error) |

Exit codes make it easy to integrate LinkCanary into CI/CD pipelines — fail the build if broken links are introduced.

---

## Use Cases

- **Site migrations** — moved from Squarespace, WordPress, or another CMS? Verify that old URLs resolve correctly and catch the 404s and redirect loops that migrations inevitably create
- **Content teams** — audit your blog or docs site after restructuring URLs or reorganizing content
- **SEO professionals** — identify redirect chains that dilute link equity across client sites
- **Developers** — add `linkcheck` to your CI/CD pipeline to catch broken links before deploy
- **Agencies** — generate interactive HTML reports to share with clients

---

## Requirements

- Python 3.10+
- A `sitemap.xml` on your target site

### Dependencies

- `requests` — HTTP client
- `beautifulsoup4` + `lxml` — HTML parsing
- `pandas` — report generation
- `tqdm` — progress bars
- `urllib3` — URL handling

All dependencies install automatically via `pip install -e .`

---

## Contributing

Contributions are welcome! Whether it's a bug fix, new feature, or documentation improvement — open an issue or submit a pull request.

---

## License

MIT — use it however you want, commercially or otherwise.

---

<p align="center">
  <strong>Migrated your site recently? Don't wait for your traffic to drop.</strong><br>
  Run `linkcheck https://yoursite.com/sitemap.xml` and find out what's broken.
</p>
