"""
usage_store.py — Per-scan usage log, backing the dashboard's stats view.

Stored in DATA_DIR/usage.json, oldest scan first. Only the newest
MAX_ENTRIES scans are kept so the file can't grow without bound; the
per-user totals are computed from those retained scans.
"""
from datetime import datetime, timezone
from typing import Dict, List

from .json_store import lock, read_json, write_json
from .paths import USAGE_PATH

MAX_ENTRIES = 5000


def log_scan(user_id: int, username: str, url: str, verdict: str) -> None:
    with lock:
        scans = read_json(USAGE_PATH, [])
        scans.append({
            "user_id": user_id,
            "username": username or "",
            "url": url,
            "verdict": verdict,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        })
        write_json(USAGE_PATH, scans[-MAX_ENTRIES:])


def get_per_user_stats() -> List[Dict]:
    per_user: Dict[int, Dict] = {}
    for scan in read_json(USAGE_PATH, []):
        stats = per_user.setdefault(scan["user_id"], {"user_id": scan["user_id"], "scan_count": 0})
        stats["username"] = scan["username"]
        stats["scan_count"] += 1
        stats["last_scan"] = scan["scanned_at"]
    return sorted(per_user.values(), key=lambda s: s["scan_count"], reverse=True)


def get_recent_scans(limit: int = 25) -> List[Dict]:
    return read_json(USAGE_PATH, [])[-limit:][::-1]
