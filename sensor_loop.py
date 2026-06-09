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
from firebase import is_firebase_initialized, push_status_now

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


def sensor_monitor_loop(state: SystemState, absence_tracker=None):
    """Monitor sensors for entry/exit detection and NFC tags.

    The absence_tracker (Detector B) is notified on every entry/exit so the
    dashboard clock and overdue-return logic stay in sync. Tracking runs even
    when the system is disarmed; only event logging is gated by armed state.
    """
    monitor = SensorMonitor()
    log.info("Sensor monitor started")

    def on_entry():
        # Always close an open absence so the clock never gets stuck, even if the
        # person returns while the system is disarmed.
        if absence_tracker:
            absence_tracker.on_entry()
        if state.armed:
            save_entry_exit_event(state, "entry")

    def on_exit():
        # Only open a new absence while armed (when exits are actually logged).
        if state.armed:
            save_entry_exit_event(state, "exit")
            if absence_tracker:
                absence_tracker.on_exit()

    def on_nfc_change(armed: bool):
        """Handle NFC tag detection and system state sync."""
        log.warning(f"NFC tag detected: system {'arming' if armed else 'disarming'}")

        state.set_armed(armed)
        state.set_keyword_spotting(armed)
        state.set_anomaly_detection(armed)
        monitor.set_led_armed(armed)
        push_status_now(state)
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
