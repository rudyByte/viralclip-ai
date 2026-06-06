import logging
import re
from urllib.parse import urlparse, parse_qs

from core.transcriber import Transcript, TranscriptSegment, WordTimestamp

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/")[0]
        if video_id:
            return video_id
    query_id = parse_qs(parsed.query).get("v", [None])[0]
    if query_id:
        return query_id
    match = re.search(r"(?:shorts|embed|live)/([0-9A-Za-z_-]{11})", url)
    if match:
        return match.group(1)
    match = re.search(r"([0-9A-Za-z_-]{11})", url)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot extract video ID from URL: {url}")


def _segments_to_transcript(items: list[dict], language: str = "unknown") -> Transcript:
    segments = []
    full_text = []
    for idx, item in enumerate(items):
        start = float(item.get("start", 0.0))
        duration = float(item.get("duration", 0.0))
        end = start + max(duration, 0.1)
        text = (item.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        words_raw = text.split()
        word_count = max(len(words_raw), 1)
        word_duration = max((end - start) / word_count, 0.05)
        words = [
            WordTimestamp(
                word=word,
                start=start + (i * word_duration),
                end=min(end, start + ((i + 1) * word_duration)),
                probability=1.0,
            )
            for i, word in enumerate(words_raw)
        ]
        segments.append(TranscriptSegment(id=idx, start=start, end=end, text=text, words=words))
        full_text.append(text)
    total_duration = segments[-1].end if segments else 0.0
    return Transcript(language=language, duration=total_duration, segments=segments, full_text=" ".join(full_text))


def get_youtube_transcript(video_id: str) -> Transcript | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
    except Exception as exc:
        logger.warning(f"youtube-transcript-api unavailable: {exc}")
        return None

    languages = ["en", "hi", "gu"]
    try:
        items = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        return _segments_to_transcript(items, language=",".join(languages))
    except (NoTranscriptFound, TranscriptsDisabled):
        pass
    except Exception as exc:
        logger.warning(f"Manual transcript fetch failed for {video_id}: {exc}")

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        for lang in languages:
            try:
                transcript = transcript_list.find_generated_transcript([lang])
                return _segments_to_transcript(transcript.fetch(), language=lang)
            except Exception:
                continue
        for transcript in transcript_list:
            return _segments_to_transcript(transcript.fetch(), language=getattr(transcript, "language_code", "unknown"))
    except Exception as exc:
        logger.warning(f"No YouTube transcript available for {video_id}: {exc}")

    return None


async def get_youtube_transcript_async(video_id: str) -> Transcript | None:
    import asyncio
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: get_youtube_transcript(video_id))
