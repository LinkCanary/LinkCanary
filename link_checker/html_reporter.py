"""HTML report generation module."""

import csv
import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class HTMLReportGenerator:
    """Generates interactive HTML reports from CSV link reports."""
    
    def __init__(self):
        self.data = []
        self.summary = {}
        self.site_domain = ""
        self.report_timestamp = ""
    
    def load_csv(self, csv_path: str) -> None:
        """Load data from a CSV file."""
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.data = list(reader)
        
        if self.data:
            first_source = self.data[0].get('source_page', '')
            if first_source and first_source != 'multiple':
                parsed = urlparse(first_source)
                self.site_domain = f"{parsed.scheme}://{parsed.netloc}"
            else:
                for row in self.data:
                    example = row.get('example_pages', '')
                    if example:
                        first_url = example.split('|')[0]
                        parsed = urlparse(first_url)
                        self.site_domain = f"{parsed.scheme}://{parsed.netloc}"
                        break
        
        csv_stat = os.stat(csv_path)
        self.report_timestamp = datetime.fromtimestamp(csv_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        self._calculate_summary()
    
    def _calculate_summary(self) -> None:
        """Calculate summary statistics from loaded data."""
        self.summary = {
            'total': len(self.data),
            'by_priority': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0},
            'by_issue_type': {
                'broken': 0,
                'redirect_loop': 0,
                'redirect_chain': 0,
                'redirect': 0,
                'canonical_redirect': 0,
                'ok': 0,
                'error': 0,
            },
        }
        
        for row in self.data:
            priority = row.get('priority', 'low')
            issue_type = row.get('issue_type', 'ok')
            
            if priority in self.summary['by_priority']:
                self.summary['by_priority'][priority] += 1
            
            if issue_type in self.summary['by_issue_type']:
                self.summary['by_issue_type'][issue_type] += 1
    
    def generate_html(self, output_path: str, open_browser: bool = False) -> None:
        """Generate HTML report and save to file."""
        html_content = self._build_html()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        if open_browser:
            import webbrowser
            webbrowser.open(f'file://{os.path.abspath(output_path)}')
    
    def _build_html(self) -> str:
        """Build the complete HTML document."""
        data_json = json.dumps(self.data, ensure_ascii=False)
        summary_json = json.dumps(self.summary, ensure_ascii=False)
        
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LinkCanary Report - {html.escape(self.site_domain)}</title>
    <style>
{self._get_css()}
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1>LinkCanary Report</h1>
            <div class="meta">
                <span class="site">{html.escape(self.site_domain)}</span>
                <span class="timestamp">Generated: {html.escape(self.report_timestamp)}</span>
            </div>
        </div>
    </header>
    
    <div class="dashboard">
        <div class="stat-card total">
            <div class="stat-value" id="total-issues">{self.summary['total']}</div>
            <div class="stat-label">Total Issues</div>
        </div>
        <div class="stat-card critical">
            <div class="stat-value" id="critical-count">{self.summary['by_priority']['critical']}</div>
            <div class="stat-label">Critical</div>
        </div>
        <div class="stat-card high">
            <div class="stat-value" id="high-count">{self.summary['by_priority']['high']}</div>
            <div class="stat-label">High</div>
        </div>
        <div class="stat-card medium">
            <div class="stat-value" id="medium-count">{self.summary['by_priority']['medium']}</div>
            <div class="stat-label">Medium</div>
        </div>
        <div class="stat-card low">
            <div class="stat-value" id="low-count">{self.summary['by_priority']['low']}</div>
            <div class="stat-label">Low</div>
        </div>
    </div>
    
    <div class="issue-types">
        <div class="issue-type-item">
            <span class="badge badge-broken">Broken</span>
            <span class="count" id="broken-count">{self.summary['by_issue_type']['broken']}</span>
        </div>
        <div class="issue-type-item">
            <span class="badge badge-loop">Loops</span>
            <span class="count" id="loop-count">{self.summary['by_issue_type']['redirect_loop']}</span>
        </div>
        <div class="issue-type-item">
            <span class="badge badge-chain">Chains</span>
            <span class="count" id="chain-count">{self.summary['by_issue_type']['redirect_chain']}</span>
        </div>
        <div class="issue-type-item">
            <span class="badge badge-redirect">Redirects</span>
            <span class="count" id="redirect-count">{self.summary['by_issue_type']['redirect']}</span>
        </div>
        <div class="issue-type-item">
            <span class="badge badge-canonical">Canonical</span>
            <span class="count" id="canonical-count">{self.summary['by_issue_type']['canonical_redirect']}</span>
        </div>
    </div>
    
    <div class="filters-bar">
        <input type="text" id="search-input" class="search-input" placeholder="Filter by URL or page...">
        
        <div class="filter-group">
            <label>Issue Type:</label>
            <select id="issue-type-filter" class="filter-select">
                <option value="">All Types</option>
                <option value="broken">Broken</option>
                <option value="redirect_loop">Redirect Loop</option>
                <option value="redirect_chain">Redirect Chain</option>
                <option value="redirect">Redirect</option>
                <option value="canonical_redirect">Canonical</option>
                <option value="ok">OK</option>
            </select>
        </div>
        
        <div class="filter-group">
            <label>Link Type:</label>
            <select id="link-type-filter" class="filter-select">
                <option value="">Both</option>
                <option value="internal">Internal</option>
                <option value="external">External</option>
            </select>
        </div>
        
        <div class="filter-group">
            <label>Status:</label>
            <select id="status-filter" class="filter-select">
                <option value="">All Statuses</option>
            </select>
        </div>
        
        <button id="clear-filters" class="btn btn-secondary">Clear Filters</button>
    </div>
    
    <div class="tabs">
        <button class="tab active" data-priority="">All Issues</button>
        <button class="tab" data-priority="critical">Critical</button>
        <button class="tab" data-priority="high">High</button>
        <button class="tab" data-priority="medium">Medium</button>
        <button class="tab" data-priority="low">Low</button>
    </div>
    
    <div class="results-info">
        <span id="showing-count">Showing {self.summary['total']} issues</span>
        <div class="export-buttons">
            <button id="export-csv" class="btn btn-small">Export CSV</button>
            <button id="print-report" class="btn btn-small">Print</button>
        </div>
    </div>
    
    <main class="issues-container" id="issues-container">
    </main>
    
    <footer class="footer">
        <p>Generated by <a href="https://github.com/chesterbeard/linkcanary" target="_blank">LinkCanary</a></p>
    </footer>
    
    <script>
