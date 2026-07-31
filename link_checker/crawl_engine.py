"""Subprocess wrapper for the Go crawl-engine binary.

Finds and invokes the Go crawl-engine, parses its JSON output, and
converts the results into the same Python data structures (ExtractedLink,
LinkStatus) that the existing CLI uses. This lets the CLI swap the
Python crawl/check pipeline for the Go one transparently.
"""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .checker import LinkStatus
from .crawler import ExtractedLink

logger = logging.getLogger(__name__)

# Names to try when looking for the binary on PATH.
_BINARY_NAMES = ["linkcanary-crawl-engine", "crawl-engine"]

# Relative path to a locally-built binary (crawl-engine/ dir).
_LOCAL_BINARY = Path(__file__).resolve().parent.parent / "crawl-engine" / "crawl-engine"


@dataclass
class CrawlEngineResult:
    """Parsed output from the Go crawl-engine."""
    links: list[ExtractedLink] = field(default_factory=list)
    link_statuses: dict[str, LinkStatus] = field(default_factory=dict)
    page_urls: list[str] = field(default_factory=list)
    sitemap_urls: list[str] = field(default_factory=list)
    page_html: dict[str, str] = field(default_factory=dict)
    robots_stats: dict = field(default_factory=dict)
    retry_stats: dict = field(default_factory=dict)
    baseline_urls: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def find_crawl_engine() -> Optional[str]:
    """Locate the Go crawl-engine binary.

    Checks the local crawl-engine/ directory first, then PATH.
    Returns the path or None if not found.
    """
    # Check local build
    if _LOCAL_BINARY.exists() and os.access(_LOCAL_BINARY, os.X_OK):
        return str(_LOCAL_BINARY)

    # Check PATH
    for name in _BINARY_NAMES:
        path = shutil.which(name)
        if path:
            return path

    return None


def is_available() -> bool:
    """Check if the Go crawl-engine binary is available."""
    return find_crawl_engine() is not None


def _build_args(parsed_args, collect_html: bool) -> list[str]:
    """Build the command-line arguments for the Go binary from CLI args."""
    args: list[str] = []

    # Input source
    if parsed_args.url:
        args.extend(["--url", parsed_args.url])
    elif parsed_args.urls_file:
        args.extend(["--urls-file", parsed_args.urls_file])
    elif parsed_args.sitemap_url:
        args.extend(["--sitemap-url", parsed_args.sitemap_url])

    # Crawl settings
    args.extend(["--delay", str(parsed_args.delay)])
    args.extend(["--timeout", str(parsed_args.timeout)])

    if not parsed_args.no_retry:
        args.extend(["--max-retries", str(parsed_args.max_retries)])
        args.extend(["--retry-delay", str(parsed_args.retry_delay)])
        args.extend(["--retry-backoff", str(parsed_args.retry_backoff)])
    else:
        args.append("--no-retry")

    # Auth
    if parsed_args.auth_user:
        args.extend(["--auth-user", parsed_args.auth_user])
    if parsed_args.auth_pass:
        args.extend(["--auth-pass", parsed_args.auth_pass])
    elif parsed_args.auth_pass_env:
        args.extend(["--auth-pass-env", parsed_args.auth_pass_env])

    # Headers and cookies
    for header in parsed_args.headers:
        args.extend(["--header", header])
    for cookie in parsed_args.cookies:
        args.extend(["--cookie", cookie])

    # Filtering
    if parsed_args.internal_only:
        args.append("--internal-only")
    if parsed_args.external_only:
        args.append("--external-only")
    for pattern in parsed_args.exclude_patterns:
        args.extend(["--exclude-pattern", pattern])
    for pattern in parsed_args.include_patterns:
        args.extend(["--include-pattern", pattern])
    args.extend(["--pattern-type", parsed_args.pattern_type])

    # Other options
    if parsed_args.max_pages:
        args.extend(["--max-pages", str(parsed_args.max_pages)])
    if parsed_args.verbose:
        args.append("--verbose")
    if parsed_args.user_agent:
        args.extend(["--user-agent", parsed_args.user_agent])
    if parsed_args.include_subdomains:
        args.append("--include-subdomains")
    if parsed_args.ignore_robots:
        args.append("--ignore-robots")
    if parsed_args.since:
        args.extend(["--since", parsed_args.since.strftime("%Y-%m-%d")])

    # Baseline sitemap
    if parsed_args.baseline_sitemap:
        args.extend(["--baseline-sitemap", parsed_args.baseline_sitemap])

    # Collect HTML for embeddings
    if collect_html:
        args.append("--collect-html")

    return args


