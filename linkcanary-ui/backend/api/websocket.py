"""WebSocket endpoint for real-time progress updates."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from ..models import Crawl, CrawlStatus
from ..models.database import async_session

router = APIRouter()

active_connections: Dict[str, Set[WebSocket]] = {}


class ConnectionManager:
    """Manage WebSocket connections."""
    
    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, crawl_id: str, websocket: WebSocket):
        """Accept and register a new connection."""
        await websocket.accept()
        if crawl_id not in self.connections:
            self.connections[crawl_id] = set()
        self.connections[crawl_id].add(websocket)
    
    def disconnect(self, crawl_id: str, websocket: WebSocket):
        """Remove a connection."""
        if crawl_id in self.connections:
            self.connections[crawl_id].discard(websocket)
            if not self.connections[crawl_id]:
                del self.connections[crawl_id]
    
    async def broadcast(self, crawl_id: str, message: dict):
        """Send message to all connections for a crawl."""
        if crawl_id in self.connections:
            dead_connections = set()
            for connection in self.connections[crawl_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)
            
            for dead in dead_connections:
                self.connections[crawl_id].discard(dead)


manager = ConnectionManager()


@router.websocket("/ws/crawl/{crawl_id}")
async def crawl_progress_websocket(websocket: WebSocket, crawl_id: str):
    """WebSocket endpoint for crawl progress updates."""
    await manager.connect(crawl_id, websocket)
    
    try:
        while True:
            async with async_session() as db:
                result = await db.execute(select(Crawl).where(Crawl.id == crawl_id))
                crawl = result.scalar_one_or_none()
                
                if not crawl:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Crawl not found",
                    })
                    break
                
                elapsed = 0.0
                if crawl.started_at:
                    if crawl.completed_at:
                        elapsed = (crawl.completed_at - crawl.started_at).total_seconds()
                    else:
                        elapsed = (datetime.utcnow() - crawl.started_at).total_seconds()
                
                await websocket.send_json({
                    "type": "progress",
                    "crawl_id": crawl_id,
                    "status": crawl.status.value,
                    "pages_crawled": crawl.pages_crawled,
                    "total_pages": crawl.total_pages,
                    "links_checked": crawl.links_checked,
                    "issues_found": crawl.total_issues,
                    "issues": {
                        "critical": crawl.issues_critical,
                        "high": crawl.issues_high,
                        "medium": crawl.issues_medium,
                        "low": crawl.issues_low,
                    },
                    "elapsed_seconds": elapsed,
                    "error_message": crawl.error_message,
                })
                
                if crawl.status in (CrawlStatus.COMPLETED, CrawlStatus.FAILED, CrawlStatus.CANCELLED):
                    await websocket.send_json({
                        "type": "complete",
                        "crawl_id": crawl_id,
                        "status": crawl.status.value,
                        "report_available": bool(crawl.report_csv_path),
                    })
                    break
            
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=1.5)
            except asyncio.TimeoutError:
                pass
    
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(crawl_id, websocket)


async def send_progress_update(crawl_id: str, data: dict):
    """Send progress update to all connected clients."""
    await manager.broadcast(crawl_id, {
        "type": "progress",
        "crawl_id": crawl_id,
        **data,
    })
