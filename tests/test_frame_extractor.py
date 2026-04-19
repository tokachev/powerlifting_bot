"""Tests for video frame extraction using OpenCV."""

from __future__ import annotations

import base64
from pathlib import Path

import cv2
import numpy as np
import pytest

from pwrbot.video.frame_extractor import (
    ExtractedFrames,
    FrameExtractionError,
    extract_key_frames,
)


def _make_test_video(path: Path, n_frames: int = 30, fps: float = 30.0) -> None:
    """Write a small synthetic MP4 video with solid-colour frames."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (320, 240))
    for i in range(n_frames):
        # Each frame is a distinct colour so we can verify uniqueness
        frame = np.full((240, 320, 3), fill_value=(i * 8) % 256, dtype=np.uint8)
        writer.write(frame)
    writer.release()


@pytest.fixture
def video_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.mp4"
    _make_test_video(p, n_frames=30, fps=30.0)
    return p


def test_extract_returns_correct_frame_count(video_path: Path) -> None:
    result = extract_key_frames(video_path, max_frames=4)
    assert isinstance(result, ExtractedFrames)
    assert len(result.frames_b64) == 4


def test_extract_caps_at_total_frames(tmp_path: Path) -> None:
    p = tmp_path / "short.mp4"
    _make_test_video(p, n_frames=3, fps=30.0)
    result = extract_key_frames(p, max_frames=10)
    assert len(result.frames_b64) == 3


def test_frames_are_valid_jpeg(video_path: Path) -> None:
    result = extract_key_frames(video_path, max_frames=2)
    for b64 in result.frames_b64:
        raw = base64.b64decode(b64)
        # JPEG magic bytes: FF D8 FF
        assert raw[:2] == b"\xff\xd8", "Frame should be valid JPEG"


def test_metadata(video_path: Path) -> None:
    result = extract_key_frames(video_path, max_frames=6)
    assert result.total_frames == 30
    assert result.fps == pytest.approx(30.0, abs=1.0)
    assert result.duration_s == pytest.approx(1.0, abs=0.2)


def test_resize_reduces_width(tmp_path: Path) -> None:
    p = tmp_path / "wide.mp4"
    # Create a 1280-wide video
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(p), fourcc, 30.0, (1280, 720))
    writer.write(np.zeros((720, 1280, 3), dtype=np.uint8))
    writer.release()

    result = extract_key_frames(p, max_frames=1, resize_width=640)
    raw = base64.b64decode(result.frames_b64[0])
    arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    assert arr.shape[1] == 640


def test_bad_path_raises() -> None:
    with pytest.raises(FrameExtractionError, match="Cannot open"):
        extract_key_frames(Path("/nonexistent/video.mp4"))


def test_single_frame_video(tmp_path: Path) -> None:
    p = tmp_path / "single.mp4"
    _make_test_video(p, n_frames=1, fps=30.0)
    result = extract_key_frames(p, max_frames=6)
    assert len(result.frames_b64) == 1


# ---------------------------------------------------------------------------
# Motion window detection
# ---------------------------------------------------------------------------


def _static_frame(shade: int = 60, size: tuple[int, int] = (240, 320)) -> np.ndarray:
    h, w = size
    return np.full((h, w, 3), shade, dtype=np.uint8)


def _moving_square_frame(x: int, size: tuple[int, int] = (240, 320)) -> np.ndarray:
    h, w = size
    img = np.full((h, w, 3), 20, dtype=np.uint8)
    sq = 60
    x = max(0, min(w - sq, x))
    img[h // 2 - sq // 2 : h // 2 + sq // 2, x : x + sq] = 240
    return img


def _write_video(path: Path, frames: list[np.ndarray], fps: float = 30.0) -> None:
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    if not writer.isOpened():
        pytest.skip("mp4v encoder not available on this platform")
    try:
        for f in frames:
            writer.write(f)
    finally:
        writer.release()


def test_motion_window_static_video(tmp_path: Path) -> None:
    """Static video: detection returns None, frames span full range."""
    p = tmp_path / "static.mp4"
    _write_video(p, [_static_frame(128) for _ in range(60)])

    result = extract_key_frames(p, max_frames=6)

    assert result.motion_window is None
    assert len(result.frames_b64) == 6


def test_motion_window_detects_active_phase(tmp_path: Path) -> None:
    """Static prefix + moving object in tail → window skips the prefix."""
    p = tmp_path / "motion.mp4"
    frames = [_static_frame(40) for _ in range(45)]
    for i in range(45):
        frames.append(_moving_square_frame(20 + (i * 6) % 220))
    frames.extend(_static_frame(40) for _ in range(10))
    _write_video(p, frames)

    result = extract_key_frames(p, max_frames=6)

    assert result.motion_window is not None, "motion phase should be detected"
    start, end = result.motion_window
    # Motion begins ~frame 45; tolerate ±1-sample expansion (step=6)
    assert start >= 30, f"start={start} should skip most of the static prefix"
    assert end <= result.total_frames - 1
    assert end - start >= 6
    assert len(result.frames_b64) == 6


def test_motion_window_full_coverage_falls_back(tmp_path: Path) -> None:
    """Motion across whole video → coverage >90% → fallback to full range."""
    p = tmp_path / "all_motion.mp4"
    # Step 17 isn't a multiple of the motion sample stride (≈6 @ 30fps),
    # so every sample sees a different square position → continuous motion.
    frames = [_moving_square_frame(20 + (i * 17) % 220) for i in range(80)]
    _write_video(p, frames)

    result = extract_key_frames(p, max_frames=6)

    assert result.motion_window is None
    assert len(result.frames_b64) == 6


def test_motion_window_skipped_for_short_video(tmp_path: Path) -> None:
    """Video shorter than 2*max_frames: skip detection entirely."""
    p = tmp_path / "tiny.mp4"
    # total=10 < 2*6 → skip detection
    frames = [_moving_square_frame(20 + i * 20) for i in range(10)]
    _write_video(p, frames)

    result = extract_key_frames(p, max_frames=6)

    assert result.motion_window is None
    assert len(result.frames_b64) == 6
