"""Report generation module."""

import logging
from collections import defaultdict
from dataclasses import dataclass, fields as dataclass_fields
from typing import Optional
from urllib.parse import urlparse

import pandas as pd

from .checker import LinkStatus
from .crawler import ExtractedLink
from .utils import normalize_url

logger = logging.getLogger(__name__)

WEAK_ANCHOR_TEXTS = frozenset({
    '', 'click here', 'here', 'read more', 'learn more', 'more',
    'link', 'this', 'this page', 'this link', 'go', 'visit',
    'visit here', 'click', 'tap here', 'details', 'info',
    'information', 'page', 'article', 'post', 'continue',
    'continue reading', 'see more', 'view more', 'find out more',
})


def _classify_anchor_quality(link_text: str, element_type: str) -> str:
    """Returns 'weak' if the anchor text is non-descriptive, '' otherwise."""
    if element_type != 'a':
        return ''  # only applies to anchor tags
    normalized = link_text.strip().lower()
    if normalized in WEAK_ANCHOR_TEXTS:
        return 'weak'
    return ''


@dataclass
class ReportRow:
    """A single row in the report."""
    source_page: str
    occurrence_count: int
    example_pages: str
    link_url: str
    link_text: str
    link_type: str
    element_type: str
    status_code: int
    issue_type: str
    priority: str
    redirect_chain: str
    final_url: str
    recommended_fix: str
    response_time_ms: Optional[float] = None
    anchor_quality: str = ''


