"""
ViralClip AI — Clips API Routes
GET    /api/clips/{job_id}             — list all clips for a job
GET    /api/clips/detail/{clip_id}     — get single clip details
GET    /api/clips/{clip_id}/download   — download clip file
GET    /api/clips/{clip_id}/hooks      — get AI-generated hooks
POST   /api/clips/{clip_id}/regenerate — regenerate with new settings
"""
import logging
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from database import get_db, Clip, Hook, Job
from utils.virality_scorer import ViralityScorer

router = APIRouter(prefix="/api/clips", tags=["clips"])
logger = logging.getLogger(__name__)
scorer = ViralityScorer()


def clip_to_dict(clip: Clip) -> dict:
    scores = {
        "curiosity_hook": clip.score_curiosity,
        "emotional_intensity": clip.score_emotion,
        "controversy": clip.score_controversy,
        "storytelling": clip.score_storytelling,
        "novelty": clip.score_novelty,
        "retention": clip.score_retention,
        "audience_hook": clip.score_audience_hook,
        "educational_value": clip.score_educational,
    }
    return {
        "id": clip.id,
        "job_id": clip.job_id,
        "clip_index": clip.clip_index,
        "start_time": clip.start_time,
        "end_time": clip.end_time,
        "duration": clip.duration,
        "virality_score": clip.virality_score,
        "virality_label": scorer.get_score_label(clip.virality_score),
        "reason": clip.reason,
        "scores": scores,
        "score_breakdown": scorer.get_score_breakdown(scores),
        "caption_style": clip.caption_style,
        "background_type": clip.background_type,
        "status": clip.status,
        "has_export": clip.export_path is not None and Path(clip.export_path or "").exists(),
        "created_at": clip.created_at.isoformat() if clip.created_at else "",
    }


@router.get("/{job_id}")
async def list_clips(job_id: str, db: AsyncSession = Depends(get_db)):
    """List all clips for a given job, sorted by virality score."""
    result = await db.execute(
        select(Clip).where(Clip.job_id == job_id).order_by(Clip.virality_score.desc())
    )
    clips = result.scalars().all()

    if not clips:
        # Check job exists
        job_result = await db.execute(select(Job).where(Job.id == job_id))
        if not job_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Job not found")

    return {"clips": [clip_to_dict(c) for c in clips], "total": len(clips)}


@router.get("/detail/{clip_id}")
async def get_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed info for a single clip."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip_to_dict(clip)


@router.get("/{clip_id}/download")
async def download_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Stream the final exported clip file."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    export_path = clip.export_path
    if not export_path or not Path(export_path).exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    filename = f"viralclip_{clip.clip_index + 1}_score{clip.virality_score}.mp4"
    return FileResponse(
        path=export_path,
        media_type="video/mp4",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{clip_id}/hooks")
async def get_clip_hooks(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Get AI-generated titles, hooks, captions, and hashtags for a clip."""
    result = await db.execute(select(Hook).where(Hook.clip_id == clip_id))
    hook = result.scalar_one_or_none()

    if not hook:
        raise HTTPException(status_code=404, detail="No hooks generated for this clip yet")

    hashtags = []
    if hook.hashtags:
        try:
            hashtags = json.loads(hook.hashtags)
        except (json.JSONDecodeError, TypeError):
            hashtags = []

    return {
        "clip_id": clip_id,
        "title": hook.title,
        "hook": hook.hook,
        "caption": hook.caption,
        "hashtags": hashtags,
        "thumbnail_text": hook.thumbnail_text,
    }


class RegenerateRequest(BaseModel):
    caption_style: Optional[str] = None
    background_type: Optional[str] = None


@router.post("/{clip_id}/regenerate")
async def regenerate_clip(
    clip_id: str,
    req: RegenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Queue clip for regeneration with different caption/background settings."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    # Update settings and mark for regeneration
    from sqlalchemy import update
    updates = {"status": "pending"}
    if req.caption_style:
        updates["caption_style"] = req.caption_style
    if req.background_type:
        updates["background_type"] = req.background_type

    await db.execute(update(Clip).where(Clip.id == clip_id).values(**updates))
    await db.commit()

    return {"message": "Clip queued for regeneration", "clip_id": clip_id}


@router.get("/{clip_id}/preview")
async def preview_clip(clip_id: str, db: AsyncSession = Depends(get_db)):
    """Stream the final exported clip file inline (not as attachment)."""
    result = await db.execute(select(Clip).where(Clip.id == clip_id))
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found")

    export_path = clip.export_path
    if not export_path or not Path(export_path).exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    return FileResponse(
        path=export_path,
        media_type="video/mp4",
    )

