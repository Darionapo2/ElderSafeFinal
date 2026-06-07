"""
Telegram Bot API integration for alerts.
"""

import logging
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)


def is_configured():
    """Check if Telegram is properly configured."""
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def send_alert(alert_type: str, message: str, details: str = ""):
    """Send alert to Telegram."""
    if not is_configured():
        log.warning("Telegram not configured, skipping alert")
        return

    text = f"🚨 {alert_type}\n{message}"
    if details:
        text += f"\n\n{details}"

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5
        )
        log.info(f"✓ Telegram alert sent: {alert_type}")
    except Exception as e:
        log.error(f"Failed to send Telegram alert: {e}")


def send_message(text: str):
    """Send plain message to Telegram."""
    if not is_configured():
        log.warning("Telegram not configured, skipping message")
        return

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5
        )
    except Exception as e:
        log.error(f"Failed to send Telegram message: {e}")
