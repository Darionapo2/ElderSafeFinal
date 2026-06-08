#!/usr/bin/env python3
"""
ElderSafeFinal Telegram Bot.
Polls Telegram for commands and sends them to Arduino via Firebase.
Can run on any machine (RPi, laptop, cloud).
"""

import os
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# Configuration from environment
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FIREBASE_DB_URL = os.getenv("FIREBASE_DATABASE_URL")

# Build Firebase credentials from environment variables
firebase_creds_dict = {
    "type": os.getenv("FIREBASE_TYPE", "service_account"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
}

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(firebase_creds_dict)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})

log.info("ElderSafeFinal Telegram Bot initialized")


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
        log.error(f"Telegram message send failed: {e}")


def get_firebase_status() -> dict:
    """Get system status from Firebase."""
    try:
        snapshot = db.reference("status").get()
        if snapshot is None:
            log.warning("Status not yet available in Firebase")
            return {}
        status = snapshot.val()
        return status if status else {}
    except Exception as e:
        log.error(f"Firebase status read failed: {e}")
        return {}


def format_status_message(status: dict) -> str:
    """Format status as readable message."""
    if not status:
        return "System unavailable"

    armed_status = "armed" if status.get("armed") else "disarmed"
    keyword_status = "on" if status.get("keyword_spotting") else "off"
    anomaly_status = "on" if status.get("anomaly_detection") else "off"

    return f"""
System Status:

Armed: {armed_status}

Keyword Spotting: {keyword_status}
Anomaly Detection: {anomaly_status}

Recent Events:
Total: {status.get('total_events', 0)}
Entries: {status.get('entries', 0)}
Exits: {status.get('exits', 0)}
Alarms: {status.get('alarms', 0)}

Last update: {status.get('last_update', 'N/A')}
"""


def send_firebase_command(cmd_type: str, value: bool, timeout: int = 15) -> str:
    """Send command via Firebase and wait for Arduino response."""
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

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                snapshot = db.reference(f"commands/{cmd_id}").get()
                cmd = snapshot.val() if snapshot else None

                if cmd:
                    status = cmd.get("status")
                    if status == "completed":
                        response = cmd.get("response", "Command executed")
                        return f"OK: {response}"
                    elif status == "failed":
                        error = cmd.get("response", "Unknown error")
                        return f"Error: {error}"
            except Exception as e:
                log.debug(f"Command response read failed: {e}")

            time.sleep(0.5)

        return "Timeout: Arduino did not respond within 15 seconds"

    except Exception as e:
        log.error(f"Firebase command send failed: {e}")
        return f"Error: {str(e)}"


def process_command(message: str) -> str:
    """Process user command and return response."""
    command = message.lower().strip()

    if command in ["/start", "/help"]:
        return """
ElderSafeFinal Bot

Available commands:
/status - Show system status
/arm - Arm system
/disarm - Disarm system
/enable_keyword - Enable keyword spotting
/disable_keyword - Disable keyword spotting
/enable_anomaly - Enable anomaly detection
/disable_anomaly - Disable anomaly detection
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
        return "Unknown command. Use /help for available commands."


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
            log.error(f"Telegram polling failed: {e}")

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
        log.info("Bot stopped")
