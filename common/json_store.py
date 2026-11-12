"""
json_store.py — Small helpers for the JSON files under DATA_DIR.

The bot and the dashboard run as two threads of one process and share these
files, so read-modify-write sequences hold `lock`. Writes go through a temp
file plus os.replace(), so a crash mid-write can never leave a half-written
file behind. mkstemp creates the file as 0600, which keeps the stored
secrets readable by the owner only.
"""
import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from .paths import ensure_data_dirs

logger = logging.getLogger("urlwarden.json_store")

lock = threading.RLock()


def read_json(path: Path, default: Any) -> Any:
    """Return the parsed file, or `default` if it's missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except (json.JSONDecodeError, OSError):
        logger.error("Could not read %s, treating it as empty", path, exc_info=True)
        return default


def write_json(path: Path, data: Any) -> None:
    ensure_data_dirs()
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise
