"""
ViralClip AI — Backend Configuration
Loads all settings from environment variables / .env file
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path
import os


class Settings(BaseSettings):
    # API Keys
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    # Use a high-TPD model for bulk detection (500K/day free), big model only for hook copy
    groq_detection_model: str = Field("llama-3.1-8b-instant", env="GROQ_DETECTION_MODEL")
    groq_hook_model: str = Field("llama-3.3-70b-versatile", env="GROQ_HOOK_MODEL")

    # App
    app_host: str = Field("0.0.0.0", env="APP_HOST")
    app_port: int = Field(8000, env="APP_PORT")
    debug: bool = Field(False, env="DEBUG")

    # Paths
    temp_dir: str = Field("./temp", env="TEMP_DIR")
    export_dir: str = Field("./exports", env="EXPORT_DIR")
    assets_dir: str = Field("./assets", env="ASSETS_DIR")
    models_dir: str = Field("./models", env="MODELS_DIR")

    # Processing
    max_concurrent_jobs: int = Field(2, env="MAX_CONCURRENT_JOBS")

    # Whisper
    whisper_model: str = Field("small", env="WHISPER_MODEL")
    whisper_device: str = Field("cpu", env="WHISPER_DEVICE")
    whisper_compute_type: str = Field("int8", env="WHISPER_COMPUTE_TYPE")

    # Clip Defaults
    default_clip_min_duration: int = Field(30, env="DEFAULT_CLIP_MIN_DURATION")
    default_clip_max_duration: int = Field(60, env="DEFAULT_CLIP_MAX_DURATION")
    default_num_clips: int = Field(3, env="DEFAULT_NUM_CLIPS")
    max_clips_per_job: int = Field(10, env="MAX_CLIPS_PER_JOB")
    default_caption_style: str = Field("hormozi", env="DEFAULT_CAPTION_STYLE")
    default_background: str = Field("subway", env="DEFAULT_BACKGROUND")

    # Export
    export_width: int = Field(1080, env="EXPORT_WIDTH")
    export_height: int = Field(1920, env="EXPORT_HEIGHT")
    export_fps: int = Field(30, env="EXPORT_FPS")
    export_video_bitrate: str = Field("8M", env="EXPORT_VIDEO_BITRATE")
    export_audio_bitrate: str = Field("192k", env="EXPORT_AUDIO_BITRATE")

    # CORS
    frontend_url: str = Field("http://localhost:3000", env="FRONTEND_URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def ensure_dirs(self):
        """Create required directories if they don't exist."""
        for d in [self.temp_dir, self.export_dir, self.assets_dir, self.models_dir,
                  f"{self.assets_dir}/gameplay/subway",
                  f"{self.assets_dir}/gameplay/minecraft",
                  f"{self.assets_dir}/gameplay/gta",
                  f"{self.assets_dir}/gameplay/templerun"]:
            Path(d).mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
