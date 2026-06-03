import ssl

# Disable strict OpenSSL 3.0+ check for SSL: UNEXPECTED_EOF_WHILE_READING globally
try:
    orig_create_default_context = ssl.create_default_context
    def patched_create_default_context(*args, **kwargs):
        context = orig_create_default_context(*args, **kwargs)
        op_ignore = getattr(ssl, "OP_IGNORE_UNEXPECTED_EOF", 8388608)
        context.options |= op_ignore
        return context
    ssl.create_default_context = patched_create_default_context
except Exception:
    pass

import logging
import asyncio
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import get_settings
from database import init_db, AsyncSessionLocal, Job
from api.routes.video import router as video_router
from api.routes.clips import router as clips_router
from core.pipeline import run_pipeline

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

# ── Queue Worker ──────────────────────────────────────────────────────────────
worker_task: asyncio.Task = None
cleanup_task: asyncio.Task = None

async def queue_worker_loop():
    logger.info("Persistent queue worker loop started.")
    try:
        while True:
            await asyncio.sleep(3)
            # Find running jobs in database
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                
                # Check how many jobs are currently running
                running_query = select(Job).where(Job.status.in_(["downloading", "transcribing", "analyzing", "clipping"]))
                running_jobs = (await db.execute(running_query)).scalars().all()
                active_count = len(running_jobs)

                if active_count >= settings.max_concurrent_jobs:
                    continue

                # Find oldest queued job
                queued_query = select(Job).where(Job.status == "queued").order_by(Job.created_at.asc())
                next_job = (await db.execute(queued_query)).scalars().first()

                if not next_job:
                    continue

                # Mark it as active to reserve it
                job_id = next_job.id
                youtube_url = next_job.youtube_url
                min_dur = next_job.clip_min_duration
                max_dur = next_job.clip_max_duration
                num_c = next_job.num_clips
                cap_style = next_job.caption_style
                bg_type = next_job.background_type
                layout_temp = getattr(next_job, "layout_template", "split_50_50") or "split_50_50"

                # Update state before running pipeline to avoid double-processing
                from sqlalchemy import update
                await db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(status="downloading", progress=1, current_step="Starting...")
                )
                await db.commit()

            # Execute run_pipeline in background
            asyncio.create_task(
                run_pipeline(
                    job_id=job_id,
                    youtube_url=youtube_url,
                    clip_min_duration=min_dur,
                    clip_max_duration=max_dur,
                    num_clips=num_c,
                    caption_style=cap_style,
                    background_type=bg_type,
                    layout_template=layout_temp
                )
            )
            logger.info(f"Launched pipeline task for job: {job_id}")

    except asyncio.CancelledError:
        logger.info("Queue worker loop cancelled.")
    except Exception as e:
        logger.error(f"Error in queue worker loop: {e}", exc_info=True)


async def temp_cleanup_loop():
    logger.info("Automatic temp files cleanup scheduler started.")
    try:
        while True:
            temp_path = Path(settings.temp_dir)
            if temp_path.exists() and temp_path.is_dir():
                now = datetime.now()
                cutoff = now - timedelta(hours=24)
                logger.info(f"Running scheduled temp cleanup. Cutoff time: {cutoff}")
                
                cleaned_count = 0
                for item in temp_path.iterdir():
                    try:
                        mtime = datetime.fromtimestamp(item.stat().st_mtime)
                        if mtime < cutoff:
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                            cleaned_count += 1
                    except Exception as item_err:
                        logger.error(f"Failed to delete {item}: {item_err}")
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} temp items.")
            
            # Wait for 1 hour
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Temp cleanup scheduler loop cancelled.")
    except Exception as e:
        logger.error(f"Error in temp cleanup scheduler loop: {e}", exc_info=True)


