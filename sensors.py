"""
Sensor interface via Arduino Bridge.
Reads Reed switch, PIR sensor, and system armed state.
"""

import logging
import time
from arduino.app_utils import Bridge

log = logging.getLogger(__name__)

DEBOUNCE_MS = 3000
PIR_DEBOUNCE_MS = 5000


class SensorMonitor:
    def __init__(self):
        self.prev_reed = None
        self.prev_pir = None
        self.prev_nfc_armed = None  # Track NFC state for changes
        self.last_pir_ms = None
        self.start_time = time.time()

        # Event sequencing (reed/pir timing)
        self.reed_triggered_ms = None  # Timestamp when reed was triggered
        self.pir_triggered_ms = None   # Timestamp when pir was triggered
        self.event_timeout_ms = 3000   # Max 3 seconds between reed and pir

    def now_ms(self):
        return int((time.time() - self.start_time) * 1000)

    def get_reed_state(self):
        try:
            state = Bridge.call("get_reed_state")
            return int(state) if state is not None else None
        except Exception as e:
            log.error(f"Reed state read failed: {e}")
            return None

    def get_pir_state(self):
        try:
            state = Bridge.call("get_pir_state")
            return int(state) if state is not None else None
        except Exception as e:
            log.error(f"PIR state read failed: {e}")
            return None

    def get_system_armed(self):
        try:
            state = Bridge.call("get_system_armed")
            return int(state) if state is not None else 0
        except Exception as e:
            log.error(f"Armed state read failed: {e}")
            return 0

    def get_nfc_armed(self):
        """Read NFC armed state from MCU RFID reader."""
        try:
            state = Bridge.call("get_nfc_armed")
            return int(state) if state is not None else 0
        except Exception as e:
            log.error(f"NFC armed state read failed: {e}")
            return 0

    def set_system_armed(self, armed: bool):
        """Control system armed state and update MCU."""
        try:
            Bridge.call("set_system_armed", 1 if armed else 0)
            log.info(f"System {'armed' if armed else 'disarmed'}")
        except Exception as e:
            log.error(f"Failed to set armed state: {e}")

    def set_led_green(self, state: int):
        """Control green LED."""
        try:
            Bridge.call("set_led_green", state)
            log.debug(f"Green LED: {'on' if state else 'off'}")
        except Exception as e:
            log.error(f"Failed to set green LED: {e}")

    def set_led_red(self, state: int):
        """Control red LED."""
        try:
            Bridge.call("set_led_red", state)
            log.debug(f"Red LED: {'on' if state else 'off'}")
        except Exception as e:
            log.error(f"Failed to set red LED: {e}")

    def set_led_armed(self, armed: bool):
        """Update LED status to match system state."""
        try:
            if armed:
                Bridge.call("set_led_green", 1)
                Bridge.call("set_led_red", 0)
            else:
                Bridge.call("set_led_green", 0)
                Bridge.call("set_led_red", 1)
            log.debug(f"LED updated: {'green (armed)' if armed else 'red (disarmed)'}")
        except Exception as e:
            log.error(f"Failed to update LED: {e}")

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

        if self.prev_pir is not None and self.prev_pir != pir:
            state_text = "motion detected" if pir == 1 else "no motion"
            log.info(f"PIR: {state_text}")

        if self.prev_nfc_armed is not None and self.prev_nfc_armed != nfc_armed:
            log.warning(f"NFC tag detected: system {'armed' if nfc_armed else 'disarmed'}")
            if on_nfc_change_callback:
                on_nfc_change_callback(bool(nfc_armed))
            self.set_led_armed(bool(nfc_armed))

        reed_triggered = (self.prev_reed is not None and self.prev_reed == 0 and reed == 1)

        pir_raw = (self.prev_pir is not None and self.prev_pir == 0 and pir == 1)
        pir_triggered = pir_raw and (self.last_pir_ms is None or (t - self.last_pir_ms) > PIR_DEBOUNCE_MS)

        if pir_triggered:
            self.last_pir_ms = t

        if reed_triggered:
            self.reed_triggered_ms = t
            log.debug(f"Reed triggered at {t}ms")

        if pir_triggered and self.reed_triggered_ms is not None:
            time_since_reed = t - self.reed_triggered_ms
            if time_since_reed <= self.event_timeout_ms:
                log.info(f"Entry detected (Reed->PIR in {time_since_reed}ms)")
                if on_entry_callback:
                    on_entry_callback()
                self.beep_entry()
                self.reed_triggered_ms = None
            else:
                log.debug(f"Reed-PIR timeout: {time_since_reed}ms elapsed")

        if pir_triggered:
            self.pir_triggered_ms = t
            log.debug(f"PIR triggered at {t}ms")

        if reed_triggered and self.pir_triggered_ms is not None:
            time_since_pir = t - self.pir_triggered_ms
            if time_since_pir <= self.event_timeout_ms:
                log.info(f"Exit detected (PIR->Reed in {time_since_pir}ms)")
                if on_exit_callback:
                    on_exit_callback()
                self.beep_exit()
                self.pir_triggered_ms = None
            else:
                log.debug(f"PIR-Reed timeout: {time_since_pir}ms elapsed")

        if self.reed_triggered_ms is not None and (t - self.reed_triggered_ms) > self.event_timeout_ms:
            self.reed_triggered_ms = None

        if self.pir_triggered_ms is not None and (t - self.pir_triggered_ms) > self.event_timeout_ms:
            self.pir_triggered_ms = None

        self.prev_reed = reed
        self.prev_pir = pir
        self.prev_nfc_armed = nfc_armed
