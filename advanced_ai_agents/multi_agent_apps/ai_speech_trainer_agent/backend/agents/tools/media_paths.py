"""Containment for media paths that reach the analysis tools.

The /analyze request and the model-selected tool arguments both carry a file
path. Only regular files inside the upload directory (where the Streamlit
frontend saves uploads) may be decoded; anything else on the host is rejected.
"""

import os
import tempfile
from pathlib import Path

UPLOAD_DIR_ENV = "SPEECH_TRAINER_UPLOAD_DIR"
DEFAULT_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "ai_speech_trainer_uploads")
ALLOWED_MEDIA_EXTENSIONS = {".mp4", ".mp3", ".wav", ".m4a"}


def upload_dir() -> Path:
    return Path(os.getenv(UPLOAD_DIR_ENV) or DEFAULT_UPLOAD_DIR).expanduser().resolve()


def resolve_upload_media(path: str) -> str:
    """Return the resolved path if it is an uploaded media file, else raise ValueError."""
    if not isinstance(path, str) or not path.strip() or "\x00" in path:
        raise ValueError("A media file path is required.")
    root = upload_dir()
    candidate = Path(path.strip()).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    if candidate.is_symlink():
        raise ValueError("Symlinked media files are not accepted.")
    try:
        resolved = candidate.resolve(strict=True)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        raise ValueError("Media file not found in the upload directory.") from exc
    if resolved == root or not resolved.is_relative_to(root):
        raise ValueError("Media files must be inside the upload directory.")
    if not resolved.is_file():
        raise ValueError("Media path must be a regular file.")
    if resolved.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
        raise ValueError("Unsupported media file type.")
    return str(resolved)
