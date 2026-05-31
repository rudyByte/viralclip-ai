"""
ViralClip AI — Transcription Module
Uses faster-whisper large-v3-turbo for local, fast, accurate transcription.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class TranscriptSegment:
    id: int
    start: float
    end: float
    text: str
    words: list[WordTimestamp]
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0


@dataclass
class Transcript:
    language: str
    duration: float
    segments: list[TranscriptSegment]
    full_text: str

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "duration": self.duration,
            "full_text": self.full_text,
            "segments": [
                {
                    "id": s.id,
                    "start": s.start,
                    "end": s.end,
                    "text": s.text,
                    "words": [
                        {"word": w.word, "start": w.start, "end": w.end, "probability": w.probability}
                        for w in s.words
                    ],
                }
                for s in self.segments
            ],
        }

    def get_chunks_for_analysis(self, chunk_duration: float = 120.0) -> list[dict]:
        """
        Split transcript into chunks for Groq analysis.
        Returns list of {start, end, text} dicts.
        """
        chunks = []
        current_chunk_text = []
        current_chunk_start = 0.0
        current_chunk_end = 0.0

        for seg in self.segments:
            current_chunk_text.append(seg.text.strip())
            current_chunk_end = seg.end

            if seg.end - current_chunk_start >= chunk_duration:
                chunks.append({
                    "start": current_chunk_start,
                    "end": current_chunk_end,
                    "text": " ".join(current_chunk_text),
                })
                current_chunk_text = []
                current_chunk_start = seg.end

        # Last chunk
        if current_chunk_text:
            chunks.append({
                "start": current_chunk_start,
                "end": current_chunk_end,
                "text": " ".join(current_chunk_text),
            })

        return chunks

    def get_words_in_range(self, start: float, end: float) -> list[WordTimestamp]:
        """Get all word timestamps within a time range."""
        words = []
        for seg in self.segments:
            if seg.end < start or seg.start > end:
                continue
            for w in seg.words:
                if start <= w.start <= end:
                    words.append(w)
        return words


class Transcriber:
    _model = None  # Class-level model cache to avoid reloading

    def __init__(self, model_name: str = "large-v3-turbo", device: str = "auto", compute_type: str = "float16"):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type

    def _load_model(self):
        """Load faster-whisper model (cached at class level)."""
        if Transcriber._model is None:
            logger.info(f"Loading faster-whisper model: {self.model_name} on {self.device}")
            from faster_whisper import WhisperModel
            Transcriber._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("Whisper model loaded successfully")
        return Transcriber._model

    def transcribe(
        self,
        audio_path: str,
        progress_callback: Optional[Callable] = None,
    ) -> Transcript:
        """
        Transcribe audio file using faster-whisper.
        Returns Transcript with word-level timestamps.
        """
        model = self._load_model()

        logger.info(f"Starting transcription: {audio_path}")

        segments_raw, info = model.transcribe(
            audio_path,
            word_timestamps=True,
            beam_size=5,
            language=None,  # auto-detect
            condition_on_previous_text=True,
            vad_filter=True,                # Filter silence
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        segments = []
        full_text_parts = []

        for i, seg in enumerate(segments_raw):
            words = []
            if seg.words:
                for w in seg.words:
                    words.append(WordTimestamp(
                        word=w.word,
                        start=w.start,
                        end=w.end,
                        probability=w.probability,
                    ))

            segment = TranscriptSegment(
                id=i,
                start=seg.start,
                end=seg.end,
                text=seg.text,
                words=words,
                avg_logprob=seg.avg_logprob,
                no_speech_prob=seg.no_speech_prob,
            )
            segments.append(segment)
            full_text_parts.append(seg.text.strip())

            if progress_callback and segments:
                # Approximate progress
                pct = min(int((seg.end / info.duration) * 100), 99)
                progress_callback(pct)

        transcript = Transcript(
            language=info.language,
            duration=info.duration,
            segments=segments,
            full_text=" ".join(full_text_parts),
        )

        logger.info(f"Transcription complete: {len(segments)} segments, lang={info.language}")
        return transcript

    def save_transcript(self, transcript: Transcript, path: str):
        """Save transcript to JSON file."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(transcript.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load_transcript(path: str) -> Transcript:
        """Load transcript from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        segments = []
        for s in data["segments"]:
            words = [
                WordTimestamp(w["word"], w["start"], w["end"], w.get("probability", 1.0))
                for w in s.get("words", [])
            ]
            segments.append(TranscriptSegment(
                id=s["id"], start=s["start"], end=s["end"],
                text=s["text"], words=words,
            ))

        return Transcript(
            language=data["language"],
            duration=data["duration"],
            segments=segments,
            full_text=data["full_text"],
        )

    async def transcribe_async(
        self,
        audio_path: str,
        progress_callback: Optional[Callable] = None,
    ) -> Transcript:
        """Async wrapper for transcribe."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.transcribe(audio_path, progress_callback)
        )
