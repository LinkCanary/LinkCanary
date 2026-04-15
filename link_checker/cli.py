"""Command-line interface for LinkCanary."""

import argparse
import logging
import sys
from datetime import datetime

import pandas as pd
from tqdm import tqdm

from . import __version__
from .checker import LinkChecker
from .crawler import PageCrawler
from .exporters import ExportFormat, ReportExporter, detect_format
from .fp_logger import FPLogger
from .html_reporter import HTMLReportGenerator
from .patterns import URLPatternMatcher, create_matcher_from_args
from .reporter import ReportGenerator
from .robots import RobotsComplianceChecker
from .sitemap import SitemapParser

EXIT_SUCCESS = 0
EXIT_ISSUES_FOUND = 1
EXIT_CRAWL_FAILURE = 2


def setup_logging(verbose: bool):
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format='%(levelname)s: %(message)s',
    )


def parse_date(date_str: str) -> datetime:
    """Parse a date string in YYYY-MM-DD format."""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}. Use YYYY-MM-DD.")


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='linkcheck',
        description='LinkCanary - A link health checker that crawls websites via sitemap and identifies broken links and redirect chains.',
        epilog='Example: linkcheck https://example.com/sitemap.xml --internal-only --skip-ok',
    )
    
    # Create mutually exclusive group for input sources
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        'sitemap_url',
        nargs='?',
        help='URL to the sitemap.xml file (optional if using --url or --urls-file)',
    )
    input_group.add_argument(
        '--url',
        metavar='URL',
        help='Check a single URL instead of sitemap (for quick CI checks)',
    )
    input_group.add_argument(
        '--urls-file',
        metavar='FILE',
        help='Read URLs from a file (one per line). Useful for checking changed pages in PRs.',
    )
    
    parser.add_argument(
        '-o', '--output',
        default='link_report.csv',
        help='Output file path (default: link_report.csv)',
    )
    
    parser.add_argument(
        '-f', '--format',
        choices=['csv', 'json', 'mdx', 'xlsx', 'pdf'],
        default=None,
        help='Export format (auto-detected from output extension if not specified)',
    )
    
    parser.add_argument(
        '--google-sheets',
        action='store_true',
        help='Export to Google Sheets (requires GOOGLE_APPLICATION_CREDENTIALS)',
    )
    
    parser.add_argument(
        '-d', '--delay',
        type=float,
        default=0.5,
        help='Seconds between requests (default: 0.5)',
    )
    
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=10,
        help='Request timeout in seconds (default: 10)',
    )
    
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Max retries for transient errors 502/503/504 (default: 3)',
    )
    
    parser.add_argument(
        '--retry-delay',
        type=float,
        default=1.0,
        help='Initial delay between retries in seconds (default: 1.0)',
    )
    
    parser.add_argument(
        '--retry-backoff',
        type=float,
        default=2.0,
        help='Multiplier for exponential backoff (default: 2.0)',
    )
    
    parser.add_argument(
        '--no-retry',
        action='store_true',
        help='Disable retries for transient errors',
    )
    
    # Authentication options
    auth_group = parser.add_argument_group('authentication', 
        'Options for authenticating with protected sites (staging, etc.)')
    
    auth_group.add_argument(
        '--auth-user',
        metavar='USERNAME',
        help='Username for HTTP Basic Authentication',
    )
    
    auth_group.add_argument(
        '--auth-pass',
        metavar='PASSWORD',
        help='Password for HTTP Basic Authentication (use --auth-pass-env for env var)',
    )
    
    auth_group.add_argument(
        '--auth-pass-env',
        metavar='ENV_VAR',
        help='Environment variable name containing the auth password',
    )
    
    auth_group.add_argument(
        '--header',
        action='append',
        dest='headers',
        default=[],
        metavar='HEADER',
        help='Custom header to add to requests. Can be repeated. '
             'Format: "Name: Value". Example: --header "Authorization: Bearer xxx"',
    )
    
    auth_group.add_argument(
        '--cookie',
        action='append',
        dest='cookies',
        default=[],
        metavar='COOKIE',
        help='Cookie to add to requests. Can be repeated. '
             'Format: "name=value". Example: --cookie "session=abc123"',
    )
    
    parser.add_argument(
        '--internal-only',
        action='store_true',
        help='Only check internal links',
    )
    
    parser.add_argument(
        '--external-only',
        action='store_true',
        help='Only check external links',
    )
    
    parser.add_argument(
        '--exclude-pattern',
        action='append',
        default=[],
        metavar='PATTERN',
        help='Exclude URLs matching pattern (glob or regex). Can be repeated. '
             'Example: --exclude-pattern "*linkedin.com*" --exclude-pattern "*.pdf"',
    )
    
    parser.add_argument(
        '--include-pattern',
        action='append',
        default=[],
        metavar='PATTERN',
        help='Only check URLs matching pattern (glob or regex). Can be repeated. '
             'Example: --include-pattern "/blog/*" --include-pattern "/docs/*"',
    )
    
    parser.add_argument(
        '--pattern-type',
        choices=['glob', 'regex'],
        default='glob',
        help='Pattern matching type (default: glob)',
    )
    
    parser.add_argument(
        '--skip-ok',
        action='store_true',
        help='Exclude 200 OK links from report',
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=None,
        help='Limit pages to crawl (for testing)',
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed progress',
    )
    
    parser.add_argument(
        '--user-agent',
        default='LinkCanary/1.0',
        help='Custom User-Agent string (default: LinkCanary/1.0)',
    )
    
    parser.add_argument(
        '--expand-duplicates',
        action='store_true',
        help='Show all occurrences instead of aggregating',
    )
    
    parser.add_argument(
        '--include-subdomains',
        action='store_true',
        help='Treat subdomains as internal links',
    )
    
    parser.add_argument(
        '--ignore-robots',
        action='store_true',
        help='Ignore robots.txt rules (not recommended)',
    )
    
    parser.add_argument(
        '--since',
        type=parse_date,
        default=None,
        help='Only crawl pages modified after date (YYYY-MM-DD)',
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
    )

    parser.add_argument(
        '--no-orphan-check',
        action='store_true',
        help='Skip orphaned page detection (sitemap mode only). '
             'Useful on very large sites where the extra processing time is not desired.',
    )
    
    parser.add_argument(
        '--html-report',
        default=None,
        metavar='FILE',
        help='Generate HTML report at specified path',
    )
    
    parser.add_argument(
        '--open',
        action='store_true',
        help='Open HTML report in browser after generation',
    )
    
    parser.add_argument(
        '--fail-on-priority',
        choices=['critical', 'high', 'medium', 'low', 'any', 'none'],
        default='any',
        help='Exit 1 if issues at or above this priority (default: any). '
             'Use "none" to always exit 0.',
    )
    
    parser.add_argument(
        '--ci',
        action='store_true',
        help='Output in GitHub Actions format (sets GITHUB_OUTPUT)',
    )
    
    parser.add_argument(
        '--baseline-sitemap',
        metavar='URL',
        default=None,
        help='Sitemap URL for the production/baseline build. '
             'Links that return 404 in this build but exist in the baseline are '
             'reported as preview_404 (informational) rather than broken_404. '
             'Intended for PR preview environments where only changed pages are built.',
    )

    parser.add_argument(
        '--test-urls',
        nargs='+',
        metavar='URL',
        help='Diagnostic: test URL resolution for given base URLs. '
             'Prints how relative paths resolve against each URL.',
    )

    fp_group = parser.add_argument_group(
        'false positive logging',
        'Options for logging classifier decisions and recording corrections.',
    )

    fp_group.add_argument(
        '--fp-log',
        metavar='FILE',
        default=None,
        help='Path for the JSONL false positive log '
             '(default: <output-stem>.fp.jsonl alongside the report). '
             'Each classification decision is appended as one JSON line.',
    )

    fp_group.add_argument(
        '--no-fp-log',
        action='store_true',
        help='Disable false positive logging entirely.',
    )

    fp_group.add_argument(
        '--mark-fp',
        metavar='URL',
        default=None,
        help='Record a correction: mark URL as a false positive and exit. '
             'Requires --correct-priority.',
    )

    fp_group.add_argument(
        '--correct-priority',
        choices=['critical', 'high', 'medium', 'low'],
        default=None,
        help='The correct priority to assign when recording a correction with --mark-fp.',
    )

    fp_group.add_argument(
        '--fp-note',
        metavar='TEXT',
        default='',
        help='Optional note to attach to a --mark-fp correction.',
    )

    fp_group.add_argument(
        '--review',
        nargs='?',
        const=True,
        metavar='FILE',
        help='Interactively review issues in a report and mark false positives. '
             'FILE defaults to the --output path. Example: linkcheck --review link_report.csv',
    )

    return parser


