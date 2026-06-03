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
VIRAL_DETECTION_PROMPT = """You are a viral video editor and content strategist. 
Identify the top {num_clips} viral segments in the transcript below.

CRITICAL REQUIREMENTS:
1. Target Duration: Each segment must be strictly between {min_duration} and {max_duration} seconds long (duration = end_time - start_time).
2. Hook/Start: The start_time must mark a strong hook or the beginning of an interesting idea.
3. Logical Ending: The end_time must be a logical cut-off point (e.g., at the end of a sentence, a punchline, or a completed thought). Do not cut off mid-phrase, mid-sentence, or in a way that leaves the viewer hanging without context.
4. Timestamps: Return start_time and end_time as raw float seconds from the transcript timestamps.
5. Multilingual support: The transcript might be in English, Hindi, Gujarati, or any other language. Analyze it carefully to find the best viral segments. The reason must be in English, but hook_words should be in the original language.

TRANSCRIPT:
{transcript}

Return ONLY a JSON array, no markdown:
[{{"start_time":<float>,"end_time":<float>,"score":<int 0-100>,"reason":"<one sentence explanation of why this moment goes viral>","hook_words":"<first 5 words of the hook>","scores":{{"curiosity_hook":<int 0-10>,"emotional_intensity":<int 0-10>,"controversy":<int 0-10>,"storytelling":<int 0-10>,"novelty":<int 0-10>,"retention":<int 0-10>,"audience_hook":<int 0-10>,"educational_value":<int 0-10>}}}}]"""


def adjust_clip_boundaries(
    start_time: float,
    end_time: float,
    transcript_words: list,
    min_duration: float,
    max_duration: float,
) -> tuple[float, float]:
    """
    Align start_time and end_time to actual word boundaries.
    Search backwards from start_time + max_duration for a logical sentence or pause gap boundary.
    """
    if not transcript_words:
        return start_time, min(end_time, start_time + max_duration)

    # Filter words to get a sorted list of timestamps
    # Word timestamps might have dict form (if loaded from json) or object form
    words = []
    for w in transcript_words:
        if hasattr(w, "start"):
            words.append((w.start, w.end, w.word))
        else:
            words.append((w.get("start", 0.0), w.get("end", 0.0), w.get("word", "")))
            
    words.sort(key=lambda x: x[0])
    
    if not words:
        return start_time, min(end_time, start_time + max_duration)

    # 1. Find first word that starts at or after start_time (or closest to it)
    start_idx = 0
    min_diff = float("inf")
    for idx, (w_start, w_end, w_word) in enumerate(words):
        diff = abs(w_start - start_time)
        if diff < min_diff:
            min_diff = diff
            start_idx = idx

    actual_start = words[start_idx][0]
    
    # 2. Collect candidate end words within [actual_start + min_duration, actual_start + max_duration]
    valid_end_words = []
    for idx in range(start_idx, len(words)):
        w_start, w_end, w_word = words[idx]
        dur = w_end - actual_start
        if dur > max_duration:
            break
        if dur >= min_duration:
            valid_end_words.append((idx, w_start, w_end, w_word))

    if not valid_end_words:
        # Fallback: if no word falls in [min_duration, max_duration], just find the last word that keeps it under max_duration
        fallback_end = actual_start + max_duration
        for idx in range(start_idx, len(words)):
            w_start, w_end, w_word = words[idx]
            if w_end - actual_start > max_duration:
                break
            fallback_end = w_end
        return actual_start, fallback_end

    # 3. Look for a logical ending word (punctuation or pause)
    # Search backwards from the end of valid_end_words to find the latest logical point
    best_end = None
    for idx_in_valid, (original_idx, w_start, w_end, w_word) in enumerate(reversed(valid_end_words)):
        clean_word = w_word.strip()
        
        # Check punctuation ending
        ends_with_punc = clean_word and clean_word[-1] in (".", "?", "!", ",", ";", ":", "।")
        
        # Check spoken pause (silence to next word > 0.4s)
        has_pause = False
        if original_idx < len(words) - 1:
            next_start = words[original_idx + 1][0]
            if next_start - w_end > 0.4:
                has_pause = True
                
        if ends_with_punc or has_pause:
            best_end = w_end
            break

    if best_end is not None:
        return actual_start, best_end
    else:
        # If no logical end found, use the last valid word
        return actual_start, valid_end_words[-1][2]

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

    async def _call_groq_with_retry(
        self,
        model: str,
        messages: list,
        temperature: float,
        max_tokens: int,
        retries: int = 5,
    ) -> str:
        """Call Groq API with exponential backoff on rate limits or payload errors."""
        delay = 5.0
        for attempt in range(retries):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                is_rate_limit = any(
                    term in err_str.lower()
                    for term in ["rate_limit_exceeded", "429", "413", "payload too large", "too many requests", "limit exceeded"]
                )
                
                if is_rate_limit and attempt < retries - 1:
                    logger.warning(
                        f"Groq API rate limit or payload size issue on {model} (Attempt {attempt + 1}/{retries}): {err_str}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= 2.0
                else:
                    logger.error(f"Groq API call failed permanently on attempt {attempt + 1}: {e}")
                    raise
        raise RuntimeError("Failed to get response from Groq API after maximum retries.")

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

        # Reduced to 5000 chars to stay safely within Groq TPM limits
        max_chars = 5000
        batches = self._split_transcript_into_batches(transcript_chunks, max_chars)
        clips_per_batch = max(2, num_clips // len(batches) + 1)

        logger.info(f"Analyzing {len(batches)} batches with {self.detection_model} for {clips_per_batch} clips/batch")

        for batch_idx, batch in enumerate(batches):
            if batch_idx > 0:
                logger.info("Sleeping for 2.0 seconds between batches to avoid Groq rate limit bursting...")
                await asyncio.sleep(2.0)

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
                raw = await self._call_groq_with_retry(
                    model=self.detection_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,
                )

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
                    if min_duration <= moment.duration <= (max_duration + 30) and moment.score > 0:
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
            raw = await self._call_groq_with_retry(
                model=self.hook_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=512,
            )
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
