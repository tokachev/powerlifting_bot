"""Annotate video frames with pose landmarks, skeleton, and key angles via MediaPipe."""

from __future__ import annotations

import base64
import math

import cv2
import numpy as np

try:
    import mediapipe as mp

    _HAS_MEDIAPIPE = True
except ImportError:
    _HAS_MEDIAPIPE = False

# Landmark indices (MediaPipe Pose 33-point model)
_L_SHOULDER = 11
_R_SHOULDER = 12
_L_HIP = 23
_R_HIP = 24
_L_KNEE = 25
_R_KNEE = 26
_L_ANKLE = 27
_R_ANKLE = 28

_SKELETON_PAIRS = [
    (_L_SHOULDER, _R_SHOULDER),
    (_L_SHOULDER, _L_HIP),
    (_R_SHOULDER, _R_HIP),
    (_L_HIP, _R_HIP),
    (_L_HIP, _L_KNEE),
    (_R_HIP, _R_KNEE),
    (_L_KNEE, _L_ANKLE),
    (_R_KNEE, _R_ANKLE),
]

_ALL_JOINTS = [_L_SHOULDER, _R_SHOULDER, _L_HIP, _R_HIP, _L_KNEE, _R_KNEE, _L_ANKLE, _R_ANKLE]

# BGR colours
_CLR_SKELETON = (230, 216, 60)   # cyan-ish
_CLR_JOINT = (0, 220, 0)        # green
_CLR_SPINE = (0, 0, 230)        # red — actual spine
_CLR_REF = (0, 200, 0)          # green — vertical reference
_CLR_ARC = (0, 230, 230)        # yellow
_CLR_TEXT = (255, 255, 255)      # white
_CLR_BG = (30, 30, 30)          # dark bg for text


def annotate_frames(frames_b64: list[str]) -> list[str]:
    """Annotate a batch of base64-JPEG frames with pose skeleton and angles.

    Returns list of same length; frames where pose detection fails are returned unchanged.
    If mediapipe is not installed, returns frames unchanged.
    """
    if not _HAS_MEDIAPIPE or not frames_b64:
        return frames_b64

    with mp.solutions.pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        min_detection_confidence=0.5,
    ) as pose:
        return [_annotate_one(fb64, pose) for fb64 in frames_b64]


def build_collage(
    all_frames_b64: list[str],
    problem_indices_1based: list[int],
    cell_width: int = 360,
) -> str:
    """Build a numbered grid collage. Problem frames get pose annotation.

    Returns a single base64 JPEG image.
    """
    n = len(all_frames_b64)
    if n == 0:
        return ""

    # Annotate problem frames
    annotated: list[str] = []
    problem_set = {i - 1 for i in problem_indices_1based}  # to 0-based
    if _HAS_MEDIAPIPE:
        # Batch-annotate only problem frames
        to_annotate_idx = [i for i in range(n) if i in problem_set]
        to_annotate_b64 = [all_frames_b64[i] for i in to_annotate_idx]
        annotated_b64 = annotate_frames(to_annotate_b64)
        ann_map = dict(zip(to_annotate_idx, annotated_b64))
        annotated = [ann_map.get(i, all_frames_b64[i]) for i in range(n)]
    else:
        annotated = list(all_frames_b64)

    # Decode all to numpy
    cells: list[np.ndarray] = []
    for i, fb64 in enumerate(annotated):
        img_bytes = base64.b64decode(fb64)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            frame = np.zeros((cell_width, cell_width, 3), dtype=np.uint8)

        # Resize to uniform cell width
        h, w = frame.shape[:2]
        scale = cell_width / w
        frame = cv2.resize(frame, (cell_width, int(h * scale)), interpolation=cv2.INTER_AREA)

        # Frame number label (top-left)
        is_problem = i in problem_set
        label = str(i + 1)
        lbl_clr = (0, 0, 255) if is_problem else (255, 255, 255)
        bg_clr = (0, 0, 180) if is_problem else (40, 40, 40)
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(label, font, 0.8, 2)
        pad = 6
        cv2.rectangle(frame, (0, 0), (tw + 2 * pad, th + 2 * pad), bg_clr, -1)
        cv2.putText(frame, label, (pad, th + pad), font, 0.8, lbl_clr, 2, cv2.LINE_AA)

        cells.append(frame)

    # Grid layout: 3 columns
    cols = 3 if n > 2 else n
    rows_count = math.ceil(n / cols)

    # Uniform cell height = max across all cells
    cell_h = max(c.shape[0] for c in cells)

    # Pad cells to same height
    padded: list[np.ndarray] = []
    for c in cells:
        if c.shape[0] < cell_h:
            pad_bottom = np.zeros((cell_h - c.shape[0], c.shape[1], 3), dtype=np.uint8)
            c = np.vstack([c, pad_bottom])
        padded.append(c)

    # Fill missing cells with black
    while len(padded) < rows_count * cols:
        padded.append(np.zeros((cell_h, cell_width, 3), dtype=np.uint8))

    # Assemble grid
    grid_rows: list[np.ndarray] = []
    for r in range(rows_count):
        row_cells = padded[r * cols : (r + 1) * cols]
        grid_rows.append(np.hstack(row_cells))
    grid = np.vstack(grid_rows)

    _, buf = cv2.imencode(".jpg", grid, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _annotate_one(frame_b64: str, pose) -> str:  # noqa: ANN001
    img_bytes = base64.b64decode(frame_b64)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return frame_b64

    results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    if not results.pose_landmarks:
        return frame_b64

    lm = results.pose_landmarks.landmark
    h, w = frame.shape[:2]

    _draw_skeleton(frame, lm, w, h)
    _draw_spine_analysis(frame, lm, w, h)
    _draw_knee_angles(frame, lm, w, h)

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return base64.b64encode(buf.tobytes()).decode("ascii")


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _px(landmark, w: int, h: int) -> tuple[int, int]:
    return int(landmark.x * w), int(landmark.y * h)


def _mid(p1: tuple[int, int], p2: tuple[int, int]) -> tuple[int, int]:
    return (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2


def _angle(p1: tuple[int, int], vertex: tuple[int, int], p2: tuple[int, int]) -> float:
    """Angle at *vertex* in degrees."""
    v1 = (p1[0] - vertex[0], p1[1] - vertex[1])
    v2 = (p2[0] - vertex[0], p2[1] - vertex[1])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    m1 = math.hypot(*v1)
    m2 = math.hypot(*v2)
    if m1 == 0 or m2 == 0:
        return 0.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / (m1 * m2)))))


