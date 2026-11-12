"""
credentials_store.py — Telegram bot token and VirusTotal API key, stored in
DATA_DIR/credentials.json (0600) and set from the dashboard.

Key-value on purpose: a future second threat-intel provider just adds
another key (see bot/providers/base.py for the provider interface).
"""
from .json_store import lock, read_json, write_json
from .paths import CREDENTIALS_PATH

TELEGRAM_SERVICE = "telegram_bot_token"
VIRUSTOTAL_SERVICE = "virustotal_api_key"


def get_credential(service: str) -> str:
    return read_json(CREDENTIALS_PATH, {}).get(service, "")


def set_credential(service: str, value: str) -> None:
    with lock:
        credentials = read_json(CREDENTIALS_PATH, {})
        credentials[service] = value
        write_json(CREDENTIALS_PATH, credentials)


def get_telegram_token() -> str:
    return get_credential(TELEGRAM_SERVICE)


def get_virustotal_key() -> str:
    return get_credential(VIRUSTOTAL_SERVICE)


def set_telegram_token(value: str) -> None:
    set_credential(TELEGRAM_SERVICE, value)


def set_virustotal_key(value: str) -> None:
    set_credential(VIRUSTOTAL_SERVICE, value)


def mask_secret(value: str) -> str:
    """Render a secret as bullets with only the last 4 characters visible, e.g. ••••••1234."""
    if not value:
        return ""
    tail = value[-4:] if len(value) > 4 else value
    hidden_count = max(len(value) - len(tail), 6)
    return ("•" * hidden_count) + tail
