"""Constrain media downloads to their configured storage directory."""

import os

from fastapi import HTTPException


def media_path(root, *parts):
    """Resolve single-component names without traversal or external symlinks."""
    names = []
    for part in parts:
        if not part or part in {".", ".."} or "\\" in part or any(ord(c) < 32 for c in part):
            raise HTTPException(status_code=400, detail="Invalid media filename")
        if os.path.basename(part) != part:
            raise HTTPException(status_code=400, detail="Invalid media filename")
        names.append(os.path.basename(part))
    root = os.path.realpath(root)
    result = os.path.realpath(os.path.join(root, *names))
    if os.path.commonpath([root, result]) != root:
        raise HTTPException(status_code=400, detail="Invalid media filename")
    return result