def _draw_skeleton(frame: np.ndarray, lm, w: int, h: int) -> None:  # noqa: ANN001
    for a, b in _SKELETON_PAIRS:
        cv2.line(frame, _px(lm[a], w, h), _px(lm[b], w, h), _CLR_SKELETON, 2, cv2.LINE_AA)
    for j in _ALL_JOINTS:
        cv2.circle(frame, _px(lm[j], w, h), 5, _CLR_JOINT, -1, cv2.LINE_AA)


def _draw_spine_analysis(frame: np.ndarray, lm, w: int, h: int) -> None:  # noqa: ANN001
    """Draw spine line (shoulder→hip) + vertical reference + angle value."""
    mid_sh = _mid(_px(lm[_L_SHOULDER], w, h), _px(lm[_R_SHOULDER], w, h))
    mid_hp = _mid(_px(lm[_L_HIP], w, h), _px(lm[_R_HIP], w, h))

    # Actual spine — red solid
    cv2.line(frame, mid_hp, mid_sh, _CLR_SPINE, 3, cv2.LINE_AA)

    # Vertical reference from hip — green dashed
    spine_len = abs(mid_sh[1] - mid_hp[1])
    if spine_len < 10:
        return
    ref_top = (mid_hp[0], mid_hp[1] - spine_len)
    _dashed_line(frame, mid_hp, ref_top, _CLR_REF, 2)

    # Spine angle from vertical
    dx = mid_sh[0] - mid_hp[0]
    dy = mid_hp[1] - mid_sh[1]  # y-axis inverted
    angle_deg = math.degrees(math.atan2(abs(dx), dy)) if dy > 0 else 0.0

    # Arc
    radius = min(35, spine_len // 3)
    start, end = -90, -90 + (angle_deg if dx >= 0 else -angle_deg)
    cv2.ellipse(
        frame, mid_hp, (radius, radius), 0,
        min(start, end), max(start, end),
        _CLR_ARC, 2, cv2.LINE_AA,
    )

    # Label (ASCII only — cv2.putText doesn't support Cyrillic)
    _text(frame, f"{angle_deg:.0f} deg", (mid_hp[0] + 12, mid_hp[1] - radius - 8))


def _draw_knee_angles(frame: np.ndarray, lm, w: int, h: int) -> None:  # noqa: ANN001
    sides = [
        (_L_HIP, _L_KNEE, _L_ANKLE, -55),
        (_R_HIP, _R_KNEE, _R_ANKLE, 10),
    ]
    for hip_i, knee_i, ankle_i, text_off_x in sides:
        hip = _px(lm[hip_i], w, h)
        knee = _px(lm[knee_i], w, h)
        ankle = _px(lm[ankle_i], w, h)
        ang = _angle(hip, knee, ankle)
        _text(frame, f"{ang:.0f} deg", (knee[0] + text_off_x, knee[1] - 12), scale=0.55)


def _dashed_line(
    frame: np.ndarray, p1: tuple[int, int], p2: tuple[int, int],
    colour: tuple[int, int, int], thickness: int,
) -> None:
    dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    if dist == 0:
        return
    dx, dy = (p2[0] - p1[0]) / dist, (p2[1] - p1[1]) / dist
    pos, draw = 0.0, True
    while pos < dist:
        seg = 10 if draw else 7
        nxt = min(pos + seg, dist)
        if draw:
            sp = (int(p1[0] + dx * pos), int(p1[1] + dy * pos))
            ep = (int(p1[0] + dx * nxt), int(p1[1] + dy * nxt))
            cv2.line(frame, sp, ep, colour, thickness, cv2.LINE_AA)
        pos = nxt
        draw = not draw


def _text(
    frame: np.ndarray, txt: str, pos: tuple[int, int],
    scale: float = 0.6, colour: tuple[int, int, int] = _CLR_TEXT,
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(txt, font, scale, 1)
    x, y = pos
    cv2.rectangle(frame, (x - 2, y - th - 4), (x + tw + 2, y + baseline + 2), _CLR_BG, -1)
    cv2.putText(frame, txt, (x, y), font, scale, colour, 1, cv2.LINE_AA)
