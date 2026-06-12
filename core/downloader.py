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

try:
    from yt_dlp.networking.impersonate import ImpersonateTarget
except Exception:
    ImpersonateTarget = None

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
        po_token_file = os.environ.get("YT_DLP_PO_TOKEN_FILE", "/app/data/po_token.txt")
        self.po_token = None
        if os.path.exists(po_token_file) and os.path.getsize(po_token_file) > 20:
            try:
                self.po_token = Path(po_token_file).read_text(encoding="utf-8").strip()
                logger.info("Loaded saved YouTube PO Token.")
            except Exception as e:
                logger.warning(f"Failed to load PO Token file: {e}")
        
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
        """Construct standard ydl_opts with cookie and client spoofing workarounds.
        
        Base opts are deliberately minimal — individual attempts configure
        their own player_client / extractor_args via _apply_youtube_args.
        """
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
            "nocheckcertificate": True,
            "legacyserverconnect": True,
            "source_address": "0.0.0.0",
            "format": video_format,
            "extractor_args": {
                "youtube": {
                    "skip": ["webpage"],  # Skip webpage — hit innerTube API directly
                    "player_client": ["android_vr"]
                }
            }
        }
        # Local dev: try browser cookies
        if not os.environ.get("RUNNING_IN_DOCKER"):
            opts["cookiesfrombrowser"] = ("chrome", "firefox", "edge", "safari")
            logger.info("Attempting to use browser cookies (local execution)")

        if extra_opts:
            for k, v in extra_opts.items():
                if k == "extractor_args" and "extractor_args" in opts:
                    for ext, args in v.items():
                        if ext in opts["extractor_args"]:
                            opts["extractor_args"][ext].update(args)
                        else:
                            opts["extractor_args"][ext] = args
                else:
                    opts[k] = v
        return opts

    def _add_impersonation(self, opts: dict) -> dict:
        if ImpersonateTarget is not None:
            try:
                opts["impersonate"] = ImpersonateTarget.from_str("chrome")
            except Exception:
                logger.warning("yt-dlp impersonation target unavailable; continuing without it.")
        return opts

    def _po_tokens(self, clients: list[str] | None) -> list[str]:
        if not self.po_token:
            return []
        token = self.po_token.strip()
        if "+" in token:
            return [token]
        tokens = []
        for client in clients or ["mweb", "web"]:
            if client == "mweb":
                tokens.append(f"mweb.gvs+{token}")
            elif client == "web":
                tokens.append(f"web+{token}")
                tokens.append(f"web.gvs+{token}")
        return tokens

    def _apply_youtube_args(
        self,
        opts: dict,
        clients: list[str] | None,
        use_po_token: bool = False,
    ) -> None:
        if clients:
            youtube_args = {"player_client": clients}
            po_tokens = self._po_tokens(clients) if use_po_token else []
            if po_tokens:
                youtube_args["po_token"] = po_tokens
            opts["extractor_args"] = {"youtube": youtube_args}
        else:
            opts.pop("extractor_args", None)

    def get_video_info(self, url: str) -> VideoInfo:
        """Fetch video metadata without downloading. Uses deep fallback chain."""
        cookies_path = self.cookies_file_path or self.default_cookies_file_path
        # Try 10 different client/extractor strategies in order
        attempts = [
            # 1-3: Try with cookies on web/mweb/android clients (cookies bypass most IP blocks)
            {"clients": ["web"], "cookiefile": cookies_path, "po": False, "impersonate": True},
            {"clients": ["mweb"], "cookiefile": cookies_path, "po": True, "impersonate": True},
            {"clients": ["android"], "cookiefile": cookies_path, "po": False, "impersonate": False},
            # 4-6: Try no-cookie approaches with various API clients
            {"clients": ["android_vr", "android_creator"], "cookiefile": None, "po": False, "impersonate": False},
            {"clients": ["ios"], "cookiefile": None, "po": False, "impersonate": False},
            {"clients": ["web_safari"], "cookiefile": None, "po": False, "impersonate": True},
            # 7-8: Try TV/embedded clients
            {"clients": ["tv_embedded"], "cookiefile": None, "po": False, "impersonate": False},
            {"clients": ["tv"], "cookiefile": None, "po": False, "impersonate": False},
            # 9-10: Default yt-dlp behavior (no custom extractor_args)
            {"clients": None, "cookiefile": cookies_path, "po": False, "impersonate": True},
            {"clients": None, "cookiefile": None, "po": False, "impersonate": False},
        ]
        last_error = None
        for attempt, attempt_cfg in enumerate(attempts, start=1):
            try:
                opts = self._get_ydl_opts({"skip_download": True, "format": "best"})
                opts.pop("cookiesfrombrowser", None)
                opts.pop("cookiefile", None)
                self._apply_youtube_args(opts, attempt_cfg["clients"], attempt_cfg["po"])
                if attempt_cfg["cookiefile"]:
                    opts["cookiefile"] = attempt_cfg["cookiefile"]
                if attempt_cfg["impersonate"]:
                    self._add_impersonation(opts)
                logger.info(
                    f"Metadata attempt {attempt}: clients={attempt_cfg['clients'] or 'default'} "
                    f"cookies={'yes' if attempt_cfg['cookiefile'] else 'no'} "
                    f"po={'yes' if attempt_cfg['po'] and self.po_token else 'no'}"
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

        base_opts = {
            "outtmpl": video_path,
            "merge_output_format": "mp4",
            "noprogress": True,
            "progress_hooks": [progress_hook],
            "continuedl": True,
            "http_chunk_size": 10485760,
            "sleep_interval_requests": 2,
            "throttledratelimit": 100000,
            "postprocessors": [{
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }],
        }
        
        ydl_opts = self._get_ydl_opts(base_opts)

        # Escalating fallback chain — tries cookies-first (often bypasses IP blocks),
        # then multiple API client types, then raw extraction.
        cookies_path = self.cookies_file_path or self.default_cookies_file_path
        attempts = [
            # Cookies-based approaches (most likely to work on datacenter IPs)
            {"format": None, "clients": ["web"], "cookiefile": cookies_path, "po": False, "impersonate": True},
            {"format": None, "clients": ["mweb"], "cookiefile": cookies_path, "po": True, "impersonate": True},
            {"format": None, "clients": ["android"], "cookiefile": cookies_path, "po": False, "impersonate": False},
            # No-cookie API client approaches
            {"format": None, "clients": ["android_vr"], "cookiefile": None, "po": False, "impersonate": False},
            {"format": None, "clients": ["ios"], "cookiefile": None, "po": False, "impersonate": False},
            {"format": None, "clients": ["web_safari"], "cookiefile": None, "po": False, "impersonate": True},
            # TV clients
            {"format": "best", "clients": ["tv_embedded"], "cookiefile": None, "po": False, "impersonate": False},
            {"format": "best", "clients": ["tv"], "cookiefile": None, "po": False, "impersonate": False},
            # Default yt-dlp (no custom extractor_args)
            {"format": "best", "clients": None, "cookiefile": cookies_path, "po": False, "impersonate": True},
            {"format": "best", "clients": None, "cookiefile": None, "po": False, "impersonate": False},
        ]

        for attempt, attempt_cfg in enumerate(attempts, start=1):
            try:
                current_opts = ydl_opts.copy()
                current_opts.pop("cookiesfrombrowser", None)
                current_opts.pop("cookiefile", None)
                self._apply_youtube_args(current_opts, attempt_cfg["clients"], attempt_cfg["po"])
                if attempt_cfg["format"] is not None:
                    current_opts["format"] = attempt_cfg["format"]
                if attempt_cfg["cookiefile"]:
                    current_opts["cookiefile"] = attempt_cfg["cookiefile"]
                if attempt_cfg["impersonate"]:
                    self._add_impersonation(current_opts)
                logger.info(
                    f"Download attempt {attempt}: clients={attempt_cfg['clients'] or 'default'} "
                    f"cookies={'yes' if attempt_cfg['cookiefile'] else 'no'} "
                    f"po={'yes' if attempt_cfg['po'] and self.po_token else 'no'}"
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
            "-ar", "16000",
            "-ac", "1",
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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.download_video(url, job_id, progress_callback)
        )

    async def get_video_info_async(self, url: str) -> VideoInfo:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.get_video_info(url))
