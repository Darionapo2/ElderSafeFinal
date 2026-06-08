"""
Audio processing bricks: KeywordSpotting only.
"""

import logging
from arduino.app_bricks.keyword_spotting import KeywordSpotting
from arduino.app_peripherals.microphone import Microphone
from config import WS_AUDIO_PORT, SAMPLE_RATE, CHANNELS, CONFIDENCE, DEBOUNCE_SEC
from models import SystemState
from events import on_keyword_detected

log = logging.getLogger(__name__)


def setup_audio_bricks(state: SystemState):
    """Setup KeywordSpotting brick."""
    log.info("Initializing audio bricks...")

    mic = Microphone(
        device=f"ws://0.0.0.0:{WS_AUDIO_PORT}",
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )

    try:
        spotter = KeywordSpotting(mic=mic, confidence=CONFIDENCE, debounce_sec=DEBOUNCE_SEC)

        # Callback checks state BEFORE processing
        # This allows enabling/disabling via command
        def on_aiuto():
            if state.keyword_spotting_enabled:
                on_keyword_detected(state)
            else:
                log.debug("Keyword 'aiuto' detected but keyword_spotting disabled - ignoring")

        spotter.on_detect("aiuto", on_aiuto)
        log.info("KeywordSpotting configured (can be toggled via command)")
    except Exception as e:
        log.error(f"KeywordSpotting setup failed: {e}")

    return mic
