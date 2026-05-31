"""
ViralClip AI — Pipeline Orchestrator
Coordinates the full processing pipeline for a single job.
"""
import asyncio
import logging
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

from config import get_settings
from database import AsyncSessionLocal, Job, Clip, Hook
from core.downloader import Downloader
from core.transcriber import Transcriber
from core.analyzer import GroqAnalyzer
from core.clipper import Clipper
from core.caption_generator import CaptionGenerator
from core.background_mixer import BackgroundMixer
from utils.face_tracker import FaceTracker
from utils.virality_scorer import ViralityScorer

logger = logging.getLogger(__name__)
settings = get_settings()


async def update_job_status(job_id: str, status: str, progress: int, step: str = "", error: str = ""):
    """Update job status in database."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, update
        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=status,
                progress=progress,
                current_step=step,
                error_message=error if error else None,
                completed_at=datetime.utcnow() if status in ("done", "error") else None,
            )
        )
        await db.commit()


async def run_pipeline(
    job_id: str,
    youtube_url: str,
    clip_min_duration: int = 30,
    clip_max_duration: int = 60,
    num_clips: int = 5,
    caption_style: str = "hormozi",
    background_type: str = "subway",
):
    """Full ViralClip AI processing pipeline."""
    temp_dir = Path(settings.temp_dir) / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    export_dir = Path(settings.export_dir) / job_id
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        # ── Step 1: Download ──────────────────────────────────────────
        await update_job_status(job_id, "downloading", 5, "Downloading video...")
        logger.info(f"[{job_id}] Downloading: {youtube_url}")

        downloader = Downloader(str(temp_dir))
        info = await downloader.get_video_info_async(youtube_url)

        async with AsyncSessionLocal() as db:
            from sqlalchemy import update as sq_update
            await db.execute(
                sq_update(Job).where(Job.id == job_id).values(
                    title=info.title,
                    channel=info.channel,
                    thumbnail_url=info.thumbnail,
                    duration_seconds=info.duration,
                )
            )
            await db.commit()

        def dl_progress(pct):
            asyncio.run_coroutine_threadsafe(
                update_job_status(job_id, "downloading", 5 + int(pct * 0.15), f"Downloading... {pct}%"),
                asyncio.get_event_loop(),
            )

        video_path, audio_path = await downloader.download_video_async(
            youtube_url, job_id, progress_callback=dl_progress
        )

        async with AsyncSessionLocal() as db:
            from sqlalchemy import update as sq_update
            await db.execute(
                sq_update(Job).where(Job.id == job_id).values(
                    video_path=video_path, audio_path=audio_path
                )
            )
            await db.commit()

        # ── Step 2: Transcribe ────────────────────────────────────────
        await update_job_status(job_id, "transcribing", 22, "Transcribing audio with Whisper...")
        logger.info(f"[{job_id}] Transcribing...")

        transcriber = Transcriber(
            model_name=settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
        transcript = await transcriber.transcribe_async(audio_path)

        transcript_path = str(temp_dir / "transcript.json")
        transcriber.save_transcript(transcript, transcript_path)

        async with AsyncSessionLocal() as db:
            from sqlalchemy import update as sq_update
            await db.execute(
                sq_update(Job).where(Job.id == job_id).values(transcript_path=transcript_path)
            )
            await db.commit()

        # ── Step 3: Analyze with Groq ─────────────────────────────────
        await update_job_status(job_id, "analyzing", 45, "Detecting viral moments with Groq AI...")
        logger.info(f"[{job_id}] Analyzing viral moments...")

        chunks = transcript.get_chunks_for_analysis(chunk_duration=180.0)
        analyzer = GroqAnalyzer(api_key=settings.groq_api_key)

        viral_moments = await analyzer.detect_viral_moments(
            transcript_chunks=chunks,
            num_clips=num_clips,
            min_duration=clip_min_duration,
            max_duration=clip_max_duration,
        )

        logger.info(f"[{job_id}] Found {len(viral_moments)} viral moments")

        # ── Step 4: Create clips ──────────────────────────────────────
        await update_job_status(job_id, "clipping", 55, "Creating and processing clips...")

        clipper = Clipper(
            str(temp_dir),
            export_width=settings.export_width,
            export_height=settings.export_height,
            fps=settings.export_fps,
        )
        face_tracker = FaceTracker()
        caption_gen = CaptionGenerator(
            str(temp_dir),
            video_width=settings.export_width,
            video_height=settings.export_height,
        )
        bg_mixer = BackgroundMixer(settings.assets_dir)
        scorer = ViralityScorer()

        clip_records = []
        total_clips = len(viral_moments)

        for i, moment in enumerate(viral_moments):
            clip_id = str(uuid.uuid4())
            clip_progress = 55 + int((i / total_clips) * 35)
            await update_job_status(
                job_id, "clipping", clip_progress,
                f"Processing clip {i+1}/{total_clips}..."
            )

            try:
                # Extract raw clip
                raw_path = str(temp_dir / f"clip_{i}_raw.mp4")
                await clipper.extract_clip_async(video_path, moment.start_time, moment.end_time, raw_path)

                # Face track for smart crop
                face_positions = await face_tracker.analyze_video_async(
                    raw_path, sample_interval=2.0
                )

                # Crop to vertical 9:16
                cropped_path = str(temp_dir / f"clip_{i}_cropped.mp4")
                await clipper.crop_to_vertical_async(raw_path, cropped_path, face_positions)

                # Generate captions
                words = transcript.get_words_in_range(moment.start_time, moment.end_time)
                ass_path = str(temp_dir / f"clip_{i}_captions.ass")
                await caption_gen.generate_ass_file_async(
                    words, ass_path, caption_style, moment.start_time
                )

                captioned_path = str(temp_dir / f"clip_{i}_captioned.mp4")
                await caption_gen.burn_captions_async(cropped_path, ass_path, captioned_path)

                # Add gaming background
                export_path = str(export_dir / f"clip_{i+1}_{int(moment.score)}.mp4")
                await bg_mixer.mix_with_background_async(
                    captioned_path, export_path, background_type
                )

                # Generate hooks
                clip_text = " ".join(w.word for w in words)
                hooks = await analyzer.generate_hooks(clip_text, info.title)

                # Compute final virality score
                final_score = scorer.compute_score(moment.scores)

                # Save clip to DB
                async with AsyncSessionLocal() as db:
                    clip = Clip(
                        id=clip_id,
                        job_id=job_id,
                        clip_index=i,
                        start_time=moment.start_time,
                        end_time=moment.end_time,
                        duration=moment.duration,
                        virality_score=final_score,
                        reason=moment.reason,
                        score_curiosity=moment.scores.get("curiosity_hook", 0),
                        score_emotion=moment.scores.get("emotional_intensity", 0),
                        score_controversy=moment.scores.get("controversy", 0),
                        score_storytelling=moment.scores.get("storytelling", 0),
                        score_novelty=moment.scores.get("novelty", 0),
                        score_retention=moment.scores.get("retention", 0),
                        score_audience_hook=moment.scores.get("audience_hook", 0),
                        score_educational=moment.scores.get("educational_value", 0),
                        raw_clip_path=raw_path,
                        cropped_clip_path=cropped_path,
                        captioned_clip_path=captioned_path,
                        export_path=export_path,
                        caption_style=caption_style,
                        background_type=background_type,
                        status="done",
                    )
                    db.add(clip)

                    hook_record = Hook(
                        id=str(uuid.uuid4()),
                        clip_id=clip_id,
                        job_id=job_id,
                        title=hooks.titles[0] if hooks.titles else "",
                        hook=hooks.hooks[0] if hooks.hooks else "",
                        caption=hooks.captions[0] if hooks.captions else "",
                        hashtags=json.dumps(hooks.hashtags),
                        thumbnail_text=hooks.thumbnail_text,
                    )
                    db.add(hook_record)
                    await db.commit()

                clip_records.append(clip_id)
                logger.info(f"[{job_id}] Clip {i+1} done: score={final_score}")

            except Exception as e:
                logger.error(f"[{job_id}] Clip {i+1} failed: {e}", exc_info=True)
                continue

        # ── Step 5: Done ─────────────────────────────────────────────
        await update_job_status(job_id, "done", 100, f"Complete! {len(clip_records)} clips ready.")
        logger.info(f"[{job_id}] Pipeline complete. {len(clip_records)} clips exported.")

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
        await update_job_status(job_id, "error", 0, "", str(e))
        raise
