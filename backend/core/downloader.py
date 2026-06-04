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

# Deep SSL patch: OP_IGNORE_UNEXPECTED_EOF on ALL SSLContext instances
try:
    import ssl as _ssl
    _op_ignore = getattr(_ssl, "OP_IGNORE_UNEXPECTED_EOF", 8388608)
    _orig_SSLContext_init = _ssl.SSLContext.__init__
    def _patched_SSLContext_init(self, *args, **kwargs):
        if _orig_SSLContext_init is not object.__init__:
            _orig_SSLContext_init(self, *args, **kwargs)
        try:
            self.options |= _op_ignore
        except Exception:
            pass
    _ssl.SSLContext.__init__ = _patched_SSLContext_init
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
        default_cookies = os.environ.get("YT_DLP_COOKIES_FILE", "/app/data/cookies.txt")
        self.default_cookies_file_path = (
            default_cookies
            if os.path.exists(default_cookies) and os.path.getsize(default_cookies) > 100
            else None
        )
        
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
        # Determine format based on chosen resolution.
        # Uses a deep fallback chain so ANY available format is accepted.
        res_limit = "1080"
        if self.resolution == "best":
            video_format = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo[ext=mp4]+bestaudio/"
                "bestvideo+bestaudio/"
                "best[ext=mp4]/best"
            )
        else:
            if self.resolution == "720p":
                res_limit = "720"
            elif self.resolution == "480p":
                res_limit = "480"
            elif self.resolution == "360p":
                res_limit = "360"
            video_format = (
                f"bestvideo[ext=mp4][height<={res_limit}]+bestaudio[ext=m4a]/"
                f"bestvideo[ext=mp4][height<={res_limit}]+bestaudio/"
                f"bestvideo[height<={res_limit}]+bestaudio/"
                f"best[ext=mp4][height<={res_limit}]/"
                f"best[height<={res_limit}]/best"
            )

        opts = {
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 60,
            "retries": 15,
            "fragment_retries": 15,
            "file_access_retries": 5,
            "nocheckcertificate": True,  # Bypass SSL certificate check drops
            "legacyserverconnect": True,
            "source_address": "0.0.0.0",
            "impersonate": "chrome",
            "format": video_format,
            "extractor_args": {
                "youtube": {
                    # android_vr uses a different API endpoint that works on datacenter IPs
                    # without needing cookies or JS signature deciphering
                    "player_client": ["android_vr"]
                }
            }
        }
        
        # Do not attach cookies to primary android_vr opts. Stale cookies can
        # trigger bot checks; saved cookies are only used in explicit web fallback.
        if not os.environ.get("RUNNING_IN_DOCKER"):
            # Try using cookies from browser when running locally (not in Docker)
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
        cookies_path = self.cookies_file_path or self.default_cookies_file_path
        attempts = [
            {"client": "android_vr", "cookiefile": None},
            {"client": "web", "cookiefile": cookies_path},
            {"client": "ios", "cookiefile": None},
            {"client": None, "cookiefile": None},
        ]
        last_error = None
        for attempt, attempt_cfg in enumerate(attempts, start=1):
            try:
                opts = self._get_ydl_opts({"skip_download": True, "format": "best"})
                opts.pop("cookiesfrombrowser", None)
                opts.pop("cookiefile", None)
                if attempt_cfg["client"]:
                    opts["extractor_args"] = {"youtube": {"player_client": [attempt_cfg["client"]]}}
                else:
                    opts.pop("extractor_args", None)
                if attempt_cfg["cookiefile"]:
                    opts["cookiefile"] = attempt_cfg["cookiefile"]
                logger.info(
                    f"Metadata attempt {attempt}: client={attempt_cfg['client'] or 'default'} "
                    f"cookies={'yes' if attempt_cfg['cookiefile'] else 'no'}"
                )
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return VideoInfo(info)
            except Exception as err:
                last_error = err
                logger.warning(f"Metadata attempt {attempt} failed: {err}")
                continue
        raise last_error

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

        # Escalating format fallbacks – each attempt is broader than the previous.
        # This guarantees we always get *something* even if the first choice isn't available.
        cookies_path = self.cookies_file_path or self.default_cookies_file_path
        attempts = [
            {"format": None, "client": "android_vr", "cookiefile": None},
            {"format": "bestvideo+bestaudio/best", "client": "web", "cookiefile": cookies_path},
            {"format": "best", "client": "ios", "cookiefile": None},
        ]

        for attempt, attempt_cfg in enumerate(attempts, start=1):
            try:
                current_opts = ydl_opts.copy()
                current_opts.pop("cookiesfrombrowser", None)
                current_opts.pop("cookiefile", None)
                current_opts["extractor_args"] = {"youtube": {"player_client": [attempt_cfg["client"]]}}
                if attempt_cfg["format"] is not None:
                    current_opts["format"] = attempt_cfg["format"]
                if attempt_cfg["cookiefile"]:
                    current_opts["cookiefile"] = attempt_cfg["cookiefile"]
                logger.info(
                    f"Download attempt {attempt}: client={attempt_cfg['client']} "
                    f"cookies={'yes' if attempt_cfg['cookiefile'] else 'no'}"
                )

                with yt_dlp.YoutubeDL(current_opts) as ydl:
                    ydl.download([url])
                break  # Success
            except Exception as dl_err:
                if attempt < len(attempts):
                    wait = 8 * attempt
                    logger.warning(f"Download attempt {attempt} failed: {dl_err}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"All {len(attempts)} download attempts failed.")
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
