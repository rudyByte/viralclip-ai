"""
ViralClip AI — Face Tracker
Uses OpenCV to detect and track speaker face position throughout video.
"""
import cv2
import numpy as np
import asyncio
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FaceTracker:
    def __init__(self):
        # Use Haar cascade (fast, no dependencies beyond OpenCV)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml"
        )

    def analyze_video(
        self,
        video_path: str,
        sample_interval: float = 2.0,
        start_time: float = 0.0,
        end_time: Optional[float] = None,
    ) -> list[tuple[float, float, float]]:
        """
        Sample frames from video and detect face positions.
        Returns list of (timestamp, x_ratio, y_ratio) tuples.
        Face x_ratio/y_ratio are 0-1 fractions of frame dimensions.
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"Cannot open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        total_duration = total_frames / fps

        if end_time is None:
            end_time = total_duration

        positions = []
        sample_step = int(fps * sample_interval)

        # Seek to start
        start_frame = int(start_time * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        frame_num = start_frame
        end_frame = int(end_time * fps)

        while frame_num < end_frame:
            ret, frame = cap.read()
            if not ret:
                break

            timestamp = frame_num / fps
            pos = self._detect_face_center(frame)
            if pos:
                positions.append((timestamp, pos[0], pos[1]))

            # Skip ahead
            frame_num += sample_step
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)

        cap.release()

        logger.info(f"Face tracking: found {len(positions)} face positions in {video_path}")
        return positions

    def _detect_face_center(self, frame: np.ndarray) -> Optional[tuple[float, float]]:
        """
        Detect face in frame and return normalized center (x_ratio, y_ratio).
        Returns None if no face found.
        """
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # Try frontal face first
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )

        # Fall back to profile face
        if len(faces) == 0:
            faces = self.profile_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )

        if len(faces) == 0:
            return None

        # Pick largest face (most prominent speaker)
        largest = max(faces, key=lambda f: f[2] * f[3])
        fx, fy, fw, fh = largest

        # Center of face
        cx = (fx + fw / 2) / w
        cy = (fy + fh / 2) / h

        return (cx, cy)

    def get_dominant_position(
        self,
        positions: list[tuple[float, float, float]],
        smoothing: bool = True,
    ) -> tuple[float, float]:
        """
        Calculate the dominant face position across all samples.
        Returns (x_ratio, y_ratio) for crop centering.
        Falls back to (0.5, 0.35) if no faces found.
        """
        if not positions:
            return (0.5, 0.35)  # Default: center-top

        x_vals = [p[1] for p in positions]
        y_vals = [p[2] for p in positions]

        if smoothing:
            # Use median for stability (ignore outliers)
            x = float(np.median(x_vals))
            y = float(np.median(y_vals))
        else:
            x = float(np.mean(x_vals))
            y = float(np.mean(y_vals))

        # Clamp to valid range
        x = max(0.1, min(0.9, x))
        y = max(0.1, min(0.9, y))

        return (x, y)

    async def analyze_video_async(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.analyze_video(*args, **kwargs))
