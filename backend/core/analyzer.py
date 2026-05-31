"""
ViralClip AI — Groq LLM Analyzer
Detects viral moments from transcript using llama-3.3-70b-versatile.
"""
import json
import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional
from groq import Groq, AsyncGroq

logger = logging.getLogger(__name__)

VIRAL_DETECTION_PROMPT = """You are a viral short-form content strategist with 10 years of experience creating YouTube Shorts, TikToks, and Instagram Reels that rack up millions of views.

Analyze the transcript below and identify the TOP {num_clips} most viral-worthy moments.

Score each moment across these dimensions (0–10 each):
- curiosity_hook: Does it make viewers desperate to know what comes next?
- emotional_intensity: Fear, excitement, inspiration, anger, joy, or surprise?
- controversy: Does it challenge a popular belief or spark debate?
- storytelling: Clear setup → conflict → resolution arc present?
- novelty: Is the info surprising, counterintuitive, or rarely known?
- retention: Would a viewer watch the full clip without scrolling away?
- audience_hook: Does it directly address a specific audience's pain or desire?
- educational_value: Does it teach something genuinely useful or insightful?

IMPORTANT RULES:
- Each clip must be {min_duration}–{max_duration} seconds long (based on timestamps)
- Never cut mid-sentence — find natural break points
- The first 3 words of each clip must immediately hook the viewer
- Prioritize moments with emotional peaks, surprising reveals, or strong hooks
- Sort results by overall score descending

TRANSCRIPT:
{transcript}

Return ONLY a valid JSON array — no markdown fences, no explanation, no commentary:
[
  {{
    "start_time": <float seconds>,
    "end_time": <float seconds>,
    "score": <integer 0-100>,
    "reason": "<one compelling sentence explaining viral potential>",
    "hook_words": "<first 5-7 words that open this clip>",
    "scores": {{
      "curiosity_hook": <0-10>,
      "emotional_intensity": <0-10>,
      "controversy": <0-10>,
      "storytelling": <0-10>,
      "novelty": <0-10>,
      "retention": <0-10>,
      "audience_hook": <0-10>,
      "educational_value": <0-10>
    }}
  }}
]"""

HOOK_GENERATOR_PROMPT = """You are a viral content copywriter who specializes in YouTube Shorts, TikTok, and Instagram Reels.

Given this transcript excerpt from a short video clip, generate compelling content hooks.

TRANSCRIPT:
{transcript}

TOPIC/CONTEXT: {context}

Generate the following in JSON format:
{{
  "titles": [
    "<YouTube Short title 1 — max 60 chars, curiosity-driven>",
    "<YouTube Short title 2 — controversy angle>",
    "<YouTube Short title 3 — value/benefit angle>"
  ],
  "hooks": [
    "<TikTok opening hook 1 — starts with action verb>",
    "<TikTok opening hook 2 — starts with a number or stat>",
    "<TikTok opening hook 3 — starts with a question>"
  ],
  "captions": [
    "<Instagram caption 1 with emojis>",
    "<Instagram caption 2 — storytelling format>"
  ],
  "hashtags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>", "<tag6>", "<tag7>", "<tag8>"],
  "thumbnail_text": "<Bold 3-5 word thumbnail text — UPPERCASE format>"
}}

Return ONLY valid JSON — no markdown, no explanation."""


@dataclass
class ViralMoment:
    start_time: float
    end_time: float
    score: int
    reason: str
    hook_words: str = ""
    scores: dict = None

    def __post_init__(self):
        if self.scores is None:
            self.scores = {}

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class HookContent:
    titles: list[str]
    hooks: list[str]
    captions: list[str]
    hashtags: list[str]
    thumbnail_text: str


