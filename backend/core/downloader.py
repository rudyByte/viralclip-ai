"""
ViralClip AI — YouTube Downloader
Uses yt-dlp to download video and extract audio.
"""
import yt_dlp
import os
import asyncio
from pathlib import Path
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)


class VideoInfo:
    def __init__(self, data: dict):
        self.id = data.get("id", "")
        self.title = data.get("title", "Unknown")
        self.channel = data.get("uploader", "Unknown")
        self.duration = data.get("duration", 0)
        self.thumbnail = data.get("thumbnail", "")
        self.description = data.get("description", "")
        self.view_count = data.get("view_count", 0)


class Downloader:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_video_info(self, url: str) -> VideoInfo:
        """Fetch video metadata without downloading."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return VideoInfo(info)

    def download_video(
        self,
        url: str,
        job_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> tuple[str, str]:
        """
        Download video and extract audio.
        Returns (video_path, audio_path).
        """
        video_path = str(self.output_dir / f"{job_id}_video.mp4")
        audio_path = str(self.output_dir / f"{job_id}_audio.wav")

        def progress_hook(d):
            if d["status"] == "downloading" and progress_callback:
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 1)
                pct = int((downloaded / total) * 100) if total else 0
                progress_callback(pct)

        # Download best video+audio merged
        ydl_opts = {
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": video_path,
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [progress_hook],
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        logger.info(f"Video downloaded: {video_path}")

        # Extract audio as WAV for Whisper
        self._extract_audio(video_path, audio_path)
        logger.info(f"Audio extracted: {audio_path}")

        return video_path, audio_path

    def _extract_audio(self, video_path: str, audio_path: str):
        """Extract 16kHz mono WAV audio for Whisper transcription."""
        import subprocess
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-ar", "16000",       # 16kHz sample rate for Whisper
            "-ac", "1",           # Mono
            "-f", "wav",
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg audio extraction failed: {result.stderr}")

    async def download_video_async(
        self,
        url: str,
        job_id: str,
        progress_callback: Optional[Callable] = None,
    ) -> tuple[str, str]:
        """Async wrapper for download_video."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.download_video(url, job_id, progress_callback)
        )

    async def get_video_info_async(self, url: str) -> VideoInfo:
        """Async wrapper for get_video_info."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.get_video_info(url))
