# LinkCanary

A command-line tool that crawls websites via sitemap, checks all links, and identifies broken links and redirect chains.

## Installation

```bash
# Clone the repository
git clone https://github.com/LinkCanary/LinkCanary.git
cd LinkCanary

# Create virtual environment and install
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

## Usage

```bash
# Basic usage
linkcheck https://example.com/sitemap.xml

# Check only internal links, exclude OK links from report
linkcheck https://example.com/sitemap.xml --internal-only --skip-ok

# Custom output file and slower crawl rate
linkcheck https://example.com/sitemap.xml -o report.csv --delay 2.0

# Test run on first 10 pages with verbose output
linkcheck https://example.com/sitemap.xml --max-pages 10 --verbose

# Include subdomains as internal links
linkcheck https://example.com/sitemap.xml --include-subdomains

# Only check pages modified after a specific date
linkcheck https://example.com/sitemap.xml --since 2025-01-01
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-o, --output` | `link_report.csv` | Output file path |
| `-d, --delay` | `0.5` | Seconds between requests |
| `-t, --timeout` | `10` | Request timeout in seconds |
| `--internal-only` | `false` | Only check internal links |
| `--external-only` | `false` | Only check external links |
| `--skip-ok` | `false` | Exclude 200 OK links from report |
| `--max-pages` | `none` | Limit pages to crawl (for testing) |
| `-v, --verbose` | `false` | Show detailed progress |
| `--user-agent` | `LinkCanary/1.0` | Custom User-Agent string |
| `--expand-duplicates` | `false` | Show all occurrences instead of aggregating |
| `--include-subdomains` | `false` | Treat subdomains as internal links |
| `--since` | `none` | Only crawl pages modified after date (YYYY-MM-DD) |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success - no issues found |
| `1` | Issues found - broken links or redirects detected |
| `2` | Crawl failure - couldn't fetch sitemap or fatal error |

## Report Output

The CSV report includes:

- **source_page** - Page where the link appears
- **occurrence_count** - Number of pages containing this link
- **link_url** - The problematic link
- **status_code** - HTTP status code
- **issue_type** - broken / redirect / redirect_chain / canonical_redirect / redirect_loop / ok
- **priority** - critical / high / medium / low
- **redirect_chain** - Full chain with status codes (e.g., `301:url1 → 302:url2 → 200:url3`)
- **final_url** - Where the link ultimately resolves
- **recommended_fix** - Suggested action
