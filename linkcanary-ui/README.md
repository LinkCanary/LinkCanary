# LinkCanary

Find broken links and redirect chains before your visitors do.

LinkCanary is an open-source site auditing tool that crawls your website via sitemap, checks every link, and surfaces the problems that silently kill your SEO — broken links, redirect chains, redirect loops, and canonical mismatches.

Use it from the command line for quick audits, or spin up the included web UI for a dashboard experience with real-time progress and a reports library.

## Why LinkCanary?

Every broken internal link is a dead end for users and search engines. Redirect chains bleed PageRank. Canonical mismatches confuse crawlers. These issues accumulate quietly — especially on content-heavy sites — and most people don't discover them until traffic drops.

LinkCanary gives you a fast, repeatable way to catch these problems:

- **Sitemap-driven crawling** — respects your site structure instead of brute-force spidering
- **Broken link detection** — flags 4xx and 5xx responses across internal and external links
- **Redirect chain mapping** — traces the full hop path (e.g., 301:url1 → 302:url2 → 200:url3)
- **Redirect loop detection** — catches infinite loops before your users hit them
- **Canonical URL analysis** — identifies pages where the canonical doesn't match the served URL
- **Priority classification** — issues ranked as critical, high, medium, or low so you fix what matters first
- **Actionable fix recommendations** — each issue includes a suggested resolution
- **CSV + interactive HTML reports** — share with your team or clients
- **Web-based UI** — run audits without touching the terminal

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

Open http://localhost:3000 in your browser.

For production workloads, enable Celery/Redis for background task management:

```bash
pip install -e ".[celery]"
export LINKCANARY_USE_CELERY=true
redis-server &
celery -A backend.tasks.celery_app worker &
linkcanary-ui
```

Web UI features:

- Dashboard with one-click crawl launch
- Advanced configuration options
- Real-time progress monitoring
- Reports library with search and filtering
- Interactive report viewer
- CSV and HTML report downloads
- Backlink checker tool

## CLI Options

| Flag                           | Default           | Description                                    |
|--------------------------------|-------------------|------------------------------------------------|
| -o, --output                   | link_report.csv   | Output file path                               |
| -d, --delay                    | 0.5               | Seconds between requests                       |
| -t, --timeout                  | 10                | Request timeout in seconds                     |
| --internal-only                | false             | Only check internal links                      |
| --external-only                | false             | Only check external links                      |
| --skip-ok                      | false             | Exclude 200 OK links from report               |
| --max-pages                    | none              | Limit pages to crawl (useful for testing)     |
| -v, --verbose                  | false             | Show detailed progress                          |
| --user-agent                   | LinkCanary/1.0    | Custom User-Agent string                       |
| --expand-duplicates            | false             | Show all occurrences instead of aggregating    |
| --include-subdomains           | false             | Treat subdomains as internal links             |
| --since                        | none              | Only crawl pages modified after date (YYYY-MM-DD) |
| --html-report                  | none              | Generate HTML report at specified path         |
| --open                         | false             | Open HTML report in browser after generation    |

## Understanding the Report

LinkCanary outputs a CSV (and optionally an interactive HTML report) with the following columns:

| Column            | Description                                                                      |
|-------------------|----------------------------------------------------------------------------------|
| source_page       | The page where the problematic link was found                                    |
| occurrence_count  | Number of pages containing this link                                            |
| link_url         | The broken or redirecting URL                                                   |
| status_code      | HTTP response code                                                               |
| issue_type       | broken · redirect · redirect_chain · canonical_redirect · redirect_loop · ok    |
| priority         | critical · high · medium · low                                                  |
| redirect_chain   | Full redirect path with status codes (e.g., 301:url1 → 302:url2 → 200:url3)     |
| final_url        | Where the link ultimately resolves                                              |
| recommended_fix  | Suggested action to resolve the issue                                            |

### Exit Codes

