#!/usr/bin/env python3
"""
ElderSafeFinal Telegram Bot - Optional Component
Polls Telegram for commands and sends them to Arduino.
Can run on any machine (RPi, laptop, cloud).
"""

import os
import json
import time
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ARDUINO_IP = os.getenv("ARDUINO_IP", "localhost")
ARDUINO_PORT = os.getenv("ARDUINO_PORT", "8000")

ARDUINO_URL = f"http://{ARDUINO_IP}:{ARDUINO_PORT}"

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    log.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
    exit(1)


def get_arduino_status():
    """Get Arduino system status."""
    try:
        response = requests.get(f"{ARDUINO_URL}/api/status", timeout=5)
        if response.ok:
            return response.json()
    except Exception as e:
        log.warning(f"Failed to get Arduino status: {e}")
    return None


def control_arduino(command: str, value: bool = None):
    """Send control command to Arduino."""
    try:
        payload = {}

        if command == "arm":
            payload = {"armed": True}
        elif command == "disarm":
            payload = {"armed": False}
        elif command == "enable_sound":
            payload = {"sound_classification": True}
        elif command == "disable_sound":
            payload = {"sound_classification": False}
        elif command == "enable_keyword":
            payload = {"keyword_spotting": True}
        elif command == "disable_keyword":
            payload = {"keyword_spotting": False}
        elif command == "enable_anomaly":
            payload = {"anomaly_detection": True}
        elif command == "disable_anomaly":
            payload = {"anomaly_detection": False}

        if not payload:
            return False

        response = requests.post(f"{ARDUINO_URL}/api/control", json=payload, timeout=5)
        return response.ok

    except Exception as e:
        log.error(f"Failed to control Arduino: {e}")
        return False


def send_telegram_message(text: str):
    """Send message to Telegram chat."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5
        )
    except Exception as e:
        log.error(f"Failed to send Telegram message: {e}")


def format_status_message(status: dict) -> str:
    """Format status as readable message."""
    if not status:
        return "❌ Arduino non raggiungibile"

    armed_status = "🟢 ATTIVO" if status.get("armed") else "🔴 DISATTIVATO"
    keyword_status = "✓" if status.get("keyword_spotting") else "✗"
    sound_status = "✓" if status.get("sound_classification") else "✗"
    anomaly_status = "✓" if status.get("anomaly_detection") else "✗"

    return f"""
📊 Status Arduino:

{armed_status}

Keyword Spotting: {keyword_status}
Sound Classification: {sound_status}
Anomaly Detection: {anomaly_status}

Ultimi Eventi:
• Totali: {status.get('total_events', 0)}
• Entrate: {status.get('entries', 0)}
• Uscite: {status.get('exits', 0)}
• Allarmi: {status.get('alarms', 0)}
"""


def process_command(message: str) -> str:
    """Process user command and return response."""
    command = message.lower().strip()

    if command in ["/start", "/help"]:
        return """
🏡 ElderSafeFinal Bot

Comandi disponibili:
/status - Mostra status sistema
/arm - Attiva sistema
/disarm - Disattiva sistema
/enable_sound - Abilita sound classification
/disable_sound - Disabilita sound classification
/enable_keyword - Abilita keyword spotting
/disable_keyword - Disabilita keyword spotting
/enable_anomaly - Abilita anomaly detection
/disable_anomaly - Disabilita anomaly detection
"""

    elif command == "/status":
        status = get_arduino_status()
        return format_status_message(status)

    elif command in ["/arm", "/enable"]:
        if control_arduino("arm"):
            return "✓ Sistema ATTIVATO"
        else:
            return "✗ Errore nell'attivazione"

    elif command in ["/disarm", "/disable"]:
        if control_arduino("disarm"):
            return "✓ Sistema DISATTIVATO"
        else:
            return "✗ Errore nella disattivazione"

    elif command == "/enable_sound":
        if control_arduino("enable_sound"):
            return "✓ Sound classification ABILITATO"
        else:
            return "✗ Errore"

    elif command == "/disable_sound":
        if control_arduino("disable_sound"):
            return "✓ Sound classification DISABILITATO"
        else:
            return "✗ Errore"

    elif command == "/enable_keyword":
        if control_arduino("enable_keyword"):
            return "✓ Keyword spotting ABILITATO"
        else:
            return "✗ Errore"

    elif command == "/disable_keyword":
        if control_arduino("disable_keyword"):
            return "✓ Keyword spotting DISABILITATO"
        else:
            return "✗ Errore"

    elif command == "/enable_anomaly":
        if control_arduino("enable_anomaly"):
            return "✓ Anomaly detection ABILITATO"
        else:
            return "✗ Errore"

    elif command == "/disable_anomaly":
        if control_arduino("disable_anomaly"):
            return "✓ Anomaly detection DISABILITATO"
        else:
            return "✗ Errore"

    else:
        return "❓ Comando non riconosciuto. Usa /help per la lista di comandi."


def poll_telegram():
    """Poll Telegram for new messages."""
    log.info("Starting Telegram bot polling...")

    last_update_id = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            response = requests.get(url, params={"offset": last_update_id}, timeout=30)
            updates = response.json()

            if updates.get("ok"):
                for update in updates.get("result", []):
                    last_update_id = update["update_id"] + 1

                    message = update.get("message", {})
                    chat_id = message.get("chat", {}).get("id")
                    text = message.get("text", "")

                    if text and chat_id:
                        log.info(f"Received command: {text}")
                        response_text = process_command(text)

                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                            json={"chat_id": chat_id, "text": response_text}
                        )

        except Exception as e:
            log.error(f"Polling error: {e}")

        time.sleep(1)


if __name__ == "__main__":
    log.info("=" * 70)
    log.info("ElderSafeFinal Telegram Bot")
    log.info("=" * 70)
    log.info(f"Arduino: {ARDUINO_URL}")
    log.info("Polling Telegram for commands...")
    log.info("=" * 70)

    try:
        poll_telegram()
    except KeyboardInterrupt:
        log.info("\n✓ Bot stopped")
