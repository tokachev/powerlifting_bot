"""Extract evenly-spaced key frames from a video file using OpenCV."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class FrameExtractionError(Exception):
    """Raised when the video cannot be opened or frames cannot be read."""


@dataclass(slots=True)
class ExtractedFrames:
    frames_b64: list[str]
    fps: float
    total_frames: int
    duration_s: float


def extract_key_frames(
    video_path: Path,
    max_frames: int = 6,
    resize_width: int = 720,
) -> ExtractedFrames:
    """Open *video_path* and return up to *max_frames* evenly-spaced JPEG frames
    encoded as base64 strings.

    Each frame is resized so its width equals *resize_width* (aspect ratio kept).
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FrameExtractionError(f"Cannot open video: {video_path}")

    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration = total / fps if fps > 0 else 0.0

        if total <= 0:
            raise FrameExtractionError("Video has no frames")

        n_frames = min(max_frames, total)
        if n_frames == 1:
            indices = [0]
        else:
            indices = [int(i * (total - 1) / (n_frames - 1)) for i in range(n_frames)]

        frames_b64: list[str] = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            frame = _resize(frame, resize_width)
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frames_b64.append(base64.b64encode(buf.tobytes()).decode("ascii"))

        if not frames_b64:
            raise FrameExtractionError("Could not read any frames from video")

        return ExtractedFrames(
            frames_b64=frames_b64,
            fps=fps,
            total_frames=total,
            duration_s=round(duration, 2),
        )
    finally:
        cap.release()


def _resize(frame: np.ndarray, target_width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w <= target_width:
        return frame
    scale = target_width / w
    new_h = int(h * scale)
    return cv2.resize(frame, (target_width, new_h), interpolation=cv2.INTER_AREA)
