"""
allowlist_store.py — Telegram user allowlist, stored in
DATA_DIR/allowlist.json.

is_allowed() reads the file on every call, so edits made in the dashboard
take effect immediately without restarting the bot. A missing or unreadable
file reads as an empty list, so the bot fails *closed* (denies everyone).
"""
from datetime import datetime, timezone
from typing import Dict, List

from .json_store import lock, read_json, write_json
from .paths import ALLOWLIST_PATH


def list_allowed() -> List[Dict]:
    entries = read_json(ALLOWLIST_PATH, [])
    return sorted(entries, key=lambda e: e["added_at"], reverse=True)


def is_allowed(user_id: int) -> bool:
    return any(e["user_id"] == user_id for e in read_json(ALLOWLIST_PATH, []))


def add_user(user_id: int, note: str = "") -> None:
    with lock:
        entries = read_json(ALLOWLIST_PATH, [])
        if any(e["user_id"] == user_id for e in entries):
            return
        entries.append({
            "user_id": user_id,
            "note": note,
            "added_at": datetime.now(timezone.utc).isoformat(),
        })
        write_json(ALLOWLIST_PATH, entries)


def remove_user(user_id: int) -> None:
    with lock:
        entries = read_json(ALLOWLIST_PATH, [])
        write_json(ALLOWLIST_PATH, [e for e in entries if e["user_id"] != user_id])
