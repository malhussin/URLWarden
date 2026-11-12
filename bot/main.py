"""
main.py — URLWarden bot logic, invoked by the top-level app.py entrypoint.

Waits for a Telegram bot token + VirusTotal API key to be saved from the
dashboard (see common/credentials_store.py), then starts polling for
updates.

Note: changing the Telegram token later requires restarting the container
(`docker restart urlwarden`) since python-telegram-bot builds its
Application around a fixed token at startup. Everything else — the
allowlist and the VirusTotal key — is re-read from disk on every use, so
dashboard changes to those apply immediately.

main() may be called more than once in the same process — app.py retries it
on crashes (e.g. an invalid token). python-telegram-bot closes and clears
this thread's asyncio event loop when a run_polling() attempt ends, and
asyncio's "auto-create a loop for the main thread" fallback only ever
fires once per thread — a second bare call to asyncio.get_event_loop()
(which run_polling makes internally) raises RuntimeError instead of making
a new one. So each call here explicitly creates and sets a fresh loop
first, rather than relying on that one-shot fallback.
"""
import asyncio
import logging
import time

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from common import credentials_store

from . import handlers
from .providers.virustotal import VirusTotalProvider
from .rate_limiter import AsyncRateLimiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("urlwarden.bot")

# VirusTotal free-tier budget; raise these if you have a paid key.
VT_MAX_PER_MINUTE = 4
VT_MAX_PER_DAY = 500
CONFIG_POLL_SECONDS = 10


def _wait_for_token() -> str:
    while True:
        token = credentials_store.get_telegram_token()
        if token and credentials_store.get_virustotal_key():
            return token
        logger.warning(
            "Waiting for the Telegram bot token and VirusTotal API key — "
            "set them via the admin dashboard (http://127.0.0.1:8080)."
        )
        time.sleep(CONFIG_POLL_SECONDS)


def main() -> None:
    asyncio.set_event_loop(asyncio.new_event_loop())

    token = _wait_for_token()

    rate_limiter = AsyncRateLimiter(VT_MAX_PER_MINUTE, VT_MAX_PER_DAY)
    provider = VirusTotalProvider(rate_limiter)

    app = Application.builder().token(token).build()
    app.bot_data["provider"] = provider

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("help", handlers.cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))

    logger.info("URLWarden bot starting...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
