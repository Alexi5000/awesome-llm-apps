"""Server-side budgets and filename handling for video ingestion.

Every uploaded video spends the operator's Gemini key on frame embeddings, so
the caller-supplied fps is clamped and the frame/embedding count is capped.
Uploaded filenames never become filesystem paths: videos are stored under a
random name inside the uploads directory.
"""

import math
import os
import re
import uuid
from pathlib import Path


def _float_env(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.getenv(name, "") or default)
    except ValueError:
        value = default
    if not math.isfinite(value):
        value = default
    return max(minimum, min(maximum, value))


MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100MB
MIN_FPS = 0.05
MAX_FPS = _float_env("VIDEO_MAX_FPS", 2.0, minimum=MIN_FPS, maximum=30.0)
MAX_FRAMES = int(_float_env("VIDEO_MAX_FRAMES", 600, minimum=1, maximum=10000))
FFPROBE_TIMEOUT_SECONDS = 30
FFMPEG_TIMEOUT_SECONDS = int(_float_env("VIDEO_FFMPEG_TIMEOUT_SECONDS", 300, minimum=10, maximum=3600))
VIDEO_EXTENSIONS = {
    ".3gp", ".avi", ".flv", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".ogv", ".ts", ".webm", ".wmv",
}


def clamp_fps(fps) -> float:
    """Clamp a caller-supplied extraction rate into the server budget."""
    try:
        value = float(fps)
    except (TypeError, ValueError) as exc:
        raise ValueError("fps must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("fps must be a positive finite number")
    return max(MIN_FPS, min(MAX_FPS, value))


def display_filename(filename) -> str:
    """Basename of the uploaded name with control characters removed (for display only)."""
    name = re.split(r"[\\/]", str(filename or ""))[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:200] or "video"


def stored_upload_path(uploads_dir: Path, filename) -> Path:
    """Random, contained destination for an upload, keeping only an allowlisted video extension."""
    suffix = Path(display_filename(filename)).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise ValueError("Unsupported video file type")
    root = Path(uploads_dir).resolve()
    destination = (root / f"{uuid.uuid4().hex}{suffix}").resolve()
    if destination.parent != root:
        raise ValueError("Upload path escapes the uploads directory")
    return destination