class GroqAnalyzer:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.client = AsyncGroq(api_key=api_key)

    def _clean_json_response(self, text: str) -> str:
        """Strip markdown fences and extract JSON from LLM response."""
        # Remove ```json ... ``` or ``` ... ```
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        # Find first [ or { to start of JSON
        for i, ch in enumerate(text):
            if ch in ("[", "{"):
                text = text[i:]
                break

        # Find last ] or } to end of JSON
        for i in range(len(text) - 1, -1, -1):
            if text[i] in ("]", "}"):
                text = text[:i + 1]
                break

        return text

    async def detect_viral_moments(
        self,
        transcript_chunks: list[dict],
        num_clips: int = 5,
        min_duration: int = 30,
        max_duration: int = 60,
    ) -> list[ViralMoment]:
        """
        Send transcript chunks to Groq and extract viral moments.
        Handles long videos by processing in chunks and merging results.
        """
        all_moments = []

        # Build full transcript text with timestamps for context
        full_transcript = ""
        for chunk in transcript_chunks:
            start_min = int(chunk["start"]) // 60
            start_sec = int(chunk["start"]) % 60
            full_transcript += f"\n[{start_min:02d}:{start_sec:02d}] {chunk['text']}"

        # For long transcripts, process in batches
        max_chars = 12000  # ~3k tokens, safe for llama-3.3-70b context
        batches = self._split_transcript_into_batches(transcript_chunks, max_chars)
        clips_per_batch = max(2, num_clips // len(batches) + 1)

        for batch_idx, batch in enumerate(batches):
            batch_text = "\n".join(
                f"[{int(c['start'])//60:02d}:{int(c['start'])%60:02d}] {c['text']}"
                for c in batch
            )

            prompt = VIRAL_DETECTION_PROMPT.format(
                num_clips=clips_per_batch,
                min_duration=min_duration,
                max_duration=max_duration,
                transcript=batch_text,
            )

            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=4096,
                )

                raw = response.choices[0].message.content
                clean = self._clean_json_response(raw)
                moments_data = json.loads(clean)

                for m in moments_data:
                    moment = ViralMoment(
                        start_time=float(m.get("start_time", 0)),
                        end_time=float(m.get("end_time", 0)),
                        score=int(m.get("score", 0)),
                        reason=m.get("reason", ""),
                        hook_words=m.get("hook_words", ""),
                        scores=m.get("scores", {}),
                    )
                    if moment.duration >= min_duration and moment.score > 0:
                        all_moments.append(moment)

                logger.info(f"Batch {batch_idx + 1}/{len(batches)}: found {len(moments_data)} moments")

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to parse Groq response: {e}\nRaw: {raw[:500]}")
                continue

        # Sort by score, deduplicate overlapping clips, take top N
        all_moments.sort(key=lambda m: m.score, reverse=True)
        final_moments = self._deduplicate_moments(all_moments)
        return final_moments[:num_clips]

    def _split_transcript_into_batches(
        self,
        chunks: list[dict],
        max_chars: int,
    ) -> list[list[dict]]:
        """Split transcript chunks into batches under max_chars."""
        batches = []
        current_batch = []
        current_len = 0

        for chunk in chunks:
            chunk_len = len(chunk["text"])
            if current_len + chunk_len > max_chars and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_len = 0
            current_batch.append(chunk)
            current_len += chunk_len

        if current_batch:
            batches.append(current_batch)

        return batches if batches else [chunks]

    def _deduplicate_moments(self, moments: list[ViralMoment]) -> list[ViralMoment]:
        """Remove overlapping moments, keeping the highest scored one."""
        if not moments:
            return []

        result = [moments[0]]
        for candidate in moments[1:]:
            overlaps = False
            for kept in result:
                overlap_start = max(candidate.start_time, kept.start_time)
                overlap_end = min(candidate.end_time, kept.end_time)
                if overlap_end > overlap_start:  # They overlap
                    overlaps = True
                    break
            if not overlaps:
                result.append(candidate)

        return result

    async def generate_hooks(
        self,
        transcript_text: str,
        context: str = "",
    ) -> HookContent:
        """Generate viral titles, hooks, captions, and hashtags for a clip."""
        prompt = HOOK_GENERATOR_PROMPT.format(
            transcript=transcript_text[:3000],
            context=context,
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024,
        )

        raw = response.choices[0].message.content
        clean = self._clean_json_response(raw)

        try:
            data = json.loads(clean)
            return HookContent(
                titles=data.get("titles", []),
                hooks=data.get("hooks", []),
                captions=data.get("captions", []),
                hashtags=data.get("hashtags", []),
                thumbnail_text=data.get("thumbnail_text", ""),
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse hook response: {e}")
            return HookContent([], [], [], [], "")
