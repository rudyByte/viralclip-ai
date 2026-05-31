"""
ViralClip AI — Database Models (SQLAlchemy + SQLite)
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from datetime import datetime
import uuid
import os


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./viralclip.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    youtube_url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    channel = Column(String, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    status = Column(String, default="queued")  # queued|downloading|transcribing|analyzing|clipping|done|error
    progress = Column(Integer, default=0)
    current_step = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    video_path = Column(String, nullable=True)
    audio_path = Column(String, nullable=True)
    transcript_path = Column(String, nullable=True)

    # Settings used for this job
    clip_min_duration = Column(Integer, default=30)
    clip_max_duration = Column(Integer, default=60)
    num_clips = Column(Integer, default=5)
    caption_style = Column(String, default="hormozi")
    background_type = Column(String, default="subway")

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class Clip(Base):
    __tablename__ = "clips"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, nullable=False)
    clip_index = Column(Integer, default=0)

    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=True)

    virality_score = Column(Integer, default=0)
    reason = Column(Text, nullable=True)

    # Score breakdown
    score_curiosity = Column(Float, default=0)
    score_emotion = Column(Float, default=0)
    score_controversy = Column(Float, default=0)
    score_storytelling = Column(Float, default=0)
    score_novelty = Column(Float, default=0)
    score_retention = Column(Float, default=0)
    score_audience_hook = Column(Float, default=0)
    score_educational = Column(Float, default=0)

    # File paths
    raw_clip_path = Column(String, nullable=True)
    cropped_clip_path = Column(String, nullable=True)
    captioned_clip_path = Column(String, nullable=True)
    export_path = Column(String, nullable=True)

    # Settings
    caption_style = Column(String, default="hormozi")
    background_type = Column(String, default="subway")
    status = Column(String, default="pending")  # pending|processing|done|error

    created_at = Column(DateTime, default=datetime.utcnow)


class Hook(Base):
    __tablename__ = "hooks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    clip_id = Column(String, nullable=False)
    job_id = Column(String, nullable=False)

    title = Column(Text, nullable=True)
    hook = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)  # JSON string
    thumbnail_text = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class AppSettings(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
