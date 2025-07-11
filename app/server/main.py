import asyncio
import logging
import uuid
from typing import List, Literal
from urllib.parse import urlparse
from contextlib import asynccontextmanager
from newspaper import Article
from pathlib import Path
import httpx

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, HttpUrl, field_validator
import uvicorn

from app.common.queue_utils import AsyncQueueManager
from app.common.models import URLProcessingResult
from app.common.redis_client import get_redis_key, redis_client
from app.common.config import ALLOWED_DOMAINS
from app.server.websocket.manager import WebSocketManager
from app.server.websocket.consumer import WebSocketConsumer

logger = logging.getLogger(__name__)

class URLSubmissionRequest(BaseModel):
    urls: List[HttpUrl]

    @field_validator('urls')
    @classmethod
    def validate_domains(cls, v):
        for url in v:
            try:
                parsed = urlparse(str(url))
            except Exception:
                raise ValueError(f"Invalid URL format: {url}")

            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValueError(f"Invalid URL format: {url}")

            if parsed.netloc not in ALLOWED_DOMAINS:
                raise ValueError(f"Domain {parsed.netloc} not allowed")
        return v

class URLStatus(BaseModel):
    url: str
    status: Literal["cached", "queued", "completed", "failed", "rejected"]
    detail: str | None = None
    result: URLProcessingResult | None = None
    request_id: str

class SubmissionResponse(BaseModel):
    request_id: str
    statuses: List[URLStatus]

queue_manager: AsyncQueueManager = None
websocket_manager: WebSocketManager = None
websocket_consumer: WebSocketConsumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global queue_manager, websocket_manager, websocket_consumer
    logger.info("Application startup initiated.")

    queue_manager = AsyncQueueManager()
    await queue_manager.init()
    
    websocket_manager = WebSocketManager()
    websocket_consumer = WebSocketConsumer(websocket_manager)

    await websocket_consumer.start()
    
    logger.info("All services started.")
    yield
    
    logger.info("Application shutdown initiated.")
    if websocket_consumer:
        await websocket_consumer.stop()
    if queue_manager:
        await queue_manager.close()
    logger.info("All services gracefully stopped.")

