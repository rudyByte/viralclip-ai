"""
ViralClip AI — Background Mixer
Overlays gaming footage (bottom half) under the main clip (top half).
Final output: 1080x1920 (9:16) split-screen vertical video.
"""
import subprocess
import asyncio
import logging
import random
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BACKGROUND_TYPES = ["subway", "minecraft", "gta", "templerun", "none"]


class BackgroundMixer:
    def __init__(self, assets_dir: str, export_width: int = 1080, export_height: int = 1920):
        self.assets_dir = Path(assets_dir)
        self.export_width = export_width
        self.export_height = export_height
        self.half_height = export_height // 2  # 960px each half

    def mix_with_background(
        self,
        clip_path: str,
        output_path: str,
        background_type: str = "subway",
        clip_volume: float = 1.0,
        gameplay_volume: float = 0.15,
        layout_template: str = "split_50_50",
    ) -> str:
        """
        Create split-screen: main clip (top) + gameplay (bottom).
        If no gameplay footage found, uses animated gradient background.
        """
        if background_type == "none" or layout_template == "no_gameplay":
            return self._add_plain_background(clip_path, output_path)

        gameplay_path = self._get_gameplay_clip(background_type)

        if gameplay_path is None:
            logger.warning(f"No gameplay footage found for '{background_type}', using gradient")
            return self._add_gradient_background(clip_path, output_path)

        # Get main clip duration
        clip_duration = self._get_duration(clip_path)

        # Determine main video height (main_h) and gameplay video height (gameplay_h)
        if layout_template == "split_60_40":
            main_h = 1152
            gameplay_h = 768
        elif layout_template == "split_70_30":
            main_h = 1344
            gameplay_h = 576
        else:  # split_50_50 or default
            main_h = 960
            gameplay_h = 960

        return self._stack_videos(
            clip_path=clip_path,
            gameplay_path=gameplay_path,
            output_path=output_path,
            clip_duration=clip_duration,
            clip_volume=clip_volume,
            gameplay_volume=gameplay_volume,
            main_h=main_h,
            gameplay_h=gameplay_h,
        )

    def _has_audio(self, video_path: str) -> bool:
        """Check if a video file has an audio stream."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_streams",
            "-select_streams", "a",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return "codec_type=audio" in result.stdout

    def _stack_videos(
        self,
        clip_path: str,
        gameplay_path: str,
        output_path: str,
        clip_duration: float,
        clip_volume: float,
        gameplay_volume: float,
        main_h: int = 960,
        gameplay_h: int = 960,
    ) -> str:
        """
        Stack main clip (top main_h) + gameplay (bottom gameplay_h).
        Loops gameplay if shorter than clip. Trims if longer.
        """
        w = self.export_width
        has_gameplay_audio = self._has_audio(gameplay_path)
        has_main_audio = self._has_audio(clip_path)

        # Filter complex:
        # [0:v] → scale directly to top portion (1080xmain_h) since it’s pre-cropped
        # [1:v] → scale and crop-to-fill bottom portion (1080xgameplay_h)
        # Stack vertically → 1080x1920
        # Mix audio: clip at full vol, gameplay muted/low if gameplay has audio

        if has_gameplay_audio and has_main_audio:
            filter_complex = (
                f"[0:v]scale={w}:{main_h}[top];"

                f"[1:v]scale={w}:{gameplay_h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{gameplay_h},"
                f"trim=duration={clip_duration},setpts=PTS-STARTPTS[bot];"

                f"[top][bot]vstack=inputs=2[v];"

                f"[0:a]volume={clip_volume}[main_a];"
                f"[1:a]volume={gameplay_volume}[game_a];"
                f"[main_a][game_a]amix=inputs=2:normalize=0[a]"
            )
            map_audio = "[a]"
        elif has_main_audio:
            # Gameplay has no audio — just mix gameplay visuals with clip audio only
            filter_complex = (
                f"[0:v]scale={w}:{main_h}[top];"

                f"[1:v]scale={w}:{gameplay_h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{gameplay_h},"
                f"trim=duration={clip_duration},setpts=PTS-STARTPTS[bot];"

                f"[top][bot]vstack=inputs=2[v]"
            )
            map_audio = "0:a"
        else:
            # Neither has audio — add silent track
            filter_complex = (
                f"[0:v]scale={w}:{main_h}[top];"

                f"[1:v]scale={w}:{gameplay_h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{gameplay_h},"
                f"trim=duration={clip_duration},setpts=PTS-STARTPTS[bot];"

                f"[top][bot]vstack=inputs=2[v];"

                f"anullsrc=r=44100:cl=stereo[a]"
            )
            map_audio = "[a]"

        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-stream_loop", "-1", "-i", gameplay_path,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", map_audio,
            "-t", str(clip_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Background mix failed: {result.stderr[-500:]}")
            # Fall back to plain background
            return self._add_plain_background(clip_path, output_path)

        logger.info(f"Background mixed (template heights: {main_h}/{gameplay_h}): {output_path}")
        return output_path

    def _add_plain_background(self, clip_path: str, output_path: str) -> str:
        """Simple scale to full 1080x1920 with black bars."""
        w = self.export_width
        h = self.export_height

        cmd = [
            "ffmpeg", "-y", "-i", clip_path,
            "-vf", (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Plain background fallback failed: {result.stderr[-500:]}")
            raise RuntimeError(f"FFmpeg plain background failed: {result.stderr[-300:]}")
        return output_path

    def _add_gradient_background(self, clip_path: str, output_path: str) -> str:
        """Add animated gradient background behind clip (no gameplay footage needed)."""
        w = self.export_width
        h = self.export_height
        clip_duration = self._get_duration(clip_path)

        # Generate purple-to-blue gradient background
        filter_complex = (
            f"color=c=0x0f0c29:size={w}x{h}:rate=30[bg];"
            f"[0:v]scale={w}:{int(h*0.55)}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{int(h*0.55)}:(ow-iw)/2:(oh-ih)/2:black@0[clip];"
            f"[bg][clip]overlay=(W-w)/2:0[v]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", clip_path,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "0:a",
            "-t", str(clip_duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return self._add_plain_background(clip_path, output_path)
        return output_path

    def _get_gameplay_clip(self, background_type: str) -> Optional[str]:
        """Get a random gameplay clip from the assets folder."""
        gameplay_dir = self.assets_dir / "gameplay" / background_type
        if not gameplay_dir.exists():
            return None

        clips = list(gameplay_dir.glob("*.mp4")) + list(gameplay_dir.glob("*.mov"))
        if not clips:
            return None

        return str(random.choice(clips))

    def _get_duration(self, video_path: str) -> float:
        """Get video duration in seconds."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except (ValueError, AttributeError):
            return 60.0

    async def mix_with_background_async(self, *args, **kwargs) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.mix_with_background(*args, **kwargs))
