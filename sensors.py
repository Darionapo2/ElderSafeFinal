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
        self.prev_nfc_armed = None  # Track NFC state for changes
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

    def get_nfc_armed(self):
        """Read NFC armed state (from MCU RFID reader)."""
        try:
            state = Bridge.call("get_nfc_armed")
            return int(state) if state is not None else 0
        except Exception as e:
            log.error(f"Error reading NFC armed state: {e}")
            return 0

    def set_system_armed(self, armed: bool):
        """Control system armed state (affects LEDs and MCU state)."""
        try:
            Bridge.call("set_system_armed", 1 if armed else 0)
            log.info(f"System {'ARMED' if armed else 'DISARMED'} via Firebase")
        except Exception as e:
            log.error(f"Error setting armed state: {e}")

    def set_led_green(self, state: int):
        """Control green LED directly."""
        try:
            Bridge.call("set_led_green", state)
            log.debug(f"LED GREEN: {'ON' if state else 'OFF'}")
        except Exception as e:
            log.error(f"Error setting green LED: {e}")

    def set_led_red(self, state: int):
        """Control red LED directly."""
        try:
            Bridge.call("set_led_red", state)
            log.debug(f"LED RED: {'ON' if state else 'OFF'}")
        except Exception as e:
            log.error(f"Error setting red LED: {e}")

    def set_led_armed(self, armed: bool):
        """Update LED status to match system state."""
        try:
            if armed:
                Bridge.call("set_led_green", 1)
                Bridge.call("set_led_red", 0)
            else:
                Bridge.call("set_led_green", 0)
                Bridge.call("set_led_red", 1)
            log.debug(f"LED updated: {'🟢 GREEN (armed)' if armed else '🔴 RED (disarmed)'}")
        except Exception as e:
            log.error(f"Error updating LED: {e}")

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

    def detect_passage(self, on_entry_callback=None, on_exit_callback=None, on_nfc_change_callback=None):
        """
        Detect entry/exit by monitoring reed + PIR.
        Reed first → entry, PIR first → exit.
        Also detect NFC tag changes and sync to Firebase.
        """
        reed = self.get_reed_state()
        pir = self.get_pir_state()
        nfc_armed = self.get_nfc_armed()

        if reed is None or pir is None:
            return

        t = self.now_ms()

        # ── Detect NFC state change ────────────────────────────────────────────
        if self.prev_nfc_armed is not None and self.prev_nfc_armed != nfc_armed:
            log.warning(f"🏷️  NFC TAG DETECTED: System now {'ARMED' if nfc_armed else 'DISARMED'}")
            if on_nfc_change_callback:
                on_nfc_change_callback(bool(nfc_armed))
            # Update LEDs immediately
            self.set_led_armed(bool(nfc_armed))

        # ── Detect entry/exit ──────────────────────────────────────────────────
        reed_triggered = (self.prev_reed is not None and self.prev_reed == 0 and reed == 1)
        pir_raw = (self.prev_pir is not None and self.prev_pir == 0 and pir == 1)
        pir_triggered = pir_raw and (self.last_pir_ms is None or (t - self.last_pir_ms) > PIR_DEBOUNCE_MS)

        if pir_triggered:
            self.last_pir_ms = t

        if reed_triggered:
            if self.prev_pir == 0:
                log.info("🚪 Reed first (ENTRY)")
                if on_entry_callback:
                    on_entry_callback()
                self.beep_entry()
            elif pir_triggered:
                log.info("🚪 Reed after PIR (ENTRY)")
                if on_entry_callback:
                    on_entry_callback()
                self.beep_entry()

        if pir_triggered and self.prev_reed == 0:
            log.info("👋 PIR first (EXIT)")
            if on_exit_callback:
                on_exit_callback()
            self.beep_exit()

        self.prev_reed = reed
        self.prev_pir = pir
        self.prev_nfc_armed = nfc_armed