app = FastAPI(
    title="Content Filtering and Summarization System",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

async def is_url_reachable(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, follow_redirects=True)
            if response.status_code != 200:
                return False
            if "page not found" in response.text.lower():
                return False
        return True
    except Exception:
        return False

def fetch_article_content(url: str) -> str | None:
    """Fetch the full article content from the given URL"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except Exception as e:
        logger.error(f"Failed to fetch article content from {url}: {e}")
        return None

def get_processing_result(url: str) -> URLProcessingResult | None:
    """
    Retrieve the stored processing result for a URL from Redis.
    Returns None if the key does not exist.
    """
    key = get_redis_key(url)
    json_data = redis_client.get(key)
    if not json_data:
        return None

    return URLProcessingResult.model_validate_json(json_data)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML UI"""
    html_file = Path(__file__).parent / "static" / "index.html"
    if html_file.exists():
        return FileResponse(html_file)
    else:
        return HTMLResponse("""
        <html>
            <body>
                <h1>URL Processing Server</h1>
                <p>UI not found. Please ensure index.html is in the static directory.</p>
                <p>API endpoints:</p>
                <ul>
                    <li>POST /api/submit - Submit URLs for processing</li>
                    <li>GET /api/health - Health check</li>
                    <li>WS /ws/{request_id} - WebSocket for real-time updates</li>
                </ul>
            </body>
        </html>
        """)

@app.post("/api/submit", response_model=SubmissionResponse)
async def submit_urls(request: URLSubmissionRequest):
    batch_request_id = str(uuid.uuid4())
    statuses = []

    logger.info(f"Received URLs submission: {len(request.urls)} URLs, batch_request_id: {batch_request_id}")

    if not queue_manager:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="System services are not initialized. Please try again later."
        )

    for url_obj in request.urls:
        url_str = str(url_obj)
        url_specific_request_id = str(uuid.uuid4()) 
        
        try:
            existing_result = get_processing_result(url_str)
            if existing_result:
                try:
                    await queue_manager.publish_status_update(
                        request_id=url_specific_request_id,
                        url=url_str,
                        status="cached",
                        detail="Result retrieved from cache.",
                        result=existing_result.model_dump()
                    )
                    statuses.append(URLStatus(
                        url=url_str,
                        request_id=url_specific_request_id,
                        status="cached",
                        detail="Result retrieved from cache",
                        result=existing_result
                    ))
                except Exception as e:
                    logger.error(f"Error fetching article content for cached result {url_str}: {e}")
                    await queue_manager.publish_status_update(
                        request_id=url_specific_request_id,
                        url=url_str,
                        status="cached",
                        detail=f"Result retrieved from cache, but content fetch failed: {str(e)}",
                        result=existing_result.model_dump()
                    )
                    statuses.append(URLStatus(
                        url=url_str,
                        request_id=url_specific_request_id,
                        status="cached",
                        detail=f"Result retrieved from cache (content unavailable): {str(e)}",
                        result=existing_result
                    ))
            else:
                exists = await is_url_reachable(url_str)
                if not exists:
                    detail_msg = "URL not reachable or returned 404"
                    logger.warning(f"Rejected URL {url_str}: {detail_msg}")
                    statuses.append(URLStatus(
                        url=url_str,
                        request_id=url_specific_request_id,
                        status="rejected",
                        detail=detail_msg
                    ))
                    await queue_manager.publish_status_update(
                        request_id=url_specific_request_id,
                        url=url_str,
                        status="rejected",
                        detail=detail_msg
                    )
                    continue 
                await queue_manager.publish_url_task(
                    url=url_str,
                    request_id=url_specific_request_id,
                    priority=10,
                    retry_count=0
                )
                statuses.append(URLStatus(
                    url=url_str,
                    request_id=url_specific_request_id,
                    status="queued",
                    detail="URL queued for processing"
                ))
        except HTTPException as e:
            logger.warning(f"Rejected URL {url_str}: {e.detail}")
            statuses.append(URLStatus(
                url=url_str,
                request_id=url_specific_request_id, 
                status="rejected",
                detail=e.detail
            ))
            await queue_manager.publish_status_update(
                request_id=url_specific_request_id,
                url=url_str,
                status="rejected",
                detail=e.detail
            )
        except Exception as e:
            logger.error(f"Error processing URL {url_str}: {e}")
            await queue_manager.publish_status_update(
                request_id=url_specific_request_id,
                url=url_str,
                status="failed",
                detail=f"Error initiating processing: {str(e)}"
            )
            statuses.append(URLStatus(
                url=url_str,
                request_id=url_specific_request_id,
                status="failed",
                detail=f"Error: {str(e)}"
            ))

    return SubmissionResponse(
        request_id=batch_request_id,
        statuses=statuses
    )

@app.get("/api/content")
async def get_content(url: str = Query(...)):
    content = fetch_article_content(url)
    if content is None:
        raise HTTPException(status_code=404, detail="Content not found or failed to fetch")
    return {"url": url, "content": content}

@app.get("/api/status/{request_id}")
async def get_status(request_id: str):
    return {"request_id": request_id, "message": "Use WebSocket for real-time updates"}

@app.websocket("/ws/{request_id}")
async def websocket_endpoint(websocket: WebSocket, request_id: str):
    await websocket_manager.connect(websocket, request_id)
    try:
        while True:
            # Keep connection alive and handle any incoming messages
            # data = await websocket.receive_text()
            # logger.debug(f"Received WebSocket message from {request_id}: {data}")
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket, request_id)
    except Exception as e:
        logger.error(f"WebSocket error for {request_id}: {e}")
        await websocket_manager.disconnect(websocket, request_id)

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "message": "Server is running"}

@app.get("/ui", response_class=HTMLResponse)
async def ui():
    """Alternative endpoint to serve the UI"""
    return await read_root()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    uvicorn.run(
        "app.server.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )