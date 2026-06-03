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
    layout_template: str = "split_50_50"


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
    layout_template: Optional[str] = "split_50_50"


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
        layout_template=job.layout_template,
    )


@router.post("/process")
async def process_video(
    req: ProcessRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start the full ViralClip AI processing pipeline (supports single or comma/newline separated list of URLs)."""
    urls = [u.strip() for u in req.youtube_url.replace("\n", ",").split(",") if u.strip()]
    if not urls:
        raise HTTPException(status_code=400, detail="No valid YouTube URLs provided")

    job_ids = []
    for url in urls:
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            youtube_url=url,
            status="queued",
            progress=0,
            clip_min_duration=req.clip_min_duration,
            clip_max_duration=req.clip_max_duration,
            num_clips=req.num_clips,
            caption_style=req.caption_style,
            background_type=req.background_type,
            layout_template=req.layout_template,
            created_at=datetime.utcnow(),
        )
        db.add(job)
        job_ids.append(job_id)

    await db.commit()
    logger.info(f"Queued {len(job_ids)} jobs: {job_ids}")
    
    return {
        "job_id": job_ids[0],  # Backwards compatibility for single URL redirect
        "job_ids": job_ids,
        "status": "queued",
        "message": f"Successfully queued {len(job_ids)} video clip jobs."
    }


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
        job_responses.append(job_to_response(job, clip_count).model_dump())

    return {"jobs": job_responses, "total": len(job_responses)}


@router.delete("/{job_id}")
async def delete_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a job and all its clips from the database."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in ["downloading", "transcribing", "analyzing", "clipping"]:
        raise HTTPException(status_code=409, detail="Cannot delete a running job")

    await db.execute(delete(Hook).where(Hook.job_id == job_id))
    await db.execute(delete(Clip).where(Clip.job_id == job_id))
    await db.execute(delete(Job).where(Job.id == job_id))
    await db.commit()

    return {"message": f"Job {job_id} deleted"}
