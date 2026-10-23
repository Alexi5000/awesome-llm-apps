"""Containment for media paths that reach the analysis tools.

The /analyze request and the model-selected tool arguments both carry a file
path. Only regular files inside the upload directory (where the Streamlit
frontend saves uploads) may be decoded; anything else on the host is rejected.
"""

import os
import tempfile

UPLOAD_DIR_ENV = "SPEECH_TRAINER_UPLOAD_DIR"
DEFAULT_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "ai_speech_trainer_uploads")
ALLOWED_MEDIA_EXTENSIONS = {".mp4", ".mp3", ".wav", ".m4a"}


def upload_dir() -> str:
    return os.path.realpath(os.path.expanduser(os.getenv(UPLOAD_DIR_ENV) or DEFAULT_UPLOAD_DIR))


def resolve_upload_media(path: str) -> str:
    """Return the resolved path if it is an uploaded media file, else raise ValueError."""
    if not isinstance(path, str) or not path.strip() or "\x00" in path:
        raise ValueError("A media file path is required.")
    root = upload_dir()
    # Lexical containment first, before the filesystem is consulted at all.
    candidate = os.path.normpath(os.path.join(root, path.strip()))
    if not candidate.startswith(root + os.sep):
        raise ValueError("Media files must be inside the upload directory.")
    if os.path.islink(candidate):
        raise ValueError("Symlinked media files are not accepted.")
    # Then re-check after resolving any symlinked parent directories.
    resolved = os.path.realpath(candidate)
    if not resolved.startswith(root + os.sep):
        raise ValueError("Media files must be inside the upload directory.")
    if not os.path.isfile(resolved):
        raise ValueError("Media file not found in the upload directory.")
    if os.path.splitext(resolved)[1].lower() not in ALLOWED_MEDIA_EXTENSIONS:
        raise ValueError("Unsupported media file type.")
    return resolved
