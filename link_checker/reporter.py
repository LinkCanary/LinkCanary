"""Report generation module."""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .checker import LinkStatus
from .crawler import ExtractedLink

logger = logging.getLogger(__name__)


@dataclass
class ReportRow:
    """A single row in the report."""
    source_page: str
    occurrence_count: int
    example_pages: str
    link_url: str
    link_text: str
    link_type: str
    status_code: int
    issue_type: str
    priority: str
    redirect_chain: str
    final_url: str
    recommended_fix: str


class ReportGenerator:
    """Generates CSV reports from crawl and check results."""
    
    def __init__(self, expand_duplicates: bool = False, skip_ok: bool = False):
        self.expand_duplicates = expand_duplicates
        self.skip_ok = skip_ok
    
    def _determine_issue_type(self, status: LinkStatus) -> str:
        """Determine the issue type for a link."""
        if status.is_loop:
            return 'redirect_loop'
        
        if status.error:
            return 'error'
        
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
        
        if issue_type == 'broken' and is_internal:
            return 'high'
        
        if issue_type == 'redirect_chain':
            return 'high'
        
        if issue_type == 'redirect' and is_internal:
            return 'medium'
        
        if issue_type == 'canonical_redirect':
            return 'medium'
        
        if issue_type == 'broken' and not is_internal:
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
        if issue_type == 'redirect_loop':
            return 'Remove link - redirect loop detected'
        
        if issue_type == 'redirect_chain':
            return f'High priority: Update to {final_url} to eliminate {hop_count} redirect hops'
        
        if issue_type == 'redirect':
            return f'Update link to: {final_url}'
        
        if issue_type == 'canonical_redirect':
            return f'Update to canonical form: {final_url} (trailing slash/case)'
        
        if issue_type == 'broken' and is_internal:
            return 'Remove link or update to valid page'
        
        if issue_type == 'broken' and not is_internal:
            return 'Remove link or find replacement'
        
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
            
            issue_type = self._determine_issue_type(status)
            
            if self.skip_ok and issue_type == 'ok':
                continue
            
            is_internal = occurrences[0].is_internal
            hop_count = len(status.redirect_chain) - 1 if status.redirect_chain else 0
            
            priority = self._determine_priority(issue_type, is_internal, hop_count)
            recommended_fix = self._generate_fix_recommendation(
                issue_type, is_internal, status.final_url, hop_count
            )
            
            link_text = occurrences[0].link_text
            
            if self.expand_duplicates:
                for occ in occurrences:
                    rows.append(ReportRow(
                        source_page=occ.source_url,
                        occurrence_count=1,
                        example_pages='',
                        link_url=link_url,
                        link_text=occ.link_text or link_text,
                        link_type='internal' if is_internal else 'external',
                        status_code=status.status_code,
                        issue_type=issue_type,
                        priority=priority,
                        redirect_chain=status.redirect_chain_formatted,
                        final_url=status.final_url if status.is_redirect else '',
                        recommended_fix=recommended_fix,
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
                    status_code=status.status_code,
                    issue_type=issue_type,
                    priority=priority,
                    redirect_chain=status.redirect_chain_formatted,
                    final_url=status.final_url if status.is_redirect else '',
                    recommended_fix=recommended_fix,
                ))
        
        df = pd.DataFrame([vars(row) for row in rows])
        
        if not df.empty:
            priority_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            df['priority_sort'] = df['priority'].map(priority_order)
            df = df.sort_values(['priority_sort', 'occurrence_count'], ascending=[True, False])
            df = df.drop('priority_sort', axis=1)
        
        return df
    
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
                'errors': 0,
                'critical': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
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
            'errors': issue_counts.get('error', 0),
            'critical': priority_counts.get('critical', 0),
            'high': priority_counts.get('high', 0),
            'medium': priority_counts.get('medium', 0),
            'low': priority_counts.get('low', 0),
        }
