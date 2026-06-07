"""
Firebase command listener.
Arduino listens for control commands from Firebase.
"""

import logging
import json
import os
from firebase_admin import db
from models import SystemState

log = logging.getLogger(__name__)


def setup_firebase_listener(state: SystemState):
    """Setup Firebase listener for control commands."""
    try:
        ref = db.reference("commands")

        def on_commands_change(message):
            """Called when commands change in Firebase."""
            try:
                data = message.data
                if not data:
                    return

                if "armed" in data:
                    state.set_armed(bool(data["armed"]))
                    log.info(f"Firebase command: armed = {data['armed']}")

                if "keyword_spotting" in data:
                    state.set_keyword_spotting(bool(data["keyword_spotting"]))
                    log.info(f"Firebase command: keyword_spotting = {data['keyword_spotting']}")

                if "anomaly_detection" in data:
                    state.set_anomaly_detection(bool(data["anomaly_detection"]))
                    log.info(f"Firebase command: anomaly_detection = {data['anomaly_detection']}")

            except Exception as e:
                log.error(f"Error processing Firebase command: {e}")

        ref.listen(on_commands_change)
        log.info("Firebase command listener started")

    except Exception as e:
        log.error(f"Failed to setup Firebase listener: {e}")


def publish_command(key: str, value: bool):
    """Publish a command to Firebase."""
    try:
        ref = db.reference(f"commands/{key}")
        ref.set(value)
        log.debug(f"Published command: {key} = {value}")
    except Exception as e:
        log.error(f"Failed to publish command: {e}")


def publish_status(status_dict: dict):
    """Publish system status to Firebase."""
    try:
        ref = db.reference("status")
        ref.set(status_dict)
        log.debug(f"Published status to Firebase")
    except Exception as e:
        log.error(f"Failed to publish status: {e}")