def _parse_output(data: dict) -> CrawlEngineResult:
    """Parse the JSON output from the Go crawl-engine into Python objects."""
    result = CrawlEngineResult()

    # Parse links
    for jl in data.get("links", []):
        result.links.append(ExtractedLink(
            source_url=jl.get("source_url", ""),
            link_url=jl.get("link_url", ""),
            link_text=jl.get("link_text", ""),
            is_internal=jl.get("is_internal", False),
            element_type=jl.get("element_type", "a"),
            is_mixed_content=jl.get("is_mixed_content", False),
        ))

    # Parse link statuses
    for js in data.get("link_statuses", []):
        chain = []
        for hop in js.get("redirect_chain", []):
            chain.append((hop.get("status", 0), hop.get("url", "")))

        status = LinkStatus(
            url=js.get("url", ""),
            status_code=js.get("status_code", 0),
            is_redirect=js.get("is_redirect", False),
            redirect_chain=chain,
            final_url=js.get("final_url", ""),
            is_loop=js.get("is_loop", False),
            is_canonical_redirect=js.get("is_canonical_redirect", False),
            error=js.get("error", ""),
            retries=js.get("retries", 0),
            response_time_ms=js.get("response_time_ms"),
        )
        result.link_statuses[status.url] = status

    # Parse page data
    result.page_urls = data.get("page_urls", [])
    result.sitemap_urls = data.get("sitemap_urls", [])
    result.page_html = data.get("page_html") or {}
    result.baseline_urls = data.get("baseline_urls", [])

    # Parse stats
    result.robots_stats = data.get("robots_stats", {})
    result.retry_stats = data.get("retry_stats", {})
    result.metadata = data.get("metadata", {})

    return result


def run_crawl_engine(parsed_args, collect_html: bool = False) -> CrawlEngineResult:
    """Run the Go crawl-engine and return parsed results.

    Args:
        parsed_args: Parsed argparse namespace from the CLI.
        collect_html: Whether to include page HTML in the output (for embeddings).

    Returns:
        CrawlEngineResult with links, statuses, and page data.

    Raises:
        FileNotFoundError: If the Go binary is not found.
        RuntimeError: If the Go binary fails or produces invalid output.
    """
    binary = find_crawl_engine()
    if not binary:
        raise FileNotFoundError(
            "Go crawl-engine binary not found. Build it with: "
            "cd crawl-engine && go build -o crawl-engine ."
        )

    cmd = [binary] + _build_args(parsed_args, collect_html)
    logger.debug("Running crawl-engine: %s", " ".join(cmd))

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=600,
    )

    if proc.returncode == 2:
        # Fatal error — try to parse error JSON from stderr
        try:
            err_data = json.loads(proc.stderr)
            raise RuntimeError(f"Crawl engine error: {err_data.get('error', proc.stderr)}")
        except (json.JSONDecodeError, ValueError):
            raise RuntimeError(f"Crawl engine failed: {proc.stderr}")

    if proc.returncode != 0:
        raise RuntimeError(
            f"Crawl engine exited with code {proc.returncode}: {proc.stderr}"
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse crawl engine JSON output: {exc}") from exc

    return _parse_output(data)
