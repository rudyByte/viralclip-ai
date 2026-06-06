import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class CloudinaryStorage:
    def __init__(self):
        self.cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
        self.api_key = os.getenv("CLOUDINARY_API_KEY", "").strip()
        self.api_secret = os.getenv("CLOUDINARY_API_SECRET", "").strip()
        self.enabled = bool(self.cloud_name and self.api_key and self.api_secret)

    def upload_video(self, file_path: str, public_id: str) -> dict | None:
        if not self.enabled:
            return None
        path = Path(file_path)
        if not path.exists():
            return None
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(
                cloud_name=self.cloud_name,
                api_key=self.api_key,
                api_secret=self.api_secret,
                secure=True,
            )
            result = cloudinary.uploader.upload_large(
                str(path),
                resource_type="video",
                public_id=public_id,
                folder="viralclip-ai/clips",
                overwrite=True,
            )
            return {
                "secure_url": result.get("secure_url"),
                "public_id": result.get("public_id"),
                "bytes": result.get("bytes") or path.stat().st_size,
            }
        except Exception as exc:
            logger.warning(f"Cloudinary upload failed for {file_path}: {exc}")
            return None
