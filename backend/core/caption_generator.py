"""
ViralClip AI — Caption Generator
Generates word-level animated subtitles in multiple viral styles using ASS format.
"""
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass
from core.transcriber import WordTimestamp
import subprocess

logger = logging.getLogger(__name__)


@dataclass
class CaptionStyle:
    name: str
    font_name: str
    font_size: int
    primary_color: str       # ASS color &HBBGGRR&
    highlight_color: str     # Color when word is spoken
    outline_color: str
    shadow_color: str
    bold: bool
    outline_size: int
    shadow_size: int
    margin_v: int            # Vertical margin from bottom
    words_per_line: int
    all_caps: bool


CAPTION_STYLES = {
    "hormozi": CaptionStyle(
        name="hormozi",
        font_name="Impact",
        font_size=72,
        primary_color="&H00FFFFFF&",
        highlight_color="&H0000FFFF&",   # Yellow
        outline_color="&H00000000&",
        shadow_color="&H80000000&",
        bold=True,
        outline_size=4,
        shadow_size=3,
        margin_v=280,
        words_per_line=3,
        all_caps=True,
    ),
    "gadzhi": CaptionStyle(
        name="gadzhi",
        font_name="Montserrat",
        font_size=68,
        primary_color="&H00FFFFFF&",
        highlight_color="&H000066FF&",   # Orange
        outline_color="&H00000000&",
        shadow_color="&H90000000&",
        bold=True,
        outline_size=3,
        shadow_size=2,
        margin_v=260,
        words_per_line=4,
        all_caps=True,
    ),
    "ali_abdaal": CaptionStyle(
        name="ali_abdaal",
        font_name="Arial",
        font_size=60,
        primary_color="&H00FFFFFF&",
        highlight_color="&H0000A5FF&",   # Gold
        outline_color="&H00000000&",
        shadow_color="&H70000000&",
        bold=False,
        outline_size=2,
        shadow_size=2,
        margin_v=300,
        words_per_line=5,
        all_caps=False,
    ),
    "mrbeast": CaptionStyle(
        name="mrbeast",
        font_name="Impact",
        font_size=80,
        primary_color="&H00FFFF00&",    # Bright yellow
        highlight_color="&H000000FF&",   # Red
        outline_color="&H00000000&",
        shadow_color="&H99000000&",
        bold=True,
        outline_size=5,
        shadow_size=4,
        margin_v=250,
        words_per_line=3,
        all_caps=True,
    ),
    "minimal": CaptionStyle(
        name="minimal",
        font_name="Inter",
        font_size=56,
        primary_color="&H00FFFFFF&",
        highlight_color="&H00AAAAFF&",
        outline_color="&H00111111&",
        shadow_color="&H50000000&",
        bold=False,
        outline_size=2,
        shadow_size=1,
        margin_v=320,
        words_per_line=6,
        all_caps=False,
    ),
}


class CaptionGenerator:
    def __init__(self, output_dir: str, video_width: int = 1080, video_height: int = 1920):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.video_width = video_width
        self.video_height = video_height

    def generate_ass_file(
        self,
        words: list[WordTimestamp],
        output_path: str,
        style_name: str = "hormozi",
        clip_start_offset: float = 0.0,
    ) -> str:
        """
        Generate an ASS subtitle file with word-level highlighting.
        clip_start_offset: subtract this from timestamps (for clipped segments).
        """
        style = CAPTION_STYLES.get(style_name, CAPTION_STYLES["hormozi"])

        ass_content = self._build_ass_header(style)
        ass_content += "\n[Events]\n"
        ass_content += "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

        # Group words into lines
        lines = self._group_words_into_lines(words, style.words_per_line)

        for line_words in lines:
            if not line_words:
                continue

            line_start = max(0.0, line_words[0].start - clip_start_offset)
            line_end = max(line_start + 0.1, line_words[-1].end - clip_start_offset)

            # Build text with karaoke word timing tags
            text_parts = []
            for w in line_words:
                w_start = max(0.0, w.start - clip_start_offset)
                w_end = max(w_start + 0.05, w.end - clip_start_offset)
                word_duration_cs = int((w_end - w_start) * 100)  # centiseconds

                word_text = w.word.upper() if style.all_caps else w.word

                # {\\kf<duration>} = karaoke fill (highlight sweeps across word)
                text_parts.append(f"{{\\kf{word_duration_cs}}}{word_text.strip()}")

            line_text = " ".join(text_parts)

            start_str = self._seconds_to_ass(line_start)
            end_str = self._seconds_to_ass(line_end)

            ass_content += (
                f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,"
                f"{line_text}\n"
            )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        return output_path

    def burn_captions(
        self,
        video_path: str,
        ass_path: str,
        output_path: str,
    ) -> str:
        """Burn ASS captions into video using FFmpeg."""
        # Escape path for FFmpeg filter
        safe_ass = ass_path.replace("\\", "/").replace(":", "\\:")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"ass='{safe_ass}'",
            "-c:v", "libx264", "-preset", "fast", "-crf", "16",
            "-c:a", "copy",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Caption burn failed: {result.stderr[-500:]}")

        logger.info(f"Captions burned into: {output_path}")
        return output_path

    def _group_words_into_lines(
        self,
        words: list[WordTimestamp],
        words_per_line: int,
    ) -> list[list[WordTimestamp]]:
        """Group words into display lines with natural timing gaps."""
        if not words:
            return []

        lines = []
        current_line = []

        for i, word in enumerate(words):
            current_line.append(word)

            # Break line if: max words reached OR long pause (>0.8s)
            is_last = i == len(words) - 1
            next_gap = (words[i + 1].start - word.end) if not is_last else 0

            if len(current_line) >= words_per_line or next_gap > 0.8 or is_last:
                lines.append(current_line)
                current_line = []

        return lines

    def _build_ass_header(self, style: CaptionStyle) -> str:
        bold_val = -1 if style.bold else 0
        return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {self.video_width}
PlayResY: {self.video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{style.font_size},{style.primary_color},{style.highlight_color},{style.outline_color},{style.shadow_color},{bold_val},0,0,0,100,100,0,0,1,{style.outline_size},{style.shadow_size},2,20,20,{style.margin_v},1
"""

    def _seconds_to_ass(self, seconds: float) -> str:
        """Convert seconds to ASS timestamp format H:MM:SS.cc"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    async def generate_ass_file_async(self, *args, **kwargs) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.generate_ass_file(*args, **kwargs))

    async def burn_captions_async(self, *args, **kwargs) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: self.burn_captions(*args, **kwargs))
