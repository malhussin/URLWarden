"""
paths.py — Shared filesystem layout for URLWarden.

Single source of truth for where each piece of persisted state lives. All
of it sits in the project's data/ directory (/app/data inside the Docker
image), which is excluded from git and from the Docker build context.
"""
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CREDENTIALS_PATH = DATA_DIR / "credentials.json"
ALLOWLIST_PATH = DATA_DIR / "allowlist.json"
USAGE_PATH = DATA_DIR / "usage.json"
CACHE_DIR = DATA_DIR / "cache"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
