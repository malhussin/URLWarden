"""
handlers.py — Telegram update handlers for URLWarden.

Message flow for an incoming text message:
  1. Reject anything that isn't a single, well-formed http(s) URL (by design
     — messages that mix a URL into other text are asked to resend just the
     link, rather than us guessing which substring to scan).
  2. Reject senders who aren't on the allowlist. The allowlist is read from
     disk on every message (see common/allowlist_store.py), so changes made
     in the dashboard apply immediately, no bot restart needed.
  3. Reply "Scanning..." right away, then do the real lookup and edit the
     same message with the result. python-telegram-bot schedules each
     update as its own asyncio task, so this never blocks other users even
     though we don't spawn extra threads/processes for it.
  4. Serve from the file cache when possible; otherwise call the provider,
     cache the result, and log it for the dashboard's usage stats.
"""
import logging
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import ContextTypes

from common import allowlist_store, cache_store, usage_store

from .providers.base import ProviderError, RateLimitError, ScanResult
from .rate_limiter import DailyQuotaExceeded

logger = logging.getLogger("urlwarden.bot")

VERDICT_DISPLAY = {
    "safe": ("🟢", "Safe"),
    "suspicious": ("🟡", "Suspicious"),
    "malicious": ("🔴", "Malicious"),
}

HELP_TEXT = (
    "🛡️ *URLWarden*\n\n"
    "Send me a single link and I'll check it against VirusTotal's 70+ "
    "antivirus and threat-intel engines.\n\n"
    "*Commands:*\n"
    "/start — Welcome message\n"
    "/help — This help text\n\n"
    "Just paste a URL like `https://example.com` to scan it. "
    "Only one URL per message, please."
)


def _is_well_formed_url(text: str) -> bool:
    """True only if the *entire* message is one http(s) URL with no surrounding text."""
    if not text or any(ch.isspace() for ch in text):
        return False
    parsed = urlparse(text)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _format_result(result: ScanResult) -> str:
    emoji, label = VERDICT_DISPLAY[result.verdict]
    lines = [
        f"{emoji} *Verdict: {label}*",
        "",
        f"🔴 Malicious: {result.malicious}",
        f"🟡 Suspicious: {result.suspicious}",
        f"🟢 Clean: {result.harmless}",
        f"⚪ Undetected: {result.undetected}",
        f"📊 Total engines: {result.total}",
    ]
    if result.permalink:
        lines += ["", f"[Full report]({result.permalink})"]
    lines += ["", f"_Source: {result.provider}_"]
    return "\n".join(lines)


async def cmd_start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def cmd_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    text = update.message.text.strip()

    if not _is_well_formed_url(text):
        await update.message.reply_text(
            "❓ Please send a single, well-formed URL, e.g. `https://example.com`",
            parse_mode="Markdown",
        )
        return

    if not allowlist_store.is_allowed(user.id):
        await update.message.reply_text(
            "🚫 Sorry, you're not authorized to use this bot. "
            "Ask the bot owner to add your Telegram user ID in the admin dashboard."
        )
        logger.warning("user=%s action=blocked reason=not_allowed", user.id)
        return

    url = text
    status_msg = await update.message.reply_text("🔍 Scanning...")

    cached = cache_store.get_cached(url)
    if cached is not None:
        result = ScanResult(**cached)
        await status_msg.edit_text(_format_result(result), parse_mode="Markdown", disable_web_page_preview=True)
        logger.info("user=%s url=%s verdict=%s source=cache", user.id, url, result.verdict)
        return

    provider = context.bot_data["provider"]

    try:
        result = await provider.scan_url(url)
    except DailyQuotaExceeded as exc:
        await status_msg.edit_text(f"⏳ {exc}")
        logger.warning("user=%s url=%s error=daily_quota", user.id, url)
        return
    except RateLimitError as exc:
        await status_msg.edit_text(f"⏳ {exc}. Please try again in a minute.")
        logger.warning("user=%s url=%s error=rate_limit", user.id, url)
        return
    except ProviderError as exc:
        await status_msg.edit_text(f"⚠️ Scan failed: {exc}")
        logger.error("user=%s url=%s error=%s", user.id, url, exc)
        return
    except Exception as exc:  # never leave the user without a reply on an unexpected failure
        await status_msg.edit_text("⚠️ Unexpected error while scanning. Please try again later.")
        logger.error("user=%s url=%s unexpected_error=%s", user.id, url, exc, exc_info=True)
        return

    cache_store.set_cached(url, result.__dict__)
    usage_store.log_scan(user.id, user.username or user.full_name, url, result.verdict)
    await status_msg.edit_text(_format_result(result), parse_mode="Markdown", disable_web_page_preview=True)
    logger.info("user=%s url=%s verdict=%s source=live", user.id, url, result.verdict)