const reportData = {data_json};
const summaryData = {summary_json};

{self._get_javascript()}
    </script>
</body>
</html>'''
    
    def _get_css(self) -> str:
        """Return the CSS styles."""
        return '''
:root {
    --critical: #DC2626;
    --high: #EA580C;
    --medium: #D97706;
    --low: #2563EB;
    --success: #059669;
    --neutral: #6B7280;
    --bg: #F9FAFB;
    --card-bg: #FFFFFF;
    --text: #111827;
    --text-secondary: #6B7280;
    --border: #E5E7EB;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.5;
}

.header {
    background: linear-gradient(135deg, #1e3a5f, #2d5a87);
    color: white;
    padding: 2rem;
    text-align: center;
}

.header h1 {
    font-size: 2rem;
    margin-bottom: 0.5rem;
}

.header .meta {
    opacity: 0.9;
    font-size: 0.9rem;
}

.header .meta .site {
    font-weight: 600;
    margin-right: 1rem;
}

.dashboard {
    display: flex;
    gap: 1rem;
    padding: 1.5rem;
    justify-content: center;
    flex-wrap: wrap;
    max-width: 1200px;
    margin: 0 auto;
}

.stat-card {
    background: var(--card-bg);
    border-radius: 12px;
    padding: 1.5rem 2rem;
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    min-width: 140px;
}

.stat-card .stat-value {
    font-size: 2.5rem;
    font-weight: 700;
    line-height: 1;
}

.stat-card .stat-label {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: 0.5rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.stat-card.total .stat-value { color: var(--text); }
.stat-card.critical .stat-value { color: var(--critical); }
.stat-card.high .stat-value { color: var(--high); }
.stat-card.medium .stat-value { color: var(--medium); }
.stat-card.low .stat-value { color: var(--low); }

.issue-types {
    display: flex;
    gap: 1.5rem;
    padding: 0 1.5rem 1.5rem;
    justify-content: center;
    flex-wrap: wrap;
    max-width: 1200px;
    margin: 0 auto;
}

.issue-type-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.issue-type-item .count {
    font-weight: 600;
}

.badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.badge-broken, .badge-loop { background: #FEE2E2; color: var(--critical); }
.badge-chain { background: #FFEDD5; color: var(--high); }
.badge-redirect, .badge-canonical { background: #FEF3C7; color: var(--medium); }
.badge-ok { background: #D1FAE5; color: var(--success); }
.badge-internal { background: #DBEAFE; color: var(--low); }
.badge-external { background: #E5E7EB; color: var(--neutral); }

.badge-priority-critical { background: var(--critical); color: white; }
.badge-priority-high { background: var(--high); color: white; }
.badge-priority-medium { background: var(--medium); color: white; }
.badge-priority-low { background: var(--low); color: white; }

.filters-bar {
    background: var(--card-bg);
    padding: 1rem 1.5rem;
    display: flex;
    gap: 1rem;
    align-items: center;
    flex-wrap: wrap;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 100;
    max-width: 1200px;
    margin: 0 auto;
}

.search-input {
    flex: 1;
    min-width: 200px;
    padding: 0.5rem 1rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.9rem;
}

.search-input:focus {
    outline: none;
    border-color: var(--low);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.filter-group {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.filter-group label {
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.filter-select {
    padding: 0.5rem;
    border: 1px solid var(--border);
    border-radius: 8px;
    font-size: 0.85rem;
    background: white;
}

.btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.2s;
}

.btn-secondary {
    background: var(--border);
    color: var(--text);
}

.btn-secondary:hover {
    background: #D1D5DB;
}

.btn-small {
    padding: 0.375rem 0.75rem;
    font-size: 0.8rem;
    background: var(--card-bg);
    border: 1px solid var(--border);
}

.btn-small:hover {
    background: var(--bg);
}

.tabs {
    display: flex;
    gap: 0.5rem;
    padding: 1rem 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
}

.tab {
    padding: 0.5rem 1.25rem;
    border: none;
    background: transparent;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    color: var(--text-secondary);
    border-radius: 8px;
    transition: all 0.2s;
}

.tab:hover {
    background: var(--border);
}

.tab.active {
    background: var(--text);
    color: white;
}

.results-info {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 1.5rem;
    max-width: 1200px;
    margin: 0 auto;
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.export-buttons {
    display: flex;
    gap: 0.5rem;
}

.issues-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1.5rem 2rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
    gap: 1rem;
}

.issue-card {
    background: var(--card-bg);
    border-radius: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    overflow: hidden;
    border-left: 4px solid transparent;
}

.issue-card.priority-critical { border-left-color: var(--critical); }
.issue-card.priority-high { border-left-color: var(--high); }
.issue-card.priority-medium { border-left-color: var(--medium); }
.issue-card.priority-low { border-left-color: var(--low); }

.issue-card-header {
    padding: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--border);
    background: var(--bg);
}

.occurrence-badge {
    background: var(--text);
    color: white;
    padding: 0.125rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 600;
}

.issue-card-body {
    padding: 1rem;
}

.issue-field {
    margin-bottom: 0.75rem;
}

.issue-field:last-child {
    margin-bottom: 0;
}

.issue-field-label {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
}

.issue-field-value {
    font-size: 0.9rem;
}

.url-link {
    color: var(--low);
    text-decoration: none;
    word-break: break-all;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.85rem;
}

.url-link:hover {
    text-decoration: underline;
}

.redirect-chain {
    background: var(--bg);
    padding: 0.75rem;
    border-radius: 8px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 0.8rem;
    overflow-x: auto;
}

.redirect-chain .hop {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.25rem 0;
}

.redirect-chain .status-code {
    background: var(--border);
    padding: 0.125rem 0.375rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
}

.redirect-chain .arrow {
    color: var(--text-secondary);
}

.pages-list {
    background: var(--bg);
    padding: 0.5rem 0.75rem;
    border-radius: 8px;
    max-height: 120px;
    overflow-y: auto;
}

.pages-list a {
    display: block;
    padding: 0.25rem 0;
    color: var(--low);
    text-decoration: none;
    font-size: 0.85rem;
    word-break: break-all;
}

.pages-list a:hover {
    text-decoration: underline;
}

.recommended-fix {
    background: #D1FAE5;
    color: #065F46;
    padding: 0.75rem;
    border-radius: 8px;
    font-weight: 500;
}

.issue-card-footer {
    padding: 0.75rem 1rem;
    border-top: 1px solid var(--border);
    display: flex;
    gap: 0.5rem;
}

.copy-btn {
    padding: 0.375rem 0.75rem;
    font-size: 0.8rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.copy-btn:hover {
    background: var(--border);
}

.copy-btn.copied {
    background: var(--success);
    color: white;
    border-color: var(--success);
}

.footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
    font-size: 0.85rem;
}

.footer a {
    color: var(--low);
}

.no-results {
    text-align: center;
    padding: 3rem;
    color: var(--text-secondary);
    grid-column: 1 / -1;
}

@media (max-width: 768px) {
    .dashboard {
        padding: 1rem;
    }
    
    .stat-card {
        min-width: 100px;
        padding: 1rem;
    }
    
    .stat-card .stat-value {
        font-size: 1.75rem;
    }
    
    .filters-bar {
        flex-direction: column;
        align-items: stretch;
    }
    
    .search-input {
        width: 100%;
    }
    
    .issues-container {
        grid-template-columns: 1fr;
    }
    
    .tabs {
        overflow-x: auto;
        flex-wrap: nowrap;
    }
}

@media print {
    .filters-bar, .tabs, .export-buttons, .issue-card-footer, .footer {
        display: none !important;
    }
    
    .header {
        background: none !important;
        color: black !important;
        padding: 1rem !important;
    }
    
    .issues-container {
        display: block !important;
    }
    
    .issue-card {
        break-inside: avoid;
        margin-bottom: 1rem;
        box-shadow: none !important;
        border: 1px solid var(--border) !important;
    }
}
'''
    
    def _get_javascript(self) -> str:
        """Return the JavaScript code."""
        return '''
let currentPriority = '';
let currentIssueType = '';
let currentLinkType = '';
let currentStatusCode = '';
let searchQuery = '';

function init() {
    populateStatusCodes();
    renderIssues();
    setupEventListeners();
}

function populateStatusCodes() {
    const statusCodes = [...new Set(reportData.map(d => d.status_code))].sort();
    const select = document.getElementById('status-filter');
    statusCodes.forEach(code => {
        const option = document.createElement('option');
        option.value = code;
        option.textContent = code;
        select.appendChild(option);
    });
}

function setupEventListeners() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentPriority = tab.dataset.priority;
            renderIssues();
        });
    });
    
    document.getElementById('search-input').addEventListener('input', (e) => {
        searchQuery = e.target.value.toLowerCase();
        renderIssues();
    });
    
    document.getElementById('issue-type-filter').addEventListener('change', (e) => {
        currentIssueType = e.target.value;
        renderIssues();
    });
    
    document.getElementById('link-type-filter').addEventListener('change', (e) => {
        currentLinkType = e.target.value;
        renderIssues();
    });
    
    document.getElementById('status-filter').addEventListener('change', (e) => {
        currentStatusCode = e.target.value;
        renderIssues();
    });
    
    document.getElementById('clear-filters').addEventListener('click', () => {
        searchQuery = '';
        currentIssueType = '';
        currentLinkType = '';
        currentStatusCode = '';
        document.getElementById('search-input').value = '';
        document.getElementById('issue-type-filter').value = '';
        document.getElementById('link-type-filter').value = '';
        document.getElementById('status-filter').value = '';
        renderIssues();
    });
    
    document.getElementById('export-csv').addEventListener('click', exportFilteredCSV);
    document.getElementById('print-report').addEventListener('click', () => window.print());
}

function filterData() {
    return reportData.filter(item => {
        if (currentPriority && item.priority !== currentPriority) return false;
        if (currentIssueType && item.issue_type !== currentIssueType) return false;
        if (currentLinkType && item.link_type !== currentLinkType) return false;
        if (currentStatusCode && item.status_code !== currentStatusCode) return false;
        
        if (searchQuery) {
            const searchFields = [
                item.link_url,
                item.source_page,
                item.example_pages,
                item.link_text,
            ].join(' ').toLowerCase();
            if (!searchFields.includes(searchQuery)) return false;
        }
        
        return true;
    });
}

function renderIssues() {
    const filtered = filterData();
    const container = document.getElementById('issues-container');
    document.getElementById('showing-count').textContent = `Showing ${filtered.length} of ${reportData.length} issues`;
    
    if (filtered.length === 0) {
        container.innerHTML = '<div class="no-results">No issues match the current filters</div>';
        return;
    }
    
    container.innerHTML = filtered.map(item => createIssueCard(item)).join('');
    
    container.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const text = btn.dataset.copy;
            navigator.clipboard.writeText(text).then(() => {
                btn.classList.add('copied');
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.textContent = originalText;
                }, 1500);
            });
        });
    });
}

