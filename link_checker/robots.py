"""robots.txt parser and compliance checker.

Implements robots.txt protocol for professional crawler etiquette.
Prevents getting IP banned by respecting site policies.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


@dataclass
class RobotsRule:
    """A single robots.txt rule."""
    user_agent: str
    allow_paths: list[str] = field(default_factory=list)
    disallow_paths: list[str] = field(default_factory=list)
    crawl_delay: Optional[float] = None


class RobotsTxtParser:
    """Parses robots.txt and checks URL permissions."""

    def __init__(
        self,
        user_agent: str = 'LinkCanary',
        timeout: int = 10,
    ):
        self.user_agent = user_agent.lower()
        self.timeout = timeout
        self._cache: dict[str, list[RobotsRule]] = {}
        self._fetched_domains: set[str] = set()

    def fetch_robots_txt(self, base_url: str) -> Optional[str]:
        """
        Fetch robots.txt for a domain.

        Args:
            base_url: Base URL to fetch robots.txt from

        Returns:
            robots.txt content or None if not found
        """
        parsed = urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        try:
            response = requests.get(
                robots_url,
                timeout=self.timeout,
                headers={'User-Agent': self.user_agent},
            )

            if response.status_code == 200:
                logger.info(f"Found robots.txt at {robots_url}")
                return response.text
            else:
                logger.debug(f"No robots.txt at {robots_url} (status: {response.status_code})")
                return None

        except requests.RequestException as e:
            logger.debug(f"Failed to fetch robots.txt: {e}")
            return None

    def parse_robots_txt(self, content: str) -> list[RobotsRule]:
        """
        Parse robots.txt content into rules.

        Args:
            content: robots.txt text content

        Returns:
            List of RobotsRule objects
        """
        rules = []
        current_rule = None

        for line in content.splitlines():
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse directive
            if ':' not in line:
                continue

            directive, value = line.split(':', 1)
            directive = directive.strip().lower()
            value = value.strip()

            if directive == 'user-agent':
                # Start new rule group
                if current_rule:
                    rules.append(current_rule)
                current_rule = RobotsRule(user_agent=value.lower())

            elif current_rule:
                if directive == 'allow':
                    current_rule.allow_paths.append(value)
                elif directive == 'disallow':
                    current_rule.disallow_paths.append(value)
                elif directive == 'crawl-delay':
                    try:
                        current_rule.crawl_delay = float(value)
                    except ValueError:
                        pass

        # Add final rule
        if current_rule:
            rules.append(current_rule)

        return rules

    def get_rules_for_domain(self, base_url: str) -> list[RobotsRule]:
        """
        Get robots.txt rules for a domain (cached).

        Args:
            base_url: Base URL to get rules for

        Returns:
            List of applicable RobotsRule objects
        """
        parsed = urlparse(base_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._cache:
            content = self.fetch_robots_txt(base_url)
            if content:
                self._cache[domain] = self.parse_robots_txt(content)
            else:
                self._cache[domain] = []
            self._fetched_domains.add(domain)

        return self._cache.get(domain, [])

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if a path matches a robots.txt pattern.

        Supports:
        - * matches any sequence of characters
        - $ matches end of URL

        Args:
            path: URL path to check
            pattern: robots.txt pattern

        Returns:
            True if path matches pattern
        """
        if pattern == '/':
            return True

        # Handle wildcards
        if '*' in pattern or '$' in pattern:
            # Convert robots.txt pattern to regex-like matching
            import re
            # Escape special regex chars except * and $
            regex_pattern = ''
            for char in pattern:
                if char == '*':
                    regex_pattern += '.*'
                elif char == '$':
                    regex_pattern += '$'
                elif char in '.^+?{}[]|()\\':
                    regex_pattern += '\\' + char
                else:
                    regex_pattern += char

            if not regex_pattern.endswith('$'):
                regex_pattern += '.*'

            return bool(re.match(regex_pattern, path))

        # Simple prefix match
        return path.startswith(pattern)

    def is_allowed(self, url: str, base_url: str) -> tuple[bool, str]:
        """
        Check if a URL is allowed by robots.txt.

        Args:
            url: URL to check
            base_url: Base URL for the site

        Returns:
            Tuple of (is_allowed, reason)
        """
        rules = self.get_rules_for_domain(base_url)

        if not rules:
            return True, "no robots.txt"

        parsed = urlparse(url)
        path = parsed.path or '/'
        if parsed.query:
            path += '?' + parsed.query

        # Find applicable rules (most specific user-agent match)
        applicable_rules = []
        for rule in rules:
            # Check if rule applies to our user-agent
            if rule.user_agent == '*':
                applicable_rules.append(rule)
            elif self.user_agent in rule.user_agent or rule.user_agent in self.user_agent:
                applicable_rules.insert(0, rule)  # More specific rules first

        # If no applicable rules, allowed
        if not applicable_rules:
            return True, "no applicable rules"

        # Check rules in order (most specific first)
        for rule in applicable_rules:
            # Check Allow directives first (they take precedence)
            for allow_pattern in rule.allow_paths:
                if self._matches_pattern(path, allow_pattern):
                    return True, f"allowed by pattern: {allow_pattern}"

            # Check Disallow directives
            for disallow_pattern in rule.disallow_paths:
                if disallow_pattern and self._matches_pattern(path, disallow_pattern):
                    return False, f"disallowed by pattern: {disallow_pattern}"

        return True, "no matching disallow rules"

    def get_crawl_delay(self, base_url: str) -> Optional[float]:
        """
        Get crawl delay from robots.txt.

        Args:
            base_url: Base URL for the site

        Returns:
            Crawl delay in seconds or None
        """
        rules = self.get_rules_for_domain(base_url)

        for rule in rules:
            if rule.user_agent == '*' or self.user_agent in rule.user_agent:
                if rule.crawl_delay is not None:
                    return rule.crawl_delay

        return None

    def get_stats(self) -> dict:
        """Get robots.txt statistics."""
        return {
            'domains_fetched': len(self._fetched_domains),
            'cached_domains': list(self._fetched_domains),
        }


class RobotsComplianceChecker:
    """High-level robots.txt compliance checker for crawlers."""

    def __init__(
        self,
        user_agent: str = 'LinkCanary/1.0',
        timeout: int = 10,
        ignore_robots: bool = False,
    ):
        self.parser = RobotsTxtParser(user_agent=user_agent, timeout=timeout)
        self.ignore_robots = ignore_robots
        self._skipped_urls: dict[str, str] = {}  # url -> reason

    def check_url(self, url: str, base_url: str) -> tuple[bool, str]:
        """
        Check if a URL should be crawled.

        Args:
            url: URL to check
            base_url: Base URL for the site

        Returns:
            Tuple of (should_crawl, reason)
        """
        if self.ignore_robots:
            return True, "robots.txt ignored"

        is_allowed, reason = self.parser.is_allowed(url, base_url)

        if not is_allowed:
            self._skipped_urls[url] = reason
            logger.info(f"Skipping {url}: {reason}")

        return is_allowed, reason

    def filter_urls(self, urls: list[str], base_url: str) -> tuple[list[str], dict[str, str]]:
        """
        Filter URLs based on robots.txt rules.

        Args:
            urls: List of URLs to filter
            base_url: Base URL for the site

        Returns:
            Tuple of (allowed_urls, skipped_urls_with_reasons)
        """
        if self.ignore_robots:
            return urls, {}

        allowed = []
        for url in urls:
            is_allowed, reason = self.check_url(url, base_url)
            if is_allowed:
                allowed.append(url)

        return allowed, self._skipped_urls

    def get_crawl_delay(self, base_url: str) -> Optional[float]:
        """Get recommended crawl delay for a domain."""
        return self.parser.get_crawl_delay(base_url)

    def get_skipped_urls(self) -> dict[str, str]:
        """Get URLs skipped due to robots.txt."""
        return self._skipped_urls.copy()

    def get_stats(self) -> dict:
        """Get compliance statistics."""
        return {
            'ignored': self.ignore_robots,
            'urls_skipped': len(self._skipped_urls),
            **self.parser.get_stats(),
        }
