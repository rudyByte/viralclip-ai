"""
ViralClip AI — Pipeline Orchestrator
Coordinates the full processing pipeline for a single job.
Supports checkpoint-based resume at every phase.
"""
import asyncio
import logging
import os
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import get_settings
from database import AsyncSessionLocal, Job, Clip, Hook
from core.downloader import Downloader
from core.transcriber import Transcriber
from core.analyzer import GroqAnalyzer, ViralMoment
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
        from sqlalchemy import update
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


async def _get_job(job_id: str) -> Optional[Job]:
    """Fetch the latest job record from DB."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Job).where(Job.id == job_id))
        return result.scalars().first()


async def run_pipeline(
    job_id: str,
    youtube_url: str,
    clip_min_duration: int = 30,
    clip_max_duration: int = 60,
    num_clips: int = 5,
    caption_style: str = "hormozi",
    background_type: str = "subway",
    layout_template: str = "split_50_50",
    resolution: str = "1080p",
    cookies: Optional[str] = None,
):
    """
    Full ViralClip AI processing pipeline with checkpoint-based resume.

    Phases:
      1. Download  — skipped if video_path + audio_path files already exist
      2. Transcribe — skipped if transcript.json already saved on disk
      3. Analyze   — skipped if viral_moments.json already saved on disk
      4. Clip      — per-clip resume: skips clips whose DB record is 'done' and export file exists
    """
    temp_dir = Path(settings.temp_dir) / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    export_dir = Path(settings.export_dir) / job_id
    export_dir.mkdir(parents=True, exist_ok=True)

    yt_title = "YouTube Video"  # Safe default
    yt_channel = "Unknown"

    try:
        # ── Load existing job record for checkpoint data ───────────────
        job = await _get_job(job_id)

        # ── Step 1: Download ──────────────────────────────────────────
        video_path = job.video_path if job else None
        audio_path = job.audio_path if job else None

        # Check if files already exist on disk (for resuming interrupted downloads)
        expected_video_path = temp_dir / f"{job_id}_video.mp4"
        expected_audio_path = temp_dir / f"{job_id}_audio.wav"

        if expected_video_path.exists():
            logger.info(f"[{job_id}] ✓ Video file already found on disk at {expected_video_path}. Skipping download.")
            video_path = str(expected_video_path)
            
            if not expected_audio_path.exists():
                logger.info(f"[{job_id}] Audio file missing. Extracting from existing video...")
                await update_job_status(job_id, "downloading", 10, "Extracting audio from existing download...")
                downloader = Downloader(str(temp_dir), resolution=resolution, cookies=cookies)
                await asyncio.get_running_loop().run_in_executor(
                    None, downloader._extract_audio, video_path, str(expected_audio_path)
                )
            
            audio_path = str(expected_audio_path)
            
            # Update video info in DB if missing
            if not job or not job.title:
                try:
                    downloader = Downloader(str(temp_dir), resolution=resolution, cookies=cookies)
                    info = await downloader.get_video_info_async(youtube_url)
                    async with AsyncSessionLocal() as db:
                        from sqlalchemy import update as sq_update
                        await db.execute(
                            sq_update(Job).where(Job.id == job_id).values(
                                title=info.title,
                                channel=info.channel,
                                thumbnail_url=info.thumbnail,
                                duration_seconds=info.duration,
                                video_path=video_path,
                                audio_path=audio_path,
                            )
                        )
                        await db.commit()
                    yt_title = info.title
                    yt_channel = info.channel
                except Exception as ex:
                    logger.warning(f"[{job_id}] Failed to fetch info for cached download: {ex}")
                    yt_title = "YouTube Video"
            else:
                async with AsyncSessionLocal() as db:
                    from sqlalchemy import update as sq_update
                    await db.execute(
                        sq_update(Job).where(Job.id == job_id).values(
                            video_path=video_path, audio_path=audio_path
                        )
                    )
                    await db.commit()
                yt_title = job.title or "YouTube Video"
                yt_channel = job.channel or "Unknown"
            
            await update_job_status(job_id, "downloading", 20, "Video and audio loaded from disk, resuming...")
        elif video_path and audio_path and os.path.exists(video_path) and os.path.exists(audio_path):
            logger.info(f"[{job_id}] ✓ Step 1 checkpoint: video/audio already on disk, skipping download.")
            await update_job_status(job_id, "downloading", 20, "Video already downloaded, resuming...")
            yt_title = job.title or "YouTube Video"
            yt_channel = job.channel or "Unknown"
        else:
            await update_job_status(job_id, "downloading", 5, "Downloading video...")
            logger.info(f"[{job_id}] Step 1: Downloading {youtube_url}")

            downloader = Downloader(str(temp_dir), resolution=resolution, cookies=cookies)
            info = await downloader.get_video_info_async(youtube_url)
            yt_title = info.title
            yt_channel = info.channel

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

            loop = asyncio.get_running_loop()

            def dl_progress(pct):
                asyncio.run_coroutine_threadsafe(
                    update_job_status(job_id, "downloading", 5 + int(pct * 0.15), f"Downloading... {pct}%"),
                    loop,
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
        transcript_path = job.transcript_path if job else None
        cached_transcript = temp_dir / "transcript.json"

        if (transcript_path and os.path.exists(transcript_path)) or cached_transcript.exists():
            load_path = transcript_path if (transcript_path and os.path.exists(transcript_path)) else str(cached_transcript)
            logger.info(f"[{job_id}] ✓ Step 2 checkpoint: transcript found at {load_path}, skipping Whisper.")
            await update_job_status(job_id, "transcribing", 44, "Transcript already available, resuming...")
            transcript = Transcriber.load_transcript(load_path)
        else:
            await update_job_status(job_id, "transcribing", 22, "Transcribing audio with Whisper...")
            logger.info(f"[{job_id}] Step 2: Transcribing with Whisper...")

            loop = asyncio.get_running_loop()

            def transcribe_progress(pct):
                asyncio.run_coroutine_threadsafe(
                    update_job_status(job_id, "transcribing", 22 + int(pct * 0.22), f"Transcribing... {pct}%"),
                    loop,
                )

            transcriber = Transcriber(
                model_name=settings.whisper_model,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
            )
            transcript = await transcriber.transcribe_async(audio_path, progress_callback=transcribe_progress)

            transcript_path = str(cached_transcript)
            transcriber.save_transcript(transcript, transcript_path)

            async with AsyncSessionLocal() as db:
                from sqlalchemy import update as sq_update
                await db.execute(
                    sq_update(Job).where(Job.id == job_id).values(transcript_path=transcript_path)
                )
                await db.commit()

        # ── Step 3: Analyze with Groq ─────────────────────────────────
        viral_moments_path = temp_dir / "viral_moments.json"

        if viral_moments_path.exists():
            logger.info(f"[{job_id}] ✓ Step 3 checkpoint: viral_moments.json found, skipping Groq call.")
            await update_job_status(job_id, "analyzing", 54, "Viral moments already detected, resuming...")
            with open(viral_moments_path, "r", encoding="utf-8") as f:
                moments_raw = json.load(f)
            viral_moments = [
                ViralMoment(
                    start_time=float(m["start_time"]),
                    end_time=float(m["end_time"]),
                    score=int(m["score"]),
                    reason=m.get("reason", ""),
                    hook_words=m.get("hook_words", ""),
                    scores=m.get("scores", {}),
                )
                for m in moments_raw
            ]
        else:
            await update_job_status(job_id, "analyzing", 45, "Detecting viral moments with Groq AI...")
            logger.info(f"[{job_id}] Step 3: Analyzing viral moments with Groq...")

            chunks = transcript.get_chunks_for_analysis(chunk_duration=180.0)
            analyzer = GroqAnalyzer(
                api_key=settings.groq_api_key,
                detection_model=settings.groq_detection_model,
                hook_model=settings.groq_hook_model,
            )

            viral_moments = await analyzer.detect_viral_moments(
                transcript_chunks=chunks,
                num_clips=num_clips,
                min_duration=clip_min_duration,
                max_duration=clip_max_duration,
            )

            # Persist so future retries skip this expensive step
            moments_json = [
                {
                    "start_time": m.start_time,
                    "end_time": m.end_time,
                    "score": m.score,
                    "reason": m.reason,
                    "hook_words": m.hook_words,
                    "scores": m.scores,
                }
                for m in viral_moments
            ]
            with open(viral_moments_path, "w", encoding="utf-8") as f:
                json.dump(moments_json, f, indent=2, ensure_ascii=False)
            logger.info(f"[{job_id}] Saved {len(viral_moments)} viral moments to {viral_moments_path}")

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
        hook_analyzer = GroqAnalyzer(
            api_key=settings.groq_api_key,
            detection_model=settings.groq_detection_model,
            hook_model=settings.groq_hook_model,
        )

        clip_records = []
        total_clips = len(viral_moments)

        for i, moment in enumerate(viral_moments):
            clip_progress = 55 + int((i / max(total_clips, 1)) * 35)
            await update_job_status(
                job_id, "clipping", clip_progress,
                f"Processing clip {i+1}/{total_clips}..."
            )

            # ── Per-clip checkpoint ───────────────────────────────────
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                result = await db.execute(
                    select(Clip).where(Clip.job_id == job_id, Clip.clip_index == i)
                )
                existing_clip = result.scalars().first()

            if existing_clip:
                if existing_clip.status == "done" and existing_clip.export_path and os.path.exists(existing_clip.export_path):
                    logger.info(f"[{job_id}] ✓ Clip {i+1} checkpoint: already done, skipping.")
                    clip_records.append(existing_clip.id)
                    continue
                else:
                    # Remove incomplete record so we retry cleanly
                    logger.warning(f"[{job_id}] Clip {i+1} is incomplete — removing stale DB record and retrying.")
                    async with AsyncSessionLocal() as db:
                        from sqlalchemy import delete
                        await db.execute(delete(Clip).where(Clip.id == existing_clip.id))
                        await db.execute(delete(Hook).where(Hook.clip_id == existing_clip.id))
                        await db.commit()

            clip_id = str(uuid.uuid4())

            try:
                # ── Logical boundary adjustment ───────────────────────
                from core.analyzer import adjust_clip_boundaries
                adjusted_start, adjusted_end = adjust_clip_boundaries(
                    start_time=moment.start_time,
                    end_time=moment.end_time,
                    transcript_words=transcript.all_words,
                    min_duration=clip_min_duration,
                    max_duration=clip_max_duration,
                )
                moment.start_time = adjusted_start
                moment.end_time = adjusted_end

                # Extract raw clip
                raw_path = str(temp_dir / f"clip_{i}_raw.mp4")
                await clipper.extract_clip_async(video_path, moment.start_time, moment.end_time, raw_path)

                # Face track for smart crop
                face_positions = await face_tracker.analyze_video_async(raw_path, sample_interval=2.0)

                # Crop to vertical using layout template target height
                if layout_template == "split_50_50":
                    target_h = 960
                elif layout_template == "split_60_40":
                    target_h = 1152
                elif layout_template == "split_70_30":
                    target_h = 1344
                else:  # no_gameplay or single
                    target_h = 1920

                cropped_path = str(temp_dir / f"clip_{i}_cropped.mp4")
                await clipper.crop_to_vertical_async(raw_path, cropped_path, face_positions, target_height=target_h)

                # Generate captions (supporting Hindi/Gujarati/Indic language font fallbacks)
                words = transcript.get_words_in_range(moment.start_time, moment.end_time)
                ass_path = str(temp_dir / f"clip_{i}_captions.ass")
                lang = getattr(transcript, "language", "en")
                await caption_gen.generate_ass_file_async(
                    words, ass_path, caption_style, moment.start_time,
                    language=lang, crop_height=target_h
                )

                captioned_path = str(temp_dir / f"clip_{i}_captioned.mp4")
                await caption_gen.burn_captions_async(cropped_path, ass_path, captioned_path)

                # Add gaming background mixed with customized template heights
                export_path = str(export_dir / f"clip_{i+1}_score{int(moment.score)}.mp4")
                await bg_mixer.mix_with_background_async(
                    captioned_path, export_path, background_type, layout_template=layout_template
                )

                # Generate hooks with quality model
                clip_text = " ".join(w.word for w in words)
                hooks = await hook_analyzer.generate_hooks(clip_text, yt_title)
                metadata = await hook_analyzer.generate_clip_metadata(moment, yt_title, yt_channel)

                # Compute final virality score
                final_score = scorer.compute_score(moment.scores)

                # Persist to DB
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
                        layout_template=layout_template,
                        youtube_title=metadata.get("youtube_title", ""),
                        youtube_description=metadata.get("youtube_description", ""),
                        instagram_caption=metadata.get("instagram_caption", ""),
                        hook_score=metadata.get("hook_score", 0),
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
                logger.info(f"[{job_id}] Clip {i+1}/{total_clips} done: score={final_score}")

            except Exception as e:
                logger.error(f"[{job_id}] Clip {i+1} failed: {e}", exc_info=True)
                continue

        # ── Step 5: Done ─────────────────────────────────────────────
        if not clip_records:
            raise RuntimeError(
                "No clips were successfully generated. This can occur if the Groq rate limits are exceeded, "
                "or if no viral moments were detected in the transcript. Please try again."
            )

        await update_job_status(job_id, "done", 100, f"Complete! {len(clip_records)} clips ready.")
        logger.info(f"[{job_id}] Pipeline complete. {len(clip_records)} clips exported.")

    except Exception as e:
        logger.error(f"[{job_id}] Pipeline failed: {e}", exc_info=True)
        await update_job_status(job_id, "error", 0, "", str(e))
        raise


async def regenerate_single_clip(clip_id: str):
    """Regenerate a single clip's video file with new styles, templates, or background."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, update
        clip_result = await db.execute(select(Clip).where(Clip.id == clip_id))
        clip = clip_result.scalar_one_or_none()
        if not clip:
            logger.error(f"Clip {clip_id} not found for regeneration.")
            return
            
        job_result = await db.execute(select(Job).where(Job.id == clip.job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            logger.error(f"Job {clip.job_id} not found for clip {clip_id} regeneration.")
            return

        # Mark clip as processing
        await db.execute(update(Clip).where(Clip.id == clip_id).values(status="processing"))
        await db.commit()

    job_id = job.id
    temp_dir = Path(settings.temp_dir) / job_id
    export_dir = Path(settings.export_dir) / job_id

    try:
        from core.clipper import Clipper
        from core.caption_generator import CaptionGenerator
        from core.background_mixer import BackgroundMixer
        from utils.face_tracker import FaceTracker
        from core.transcriber import Transcriber
        
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

        # Load transcript to extract word timestamps
        transcript_path = job.transcript_path or str(temp_dir / "transcript.json")
        transcript = Transcriber.load_transcript(transcript_path)
        words = transcript.get_words_in_range(clip.start_time, clip.end_time)

        # 1. Re-crop using face tracking average & target template height
        face_positions = await face_tracker.analyze_video_async(clip.raw_clip_path, sample_interval=2.0)
        
        layout = getattr(clip, "layout_template", "split_50_50") or "split_50_50"
        if layout == "split_50_50":
            target_h = 960
        elif layout == "split_60_40":
            target_h = 1152
        elif layout == "split_70_30":
            target_h = 1344
        else:  # no_gameplay or single
            target_h = 1920

        cropped_path = str(temp_dir / f"clip_{clip.clip_index}_cropped.mp4")
        await clipper.crop_to_vertical_async(
            clip.raw_clip_path, cropped_path, face_positions, target_height=target_h
        )

        # 2. Burn captions
        ass_path = str(temp_dir / f"clip_{clip.clip_index}_captions.ass")
        lang = getattr(transcript, "language", "en")
        await caption_gen.generate_ass_file_async(
            words, ass_path, clip.caption_style, clip.start_time,
            language=lang, crop_height=target_h
        )

        captioned_path = str(temp_dir / f"clip_{clip.clip_index}_captioned.mp4")
        await caption_gen.burn_captions_async(cropped_path, ass_path, captioned_path)

        # 3. Add background / Layout Mix
        export_path = str(export_dir / f"clip_{clip.clip_index+1}_score{clip.virality_score}.mp4")
        await bg_mixer.mix_with_background_async(
            captioned_path, export_path, clip.background_type, layout_template=layout
        )

        # Update database
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Clip)
                .where(Clip.id == clip_id)
                .values(
                    status="done",
                    cropped_clip_path=cropped_path,
                    captioned_clip_path=captioned_path,
                    export_path=export_path
                )
            )
            await db.commit()
        logger.info(f"Successfully regenerated clip {clip_id}")

    except Exception as e:
        logger.error(f"Failed to regenerate clip {clip_id}: {e}", exc_info=True)
        async with AsyncSessionLocal() as db:
            await db.execute(update(Clip).where(Clip.id == clip_id).values(status="error"))
            await db.commit()
