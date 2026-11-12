"""
app.py — Combined entrypoint: runs the Telegram bot and the admin dashboard
together in a single process/container.

The dashboard has nothing to wait on, so it starts immediately in a daemon
background thread (uvicorn.run() blocks, hence the thread — same pattern as
running any WSGI/ASGI server off the main thread). The bot polling loop
runs on the main thread.

If the bot crashes (most commonly: an invalid/rejected Telegram token) we
catch it, log it, and retry after a delay instead of letting the whole
process — and with it the dashboard — go down. That keeps the dashboard
reachable so the token/key can actually be fixed. A clean shutdown (e.g.
`docker stop`, which python-telegram-bot turns into a graceful return from
run_polling) exits the loop instead of retrying.
"""
import logging
import threading
import time

from bot.main import main as run_bot
from dashboard.server import main as run_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("urlwarden.app")

BOT_RETRY_SECONDS = 30


def main() -> None:
    dashboard_thread = threading.Thread(target=run_dashboard, name="dashboard", daemon=True)
    dashboard_thread.start()
    logger.info("Admin dashboard listening on :8080 (published as 127.0.0.1:8080 on the host)")

    while True:
        try:
            run_bot()
            break  # run_polling returned normally: a clean shutdown, not a crash
        except Exception:
            logger.error(
                "Bot crashed — retrying in %ss (fix credentials at http://127.0.0.1:8080 if needed)",
                BOT_RETRY_SECONDS,
                exc_info=True,
            )
            time.sleep(BOT_RETRY_SECONDS)


if __name__ == "__main__":
    main()