async def reset_stale_jobs():
    """
    Re-queue any jobs that were interrupted during a previous run.
    The checkpoint pipeline will resume them from their last saved phase.
    """
    try:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, update
            stale_query = select(Job).where(Job.status.in_(["downloading", "transcribing", "analyzing", "clipping"]))
            stale_jobs = (await db.execute(stale_query)).scalars().all()
            if stale_jobs:
                logger.info(
                    f"Found {len(stale_jobs)} stale jobs on startup — re-queueing for checkpoint resume."
                )
                await db.execute(
                    update(Job)
                    .where(Job.status.in_(["downloading", "transcribing", "analyzing", "clipping"]))
                    .values(
                        status="queued",
                        progress=0,
                        current_step="Resuming from checkpoint...",
                        error_message=None,
                        completed_at=None,
                    )
                )
                await db.commit()
    except Exception as e:
        logger.error(f"Error resetting stale jobs: {e}", exc_info=True)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_task, cleanup_task
    logger.info("ViralClip AI starting up...")
    settings.ensure_dirs()
    await init_db()
    logger.info(f"Database initialized")
    await reset_stale_jobs()
    logger.info(f"Temp dir: {settings.temp_dir}")
    logger.info(f"Export dir: {settings.export_dir}")
    logger.info(f"Groq detection model: {settings.groq_detection_model}")
    logger.info(f"Groq hook model:      {settings.groq_hook_model}")
    logger.info(f"Whisper model: {settings.whisper_model}")
    
    # Start background tasks
    worker_task = asyncio.create_task(queue_worker_loop())
    cleanup_task = asyncio.create_task(temp_cleanup_loop())
    
    yield
    
    # Stop background tasks
    tasks_to_cancel = []
    if worker_task:
        worker_task.cancel()
        tasks_to_cancel.append(worker_task)
    if cleanup_task:
        cleanup_task.cancel()
        tasks_to_cancel.append(cleanup_task)
        
    if tasks_to_cancel:
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
    logger.info("ViralClip AI shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ViralClip AI",
    description="Free open-source alternative to Opus Clip / Vidyo.ai — powered by Groq + Whisper",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Allow all Vercel deployments (*.vercel.app), local dev, and any configured frontend URL
ALLOWED_ORIGINS = [
    settings.frontend_url,
    "http://localhost:3000",
    "http://localhost:5173",
    "https://frontend-six-navy-96.vercel.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",  # all Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(video_router)
app.include_router(clips_router)

# ── Serve exports as static files ─────────────────────────────────────────────
exports_path = Path(settings.export_dir)
exports_path.mkdir(parents=True, exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(exports_path)), name="exports")


# ── WebSocket for real-time progress ─────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, job_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(job_id, []).append(ws)

    def disconnect(self, job_id: str, ws: WebSocket):
        if job_id in self.active:
            self.active[job_id].discard(ws) if hasattr(self.active[job_id], 'discard') else None
            try:
                self.active[job_id].remove(ws)
            except ValueError:
                pass

    async def broadcast(self, job_id: str, data: dict):
        if job_id not in self.active:
            return
        dead = []
        for ws in self.active[job_id]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(job_id, ws)


manager = ConnectionManager()


@app.websocket("/ws/job/{job_id}")
async def job_progress_ws(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job progress updates."""
    await manager.connect(job_id, websocket)
    try:
        while True:
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                result = await db.execute(select(Job).where(Job.id == job_id))
                job = result.scalar_one_or_none()

            if job:
                await websocket.send_json({
                    "job_id": job_id,
                    "status": job.status,
                    "progress": job.progress,
                    "current_step": job.current_step,
                    "error": job.error_message,
                })
                if job.status in ("done", "error"):
                    break

            await asyncio.sleep(1.5)

    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": "ViralClip AI",
        "version": "1.0.0",
        "groq_configured": bool(settings.groq_api_key),
        "whisper_model": settings.whisper_model,
    }


@app.get("/api/config")
async def get_config():
    """Return safe public config (no API keys)."""
    return {
        "whisper_model": settings.whisper_model,
        "max_concurrent_jobs": settings.max_concurrent_jobs,
        "default_clip_min": settings.default_clip_min_duration,
        "default_clip_max": settings.default_clip_max_duration,
        "default_num_clips": settings.default_num_clips,
        "caption_styles": ["hormozi", "gadzhi", "ali_abdaal", "mrbeast", "minimal"],
        "background_types": ["subway", "minecraft", "gta", "templerun", "none"],
        "export_resolution": f"{settings.export_width}x{settings.export_height}",
        "export_fps": settings.export_fps,
    }


if __name__ == "__main__":
    import uvicorn
    import os
    should_reload = settings.debug and os.getenv("RUNNING_IN_DOCKER") != "true"
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=should_reload,
        log_level="info",
    )
