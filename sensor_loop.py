"""
Sensor monitoring loop.
Runs in background thread to detect entry/exit passages and NFC tags.
"""

import logging
import time
from datetime import datetime
from sensors import SensorMonitor
from models import SystemState
from events import save_entry_exit_event
from firebase import is_firebase_initialized

log = logging.getLogger(__name__)


def post_nfc_command_to_firebase(armed: bool):
    """Post NFC state change to Firebase as a command."""
    if not is_firebase_initialized():
        log.debug("Firebase not initialized - NFC sync skipped")
        return

    try:
        from firebase_admin import db

        cmd_id = str(int(time.time() * 1000))
        db.reference(f"commands/{cmd_id}").set({
            "type": "set_armed",
            "value": armed,
            "source": "nfc",
            "timestamp": datetime.now().isoformat(),
            "status": "completed",
            "response": f"System {'armed' if armed else 'disarmed'} via NFC"
        })
        log.info(f"NFC state synced to Firebase (armed={armed})")

    except Exception as e:
        log.error(f"Firebase sync error: {e}")


def sensor_monitor_loop(state: SystemState):
    """Monitor sensors for entry/exit detection and NFC tags."""
    monitor = SensorMonitor()
    log.info("Sensor monitor started")

    def on_entry():
        if state.armed:
            save_entry_exit_event(state, "entry")

    def on_exit():
        if state.armed:
            save_entry_exit_event(state, "exit")

    def on_nfc_change(armed: bool):
        """Handle NFC tag detection and system state sync."""
        log.warning(f"NFC tag detected: system {'arming' if armed else 'disarming'}")

        state.set_armed(armed)
        monitor.set_led_armed(armed)
        post_nfc_command_to_firebase(armed)

    while True:
        try:
            monitor.detect_passage(
                on_entry_callback=on_entry,
                on_exit_callback=on_exit,
                on_nfc_change_callback=on_nfc_change
            )
            time.sleep(0.05)
        except Exception as e:
            log.error(f"Sensor monitor error: {e}")
            time.sleep(1)
