"""Command-line interface for LinkCanary."""

import argparse
import logging
import sys
from datetime import datetime

from tqdm import tqdm

from . import __version__
from .checker import LinkChecker
from .crawler import PageCrawler
from .html_reporter import HTMLReportGenerator
from .reporter import ReportGenerator
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
    
    parser.add_argument(
        'sitemap_url',
        help='URL to the sitemap.xml file',
    )
    
    parser.add_argument(
        '-o', '--output',
        default='link_report.csv',
        help='Output file path (default: link_report.csv)',
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


def main(args=None):
    """Main entry point."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)
    
    setup_logging(parsed_args.verbose)
    print_banner()
    
    if parsed_args.internal_only and parsed_args.external_only:
        print("Error: Cannot use both --internal-only and --external-only")
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
    
    if parsed_args.max_pages:
        page_urls = page_urls[:parsed_args.max_pages]
    
    print(f"Found {len(page_urls)} pages to crawl")
    
    crawler = PageCrawler(
        base_url=parsed_args.sitemap_url,
        user_agent=parsed_args.user_agent,
        timeout=parsed_args.timeout,
        delay=parsed_args.delay,
        include_subdomains=parsed_args.include_subdomains,
    )
    
    all_links = []
    
    try:
        with tqdm(total=len(page_urls), desc="Crawling pages", unit="page") as pbar:
            for url in page_urls:
                links = crawler.crawl_page(url)
                all_links.extend(links)
                pbar.update(1)
    finally:
        crawler.close()
    
    if parsed_args.internal_only:
        all_links = [link for link in all_links if link.is_internal]
    elif parsed_args.external_only:
        all_links = [link for link in all_links if not link.is_internal]
    
    unique_urls = list(set(link.link_url for link in all_links))
    print(f"Extracted {len(all_links)} links ({len(unique_urls)} unique)")
    
    if not unique_urls:
        print("No links to check")
        return EXIT_SUCCESS
    
    checker = LinkChecker(
        user_agent=parsed_args.user_agent,
        timeout=parsed_args.timeout,
        delay=parsed_args.delay / 2,
    )
    
    link_statuses = {}
    
    try:
        with tqdm(total=len(unique_urls), desc="Checking links", unit="link") as pbar:
            for url in unique_urls:
                status = checker.check_link(url)
                link_statuses[url] = status
                pbar.update(1)
    finally:
        checker.close()
    
    reporter = ReportGenerator(
        expand_duplicates=parsed_args.expand_duplicates,
        skip_ok=parsed_args.skip_ok,
    )
    
    df = reporter.generate_report(all_links, link_statuses)
    
    reporter.save_report(df, parsed_args.output)
    
    summary = reporter.get_summary(df)
    print_summary(summary, ci_mode=parsed_args.ci)
    
    print(f"\nReport saved to: {parsed_args.output}")
    
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