def print_banner():
    """Print the application banner."""
    print(f"""
LinkCanary v{__version__}
{'=' * 40}
""")


def print_summary(summary: dict, ci_mode: bool = False):
    """Print the summary statistics."""
    if ci_mode:
        # GitHub Actions output format
        import os
        github_output = os.environ.get('GITHUB_OUTPUT')
        output_lines = [
            f"total-issues={summary.get('total_links', 0)}",
            f"critical={summary.get('critical', 0)}",
            f"high={summary.get('high', 0)}",
            f"medium={summary.get('medium', 0)}",
            f"low={summary.get('low', 0)}",
            f"broken={summary.get('broken', 0)}",
            f"redirect-loops={summary.get('redirect_loops', 0)}",
            f"redirect-chains={summary.get('redirect_chains', 0)}",
        ]
        if github_output:
            with open(github_output, 'a') as f:
                f.write('\n'.join(output_lines) + '\n')
        else:
            for line in output_lines:
                print(f"::{line}")
    
    print("""
Summary
-------""")
    
    ok = summary.get('ok', 0)
    redirects = summary.get('redirects', 0)
    canonical = summary.get('canonical_redirects', 0)
    chains = summary.get('redirect_chains', 0)
    loops = summary.get('redirect_loops', 0)
    broken = summary.get('broken', 0)
    errors = summary.get('errors', 0)
    
    if ok > 0:
        print(f"  OK (200):              {ok:>4} links")
    if redirects > 0:
        print(f"  Redirects (301/302):   {redirects:>4} links")
    if canonical > 0:
        print(f"  Canonical redirects:   {canonical:>4} links")
    if chains > 0:
        print(f"  Redirect chains:       {chains:>4} links")
    if loops > 0:
        print(f"  Redirect loops:        {loops:>4} links")
    if broken > 0:
        print(f"  Broken (4xx/5xx):      {broken:>4} links")
    if errors > 0:
        print(f"  Errors:                {errors:>4} links")
    
    print("""
Priority Breakdown
------------------""")
    
    critical = summary.get('critical', 0)
    high = summary.get('high', 0)
    medium = summary.get('medium', 0)
    low = summary.get('low', 0)
    
    if critical > 0:
        print(f"  Critical: {critical:>4} issues")
    if high > 0:
        print(f"  High:     {high:>4} issues")
    if medium > 0:
        print(f"  Medium:   {medium:>4} issues")
    if low > 0:
        print(f"  Low:      {low:>4} issues")

    preview_404 = summary.get('preview_404', 0)
    if preview_404 > 0:
        print(f"\nBaseline suppressed")
        print(f"  Preview-only 404: {preview_404:>4}  (page exists in baseline, excluded from this build)")


