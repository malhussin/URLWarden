"""
server.py — URLWarden admin dashboard (FastAPI).

A configuration UI for the bot:
  - Sets the Telegram bot token and VirusTotal API key
    (common/credentials_store.py).
  - Manages the Telegram user allowlist (common/allowlist_store.py).
  - Shows usage stats (common/usage_store.py).

There is no login: anyone who can reach this port has full control of the
bot's configuration. Access is restricted by network binding only — the
port is published as 127.0.0.1:8080 by `docker run -p` (see README.md).

Secrets are never echoed back in plaintext: GET /api/config only returns
masked previews (e.g. ••••••1234), and nothing in this module logs raw
token/key values.
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from common import allowlist_store, credentials_store, usage_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("urlwarden.dashboard")

app = FastAPI(title="URLWarden Admin", docs_url=None, redoc_url=None, openapi_url=None)

TEMPLATE_DIR = Path(__file__).parent / "templates"


class ConfigUpdate(BaseModel):
    telegram_token: str = ""
    virustotal_api_key: str = ""


class AllowlistEntry(BaseModel):
    user_id: int
    note: str = ""


# ── Pages ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((TEMPLATE_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/healthz")
async def healthz():
    """Liveness check — used by the Docker HEALTHCHECK."""
    return {"status": "ok"}


# ── Bot / VirusTotal credentials ─────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    token = credentials_store.get_telegram_token()
    vt_key = credentials_store.get_virustotal_key()
    return {
        "telegram_token_masked": credentials_store.mask_secret(token),
        "telegram_token_set": bool(token),
        "virustotal_api_key_masked": credentials_store.mask_secret(vt_key),
        "virustotal_api_key_set": bool(vt_key),
    }


@app.post("/api/config")
async def update_config(payload: ConfigUpdate):
    telegram_token = payload.telegram_token.strip()
    virustotal_api_key = payload.virustotal_api_key.strip()
    if telegram_token:
        credentials_store.set_telegram_token(telegram_token)
    if virustotal_api_key:
        credentials_store.set_virustotal_key(virustotal_api_key)
    logger.info("Configuration updated via dashboard")  # values themselves are never logged
    return await get_config()


# ── Allowlist ────────────────────────────────────────────────────────────

@app.get("/api/allowlist")
async def get_allowlist():
    return allowlist_store.list_allowed()


@app.post("/api/allowlist")
async def add_allowlist_entry(entry: AllowlistEntry):
    allowlist_store.add_user(entry.user_id, entry.note)
    return allowlist_store.list_allowed()


@app.delete("/api/allowlist/{user_id}")
async def remove_allowlist_entry(user_id: int):
    allowlist_store.remove_user(user_id)
    return allowlist_store.list_allowed()


# ── Usage stats ──────────────────────────────────────────────────────────

@app.get("/api/stats")
async def get_stats():
    return {
        "per_user": usage_store.get_per_user_stats(),
        "recent": usage_store.get_recent_scans(),
    }


def main() -> None:
    import uvicorn

    # Inside Docker the server must listen on all interfaces for the port to
    # be published at all; the 127.0.0.1-only restriction then comes from
    # `docker run -p`. Run directly on a host there's no such layer, and the
    # dashboard has no login, so it binds to loopback only.
    host = "0.0.0.0" if Path("/.dockerenv").exists() else "127.0.0.1"

    # loop="asyncio" (instead of uvicorn's default "auto", which picks
    # uvloop) is deliberate: this runs in a background thread alongside the
    # bot (see app.py), and installing uvloop's process-wide event loop
    # policy interferes with asyncio's main-thread event loop handling that
    # python-telegram-bot relies on in bot/main.py.
    uvicorn.run(app, host=host, port=8080, log_level="warning", loop="asyncio")


if __name__ == "__main__":
    main()
