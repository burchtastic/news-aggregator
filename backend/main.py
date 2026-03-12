"""FastAPI application — news aggregator backend."""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv()

from . import database as db
from .scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="News Aggregator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helper ────────────────────────────────────────────────────────────────────

async def run_in_thread(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, fn, *args)


# ── Request / Response models ─────────────────────────────────────────────────

class BlockSourceRequest(BaseModel):
    source_name: Optional[str] = None
    source_url: Optional[str] = None


class FeedbackRequest(BaseModel):
    feedback: int  # -1, 0, or 1


class SourceUpdateRequest(BaseModel):
    active: Optional[bool] = None
    blocked: Optional[bool] = None


class AddSourceRequest(BaseModel):
    name: str
    url: str


class PreferencesRequest(BaseModel):
    blocked_sources: Optional[list[str]] = None
    blocked_keywords: Optional[list[str]] = None
    preferred_topics: Optional[list[str]] = None
    email_recipient: Optional[str] = None


# ── Articles ──────────────────────────────────────────────────────────────────

@app.get("/api/articles")
async def get_articles(
    topic: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    articles = await run_in_thread(
        db.get_articles, topic, date_from, min_score, limit, offset
    )
    return {"articles": articles, "count": len(articles)}


@app.post("/api/articles/{article_id}/feedback")
async def set_feedback(article_id: int, body: FeedbackRequest):
    if body.feedback not in (-1, 0, 1):
        raise HTTPException(status_code=400, detail="feedback must be -1, 0, or 1")
    await run_in_thread(db.set_article_feedback, article_id, body.feedback)
    return {"ok": True}


# ── Sources ───────────────────────────────────────────────────────────────────

@app.get("/api/sources")
async def get_sources():
    sources = await run_in_thread(db.get_sources)
    return {"sources": sources}


@app.post("/api/sources/block")
async def block_source(body: BlockSourceRequest):
    if not body.source_name and not body.source_url:
        raise HTTPException(status_code=400, detail="Provide source_name or source_url")
    await run_in_thread(db.block_source, body.source_name, body.source_url)
    return {"ok": True}


@app.put("/api/sources/{source_id}")
async def update_source(source_id: int, body: SourceUpdateRequest):
    await run_in_thread(db.update_source, source_id, body.active, body.blocked)
    return {"ok": True}


@app.post("/api/sources")
async def add_source(body: AddSourceRequest):
    await run_in_thread(db.add_source, body.name, body.url)
    return {"ok": True}


# ── Digest ────────────────────────────────────────────────────────────────────

@app.get("/api/digest/preview")
async def digest_preview():
    from .email_digest import build_digest_data
    data = await run_in_thread(build_digest_data)
    return {
        "article_count": data["article_count"],
        "generated_at": data["generated_at"],
        "html": data["html"],
        "articles": data["articles"],
    }


@app.post("/api/digest/send")
async def send_digest_now(background_tasks: BackgroundTasks):
    from .email_digest import send_digest
    background_tasks.add_task(send_digest)
    return {"ok": True, "message": "Digest sending in background"}


# ── Manual Fetch ──────────────────────────────────────────────────────────────

@app.post("/api/run-fetch")
async def run_fetch(background_tasks: BackgroundTasks):
    from .fetcher import run_fetch_all
    background_tasks.add_task(run_fetch_all)
    return {"ok": True, "message": "Fetch started in background"}


@app.post("/api/run-fetch/sync")
async def run_fetch_sync():
    """Synchronous fetch — waits for completion. Use for testing."""
    from .fetcher import run_fetch_all
    result = await run_in_thread(run_fetch_all)
    return result


# ── Preferences ───────────────────────────────────────────────────────────────

@app.get("/api/preferences")
async def get_preferences():
    import json
    prefs = await run_in_thread(db.get_preferences)
    return {
        "blocked_sources": json.loads(prefs.get("blocked_sources", "[]")),
        "blocked_keywords": json.loads(prefs.get("blocked_keywords", "[]")),
        "preferred_topics": json.loads(prefs.get("preferred_topics", "[]")),
        "email_recipient": prefs.get("email_recipient", ""),
    }


@app.put("/api/preferences")
async def update_preferences(body: PreferencesRequest):
    await run_in_thread(
        db.update_preferences,
        body.blocked_sources,
        body.blocked_keywords,
        body.preferred_topics,
        body.email_recipient,
    )
    return {"ok": True}


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    import json
    import sqlite3
    from .database import get_connection
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        analyzed = conn.execute("SELECT COUNT(*) FROM articles WHERE analyzed=1").fetchone()[0]
        sources = conn.execute("SELECT COUNT(*) FROM sources WHERE active=1 AND blocked=0").fetchone()[0]
        avg_score = conn.execute(
            "SELECT AVG(score) FROM articles WHERE analyzed=1"
        ).fetchone()[0] or 0
        return {
            "total_articles": total,
            "analyzed_articles": analyzed,
            "active_sources": sources,
            "avg_score": round(float(avg_score), 1),
        }
    finally:
        conn.close()


# ── Serve React frontend ──────────────────────────────────────────────────────

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

if os.path.exists(FRONTEND_DIST):
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"detail": "Frontend not built. Run: cd frontend && npm run build"}
else:
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "message": "News Aggregator API",
            "docs": "/docs",
            "note": "Build the frontend: cd frontend && npm run build",
        }
