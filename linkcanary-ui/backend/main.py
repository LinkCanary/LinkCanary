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
from .api import crawls, reports, settings as settings_api, stats, websocket
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

app.include_router(crawls.router)
app.include_router(reports.router)
app.include_router(stats.router)
app.include_router(settings_api.router)
app.include_router(websocket.router)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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
    
    if args.open:
        webbrowser.open(f"http://{args.host}:{args.port}")
    
    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.debug,
    )


if __name__ == "__main__":
    cli()
