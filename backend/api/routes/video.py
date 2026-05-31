"""
ViralClip AI — Video Processing API Routes
POST /api/video/process  — start full pipeline
GET  /api/video/status/{job_id} — poll job progress
GET  /api/video/jobs — list all jobs
DELETE /api/video/{job_id} — remove job
"""
import uuid
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, HttpUrl
from typing import Optional

from database import get_db, Job, Clip, Hook
from core.pipeline import run_pipeline
from config import get_settings

router = APIRouter(prefix="/api/video", tags=["video"])
logger = logging.getLogger(__name__)
settings = get_settings()

# Track running jobs
_running_jobs: set[str] = set()


class ProcessRequest(BaseModel):
    youtube_url: str
    clip_min_duration: int = 30
    clip_max_duration: int = 60
    num_clips: int = 5
    caption_style: str = "hormozi"
    background_type: str = "subway"


class JobResponse(BaseModel):
    id: str
    youtube_url: str
    title: Optional[str]
    channel: Optional[str]
    thumbnail_url: Optional[str]
    duration_seconds: Optional[float]
    status: str
    progress: int
    current_step: Optional[str]
    error_message: Optional[str]
    created_at: str
    completed_at: Optional[str]
    clip_count: int = 0


def job_to_response(job: Job, clip_count: int = 0) -> JobResponse:
    return JobResponse(
        id=job.id,
        youtube_url=job.youtube_url,
        title=job.title,
        channel=job.channel,
        thumbnail_url=job.thumbnail_url,
        duration_seconds=job.duration_seconds,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step,
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else "",
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        clip_count=clip_count,
    )


@router.post("/process")
async def process_video(
    req: ProcessRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Start the full ViralClip AI processing pipeline."""
    if len(_running_jobs) >= settings.max_concurrent_jobs:
        raise HTTPException(
            status_code=429,
            detail=f"Max concurrent jobs ({settings.max_concurrent_jobs}) reached. Please wait."
        )

    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        youtube_url=req.youtube_url,
        status="queued",
        progress=0,
        clip_min_duration=req.clip_min_duration,
        clip_max_duration=req.clip_max_duration,
        num_clips=req.num_clips,
        caption_style=req.caption_style,
        background_type=req.background_type,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    await db.commit()

    # Launch pipeline in background
    async def _run():
        _running_jobs.add(job_id)
        try:
            await run_pipeline(
                job_id=job_id,
                youtube_url=req.youtube_url,
                clip_min_duration=req.clip_min_duration,
                clip_max_duration=req.clip_max_duration,
                num_clips=req.num_clips,
                caption_style=req.caption_style,
                background_type=req.background_type,
            )
        finally:
            _running_jobs.discard(job_id)

    background_tasks.add_task(_run)

    logger.info(f"Job queued: {job_id}")
    return {"job_id": job_id, "status": "queued", "message": "Pipeline started"}


@router.get("/status/{job_id}")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Get real-time status of a processing job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Count completed clips
    clips_result = await db.execute(
        select(Clip).where(Clip.job_id == job_id, Clip.status == "done")
    )
    clip_count = len(clips_result.scalars().all())

    return job_to_response(job, clip_count)


@router.get("/jobs")
async def list_jobs(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all processing jobs, newest first."""
    from sqlalchemy import desc
    result = await db.execute(
        select(Job).order_by(desc(Job.created_at)).limit(limit).offset(offset)
    )
    jobs = result.scalars().all()

    job_responses = []
    for job in jobs:
        clips_result = await db.execute(
            select(Clip).where(Clip.job_id == job.id, Clip.status == "done")
        )
        clip_count = len(clips_result.scalars().all())
        job_responses.append(job_to_response(job, clip_count).dict())

    return {"jobs": job_responses, "total": len(job_responses)}


@router.delete("/{job_id}")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a job and all its clips from the database."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_id in _running_jobs:
        raise HTTPException(status_code=409, detail="Cannot delete a running job")

    await db.execute(delete(Hook).where(Hook.job_id == job_id))
    await db.execute(delete(Clip).where(Clip.job_id == job_id))
    await db.execute(delete(Job).where(Job.id == job_id))
    await db.commit()

    return {"message": f"Job {job_id} deleted"}
