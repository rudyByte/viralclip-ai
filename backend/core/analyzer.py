"""
ViralClip AI — Groq LLM Analyzer
Uses llama-3.1-8b-instant for bulk viral detection (500K TPD free tier)
and llama-3.3-70b-versatile only for hook generation.
"""
import json
import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional
from groq import AsyncGroq

logger = logging.getLogger(__name__)

# Compact prompt — ~200 tokens vs ~500 previously
VIRAL_DETECTION_PROMPT = """Viral content strategist. Find TOP {num_clips} viral moments in this transcript.

Timestamps are raw seconds (e.g. 180.50). Return start_time/end_time as raw float seconds.
Each clip: {min_duration}–{max_duration} seconds. Never cut mid-sentence.

Score 0-10: curiosity_hook, emotional_intensity, controversy, storytelling, novelty, retention, audience_hook, educational_value

TRANSCRIPT:
{transcript}

Return ONLY a JSON array, no markdown:
[{{"start_time":<float>,"end_time":<float>,"score":<int 0-100>,"reason":"<one sentence>","hook_words":"<first 5 words>","scores":{{"curiosity_hook":<int>,"emotional_intensity":<int>,"controversy":<int>,"storytelling":<int>,"novelty":<int>,"retention":<int>,"audience_hook":<int>,"educational_value":<int>}}}}]"""

# Compact hook prompt — ~150 tokens vs ~350 previously
HOOK_GENERATOR_PROMPT = """Viral copywriter. Generate hooks for this clip.

TRANSCRIPT: {transcript}
CONTEXT: {context}

Return ONLY JSON:
{{"titles":["<title1>","<title2>","<title3>"],"hooks":["<hook1>","<hook2>","<hook3>"],"captions":["<caption1>","<caption2>"],"hashtags":["<tag1>","<tag2>","<tag3>","<tag4>","<tag5>","<tag6>"],"thumbnail_text":"<3-5 WORDS UPPERCASE>"}}"""


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
    def __init__(
        self,
        api_key: str,
        detection_model: str = "llama-3.1-8b-instant",
        hook_model: str = "llama-3.3-70b-versatile",
    ):
        self.api_key = api_key
        self.detection_model = detection_model
        self.hook_model = hook_model
        self.client = AsyncGroq(api_key=api_key)

    def _clean_json_response(self, text: str) -> str:
        """Strip markdown fences and extract JSON from LLM response."""
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()
        for i, ch in enumerate(text):
            if ch in ("[", "{"):
                text = text[i:]
                break
        for i in range(len(text) - 1, -1, -1):
            if text[i] in ("]", "}"):
                text = text[:i + 1]
                break
        return text

    def _compress_chunk_text(self, text: str, max_chars: int = 3500) -> str:
        """Compress a transcript chunk to reduce token usage."""
        # Collapse multiple spaces/newlines
        text = re.sub(r"\s+", " ", text).strip()
        # Hard truncate if still too long
        return text[:max_chars]

    async def detect_viral_moments(
        self,
        transcript_chunks: list[dict],
        num_clips: int = 5,
        min_duration: int = 30,
        max_duration: int = 60,
    ) -> list[ViralMoment]:
        """
        Detect viral moments using llama-3.1-8b-instant (500K TPD).
        Processes transcript in batches, deduplicates and returns top N.
        """
        all_moments = []

        # Larger batches = fewer API calls = fewer tokens on prompt overhead
        max_chars = 14000
        batches = self._split_transcript_into_batches(transcript_chunks, max_chars)
        clips_per_batch = max(2, num_clips // len(batches) + 1)

        logger.info(f"Analyzing {len(batches)} batches with {self.detection_model} for {clips_per_batch} clips/batch")

        for batch_idx, batch in enumerate(batches):
            batch_text = "\n".join(
                f"[{c['start']:.2f}] {self._compress_chunk_text(c['text'])}"
                for c in batch
            )

            prompt = VIRAL_DETECTION_PROMPT.format(
                num_clips=clips_per_batch,
                min_duration=min_duration,
                max_duration=max_duration,
                transcript=batch_text,
            )

            raw = ""
            try:
                response = await self.client.chat.completions.create(
                    model=self.detection_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,  # Was 4096 — JSON for 3 clips needs <500 tokens
                )

                raw = response.choices[0].message.content
                clean = self._clean_json_response(raw)
                moments_data = json.loads(clean)

                batch_valid = 0
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
                        batch_valid += 1

                logger.info(f"Batch {batch_idx + 1}/{len(batches)}: {batch_valid} valid moments")

            except (json.JSONDecodeError, KeyError, Exception) as e:
                logger.error(f"Batch {batch_idx + 1} failed: {e} | Raw: {raw[:300]}")
                continue

        # Sort, deduplicate overlapping clips, return top N
        all_moments.sort(key=lambda m: m.score, reverse=True)
        final = self._deduplicate_moments(all_moments)
        logger.info(f"Final viral moments after dedup: {len(final[:num_clips])}")
        return final[:num_clips]

    def _split_transcript_into_batches(
        self,
        chunks: list[dict],
        max_chars: int,
    ) -> list[list[dict]]:
        """Split transcript chunks into batches under max_chars."""
        batches, current_batch, current_len = [], [], 0
        for chunk in chunks:
            chunk_len = len(chunk["text"])
            if current_len + chunk_len > max_chars and current_batch:
                batches.append(current_batch)
                current_batch, current_len = [], 0
            current_batch.append(chunk)
            current_len += chunk_len
        if current_batch:
            batches.append(current_batch)
        return batches if batches else [chunks]

    def _deduplicate_moments(self, moments: list[ViralMoment]) -> list[ViralMoment]:
        """Remove overlapping moments, keeping highest scored."""
        if not moments:
            return []
        result = [moments[0]]
        for candidate in moments[1:]:
            overlaps = any(
                min(candidate.end_time, kept.end_time) > max(candidate.start_time, kept.start_time)
                for kept in result
            )
            if not overlaps:
                result.append(candidate)
        return result

    async def generate_hooks(
        self,
        transcript_text: str,
        context: str = "",
    ) -> HookContent:
        """Generate viral hooks using llama-3.3-70b-versatile (quality copywriting)."""
        prompt = HOOK_GENERATOR_PROMPT.format(
            transcript=transcript_text[:2000],  # Reduced from 3000
            context=context[:200],
        )

        raw = ""
        try:
            response = await self.client.chat.completions.create(
                model=self.hook_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=512,  # Was 1024
            )
            raw = response.choices[0].message.content
            clean = self._clean_json_response(raw)
            data = json.loads(clean)
            return HookContent(
                titles=data.get("titles", []),
                hooks=data.get("hooks", []),
                captions=data.get("captions", []),
                hashtags=data.get("hashtags", []),
                thumbnail_text=data.get("thumbnail_text", ""),
            )
        except Exception as e:
            logger.error(f"Hook generation failed: {e} | Raw: {raw[:200]}")
            return HookContent([], [], [], [], "")
