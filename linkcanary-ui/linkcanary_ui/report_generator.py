"""White-label report generator for LinkCanary."""

import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import jinja2
from pydantic import BaseModel

# Try to import WeasyPrint for PDF generation (optional)
try:
    from weasyprint import HTML, CSS
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False


class WhiteLabelConfig(BaseModel):
    """Configuration for white-label reports."""
    logo_path: Optional[str] = None
    brand_color: str = "#2563eb"
    report_title: str = "Link Audit Report"
    client_name: Optional[str] = None
    output_format: str = "html"


class ReportData(BaseModel):
    """Data structure for report content."""
    site_url: str
    crawl_date: datetime
    total_links: int
    broken_links: int
    redirect_links: int
    ok_links: int
    issues_by_type: Dict[str, int]
    detailed_issues: list


class WhiteLabelReportGenerator:
    """Generate white-label HTML and PDF reports."""
    
    def __init__(self, config: WhiteLabelConfig):
        self.config = config
        self.env = jinja2.Environment(
            loader=jinja2.PackageLoader("linkcanary_ui", "templates"),
            autoescape=jinja2.select_autoescape(["html", "xml"])
        )
        
    def validate_hex_color(self, color: str) -> str:
        """Validate hex color format."""
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValueError(f"Invalid hex color: {color}. Use format #RRGGBB")
        return color
    
    def encode_logo(self, logo_path: str) -> Optional[str]:
        """Convert logo to base64 for embedding in HTML."""
        if not logo_path or not Path(logo_path).exists():
            return None
        
        try:
            with open(logo_path, 'rb') as f:
                ext = Path(logo_path).suffix.lower().replace('.', '')
                if ext == 'svg':
                    ext = 'svg+xml'
                return f"data:image/{ext};base64,{base64.b64encode(f.read()).decode()}"
        except Exception as e:
            print(f"Warning: Could not read logo file {logo_path}: {e}")
            return None
    
    def darken_color(self, hex_color: str, amount: int = 20) -> str:
        """Darken a hex color by a percentage."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return hex_color
        
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(max(0, c - amount) for c in rgb)
        return f"#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}"
    
    def generate_html(self, report_data: ReportData, output_path: str):
        """Generate HTML report with white-label branding."""
        logo_base64 = self.encode_logo(self.config.logo_path) if self.config.logo_path else None
        brand_color = self.validate_hex_color(self.config.brand_color)
        
        template = self.env.get_template("white_label_report.html")
        
        html_content = template.render(
            logo=logo_base64,
            brand_color=brand_color,
            brand_light=f"{brand_color}20",
            brand_dark=self.darken_color(brand_color),
            report_title=self.config.report_title,
            client_name=self.config.client_name,
            site_url=report_data.site_url,
            crawl_date=report_data.crawl_date.strftime("%B %d, %Y %H:%M"),
            total_links=report_data.total_links,
            broken_links=report_data.broken_links,
            redirect_links=report_data.redirect_links,
            ok_links=report_data.ok_links,
            issues_by_type=report_data.issues_by_type,
            detailed_issues=report_data.detailed_issues,
            generated_by="LinkCanary"
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def generate_pdf(self, report_data: ReportData, output_path: str):
        """Generate PDF report using WeasyPrint."""
        if not HAS_WEASYPRINT:
            print("Warning: WeasyPrint not available. Falling back to HTML.")
            html_path = output_path.replace('.pdf', '.html')
            return self.generate_html(report_data, html_path)
        
        logo_base64 = self.encode_logo(self.config.logo_path) if self.config.logo_path else None
        brand_color = self.validate_hex_color(self.config.brand_color)
        
        template = self.env.get_template("white_label_report.html")
        
        html_content = template.render(
            logo=logo_base64,
            brand_color=brand_color,
            brand_light=f"{brand_color}20",
            brand_dark=self.darken_color(brand_color),
            report_title=self.config.report_title,
            client_name=self.config.client_name,
            site_url=report_data.site_url,
            crawl_date=report_data.crawl_date.strftime("%B %d, %Y %H:%M"),
            total_links=report_data.total_links,
            broken_links=report_data.broken_links,
            redirect_links=report_data.redirect_links,
            ok_links=report_data.ok_links,
            issues_by_type=report_data.issues_by_type,
            detailed_issues=report_data.detailed_issues,
            generated_by="LinkCanary"
        )
        
        HTML(string=html_content).write_pdf(
            output_path,
            stylesheets=[CSS(string='@page { size: A4; margin: 2cm; }')]
        )
        
        return output_path
    
    def generate_report(self, report_data: ReportData, output_path: str):
        """Generate report in the specified format."""
        if self.config.output_format == 'pdf':
            return self.generate_pdf(report_data, output_path)
        else:
            return self.generate_html(report_data, output_path)


def create_white_label_report(
    site_url: str,
    crawl_date: datetime,
    total_links: int,
    broken_links: int,
    redirect_links: int,
    ok_links: int,
    issues_by_type: Dict[str, int],
    detailed_issues: list,
    logo_path: Optional[str] = None,
    brand_color: str = "#2563eb",
    report_title: str = "Link Audit Report",
    client_name: Optional[str] = None,
    output_format: str = "html",
    output_path: str = "linkcanary_report.html"
) -> str:
    """Convenience function to create a white-label report."""
    
    config = WhiteLabelConfig(
        logo_path=logo_path,
        brand_color=brand_color,
        report_title=report_title,
        client_name=client_name,
        output_format=output_format
    )
    
    report_data = ReportData(
        site_url=site_url,
        crawl_date=crawl_date,
        total_links=total_links,
        broken_links=broken_links,
        redirect_links=redirect_links,
        ok_links=ok_links,
        issues_by_type=issues_by_type,
        detailed_issues=detailed_issues
    )
    
    generator = WhiteLabelReportGenerator(config)
    return generator.generate_report(report_data, output_path)