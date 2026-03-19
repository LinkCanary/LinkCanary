"""Main FastAPI application."""

import argparse
import os
import sys
import webbrowser
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import __version__
from .api import backlinks, crawls, reports, settings as settings_api, stats, url_resolution, websocket, webhooks, mcp
from .config import settings
from .models import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    settings.ensure_dirs()
    await init_db()
    yield


app = FastAPI(
    title="LinkCanary UI",
    description="Web interface for LinkCanary link checker",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(backlinks.router)
app.include_router(crawls.router)
app.include_router(reports.router)
app.include_router(stats.router)
app.include_router(settings_api.router)
app.include_router(websocket.router)
app.include_router(webhooks.router)
app.include_router(url_resolution.router)
app.include_router(mcp.router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")


@app.get("/")
async def root():
    """Serve the frontend application."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "message": "LinkCanary UI API",
        "version": __version__,
        "docs": "/docs",
    }


@app.get("/vite.svg")
async def vite_svg():
    """Serve vite.svg."""
    return FileResponse(static_dir / "vite.svg")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


def cli():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        prog="linkcanary-ui",
        description="Start the LinkCanary web interface",
    )
    
    parser.add_argument(
        "--host",
        default=settings.host,
        help=f"Host to bind to (default: {settings.host})",
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=settings.port,
        help=f"Port to bind to (default: {settings.port})",
    )
    
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open browser automatically",
    )
    
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=f"Data directory (default: {settings.data_dir})",
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"linkcanary-ui {__version__}",
    )
    
    # White Label Report Options
    report_group = parser.add_argument_group('White Label Report Options')
    report_group.add_argument(
        '--white-label-logo',
        help='Path to client logo image (PNG/SVG)',
        default=None
    )
    report_group.add_argument(
        '--white-label-color',
        default='#2563eb',
        help='Primary brand color (hex code)'
    )
    report_group.add_argument(
        '--white-label-title',
        default='Link Audit Report',
        help='Custom report title'
    )
    report_group.add_argument(
        '--white-label-client',
        help='Client name for report header',
        default=None
    )
    report_group.add_argument(
        '--output-format',
        choices=['html', 'pdf'],
        default='html',
        help='Report format (html or pdf)'
    )
    report_group.add_argument(
        '--generate-report',
        action='store_true',
        help='Generate a white-label report'
    )
    
    args = parser.parse_args()
    
    if args.data_dir:
        settings.data_dir = args.data_dir
    
    if args.debug:
        settings.debug = True
    
    settings.ensure_dirs()
    
    print(f"""
LinkCanary UI v{__version__}
{'=' * 40}
Server: http://{args.host}:{args.port}
Data:   {settings.data_dir}
{'=' * 40}
""")
    
    if args.generate_report:
        from datetime import datetime
        from linkcanary_ui.report_generator import create_white_label_report
        
        # Mock data for demonstration - in real implementation, this would come from crawl results
        report_data = {
            'site_url': 'https://example.com',
            'crawl_date': datetime.now(),
            'total_links': 150,
            'broken_links': 12,
            'redirect_links': 8,
            'ok_links': 130,
            'issues_by_type': {
                '404 Not Found': 12,
                '500 Server Error': 3,
                'Redirect Chain': 5,
                'Slow Response': 7
            },
            'detailed_issues': [
                {
                    'url': 'https://example.com/broken-page',
                    'status': '404',
                    'issue_type': 'Broken Link',
                    'priority': 'high',
                    'details': 'Page not found'
                },
                {
                    'url': 'https://example.com/redirect-chain',
                    'status': '301',
                    'issue_type': 'Redirect Chain',
                    'priority': 'medium',
                    'details': 'Multiple redirects detected'
                }
            ]
        }
        
        output_path = f"linkcanary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        if args.output_format == 'pdf':
            output_path += '.pdf'
        else:
            output_path += '.html'
        
        result = create_white_label_report(
            site_url=report_data['site_url'],
            crawl_date=report_data['crawl_date'],
            total_links=report_data['total_links'],
            broken_links=report_data['broken_links'],
            redirect_links=report_data['redirect_links'],
            ok_links=report_data['ok_links'],
            issues_by_type=report_data['issues_by_type'],
            detailed_issues=report_data['detailed_issues'],
            logo_path=args.white_label_logo,
            brand_color=args.white_label_color,
            report_title=args.white_label_title,
            client_name=args.white_label_client,
            output_format=args.output_format,
            output_path=output_path
        )
        
        print(f"✅ Report generated successfully: {result}")
        return
    
    if args.open:
        webbrowser.open(f"http://{args.host}:{args.port}")
    
    uvicorn.run(
        "linkcanary_ui.main:app",
        host=args.host,
        port=args.port,
        reload=args.debug,
    )


if __name__ == "__main__":
    cli()
