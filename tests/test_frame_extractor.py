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