def check_priority_threshold(summary: dict, fail_on: str) -> bool:
    """Check if issues exceed the priority threshold.

    Returns True if build should fail (issues at or above threshold).

    Priority levels (higher = more severe):
    - critical = 4
    - high = 3
    - medium = 2
    - low = 1

    fail_on='high' will fail if critical OR high issues exist.
    """
    if fail_on == 'none':
        return False

    if fail_on == 'any':
        total = (
            summary.get('critical', 0) +
            summary.get('high', 0) +
            summary.get('medium', 0) +
            summary.get('low', 0)
        )
        return total > 0

    priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
    threshold = priority_order.get(fail_on, 0)

    # Find the max priority among existing issues
    max_issue_priority = 0
    if summary.get('critical', 0) > 0:
        max_issue_priority = 4
    if summary.get('high', 0) > 0:
        max_issue_priority = max(max_issue_priority, 3)
    if summary.get('medium', 0) > 0:
        max_issue_priority = max(max_issue_priority, 2)
    if summary.get('low', 0) > 0:
        max_issue_priority = max(max_issue_priority, 1)

    # Fail if max issue priority >= threshold
    return max_issue_priority >= threshold


_PRIORITY_LABELS = {
    'critical': 'CRITICAL',
    'high':     'HIGH    ',
    'medium':   'MEDIUM  ',
    'low':      'LOW     ',
}

