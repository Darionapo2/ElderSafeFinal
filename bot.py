#!/usr/bin/env python3
"""
ElderSafeFinal Telegram Bot
Polls Telegram for commands and sends them to Arduino via Firebase.
Can run on any machine (RPi, laptop, cloud).
"""

import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    log.error("firebase-admin not installed")

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
FIREBASE_CREDS = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
FIREBASE_DB_URL = os.getenv("FIREBASE_DATABASE_URL", "")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    log.error("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
    exit(1)

if not FIREBASE_AVAILABLE or not FIREBASE_CREDS or not FIREBASE_DB_URL:
    log.error("Firebase must be configured (firebase-admin, credentials, DB URL)")
    exit(1)

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CREDS)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

log.info(f"✓ Firebase initialized")
log.info(f"✓ Telegram bot token loaded")


def send_telegram_message(text: str):
    """Send message to Telegram chat."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5
        )
        log.debug(f"Message sent to Telegram")
    except Exception as e:
        log.error(f"Failed to send Telegram message: {e}")


def get_firebase_status() -> dict:
    """Get system status from Firebase."""
    try:
        status = db.reference("status").get().val()
        return status if status else {}
    except Exception as e:
        log.error(f"Failed to read status from Firebase: {e}")
        return {}


def format_status_message(status: dict) -> str:
    """Format status as readable message."""
    if not status:
        return "❌ Sistema non disponibile"

    armed_status = "🟢 ATTIVO" if status.get("armed") else "🔴 DISATTIVATO"
    keyword_status = "✓" if status.get("keyword_spotting") else "✗"
    anomaly_status = "✓" if status.get("anomaly_detection") else "✗"

    return f"""
📊 Status Sistema:

{armed_status}

Keyword Spotting: {keyword_status}
Anomaly Detection: {anomaly_status}

Ultimi Eventi:
• Totali: {status.get('total_events', 0)}
• Entrate: {status.get('entries', 0)}
• Uscite: {status.get('exits', 0)}
• Allarmi: {status.get('alarms', 0)}

⏱️ Ultimo aggiornamento: {status.get('last_update', 'N/A')}
"""


def send_firebase_command(cmd_type: str, value: bool, timeout: int = 5) -> str:
    """
    Send command via Firebase and wait for response.

    Returns response from Arduino or timeout message.
    """
    try:
        cmd_id = str(int(time.time() * 1000))

        # Write command to Firebase
        db.reference(f"commands/{cmd_id}").set({
            "type": cmd_type,
            "value": value,
            "source": "telegram",
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        })

        log.info(f"Command {cmd_id} sent: {cmd_type} = {value}")

        # Wait for response (poll Firebase)
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                cmd = db.reference(f"commands/{cmd_id}").get().val()
                if cmd:
                    status = cmd.get("status")
                    if status == "completed":
                        response = cmd.get("response", "Comando eseguito")
                        return f"✓ {response}"
                    elif status == "failed":
                        error = cmd.get("error", "Errore sconosciuto")
                        return f"✗ Errore: {error}"
            except Exception as e:
                log.debug(f"Error reading command response: {e}")

            time.sleep(0.2)  # Poll every 200ms

        return "⏱️ Timeout: Arduino non ha risposto (comando potrebbe essere in esecuzione)"

    except Exception as e:
        log.error(f"Failed to send Firebase command: {e}")
        return f"✗ Errore: {str(e)}"


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
/enable_keyword - Abilita keyword spotting
/disable_keyword - Disabilita keyword spotting
/enable_anomaly - Abilita anomaly detection
/disable_anomaly - Disabilita anomaly detection
"""

    elif command == "/status":
        status = get_firebase_status()
        return format_status_message(status)

    elif command in ["/arm", "/enable"]:
        response = send_firebase_command("set_armed", True)
        return response

    elif command in ["/disarm", "/disable"]:
        response = send_firebase_command("set_armed", False)
        return response

    elif command == "/enable_keyword":
        response = send_firebase_command("set_keyword_spotting", True)
        return response

    elif command == "/disable_keyword":
        response = send_firebase_command("set_keyword_spotting", False)
        return response

    elif command == "/enable_anomaly":
        response = send_firebase_command("set_anomaly_detection", True)
        return response

    elif command == "/disable_anomaly":
        response = send_firebase_command("set_anomaly_detection", False)
        return response

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
    log.info("Mode: Firebase commands")
    log.info("Polling Telegram for commands...")
    log.info("=" * 70)

    try:
        poll_telegram()
    except KeyboardInterrupt:
        log.info("\n✓ Bot stopped")