| Code | Meaning                                      |
|------|----------------------------------------------|
| 0    | No issues found                              |
| 1    | Broken links or redirects detected           |
| 2    | Crawl failure (couldn't fetch sitemap or fatal error) |

Exit codes make it easy to integrate LinkCanary into CI/CD pipelines — fail the build if broken links are introduced.

## Use Cases

- **Content teams** — audit your blog or docs site after a migration or URL restructure
- **SEO professionals** — identify redirect chains that dilute link equity across client sites
- **Developers** — add linkcheck to your CI/CD pipeline to catch broken links before deploy
- **Agencies** — generate branded HTML reports to share with clients
- **Site migrations** — verify that old URLs redirect correctly after moving platforms

## Requirements

- Python 3.10+
- A sitemap.xml on your target site

## Dependencies

All dependencies install automatically via Obtaining file:///Users/chesterbeard/Desktop/linkcanary/linkcanary-ui
  Installing build dependencies: started
  Installing build dependencies: finished with status 'done'
  Checking if build backend supports build_editable: started
  Checking if build backend supports build_editable: finished with status 'done'
  Getting requirements to build editable: started
  Getting requirements to build editable: finished with status 'done'
  Preparing editable metadata (pyproject.toml): started
  Preparing editable metadata (pyproject.toml): finished with status 'done'
Requirement already satisfied: linkcanary>=0.3 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (0.3)
Requirement already satisfied: fastapi>=0.109.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (0.115.6)
Requirement already satisfied: uvicorn>=0.27.0 in /opt/homebrew/lib/python3.11/site-packages (from uvicorn[standard]>=0.27.0->linkcanary-ui==0.1.0) (0.35.0)
Requirement already satisfied: websockets>=12.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (13.1)
Requirement already satisfied: sqlalchemy>=2.0.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (2.0.36)
Requirement already satisfied: aiosqlite>=0.19.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (0.22.1)
Requirement already satisfied: python-multipart>=0.0.6 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (0.0.20)
Requirement already satisfied: pydantic>=2.0.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (2.12.5)
Requirement already satisfied: pydantic-settings>=2.0.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary-ui==0.1.0) (2.10.1)
Requirement already satisfied: starlette<0.42.0,>=0.40.0 in /opt/homebrew/lib/python3.11/site-packages (from fastapi>=0.109.0->linkcanary-ui==0.1.0) (0.41.3)
Requirement already satisfied: typing-extensions>=4.8.0 in /opt/homebrew/lib/python3.11/site-packages (from fastapi>=0.109.0->linkcanary-ui==0.1.0) (4.15.0)
Requirement already satisfied: annotated-types>=0.6.0 in /opt/homebrew/lib/python3.11/site-packages (from pydantic>=2.0.0->linkcanary-ui==0.1.0) (0.7.0)
Requirement already satisfied: pydantic-core==2.41.5 in /opt/homebrew/lib/python3.11/site-packages (from pydantic>=2.0.0->linkcanary-ui==0.1.0) (2.41.5)
Requirement already satisfied: typing-inspection>=0.4.2 in /opt/homebrew/lib/python3.11/site-packages (from pydantic>=2.0.0->linkcanary-ui==0.1.0) (0.4.2)
Requirement already satisfied: anyio<5,>=3.4.0 in /opt/homebrew/lib/python3.11/site-packages (from starlette<0.42.0,>=0.40.0->fastapi>=0.109.0->linkcanary-ui==0.1.0) (4.9.0)
Requirement already satisfied: idna>=2.8 in /opt/homebrew/lib/python3.11/site-packages (from anyio<5,>=3.4.0->starlette<0.42.0,>=0.40.0->fastapi>=0.109.0->linkcanary-ui==0.1.0) (3.10)
Requirement already satisfied: sniffio>=1.1 in /opt/homebrew/lib/python3.11/site-packages (from anyio<5,>=3.4.0->starlette<0.42.0,>=0.40.0->fastapi>=0.109.0->linkcanary-ui==0.1.0) (1.3.1)
Requirement already satisfied: requests>=2.28.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary>=0.3->linkcanary-ui==0.1.0) (2.32.3)
Requirement already satisfied: beautifulsoup4>=4.11.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary>=0.3->linkcanary-ui==0.1.0) (4.13.3)
Requirement already satisfied: lxml>=4.9.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary>=0.3->linkcanary-ui==0.1.0) (5.3.0)
Requirement already satisfied: pandas>=1.5.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary>=0.3->linkcanary-ui==0.1.0) (2.2.3)
Requirement already satisfied: tqdm>=4.64.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary>=0.3->linkcanary-ui==0.1.0) (4.67.1)
Requirement already satisfied: urllib3>=1.26.0 in /opt/homebrew/lib/python3.11/site-packages (from linkcanary>=0.3->linkcanary-ui==0.1.0) (2.4.0)
Requirement already satisfied: soupsieve>1.2 in /opt/homebrew/lib/python3.11/site-packages (from beautifulsoup4>=4.11.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (2.6)
Requirement already satisfied: numpy>=1.23.2 in /opt/homebrew/lib/python3.11/site-packages (from pandas>=1.5.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (2.2.1)
Requirement already satisfied: python-dateutil>=2.8.2 in /opt/homebrew/lib/python3.11/site-packages (from pandas>=1.5.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (2.9.0.post0)
Requirement already satisfied: pytz>=2020.1 in /opt/homebrew/lib/python3.11/site-packages (from pandas>=1.5.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (2023.3)
Requirement already satisfied: tzdata>=2022.7 in /opt/homebrew/lib/python3.11/site-packages (from pandas>=1.5.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (2025.2)
Requirement already satisfied: python-dotenv>=0.21.0 in /opt/homebrew/lib/python3.11/site-packages (from pydantic-settings>=2.0.0->linkcanary-ui==0.1.0) (1.2.1)
Requirement already satisfied: six>=1.5 in /opt/homebrew/lib/python3.11/site-packages (from python-dateutil>=2.8.2->pandas>=1.5.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (1.17.0)
Requirement already satisfied: charset-normalizer<4,>=2 in /opt/homebrew/lib/python3.11/site-packages (from requests>=2.28.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (3.4.1)
Requirement already satisfied: certifi>=2017.4.17 in /opt/homebrew/lib/python3.11/site-packages (from requests>=2.28.0->linkcanary>=0.3->linkcanary-ui==0.1.0) (2025.1.31)
Requirement already satisfied: click>=7.0 in /opt/homebrew/lib/python3.11/site-packages (from uvicorn>=0.27.0->uvicorn[standard]>=0.27.0->linkcanary-ui==0.1.0) (8.1.8)
Requirement already satisfied: h11>=0.8 in /opt/homebrew/lib/python3.11/site-packages (from uvicorn>=0.27.0->uvicorn[standard]>=0.27.0->linkcanary-ui==0.1.0) (0.14.0)
Requirement already satisfied: httptools>=0.6.3 in /opt/homebrew/lib/python3.11/site-packages (from uvicorn[standard]>=0.27.0->linkcanary-ui==0.1.0) (0.6.4)
Requirement already satisfied: pyyaml>=5.1 in /opt/homebrew/lib/python3.11/site-packages (from uvicorn[standard]>=0.27.0->linkcanary-ui==0.1.0) (6.0.2)
Requirement already satisfied: uvloop>=0.15.1 in /opt/homebrew/lib/python3.11/site-packages (from uvicorn[standard]>=0.27.0->linkcanary-ui==0.1.0) (0.21.0)
Requirement already satisfied: watchfiles>=0.13 in /opt/homebrew/lib/python3.11/site-packages (from uvicorn[standard]>=0.27.0->linkcanary-ui==0.1.0) (1.0.5)
Building wheels for collected packages: linkcanary-ui
  Building editable for linkcanary-ui (pyproject.toml): started
  Building editable for linkcanary-ui (pyproject.toml): finished with status 'done'
  Created wheel for linkcanary-ui: filename=linkcanary_ui-0.1.0-0.editable-py3-none-any.whl size=5053 sha256=8b33f6b8806905adabd52ad7f0d39ec858d383b75f59c7db377f37764fe05e75
  Stored in directory: /private/var/folders/c5/5t8_llkj5nzc3ksbfy9qqhpm0000gn/T/pip-ephem-wheel-cache-4d59jruh/wheels/d0/7c/cb/61918c420078f3c1b502d670f9ff50cd33f23cb5ad9bd8447e
Successfully built linkcanary-ui
Installing collected packages: linkcanary-ui
  Attempting uninstall: linkcanary-ui
    Found existing installation: linkcanary-ui 0.1.0
    Uninstalling linkcanary-ui-0.1.0:
      Successfully uninstalled linkcanary-ui-0.1.0
Successfully installed linkcanary-ui-0.1.0:

- requests — HTTP client
- beautifulsoup4 + lxml — HTML parsing
- pandas — report generation
- tqdm — progress bars
- urllib3 — URL handling

## Contributing

Contributions are welcome! Whether it's a bug fix, new feature, or documentation improvement — open an issue or submit a pull request.

## License

MIT — use it however you want, commercially or otherwise.
