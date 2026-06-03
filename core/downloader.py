"""
ViralClip AI — YouTube Downloader
Uses yt-dlp to download video and extract audio.
Robust: supports resume, chunked download, exponential retry backoff.
"""
import yt_dlp
import os
import time
import asyncio
from pathlib import Path
from typing import Optional, Callable
import logging
import ssl

# Disable strict OpenSSL 3.0+ check for SSL: UNEXPECTED_EOF_WHILE_READING
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
    def __init__(self, output_dir: str, resolution: str = "1080p", cookies: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.resolution = resolution
        
        # Save custom cookies to a file in the job temporary directory if provided
        self.cookies_file_path = None
        if cookies and cookies.strip():
            c_file = self.output_dir / "job_cookies.txt"
            try:
                c_file.write_text(cookies.strip(), encoding="utf-8")
                self.cookies_file_path = str(c_file)
                logger.info(f"Saved custom cookies to {self.cookies_file_path}")
            except Exception as e:
                logger.error(f"Failed to write custom cookies file: {e}")

    def _get_ydl_opts(self, extra_opts: Optional[dict] = None) -> dict:
        """Construct standard ydl_opts with cookie and client spoofing workarounds."""
        # Determine format based on chosen resolution
        res_limit = "1080"
        if self.resolution == "best":
            video_format = "bestvideo+bestaudio/best"
        else:
            if self.resolution == "720p":
                res_limit = "720"
            elif self.resolution == "480p":
                res_limit = "480"
            elif self.resolution == "360p":
                res_limit = "360"
            video_format = f"bestvideo[ext=mp4][height<={res_limit}]+bestaudio[ext=m4a]/bestvideo[height<={res_limit}]+bestaudio/best[height<={res_limit}]/best"

        opts = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 60,
            "retries": 15,
            "fragment_retries": 15,
            "file_access_retries": 5,
            "nocheckcertificate": True,  # Bypass SSL certificate check drops
            "format": video_format,
            "extractor_args": {
                "youtube": {
                    "player_client": ["default", "-android_sdkless"],
                }
            }
        }
        
        # Check for cookies file (prioritize custom job-specific cookies)
        cookies_file = None
        if self.cookies_file_path and os.path.exists(self.cookies_file_path):
            cookies_file = self.cookies_file_path
        else:
            for p in [os.environ.get("YT_DLP_COOKIES_FILE"), "/app/data/cookies.txt", "data/cookies.txt", "cookies.txt"]:
                if p and os.path.exists(p):
                    cookies_file = p
                    break
                
        if cookies_file:
            opts["cookiefile"] = cookies_file
            logger.info(f"Using cookies file: {cookies_file}")
        elif not os.environ.get("RUNNING_IN_DOCKER"):
            # Try using cookies from browser when running locally (not in Docker)
            # Since cookiesfrombrowser can fail/warn if browsers aren't found/configured,
            # we will set it here and catch errors/retry dynamically if it raises exception.
            opts["cookiesfrombrowser"] = ("chrome", "firefox", "edge", "safari")
            logger.info("Attempting to use browser cookies (local execution)")
            
        if extra_opts:
            for k, v in extra_opts.items():
                if k == "extractor_args" and "extractor_args" in opts:
                    # Merge extractor_args
                    for ext, args in v.items():
                        if ext in opts["extractor_args"]:
                            opts["extractor_args"][ext].update(args)
                        else:
                            opts["extractor_args"][ext] = args
                else:
                    opts[k] = v
        return opts

    def get_video_info(self, url: str) -> VideoInfo:
        """Fetch video metadata without downloading."""
        ydl_opts = self._get_ydl_opts({
            "skip_download": True,
        })
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return VideoInfo(info)
        except Exception as err:
            # Fallback if cookiesfrombrowser caused failure
            if "cookiesfrombrowser" in ydl_opts:
                logger.warning(f"Metadata fetch with browser cookies failed ({err}). Retrying without browser cookies...")
                del ydl_opts["cookiesfrombrowser"]
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return VideoInfo(info)
            raise

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

        # Base download options (format key removed to avoid overriding format determined in _get_ydl_opts)
        base_opts = {
            "outtmpl": video_path,
            "merge_output_format": "mp4",
            "noprogress": True,
            "progress_hooks": [progress_hook],
            "continuedl": True,          # Resume partial downloads
            "http_chunk_size": 10485760,  # 10MB chunks — fewer TCP hangs
            "sleep_interval_requests": 2, # Pause between retries
            "throttledratelimit": 100000, # 100KB/s min — triggers retry if throttled below
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        }
        
        ydl_opts = self._get_ydl_opts(base_opts)

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                current_opts = ydl_opts.copy()
                if attempt > 1 and "cookiesfrombrowser" in current_opts:
                    # If first attempt failed, disable browser cookies fallback in case it triggered error
                    del current_opts["cookiesfrombrowser"]
                    
                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    ydl.download([url])
                break  # Success
            except Exception as dl_err:
                if attempt < max_attempts:
                    wait = 10 * attempt
                    logger.warning(f"Download attempt {attempt} failed: {dl_err}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"All {max_attempts} download attempts failed.")
                    raise

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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.download_video(url, job_id, progress_callback)
        )

    async def get_video_info_async(self, url: str) -> VideoInfo:
        """Async wrapper for get_video_info."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.get_video_info(url))
