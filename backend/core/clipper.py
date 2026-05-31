"""
ViralClip AI — FFmpeg Clipper
Extracts clips from video, crops to 9:16 vertical with face tracking.
"""
import subprocess
import asyncio
import logging
import os
from pathlib import Path
from typing import Optional
from core.transcriber import Transcript

logger = logging.getLogger(__name__)


class Clipper:
    def __init__(self, output_dir: str, export_width: int = 1080, export_height: int = 1920, fps: int = 30):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.export_width = export_width
        self.export_height = export_height
        self.fps = fps

    def extract_clip(
        self,
        video_path: str,
        start_time: float,
        end_time: float,
        output_path: str,
        padding: float = 0.3,
    ) -> str:
        """Extract a clip from the video at given timestamps."""
        # Add small padding for natural cuts
        start = max(0.0, start_time - padding)
        duration = (end_time + padding) - start

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            output_path,
        ]
        self._run_ffmpeg(cmd)
        logger.info(f"Extracted clip: {output_path} ({duration:.1f}s)")
        return output_path

    def crop_to_vertical(
        self,
        video_path: str,
        output_path: str,
        face_x_ratio: float = 0.5,
        face_y_ratio: float = 0.35,
    ) -> str:
        """
        Crop video to 9:16 vertical format centered on speaker.
        face_x_ratio: horizontal center of face (0-1, 0.5 = center)
        face_y_ratio: vertical center of face (0-1)
        """
        # Get source video dimensions
        probe = self._probe_video(video_path)
        src_w = probe["width"]
        src_h = probe["height"]

        # Calculate crop dimensions for 9:16
        # Crop width = source_height * (9/16)
        crop_w = int(src_h * 9 / 16)
        crop_h = src_h

        if crop_w > src_w:
            # Portrait video already — just scale
            crop_w = src_w
            crop_h = int(src_w * 16 / 9)

        # Center crop on detected face position
        crop_x = int(src_w * face_x_ratio - crop_w / 2)
        crop_x = max(0, min(crop_x, src_w - crop_w))

        crop_y = 0  # Start from top for portrait crops

        vf = (
            f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
            f"scale={self.export_width}:{self.export_height}:force_original_aspect_ratio=decrease,"
            f"pad={self.export_width}:{self.export_height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"fps={self.fps}"
        )

        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
        self._run_ffmpeg(cmd)
        logger.info(f"Cropped to vertical: {output_path}")
        return output_path

    def crop_to_vertical_smart(
        self,
        video_path: str,
        output_path: str,
        face_positions: Optional[list[tuple]] = None,
    ) -> str:
        """
        Smart crop using face position timeline.
        face_positions: list of (time, x_ratio, y_ratio) tuples
        Falls back to center crop if no face data.
        """
        if not face_positions:
            return self.crop_to_vertical(video_path, output_path)

        # Use average face position for stable cropping
        avg_x = sum(p[1] for p in face_positions) / len(face_positions)
        avg_y = sum(p[2] for p in face_positions) / len(face_positions)

        return self.crop_to_vertical(video_path, output_path, avg_x, avg_y)

    def merge_audio_video(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Replace audio track on a video."""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ]
        self._run_ffmpeg(cmd)
        return output_path

    def _probe_video(self, video_path: str) -> dict:
        """Get video dimensions using ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")

        import json
        data = json.loads(result.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                return {
                    "width": stream["width"],
                    "height": stream["height"],
                    "duration": float(stream.get("duration", 0)),
                    "fps": eval(stream.get("r_frame_rate", "30/1")),
                }
        raise RuntimeError(f"No video stream found in {video_path}")

    def _run_ffmpeg(self, cmd: list):
        """Run an FFmpeg command and raise on failure."""
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg error:\n{result.stderr[-1000:]}")

    async def extract_clip_async(self, *args, **kwargs) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.extract_clip(*args, **kwargs))

    async def crop_to_vertical_async(self, *args, **kwargs) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.crop_to_vertical_smart(*args, **kwargs))
