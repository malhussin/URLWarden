"""
cache_store.py — Short-lived, file-based cache of scan results.

Keeps the same URL from being re-submitted to a threat-intel provider
repeatedly within a short window, which matters a lot on VirusTotal's free
tier (4 requests/min, 500/day). One JSON file per URL, keyed by its SHA-256
hash, stored under DATA_DIR/cache/.
"""
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional

from .paths import CACHE_DIR, ensure_data_dirs

DEFAULT_TTL_SECONDS = 3600  # how long a result is reused before re-scanning


def _cache_path(url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def get_cached(url: str, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[Dict]:
    path = _cache_path(url)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - payload.get("cached_at", 0) > ttl_seconds:
        return None
    return payload.get("result")


def set_cached(url: str, result: Dict) -> None:
    ensure_data_dirs()
    path = _cache_path(url)
    payload = {"url": url, "cached_at": time.time(), "result": result}
    fd, tmp_path = tempfile.mkstemp(dir=str(CACHE_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp_path, path)
    except BaseException:
        os.unlink(tmp_path)
        raise
