"""URL pattern matching for filtering links.

Supports glob and regex patterns for include/exclude filtering.
"""

import fnmatch
import re
from typing import List, Optional
from urllib.parse import urlparse


class URLPatternMatcher:
    """Match URLs against include/exclude patterns."""

    def __init__(
        self,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None,
        pattern_type: str = "glob",
    ):
        """
        Initialize pattern matcher.
        
        Args:
            include_patterns: Patterns to match (only these URLs checked)
            exclude_patterns: Patterns to exclude (these URLs skipped)
            pattern_type: 'glob' or 'regex'
        """
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.pattern_type = pattern_type
        
        # Compile regex patterns if using regex
        self._compiled_include = []
        self._compiled_exclude = []
        
        if pattern_type == "regex":
            self._compiled_include = [
                re.compile(p, re.IGNORECASE) for p in self.include_patterns
            ]
            self._compiled_exclude = [
                re.compile(p, re.IGNORECASE) for p in self.exclude_patterns
            ]

    def should_check(self, url: str) -> tuple[bool, str]:
        """
        Check if a URL should be checked based on patterns.
        
        Args:
            url: URL to check
        
        Returns:
            Tuple of (should_check, reason)
        """
        # If no patterns, check everything
        if not self.include_patterns and not self.exclude_patterns:
            return True, "no patterns"
        
        # Check exclude patterns first
        if self._matches_exclude(url):
            return False, f"excluded by pattern"
        
        # Check include patterns
        if self.include_patterns:
            if self._matches_include(url):
                return True, "matched include pattern"
            else:
                return False, "not in include patterns"
        
        return True, "not excluded"

    def _matches_include(self, url: str) -> bool:
        """Check if URL matches any include pattern."""
        if not self.include_patterns:
            return True
        
        if self.pattern_type == "regex":
            return any(p.search(url) for p in self._compiled_include)
        else:
            # Glob matching
            return any(self._glob_match(url, p) for p in self.include_patterns)

    def _matches_exclude(self, url: str) -> bool:
        """Check if URL matches any exclude pattern."""
        if not self.exclude_patterns:
            return False
        
        if self.pattern_type == "regex":
            return any(p.search(url) for p in self._compiled_exclude)
        else:
            # Glob matching
            return any(self._glob_match(url, p) for p in self.exclude_patterns)

    def _glob_match(self, url: str, pattern: str) -> bool:
        """
        Match URL against glob pattern.

        Supports:
        - * matches any characters (non-greedy)
        - ** matches any characters across path segments
        - ? matches single character
        - [abc] character sets

        Pattern types:
        - Domain patterns: *linkedin.com* (wraps with wildcards)
        - Path patterns: /blog/*, /docs/**/*.md
        - Extension patterns: *.pdf, *.jpg
        """
        pattern_lower = pattern.lower()
        url_lower = url.lower()

        # Path pattern: starts with / - match against URL path
        if pattern.startswith('/'):
            parsed = urlparse(url)
            path = parsed.path.lower()
            # Use fnmatch on the path
            return fnmatch.fnmatch(path, pattern_lower) or pattern_lower in path

        # Full wildcard pattern: *something* - match anywhere in URL
        if pattern.startswith('*') and pattern.endswith('*'):
            # Remove wildcards and check if contained
            search = pattern_lower.strip('*')
            return search in url_lower

        # Prefix wildcard: *something - check suffix
        if pattern.startswith('*'):
            suffix = pattern_lower[1:]
            return url_lower.endswith(suffix) or suffix in url_lower

        # Suffix wildcard: something* - check prefix or extension
        if pattern.endswith('*'):
            prefix = pattern_lower[:-1]
            return url_lower.startswith(prefix) or prefix in url_lower

        # Has wildcard in middle: something*something
        if '*' in pattern:
            return fnmatch.fnmatch(url_lower, pattern_lower)

        # No wildcards: substring match
        return pattern_lower in url_lower

    def filter_urls(self, urls: List[str]) -> tuple[List[str], List[str]]:
        """
        Filter a list of URLs.
        
        Args:
            urls: List of URLs to filter
        
        Returns:
            Tuple of (included_urls, excluded_urls)
        """
        included = []
        excluded = []
        
        for url in urls:
            should_check, reason = self.should_check(url)
            if should_check:
                included.append(url)
            else:
                excluded.append(url)
        
        return included, excluded

    def get_stats(self) -> dict:
        """Return pattern matching statistics."""
        return {
            "include_patterns": len(self.include_patterns),
            "exclude_patterns": len(self.exclude_patterns),
            "pattern_type": self.pattern_type,
        }


def create_matcher_from_args(args) -> URLPatternMatcher:
    """Create URLPatternMatcher from CLI arguments."""
    return URLPatternMatcher(
        include_patterns=args.include_pattern,
        exclude_patterns=args.exclude_pattern,
        pattern_type=args.pattern_type,
    )


# Common preset patterns
PRESET_PATTERNS = {
    "social-media": [
        "*linkedin.com*",
        "*twitter.com*",
        "*x.com*",
        "*facebook.com*",
        "*instagram.com*",
        "*youtube.com*",
        "*tiktok.com*",
        "*pinterest.com*",
    ],
    "documents": [
        "*.pdf",
        "*.doc",
        "*.docx",
        "*.xls",
        "*.xlsx",
        "*.ppt",
        "*.pptx",
    ],
    "media": [
        "*.jpg",
        "*.jpeg",
        "*.png",
        "*.gif",
        "*.svg",
        "*.webp",
        "*.mp4",
        "*.mp3",
        "*.wav",
    ],
    "tracking": [
        "*utm_source*",
        "*utm_medium*",
        "*utm_campaign*",
        "*fbclid*",
        "*gclid*",
    ],
}


def get_preset_patterns(preset_name: str) -> List[str]:
    """Get patterns for a preset name."""
    return PRESET_PATTERNS.get(preset_name, [])
