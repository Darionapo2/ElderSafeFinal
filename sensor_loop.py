"""
Sensor monitoring loop.
Runs in background thread to detect entry/exit passages.
"""

import logging
import time
from sensors import SensorMonitor
from models import SystemState
from events import save_entry_exit_event

log = logging.getLogger(__name__)


def sensor_monitor_loop(state: SystemState):
    """Background thread: monitor sensors for entry/exit detection."""
    monitor = SensorMonitor()
    log.info("Sensor monitor started")

    def on_entry():
        if state.armed:
            save_entry_exit_event(state, "entry")

    def on_exit():
        if state.armed:
            save_entry_exit_event(state, "exit")

    while True:
        try:
            monitor.detect_passage(
                on_entry_callback=on_entry,
                on_exit_callback=on_exit
            )
            time.sleep(0.05)
        except Exception as e:
            log.error(f"Sensor monitor error: {e}")
            time.sleep(1)