function createIssueCard(item) {
    const issueTypeBadgeClass = {
        'broken': 'badge-broken',
        'redirect_loop': 'badge-loop',
        'redirect_chain': 'badge-chain',
        'redirect': 'badge-redirect',
        'canonical_redirect': 'badge-canonical',
        'ok': 'badge-ok',
        'error': 'badge-broken',
    }[item.issue_type] || 'badge-redirect';
    
    const issueTypeLabel = {
        'broken': 'Broken',
        'redirect_loop': 'Redirect Loop',
        'redirect_chain': 'Redirect Chain',
        'redirect': 'Redirect',
        'canonical_redirect': 'Canonical',
        'ok': 'OK',
        'error': 'Error',
    }[item.issue_type] || item.issue_type;
    
    const occurrenceCount = parseInt(item.occurrence_count) || 1;
    
    let pagesHtml = '';
    if (item.source_page === 'multiple' && item.example_pages) {
        const pages = item.example_pages.split('|');
        pagesHtml = `
            <div class="issue-field">
                <div class="issue-field-label">Found on ${occurrenceCount} pages</div>
                <div class="pages-list">
                    ${pages.map(p => `<a href="${escapeHtml(p)}" target="_blank">${escapeHtml(truncateUrl(p))}</a>`).join('')}
                </div>
            </div>`;
    } else if (item.source_page && item.source_page !== 'multiple') {
        pagesHtml = `
            <div class="issue-field">
                <div class="issue-field-label">Found on</div>
                <div class="issue-field-value">
                    <a href="${escapeHtml(item.source_page)}" target="_blank" class="url-link">${escapeHtml(truncateUrl(item.source_page))}</a>
                </div>
            </div>`;
    }
    
    let redirectChainHtml = '';
    if (item.redirect_chain) {
        const hops = item.redirect_chain.split(' → ');
        redirectChainHtml = `
            <div class="issue-field">
                <div class="issue-field-label">Redirect Chain</div>
                <div class="redirect-chain">
                    ${hops.map((hop, i) => {
                        const [status, url] = hop.includes(':') ? [hop.split(':')[0], hop.substring(hop.indexOf(':') + 1)] : ['', hop];
                        return `<div class="hop">
                            ${status ? `<span class="status-code">${status}</span>` : ''}
                            <a href="${escapeHtml(url)}" target="_blank" class="url-link">${escapeHtml(truncateUrl(url, 60))}</a>
                            ${i < hops.length - 1 ? '<span class="arrow">→</span>' : ''}
                        </div>`;
                    }).join('')}
                </div>
            </div>`;
    }
    
    let finalUrlHtml = '';
    if (item.final_url && !item.redirect_chain) {
        finalUrlHtml = `
            <div class="issue-field">
                <div class="issue-field-label">Final Destination</div>
                <div class="issue-field-value">
                    <a href="${escapeHtml(item.final_url)}" target="_blank" class="url-link">${escapeHtml(truncateUrl(item.final_url))}</a>
                </div>
            </div>`;
    }
    
    return `
        <div class="issue-card priority-${item.priority}">
            <div class="issue-card-header">
                <span class="badge ${issueTypeBadgeClass}">${issueTypeLabel}</span>
                <span class="badge badge-priority-${item.priority}">${item.priority}</span>
                ${occurrenceCount > 1 ? `<span class="occurrence-badge">${occurrenceCount}x</span>` : ''}
                <span class="badge badge-${item.link_type}">${item.link_type}</span>
                <span class="badge" style="background:#E5E7EB;color:var(--text)">${item.status_code}</span>
            </div>
            <div class="issue-card-body">
                <div class="issue-field">
                    <div class="issue-field-label">Broken Link${item.link_text ? ` ("${escapeHtml(truncate(item.link_text, 50))}")` : ''}</div>
                    <div class="issue-field-value">
                        <a href="${escapeHtml(item.link_url)}" target="_blank" class="url-link">${escapeHtml(item.link_url)}</a>
                    </div>
                </div>
                ${pagesHtml}
                ${redirectChainHtml}
                ${finalUrlHtml}
                ${item.recommended_fix ? `
                <div class="issue-field">
                    <div class="issue-field-label">Recommended Fix</div>
                    <div class="recommended-fix">${escapeHtml(item.recommended_fix)}</div>
                </div>` : ''}
            </div>
            <div class="issue-card-footer">
                <button class="copy-btn" data-copy="${escapeHtml(item.link_url)}">Copy URL</button>
                ${item.recommended_fix ? `<button class="copy-btn" data-copy="${escapeHtml(item.recommended_fix)}">Copy Fix</button>` : ''}
            </div>
        </div>`;
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

function truncateUrl(url, maxLen = 80) {
    if (!url || url.length <= maxLen) return url;
    const start = url.substring(0, maxLen / 2);
    const end = url.substring(url.length - maxLen / 2 + 3);
    return start + '...' + end;
}

function exportFilteredCSV() {
    const filtered = filterData();
    if (filtered.length === 0) {
        alert('No data to export');
        return;
    }
    
    const headers = Object.keys(filtered[0]);
    const csvContent = [
        headers.join(','),
        ...filtered.map(row => 
            headers.map(h => {
                const val = row[h] || '';
                return val.includes(',') || val.includes('"') || val.includes('\\n') 
                    ? `"${val.replace(/"/g, '""')}"` 
                    : val;
            }).join(',')
        )
    ].join('\\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'link_report_filtered.csv';
    link.click();
}

init();
'''
