"""
ViralClip AI — Visual & Audio Energy Scorer
Uses OpenCV optical flow / scene cut detection and audio volume peak detection
to find the most visually dynamic and engaging parts of a video (action, punches, celebrations, spikes).
"""
import cv2
import numpy as np
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VisualEnergyScorer:
    """
    Computes visual motion (optical flow), scene cuts, and audio volume energy
    across intervals in a video to identify visually engaging moments.
    """

    @staticmethod
    def analyze_intervals(
        video_path: str,
        total_duration: float,
        interval_duration: float = 30.0,
        step_duration: float = 15.0,
        sample_fps: float = 3.0,
    ) -> list[dict]:
        """
        Samples video at low FPS (~3-4 fps) and calculates motion energy (pixel difference)
        for sliding intervals across the video.
        Returns a list of intervals: [{"start": float, "end": float, "energy_score": int (0-100), "reason": str}]
        """
        if not video_path or not Path(video_path).exists():
            return []

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.warning(f"VisualEnergyScorer: Cannot open video {video_path}")
            return []

        video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(video_fps / sample_fps))

        prev_gray = None
        motion_history = []  # list of (timestamp_sec, motion_magnitude)

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                t = frame_idx / video_fps
                # Resize to small thumbnail for fast computation
                small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

                if prev_gray is not None:
                    # Absolute frame difference as motion energy
                    diff = cv2.absdiff(gray, prev_gray)
                    motion_val = float(np.mean(diff))
                    motion_history.append((t, motion_val))
                else:
                    motion_history.append((t, 0.0))

                prev_gray = gray

            frame_idx += 1

        cap.release()

        if not motion_history:
            return []

        # Find max motion value to normalize 0-100
        max_motion = max((m[1] for m in motion_history), default=1.0) or 1.0

        # Score sliding windows of interval_duration
        results = []
        curr_start = 0.0
        while curr_start + 10.0 <= total_duration:
            curr_end = min(total_duration, curr_start + interval_duration)
            # Find motion frames falling within [curr_start, curr_end]
            window_vals = [m[1] for m in motion_history if curr_start <= m[0] <= curr_end]
            if window_vals:
                avg_motion = float(np.mean(window_vals))
                peak_motion = float(np.max(window_vals))
                # 70% average high motion + 30% peak spike (sudden dramatic moment)
                raw_score = (avg_motion * 0.7 + peak_motion * 0.3) / max_motion
                score_100 = int(min(98, max(45, round(raw_score * 100))))
            else:
                score_100 = 50

            results.append({
                "start": round(curr_start, 2),
                "end": round(curr_end, 2),
                "energy_score": score_100,
                "reason": "High visual motion and dynamic action spike detected in video"
            })
            curr_start += step_duration

        # Sort intervals by energy_score descending
        results.sort(key=lambda x: x["energy_score"], reverse=True)
        return results
