"""
ViralClip AI — Database Models (SQLAlchemy + SQLite)
"""
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean, text
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
    layout_template = Column(String, default="split_50_50")
    resolution = Column(String, default="1080p")
    cookies = Column(Text, nullable=True)

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
    layout_template = Column(String, default="split_50_50")
    status = Column(String, default="pending")  # pending|processing|done|error

    # Platform-ready publishing metadata
    youtube_title = Column(Text, nullable=True)
    youtube_description = Column(Text, nullable=True)
    instagram_caption = Column(Text, nullable=True)
    hook_score = Column(Integer, nullable=True)

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
    """Initialize database tables and add missing columns for backward compatibility."""
    import logging
    db_logger = logging.getLogger("database")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    # Dynamically check and add missing columns if they don't exist
    async with AsyncSessionLocal() as session:
        # Check jobs table for layout_template
        try:
            await session.execute(text("SELECT layout_template FROM jobs LIMIT 1"))
        except Exception:
            await session.rollback()
            try:
                await session.execute(text("ALTER TABLE jobs ADD COLUMN layout_template VARCHAR DEFAULT 'split_50_50'"))
                await session.commit()
                db_logger.info("Added column 'layout_template' to 'jobs' table.")
            except Exception as e:
                db_logger.error(f"Failed to add 'layout_template' to 'jobs': {e}")
                await session.rollback()

        # Check jobs table for resolution
        try:
            await session.execute(text("SELECT resolution FROM jobs LIMIT 1"))
        except Exception:
            await session.rollback()
            try:
                await session.execute(text("ALTER TABLE jobs ADD COLUMN resolution VARCHAR DEFAULT '1080p'"))
                await session.commit()
                db_logger.info("Added column 'resolution' to 'jobs' table.")
            except Exception as e:
                db_logger.error(f"Failed to add 'resolution' to 'jobs': {e}")
                await session.rollback()

        # Check jobs table for cookies
        try:
            await session.execute(text("SELECT cookies FROM jobs LIMIT 1"))
        except Exception:
            await session.rollback()
            try:
                await session.execute(text("ALTER TABLE jobs ADD COLUMN cookies TEXT"))
                await session.commit()
                db_logger.info("Added column 'cookies' to 'jobs' table.")
            except Exception as e:
                db_logger.error(f"Failed to add 'cookies' to 'jobs': {e}")
                await session.rollback()

        # Check clips table for layout_template
        try:
            await session.execute(text("SELECT layout_template FROM clips LIMIT 1"))
        except Exception:
            await session.rollback()
            try:
                await session.execute(text("ALTER TABLE clips ADD COLUMN layout_template VARCHAR DEFAULT 'split_50_50'"))
                await session.commit()
                db_logger.info("Added column 'layout_template' to 'clips' table.")
            except Exception as e:
                db_logger.error(f"Failed to add 'layout_template' to 'clips': {e}")
                await session.rollback()

        for column_name, column_sql in [
            ("youtube_title", "ALTER TABLE clips ADD COLUMN youtube_title TEXT"),
            ("youtube_description", "ALTER TABLE clips ADD COLUMN youtube_description TEXT"),
            ("instagram_caption", "ALTER TABLE clips ADD COLUMN instagram_caption TEXT"),
            ("hook_score", "ALTER TABLE clips ADD COLUMN hook_score INTEGER"),
        ]:
            try:
                await session.execute(text(f"SELECT {column_name} FROM clips LIMIT 1"))
            except Exception:
                await session.rollback()
                try:
                    await session.execute(text(column_sql))
                    await session.commit()
                    db_logger.info(f"Added column '{column_name}' to 'clips' table.")
                except Exception as e:
                    db_logger.error(f"Failed to add '{column_name}' to 'clips': {e}")
                    await session.rollback()


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