class ReportGenerator:
    """Generates CSV reports from crawl and check results."""
    
    def __init__(self, expand_duplicates: bool = False, skip_ok: bool = False):
        self.expand_duplicates = expand_duplicates
        self.skip_ok = skip_ok
    
    def _determine_issue_type(
        self,
        status: LinkStatus,
        first_occurrence: Optional[ExtractedLink] = None,
    ) -> str:
        """Determine the issue type for a link."""
        # Mixed content takes precedence: an HTTP resource on an HTTPS page is
        # flagged regardless of its HTTP status code (it may be 200 OK).
        if first_occurrence is not None and first_occurrence.is_mixed_content:
            return 'mixed_content'

        if status.is_loop:
            return 'redirect_loop'
        
        if status.error:
            return 'error'
        
        if status.status_code == 404:
            return 'broken_404'

        if status.status_code == 410:
            return 'broken_410'

        if status.status_code >= 500:
            return 'broken_5xx'

        if status.status_code >= 400:
            return 'broken'
        
        if not status.is_redirect:
            return 'ok'
        
        if status.is_canonical_redirect:
            return 'canonical_redirect'
        
        hop_count = len(status.redirect_chain) - 1
        if hop_count >= 2:
            return 'redirect_chain'
        
        return 'redirect'
    
    def _determine_priority(
        self,
        issue_type: str,
        is_internal: bool,
        hop_count: int = 0,
    ) -> str:
        """Determine the priority level for an issue."""
        if issue_type == 'redirect_loop':
            return 'critical'
        
        if issue_type == 'redirect_chain' and hop_count >= 3:
            return 'critical'
        
        if issue_type == 'broken_5xx' and is_internal:
            return 'critical'

        if issue_type == 'mixed_content' and is_internal:
            return 'high'

        if issue_type == 'broken_404' and is_internal:
            return 'high'

        if issue_type == 'broken' and is_internal:
            return 'high'

        if issue_type == 'mixed_content' and not is_internal:
            return 'medium'

        if issue_type == 'broken_410' and is_internal:
            return 'medium'

        if issue_type == 'redirect_chain':
            return 'high'

        if issue_type == 'redirect' and is_internal:
            return 'medium'

        if issue_type == 'canonical_redirect':
            return 'medium'

        if issue_type in ('broken', 'broken_404', 'broken_410', 'broken_5xx') and not is_internal:
            return 'low'

        if issue_type == 'redirect' and not is_internal:
            return 'low'

        return 'low'
    
    def _generate_fix_recommendation(
        self,
        issue_type: str,
        is_internal: bool,
        final_url: str,
        hop_count: int = 0,
    ) -> str:
        """Generate a fix recommendation for an issue."""
        if issue_type == 'mixed_content':
            return (
                'Mixed content: this HTTP resource is loaded on an HTTPS page. '
                'Update the URL to HTTPS or remove the resource.'
            )

        if issue_type == 'redirect_loop':
            return 'Remove link - redirect loop detected'
        
        if issue_type == 'redirect_chain':
            return f'High priority: Update to {final_url} to eliminate {hop_count} redirect hops'
        
        if issue_type == 'redirect':
            return f'Update link to: {final_url}'
        
        if issue_type == 'canonical_redirect':
            return f'Update to canonical form: {final_url} (trailing slash/case)'
        
        if issue_type in ('broken', 'broken_404') and is_internal:
            return 'Remove link or update to valid page'

        if issue_type in ('broken', 'broken_404') and not is_internal:
            return 'Remove link or find replacement'

        if issue_type == 'broken_410':
            return 'Page is permanently gone (410 Gone) — remove or update this link'

        if issue_type == 'broken_5xx':
            return 'Server error — check server health; may be transient, retry later'
        
        if issue_type == 'error':
            return 'Check link manually - request failed'
        
        return ''
    
    def generate_report(
        self,
        links: list[ExtractedLink],
        link_statuses: dict[str, LinkStatus],
    ) -> pd.DataFrame:
        """
        Generate a report DataFrame from crawl and check results.
        
        Args:
            links: List of extracted links from crawling
            link_statuses: Dictionary mapping URLs to their status
        
        Returns:
            pandas DataFrame with report data
        """
        link_occurrences: dict[str, list[ExtractedLink]] = defaultdict(list)
        for link in links:
            link_occurrences[link.link_url].append(link)
        
        rows = []
        
        for link_url, occurrences in link_occurrences.items():
            status = link_statuses.get(link_url)
            if status is None:
                continue
            
            issue_type = self._determine_issue_type(status, occurrences[0])
            
            if self.skip_ok and issue_type == 'ok':
                continue
            
            is_internal = occurrences[0].is_internal
            hop_count = len(status.redirect_chain) - 1 if status.redirect_chain else 0
            
            priority = self._determine_priority(issue_type, is_internal, hop_count)
            recommended_fix = self._generate_fix_recommendation(
                issue_type, is_internal, status.final_url, hop_count
            )
            
            link_text = occurrences[0].link_text

            first_element_type = occurrences[0].element_type

            if self.expand_duplicates:
                for occ in occurrences:
                    occ_link_text = occ.link_text or link_text
                    rows.append(ReportRow(
                        source_page=occ.source_url,
                        occurrence_count=1,
                        example_pages='',
                        link_url=link_url,
                        link_text=occ_link_text,
                        link_type='internal' if is_internal else 'external',
                        element_type=occ.element_type,
                        status_code=status.status_code,
                        issue_type=issue_type,
                        priority=priority,
                        redirect_chain=status.redirect_chain_formatted,
                        final_url=status.final_url if status.is_redirect else '',
                        recommended_fix=recommended_fix,
                        response_time_ms=status.response_time_ms,
                        anchor_quality=_classify_anchor_quality(occ_link_text, occ.element_type),
                    ))
            else:
                occurrence_count = len(occurrences)
                source_pages = [occ.source_url for occ in occurrences]

                if occurrence_count <= 5:
                    source_page = source_pages[0] if occurrence_count == 1 else 'multiple'
                    example_pages = '|'.join(source_pages) if occurrence_count > 1 else ''
                else:
                    source_page = 'multiple'
                    example_pages = '|'.join(source_pages[:5])

                rows.append(ReportRow(
                    source_page=source_page,
                    occurrence_count=occurrence_count,
                    example_pages=example_pages,
                    link_url=link_url,
                    link_text=link_text,
                    link_type='internal' if is_internal else 'external',
                    element_type=first_element_type,
                    status_code=status.status_code,
                    issue_type=issue_type,
                    priority=priority,
                    redirect_chain=status.redirect_chain_formatted,
                    final_url=status.final_url if status.is_redirect else '',
                    recommended_fix=recommended_fix,
                    response_time_ms=status.response_time_ms,
                    anchor_quality=_classify_anchor_quality(link_text, first_element_type),
                ))
        
        df = pd.DataFrame([vars(row) for row in rows])
        
        if not df.empty:
            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            df['priority_sort'] = df['priority'].map(priority_order)
            df = df.sort_values(['priority_sort', 'occurrence_count'], ascending=[True, False])
            df = df.drop('priority_sort', axis=1)
        
        return df
    
    # Orphaned page detection — sitemap mode only
    def generate_orphan_report(
        self,
        sitemap_urls: list[str],
        all_links: list[ExtractedLink],
    ) -> pd.DataFrame:
        """
        Detect orphaned pages: sitemap pages with no internal links pointing to them.

        A page is orphaned when it appears in the sitemap but no other crawled page
        links to it internally. Such pages can only be reached by knowing the URL
        directly, which is a navigation and SEO problem.

        Args:
            sitemap_urls: All page URLs parsed from the sitemap (the pages that
                          were scheduled for crawling).
            all_links:    All ExtractedLink objects collected during the crawl.

        Returns:
            A DataFrame with one row per orphaned page, using the same columns
            as generate_report() so the results can be appended to the main report.
        """

        def _normalize_for_orphan(url: str) -> str:
            """Normalize a URL and strip trailing slash for comparison."""
            normed = normalize_url(url)
            parsed = urlparse(normed)
            # Strip trailing slash from path so /about and /about/ match
            stripped_path = parsed.path.rstrip('/')
            # Reconstruct without fragment (normalize_url already removes fragments)
            from urllib.parse import urlunparse
            return urlunparse((
                parsed.scheme,
                parsed.netloc,
                stripped_path,
                '',
                parsed.query,
                '',
            ))

        # Build set of normalized sitemap URLs, excluding root/homepage
        normalized_sitemap: dict[str, str] = {}  # normalized -> original
        for url in sitemap_urls:
            normed = _normalize_for_orphan(url)
            parsed = urlparse(normed)
            # Exclude bare domain root (path is '' or '/')
            if parsed.path in ('', '/'):
                continue
            normalized_sitemap[normed] = url

        # Build set of normalized internal link targets found during the crawl
        linked_urls: set[str] = {
            _normalize_for_orphan(link.link_url)
            for link in all_links
            if link.is_internal
        }

        # Orphaned = in sitemap but nobody links to them
        orphaned_normalized = set(normalized_sitemap.keys()) - linked_urls

        if not orphaned_normalized:
            return pd.DataFrame(columns=[f.name for f in dataclass_fields(ReportRow)])

        _FIX = (
            'No internal links point to this page. '
            'Add internal links from relevant content, or remove it from the sitemap '
            'if it should not be indexed.'
        )

        rows = []
        for normed in sorted(orphaned_normalized):
            original_url = normalized_sitemap[normed]
            rows.append(ReportRow(
                source_page='',
                occurrence_count=0,
                example_pages='',
                link_url=original_url,
                link_text='',
                link_type='internal',
                element_type='',
                status_code=0,
                issue_type='orphaned_page',
                priority='medium',
                redirect_chain='',
                final_url='',
                recommended_fix=_FIX,
                response_time_ms=None,
                anchor_quality='',
            ))

        return pd.DataFrame([vars(row) for row in rows])

    def save_report(self, df: pd.DataFrame, output_path: str):
        """Save the report to a CSV file."""
        df.to_csv(output_path, index=False)
        logger.info(f"Report saved to {output_path}")
    
    def get_summary(self, df: pd.DataFrame) -> dict:
        """Generate summary statistics from the report."""
        if df.empty:
            return {
                'total_links': 0,
                'ok': 0,
                'redirects': 0,
                'canonical_redirects': 0,
                'redirect_chains': 0,
                'redirect_loops': 0,
                'broken': 0,
                'broken_404': 0,
                'broken_410': 0,
                'broken_5xx': 0,
                'errors': 0,
                'mixed_content': 0,
                'orphaned_pages': 0,
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'weak_anchors': 0,
            }

        issue_counts = df['issue_type'].value_counts().to_dict()
        priority_counts = df['priority'].value_counts().to_dict()

        return {
            'total_links': len(df),
            'ok': issue_counts.get('ok', 0),
            'redirects': issue_counts.get('redirect', 0),
            'canonical_redirects': issue_counts.get('canonical_redirect', 0),
            'redirect_chains': issue_counts.get('redirect_chain', 0),
            'redirect_loops': issue_counts.get('redirect_loop', 0),
            'broken': issue_counts.get('broken', 0),
            'broken_404': issue_counts.get('broken_404', 0),
            'broken_410': issue_counts.get('broken_410', 0),
            'broken_5xx': issue_counts.get('broken_5xx', 0),
            'errors': issue_counts.get('error', 0),
            'mixed_content': issue_counts.get('mixed_content', 0),
            'orphaned_pages': issue_counts.get('orphaned_page', 0),
            'critical': priority_counts.get('critical', 0),
            'high': priority_counts.get('high', 0),
            'medium': priority_counts.get('medium', 0),
            'low': priority_counts.get('low', 0),
            'weak_anchors': int(df[df['anchor_quality'] == 'weak'].shape[0]),
        }