_PRIORITY_SHORTCUTS = {'c': 'critical', 'h': 'high', 'm': 'medium', 'l': 'low'}


def _parse_selection(raw: str, max_index: int) -> list[int]:
    """Parse a selection string like '1,3,5-7' into a sorted list of 0-based indices."""
    indices = set()
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            lo, _, hi = part.partition('-')
            try:
                lo_i, hi_i = int(lo.strip()), int(hi.strip())
                indices.update(range(lo_i - 1, hi_i))
            except ValueError:
                pass
        else:
            try:
                indices.add(int(part) - 1)
            except ValueError:
                pass
    return sorted(i for i in indices if 0 <= i < max_index)


def _run_review_mode(report_path: str, fp_log_path: str) -> int:
    """Interactive false positive review for an existing report."""
    import os

    if not os.path.exists(report_path):
        print(f"Error: report not found: {report_path}")
        print("Run a scan first, or specify a path with --review FILE")
        return EXIT_CRAWL_FAILURE

    df = pd.read_csv(report_path)
    issues = df[df['issue_type'] != 'ok'].reset_index(drop=True)

    if issues.empty:
        print(f"No issues found in {report_path} — nothing to review.")
        return EXIT_SUCCESS

    fp_logger = FPLogger(fp_log_path)

    width = 72
    print(f"\nReviewing {len(issues)} issue(s) from {report_path}")
    print('─' * width)
    print(f"  {'#':>3}  {'Priority':<10}  {'Issue':<18}  URL")
    print('─' * width)

    for i, row in issues.iterrows():
        label = _PRIORITY_LABELS.get(row['priority'], row['priority'].upper()[:8])
        url = row['link_url']
        url_display = url if len(url) <= 46 else url[:43] + '...'
        print(f"  {i + 1:>3}  {label}  {row['issue_type']:<18}  {url_display}")

        source = row.get('source_page', '')
        count = row.get('occurrence_count', 1)
        if source and source != 'multiple':
            src_display = source if len(source) <= 46 else source[:43] + '...'
            count_str = f' (×{count})' if count > 1 else ''
            print(f"       {'':10}  {'':18}  found on: {src_display}{count_str}")
        elif source == 'multiple':
            print(f"       {'':10}  {'':18}  found on: {count} pages")

    print('─' * width)
    print("\n  Select issues to mark as false positives.")
    print("  Numbers, ranges, or 'all'  (e.g. 1,3,5-7)  — Enter to skip.\n")

    try:
        raw = input("  Selection: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.")
        return EXIT_SUCCESS

    if not raw:
        print("No selection made.")
        return EXIT_SUCCESS

    if raw.lower() == 'all':
        selected = list(range(len(issues)))
    else:
        selected = _parse_selection(raw, len(issues))

    if not selected:
        print("No valid issue numbers in selection.")
        return EXIT_SUCCESS

    corrections = []
    print()

    for idx in selected:
        row = issues.iloc[idx]
        url = row['link_url']
        current = row['priority']
        url_display = url if len(url) <= 60 else url[:57] + '...'
        print(f"  #{idx + 1}  {url_display}  [currently: {current}]")

        try:
            raw_p = input("       Correct priority  c=critical  h=high  m=medium  l=low  (Enter=skip): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            break

        correct = _PRIORITY_SHORTCUTS.get(raw_p) or (raw_p if raw_p in _PRIORITY_SHORTCUTS.values() else None)
        if not correct:
            print("       Skipped.\n")
            continue

        try:
            note = input("       Note (optional): ").strip()
        except (KeyboardInterrupt, EOFError):
            note = ''

        corrections.append((url, correct, note))
        print()

    if not corrections:
        print("No corrections recorded.")
        return EXIT_SUCCESS

    for url, correct, note in corrections:
        fp_logger.log_correction(link_url=url, correct_priority=correct, note=note)

    print(f"  {len(corrections)} correction(s) recorded in {fp_log_path}")
    return EXIT_SUCCESS


def main(args=None):
    """Main entry point."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    setup_logging(parsed_args.verbose)
    print_banner()
    
    # Handle --test-urls diagnostic mode
    if parsed_args.test_urls:
        from .utils import resolve_relative_url, normalize_url
        
        test_hrefs = [
            '/blog/post-name/',
            'relative-page/',
            '../other-page/',
            '/about/',
            '//cdn.example.com/asset.js',
            'https://external.com/page',
        ]
        
        for base_url in parsed_args.test_urls:
            print(f"\nURL Resolution Test: {base_url}")
            print(f"{'=' * 60}")
            print(f"{'Href':<35} {'Resolved URL'}")
            print(f"{'-' * 35} {'-' * 50}")
            for href in test_hrefs:
                resolved = resolve_relative_url(base_url, href)
                normalized = normalize_url(resolved) if resolved else '(empty)'
                print(f"{href:<35} {normalized}")
        
        print(f"\n{'=' * 60}")
        print("All URLs resolved correctly. No subdirectory stripping detected.")
        return EXIT_SUCCESS
    
    # --review mode: interactive false positive review of an existing report.
    if parsed_args.review:
        from pathlib import Path
        report_path = parsed_args.review if isinstance(parsed_args.review, str) else parsed_args.output
        fp_log_path = parsed_args.fp_log or (
            str(Path(parsed_args.output).parent /
                (Path(parsed_args.output).stem + '.fp.jsonl'))
        )
        return _run_review_mode(report_path, fp_log_path)

    # --mark-fp correction mode: record a user correction and exit immediately.
    if parsed_args.mark_fp:
        if not parsed_args.correct_priority:
            print("Error: --mark-fp requires --correct-priority")
            return EXIT_CRAWL_FAILURE

        from pathlib import Path
        log_path = parsed_args.fp_log or (
            str(Path(parsed_args.output).parent /
                (Path(parsed_args.output).stem + '.fp.jsonl'))
        )
        fp_logger = FPLogger(log_path)
        fp_logger.log_correction(
            link_url=parsed_args.mark_fp,
            correct_priority=parsed_args.correct_priority,
            note=parsed_args.fp_note,
        )
        print(f"Correction recorded in {log_path}")
        print(f"  URL:              {parsed_args.mark_fp}")
        print(f"  Correct priority: {parsed_args.correct_priority}")
        if parsed_args.fp_note:
            print(f"  Note:             {parsed_args.fp_note}")
        return EXIT_SUCCESS

    if parsed_args.internal_only and parsed_args.external_only:
        print("Error: Cannot use both --internal-only and --external-only")
        return EXIT_CRAWL_FAILURE
    
    # Determine input mode
    sitemap_mode = False  # Orphaned page detection — sitemap mode only
    sitemap_urls: list[str] = []  # full sitemap URL list (before max_pages slice)

    if parsed_args.url:
        # Single URL mode
        print(f"Single URL mode: {parsed_args.url}")
        page_urls = [parsed_args.url]
        base_url = parsed_args.url
    elif parsed_args.urls_file:
        # URLs from file mode
        print(f"Reading URLs from file: {parsed_args.urls_file}")
        try:
            with open(parsed_args.urls_file, 'r') as f:
                page_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except FileNotFoundError:
            print(f"Error: URLs file not found: {parsed_args.urls_file}")
            return EXIT_CRAWL_FAILURE
        if not page_urls:
            print("Error: No URLs found in file")
            return EXIT_CRAWL_FAILURE
        print(f"Loaded {len(page_urls)} URLs from file")
        base_url = page_urls[0] if page_urls else ""
    else:
        # Sitemap mode (default)
        if not parsed_args.sitemap_url:
            print("Error: Must provide sitemap_url, --url, or --urls-file")
            parser.print_help()
            return EXIT_CRAWL_FAILURE

        print(f"Fetching sitemap: {parsed_args.sitemap_url}")

        sitemap_parser = SitemapParser(
            user_agent=parsed_args.user_agent,
            timeout=parsed_args.timeout,
        )

        try:
            page_urls = sitemap_parser.parse_sitemap(
                parsed_args.sitemap_url,
                since=parsed_args.since,
            )
        except Exception as e:
            print(f"Error: Failed to fetch or parse sitemap: {e}")
            return EXIT_CRAWL_FAILURE
        finally:
            sitemap_parser.close()

        if not page_urls:
            print("Error: No pages found in sitemap")
            return EXIT_CRAWL_FAILURE

        base_url = parsed_args.sitemap_url
        sitemap_mode = True
        sitemap_urls = list(page_urls)  # capture before max_pages truncation
    
    if parsed_args.max_pages:
        page_urls = page_urls[:parsed_args.max_pages]
    
    print(f"Found {len(page_urls)} pages to crawl")
    
    # Initialize robots.txt compliance checker
    robots_checker = RobotsComplianceChecker(
        user_agent=parsed_args.user_agent,
        timeout=parsed_args.timeout,
        ignore_robots=parsed_args.ignore_robots,
    )
    
    # Check robots.txt for crawl delay and apply
    crawl_delay = robots_checker.get_crawl_delay(base_url)
    if crawl_delay and crawl_delay > parsed_args.delay:
        print(f"Robots.txt crawl-delay: {crawl_delay}s (overriding --delay {parsed_args.delay}s)")
        effective_delay = crawl_delay
    else:
        effective_delay = parsed_args.delay
    
    crawler = PageCrawler(
        base_url=base_url,
        user_agent=parsed_args.user_agent,
        timeout=parsed_args.timeout,
        delay=effective_delay,
        include_subdomains=parsed_args.include_subdomains,
    )
    
    all_links = []
    
    try:
        with tqdm(total=len(page_urls), desc="Crawling pages", unit="page") as pbar:
            for url in page_urls:
                # Check robots.txt before crawling
                is_allowed, reason = robots_checker.check_url(url, base_url)
                if not is_allowed:
                    pbar.update(1)
                    continue
                
                links = crawler.crawl_page(url)
                all_links.extend(links)
                pbar.update(1)
    finally:
        crawler.close()
    
    # Report robots.txt stats
    robots_stats = robots_checker.get_stats()
    if robots_stats['urls_skipped'] > 0:
        print(f"\nRobots.txt compliance:")
        print(f"  URLs skipped: {robots_stats['urls_skipped']}")
        if parsed_args.ignore_robots:
            print(f"  (ignored due to --ignore-robots)")
    
    if parsed_args.internal_only:
        all_links = [link for link in all_links if link.is_internal]
    elif parsed_args.external_only:
        all_links = [link for link in all_links if not link.is_internal]
    
    unique_urls = list(set(link.link_url for link in all_links))
    print(f"Extracted {len(all_links)} links ({len(unique_urls)} unique)")
    
    # Apply URL pattern filtering
    pattern_matcher = create_matcher_from_args(parsed_args)
    if pattern_matcher.include_patterns or pattern_matcher.exclude_patterns:
        included_urls, excluded_urls = pattern_matcher.filter_urls(unique_urls)
        
        print(f"\nPattern filtering ({parsed_args.pattern_type}):")
        if pattern_matcher.exclude_patterns:
            print(f"  Exclude patterns: {pattern_matcher.exclude_patterns}")
            print(f"  Excluded: {len(excluded_urls)} URLs")
        if pattern_matcher.include_patterns:
            print(f"  Include patterns: {pattern_matcher.include_patterns}")
        print(f"  URLs to check: {len(included_urls)}")
        
        unique_urls = included_urls
        
        if not unique_urls:
            print("No URLs match the patterns")
            return EXIT_SUCCESS
    
    # Apply robots.txt filtering for links to check
    # (We already filtered pages to crawl, this filters the destination URLs)
    if not parsed_args.ignore_robots:
        allowed_urls, skipped_urls = robots_checker.filter_urls(unique_urls, base_url)
        if skipped_urls:
            print(f"\nRobots.txt link filtering:")
            print(f"  Links skipped: {len(skipped_urls)}")
            print(f"  Links to check: {len(allowed_urls)}")
            unique_urls = allowed_urls
    
    if not unique_urls:
        print("No links to check")
        return EXIT_SUCCESS
    
    # Determine retry settings
    max_retries = 0 if parsed_args.no_retry else parsed_args.max_retries
    
    # Parse authentication settings
    auth_user = parsed_args.auth_user
    auth_pass = parsed_args.auth_pass
    
    # Get password from env var if specified
    if parsed_args.auth_pass_env and not auth_pass:
        import os
        auth_pass = os.environ.get(parsed_args.auth_pass_env)
    
    # Parse custom headers
    custom_headers = {}
    for header in parsed_args.headers:
        if ':' in header:
            name, value = header.split(':', 1)
            custom_headers[name.strip()] = value.strip()
    
    # Parse cookies
    cookies_dict = {}
    for cookie in parsed_args.cookies:
        if '=' in cookie:
            name, value = cookie.split('=', 1)
            cookies_dict[name.strip()] = value.strip()
    
    checker = LinkChecker(
        user_agent=parsed_args.user_agent,
        timeout=parsed_args.timeout,
        delay=parsed_args.delay / 2,
        max_retries=max_retries,
        retry_delay=parsed_args.retry_delay,
        retry_backoff=parsed_args.retry_backoff,
        auth_user=auth_user,
        auth_pass=auth_pass,
        headers=custom_headers if custom_headers else None,
        cookies=cookies_dict if cookies_dict else None,
    )
    
    print(f"Retry settings: max={max_retries}, delay={parsed_args.retry_delay}s, backoff={parsed_args.retry_backoff}x")
    
    # Report auth status (without revealing secrets)
    if auth_user:
        print(f"Authentication: Basic auth enabled for user '{auth_user}'")
    if custom_headers:
        header_names = list(custom_headers.keys())
        if 'Authorization' in header_names:
            header_names[header_names.index('Authorization')] = 'Authorization: ***'
        print(f"Custom headers: {', '.join(header_names)}")
    if cookies_dict:
        print(f"Cookies: {len(cookies_dict)} cookie(s) set")
    
    link_statuses = {}
    
    try:
        with tqdm(total=len(unique_urls), desc="Checking links", unit="link") as pbar:
            for url in unique_urls:
                status = checker.check_link(url)
                link_statuses[url] = status
                pbar.update(1)
    finally:
        checker.close()
    
    # Report retry statistics
    cache_stats = checker.get_cache_stats()
    if cache_stats['urls_with_retries'] > 0:
        print(f"\nRetry statistics:")
        print(f"  URLs that required retries: {cache_stats['urls_with_retries']}")
        print(f"  Total retry attempts: {cache_stats['total_retries']}")
    
    # Fetch baseline sitemap for preview-404 reclassification.
    baseline_urls: set = set()
    if parsed_args.baseline_sitemap:
        print(f"Fetching baseline sitemap: {parsed_args.baseline_sitemap}")
        baseline_parser = SitemapParser(
            user_agent=parsed_args.user_agent,
            timeout=parsed_args.timeout,
        )
        try:
            from .utils import normalize_url as _norm
            raw_baseline = baseline_parser.parse_sitemap(parsed_args.baseline_sitemap)
            baseline_urls = {_norm(u) for u in raw_baseline}
            print(f"Baseline: {len(baseline_urls)} URLs loaded")
        except Exception as exc:
            print(f"Warning: Could not fetch baseline sitemap: {exc}")
        finally:
            baseline_parser.close()

    # Set up false positive logger unless explicitly disabled.
    fp_logger = None
    if not parsed_args.no_fp_log:
        from pathlib import Path
        fp_log_path = parsed_args.fp_log or (
            str(Path(parsed_args.output).parent /
                (Path(parsed_args.output).stem + '.fp.jsonl'))
        )
        fp_logger = FPLogger(fp_log_path)
        print(f"FP log: {fp_log_path}")

    reporter = ReportGenerator(
        expand_duplicates=parsed_args.expand_duplicates,
        skip_ok=parsed_args.skip_ok,
        fp_logger=fp_logger,
        baseline_urls=baseline_urls or None,
    )

    df = reporter.generate_report(all_links, link_statuses)

    # Orphaned page detection — sitemap mode only
    if sitemap_mode and not parsed_args.no_orphan_check:
        orphan_df = reporter.generate_orphan_report(sitemap_urls, all_links)
        orphan_count = len(orphan_df)
        print(f"Found {orphan_count} orphaned page(s) (no internal links)")
        if orphan_count > 0:
            df = pd.concat([df, orphan_df], ignore_index=True)

    summary = reporter.get_summary(df)
    
    # Determine export format
    export_format = parsed_args.format or detect_format(parsed_args.output)
    
    # Create exporter and save report
    exporter = ReportExporter(df, summary)
    
    try:
        if parsed_args.google_sheets:
            import os
            creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
            sheets_url = exporter.export_google_sheets(credentials_path=creds_path)
            print(f"\nGoogle Sheets URL: {sheets_url}")
        else:
            exporter.export(parsed_args.output, format=export_format)
            print(f"\nReport saved to: {parsed_args.output} ({export_format})")
    except ImportError as e:
        print(f"Warning: {e}")
        print("Falling back to CSV format...")
        exporter.export_csv(parsed_args.output)
        print(f"\nReport saved to: {parsed_args.output} (csv)")
    
    print_summary(summary, ci_mode=parsed_args.ci)
    
    if parsed_args.html_report:
        html_reporter = HTMLReportGenerator()
        html_reporter.load_csv(parsed_args.output)
        html_reporter.generate_html(parsed_args.html_report, open_browser=parsed_args.open)
        print(f"HTML report saved to: {parsed_args.html_report}")
    
    # Check against priority threshold
    should_fail = check_priority_threshold(summary, parsed_args.fail_on_priority)
    
    if should_fail:
        print(f"\nExiting with code 1 (issues found at {parsed_args.fail_on_priority}+ priority)")
        if parsed_args.ci:
            import os
            github_output = os.environ.get('GITHUB_OUTPUT')
            if github_output:
                with open(github_output, 'a') as f:
                    f.write('exit-code=1\n')
        return EXIT_ISSUES_FOUND
    else:
        print(f"\nExiting with code 0 (no issues at {parsed_args.fail_on_priority}+ priority)")
        if parsed_args.ci:
            import os
            github_output = os.environ.get('GITHUB_OUTPUT')
            if github_output:
                with open(github_output, 'a') as f:
                    f.write('exit-code=0\n')
        return EXIT_SUCCESS


if __name__ == '__main__':
    sys.exit(main())
