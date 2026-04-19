"""Extract evenly-spaced key frames from a video file using OpenCV."""

from __future__ import annotations

import base64
import contextlib
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
    motion_window: tuple[int, int] | None = None


# Motion detection tuning
_MOTION_SAMPLE_FPS = 5.0
_MOTION_DOWNSCALE_WIDTH = 160
_MOTION_MIN_SCORE = 2.0           # below this → treat as static
_MOTION_THR_RATIO = 0.35          # threshold as fraction of peak score
_MOTION_WINDOW_COVERAGE_MAX = 0.9  # window covering >90% of video is useless


def extract_key_frames(
    video_path: Path,
    max_frames: int = 6,
    resize_width: int = 720,
) -> ExtractedFrames:
    """Open *video_path* and return up to *max_frames* JPEG frames as base64.

    Frames are picked evenly across the motion window when it can be detected
    via frame differencing; otherwise evenly across the full video (legacy
    behavior). Each frame is resized so its width equals *resize_width*
    (aspect ratio kept).
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

        motion_window = _detect_motion_window(cap, total, fps, max_frames=max_frames)

        if n_frames == 1:
            indices = [0]
        elif motion_window is not None:
            start, end = motion_window
            span = end - start
            indices = [start + int(i * span / (n_frames - 1)) for i in range(n_frames)]
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
            motion_window=motion_window,
        )
    finally:
        cap.release()


def _detect_motion_window(
    cap: cv2.VideoCapture,
    total: int,
    fps: float,
    *,
    max_frames: int,
) -> tuple[int, int] | None:
    """Return absolute (start, end) frame indices bracketing the motion phase.

    Uses grayscale frame-differencing on downscaled samples. Returns None when
    the video is static, the detected window is shorter than *max_frames*, or
    it already covers almost the whole video (nothing to trim).
    """
    if total < max_frames * 2 or fps <= 0:
        return None

    step = max(1, round(fps / _MOTION_SAMPLE_FPS))
    sample_indices = list(range(0, total, step))
    if len(sample_indices) < 4:
        return None

    prev_gray: np.ndarray | None = None
    raw_scores: list[float] = []
    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok or frame is None:
            raw_scores.append(0.0)
            continue
        small = _resize(frame, _MOTION_DOWNSCALE_WIDTH)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if prev_gray is None or prev_gray.shape != gray.shape:
            raw_scores.append(0.0)
        else:
            raw_scores.append(float(cv2.absdiff(gray, prev_gray).mean()))
        prev_gray = gray

    with contextlib.suppress(cv2.error):
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # raw_scores[i] is motion between sample[i-1] and sample[i] (raw_scores[0] = 0)
    if not raw_scores or max(raw_scores) < _MOTION_MIN_SCORE:
        return None

    # Moving average (window=3) to smooth noise
    smoothed = _moving_average(raw_scores, window=3)
    peak = max(smoothed)
    if peak < _MOTION_MIN_SCORE:
        return None

    thr = max(_MOTION_MIN_SCORE, peak * _MOTION_THR_RATIO)
    active = [i for i, s in enumerate(smoothed) if s >= thr]
    if not active:
        return None

    # Expand by ±1 sample to capture stance/locked-out transitions
    first_sample = max(0, active[0] - 1)
    last_sample = min(len(sample_indices) - 1, active[-1] + 1)

    start_frame = sample_indices[first_sample]
    end_frame = min(total - 1, sample_indices[last_sample] + step - 1)

    if end_frame - start_frame < max_frames:
        return None

    coverage = (end_frame - start_frame + 1) / total
    if coverage > _MOTION_WINDOW_COVERAGE_MAX:
        return None

    return start_frame, end_frame


def _moving_average(values: list[float], window: int) -> list[float]:
    if window <= 1 or len(values) <= 1:
        return list(values)
    half = window // 2
    out: list[float] = []
    for i in range(len(values)):
        lo = max(0, i - half)
        hi = min(len(values), i + half + 1)
        segment = values[lo:hi]
        out.append(sum(segment) / len(segment))
    return out


def _resize(frame: np.ndarray, target_width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if w <= target_width:
        return frame
    scale = target_width / w
    new_h = int(h * scale)
    return cv2.resize(frame, (target_width, new_h), interpolation=cv2.INTER_AREA)
