"""
Sensor interface via Arduino Bridge.
Reads Reed switch, PIR sensor, and system armed state.
"""

import logging
import time
from arduino.app_utils import Bridge

log = logging.getLogger(__name__)

DEBOUNCE_MS = 500
PIR_DEBOUNCE_MS = 2000


class SensorMonitor:
    def __init__(self):
        self.prev_reed = None
        self.prev_pir = None
        self.last_pir_ms = None
        self.start_time = time.time()

    def now_ms(self):
        return int((time.time() - self.start_time) * 1000)

    def get_reed_state(self):
        try:
            state = Bridge.call("get_reed_state")
            return int(state) if state is not None else None
        except Exception as e:
            log.error(f"Error reading reed state: {e}")
            return None

    def get_pir_state(self):
        try:
            state = Bridge.call("get_pir_state")
            return int(state) if state is not None else None
        except Exception as e:
            log.error(f"Error reading PIR state: {e}")
            return None

    def get_system_armed(self):
        try:
            state = Bridge.call("get_system_armed")
            return int(state) if state is not None else 0
        except Exception as e:
            log.error(f"Error reading armed state: {e}")
            return 0

    def beep_entry(self):
        try:
            Bridge.call("beep_entry")
        except Exception as e:
            log.error(f"Error beeping entry: {e}")

    def beep_exit(self):
        try:
            Bridge.call("beep_exit")
        except Exception as e:
            log.error(f"Error beeping exit: {e}")

    def beep_alarm(self):
        try:
            Bridge.call("beep_alarm")
        except Exception as e:
            log.error(f"Error beeping alarm: {e}")

    def detect_passage(self, on_entry_callback=None, on_exit_callback=None):
        """
        Detect entry/exit by monitoring reed + PIR.
        Reed first → entry, PIR first → exit.
        """
        reed = self.get_reed_state()
        pir = self.get_pir_state()

        if reed is None or pir is None:
            return

        t = self.now_ms()

        reed_triggered = (self.prev_reed is not None and self.prev_reed == 0 and reed == 1)
        pir_raw = (self.prev_pir is not None and self.prev_pir == 0 and pir == 1)
        pir_triggered = pir_raw and (self.last_pir_ms is None or (t - self.last_pir_ms) > PIR_DEBOUNCE_MS)

        if pir_triggered:
            self.last_pir_ms = t

        if reed_triggered:
            if self.prev_pir == 0:
                log.info("Reed first (ENTRY)")
                if on_entry_callback:
                    on_entry_callback()
                self.beep_entry()
            elif pir_triggered:
                log.info("Reed after PIR (ENTRY)")
                if on_entry_callback:
                    on_entry_callback()
                self.beep_entry()

        if pir_triggered and self.prev_reed == 0:
            log.info("PIR first (EXIT)")
            if on_exit_callback:
                on_exit_callback()
            self.beep_exit()

        self.prev_reed = reed
        self.prev_pir = pir
