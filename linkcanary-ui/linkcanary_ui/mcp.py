from fastapi import FastAPI, APIRouter, Request, HTTPException
from linkcanary_ui.models.schemas import CrawlStartRequest, Webhook
from linkcanary_ui.api.crawls import start_new_crawl
from linkcanary_ui.models.crawl import Crawl
from linkcanary_ui.models.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
from linkcanary_ui.services.webhooks import WebhookService

router = APIRouter()

async def get_crawl_status(db: Session, crawl_id: str):
    crawl = db.query(Crawl).filter(Crawl.id == crawl_id).first()
    if not crawl:
        raise HTTPException(status_code=404, detail="Crawl not found")
    return crawl.to_dict()

@router.post("/mcp")
async def mcp_handler(request: Request, db: Session = Depends(get_db)):
    body = await request.json()
    tool = body.get("tool")
    
    if tool == "start_crawl":
        url = body.get("url")
        if not url:
            raise HTTPException(status_code=400, detail="URL is required for start_crawl")
        
        # We need to create a mock request object that the existing crawl function can use
        crawl_request = CrawlStartRequest(url=url)
        
        # The start_new_crawl function expects a background_tasks object,
        # but for MCP we'll run it synchronously for now.
        class MockBackgroundTasks:
            def add_task(self, *args, **kwargs):
                pass
        
        background_tasks = MockBackgroundTasks()
        
        response = await start_new_crawl(crawl_request, background_tasks, db)
        return {"crawl_id": response.get("crawl_id")}

    elif tool == "check_crawl_status":
        crawl_id = body.get("crawl_id")
        if not crawl_id:
            raise HTTPException(status_code=400, detail="crawl_id is required for check_crawl_status")
        
        status = await get_crawl_status(db, crawl_id)
        return status
        
    elif tool == "create_asana_task":
        webhook_service = WebhookService(db)
        # Find the first Asana webhook to get credentials
        asana_webhook = db.query(Webhook).filter(Webhook.type == 'asana').first()
        if not asana_webhook:
            raise HTTPException(status_code=400, detail="Asana integration not configured")
        
        title = body.get("title")
        notes = body.get("notes")
        
        payload = {
            "name": title,
            "notes": notes,
        }
        
        success, message = webhook_service.send_asana(asana_webhook, payload)
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
            
        return {"task_id": message}

    elif tool == "create_jira_issue":
        webhook_service = WebhookService(db)
        # Find the first Jira webhook to get credentials
        jira_webhook = db.query(Webhook).filter(Webhook.type == 'jira').first()
        if not jira_webhook:
            raise HTTPException(status_code=400, detail="Jira integration not configured")
            
        summary = body.get("summary")
        description = body.get("description")
        
        payload = {
            "fields": {
                "project": {"key": jira_webhook.jira_project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": jira_webhook.jira_issue_type or "Task"},
            }
        }
        
        success, message = webhook_service.send_jira(jira_webhook, payload)
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
            
        return {"issue_id": message}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {tool}")

def init_app(app: FastAPI):
    app.include_router(router)
