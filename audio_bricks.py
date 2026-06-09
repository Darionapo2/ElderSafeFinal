"""
Audio processing bricks: KeywordSpotting only.
"""

import logging
import threading
import time
from arduino.app_bricks.keyword_spotting import KeywordSpotting
from arduino.app_peripherals.microphone import Microphone
from config import WS_AUDIO_PORT, SAMPLE_RATE, CHANNELS, CONFIDENCE, DEBOUNCE_SEC
from models import SystemState
from events import on_keyword_detected

log = logging.getLogger(__name__)


def activate_alarm_buzzer(duration_seconds: int = 3):
    """Activate buzzer alarm for specified duration."""
    try:
        from sensors import SensorMonitor
        monitor = SensorMonitor()

        def buzzer_thread():
            try:
                monitor.beep_alarm()
                time.sleep(duration_seconds)
                log.info("Alarm buzzer deactivated")
            except Exception as e:
                log.error(f"Error with alarm buzzer: {e}")

        thread = threading.Thread(target=buzzer_thread, daemon=True)
        thread.start()
        log.info(f"Alarm buzzer activated for {duration_seconds} seconds")
    except Exception as e:
        log.error(f"Failed to activate alarm buzzer: {e}")


def setup_audio_bricks(state: SystemState):
    """Initialize audio processing bricks."""
    log.info("Initializing audio bricks")

    mic = Microphone(
        device=f"ws://0.0.0.0:{WS_AUDIO_PORT}",
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )

    try:
        spotter = KeywordSpotting(mic=mic, confidence=CONFIDENCE, debounce_sec=DEBOUNCE_SEC)

        def on_aiuto():
            if state.keyword_spotting_enabled:
                log.warning("KEYWORD DETECTED: 'aiuto' - ACTIVATING ALARM")
                on_keyword_detected(state)
                activate_alarm_buzzer(duration_seconds=3)
            else:
                log.debug("Keyword 'aiuto' detected but keyword spotting disabled")

        spotter.on_detect("aiuto", on_aiuto)
        log.info("KeywordSpotting brick configured")
    except Exception as e:
        log.error(f"KeywordSpotting initialization failed: {e}")

    return mic
