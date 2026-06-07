"""
Audio processing bricks: KeywordSpotting and AudioClassification.
"""

import logging
from arduino.app_bricks.keyword_spotting import KeywordSpotting
from arduino.app_bricks.audio_classification import AudioClassification
from arduino.app_peripherals.microphone import Microphone
from config import WS_AUDIO_PORT, SAMPLE_RATE, CHANNELS, CONFIDENCE, DEBOUNCE_SEC
from models import SystemState
from events import on_keyword_detected, on_sound_detected

log = logging.getLogger(__name__)


def setup_audio_bricks(state: SystemState):
    """Setup KeywordSpotting and AudioClassification bricks."""
    log.info("Initializing audio bricks...")

    # Create shared microphone for both bricks
    mic = Microphone(
        device=f"ws://0.0.0.0:{WS_AUDIO_PORT}",
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )

    # KeywordSpotting for "aiuto"
    if state.keyword_spotting_enabled:
        try:
            spotter = KeywordSpotting(mic=mic, confidence=CONFIDENCE, debounce_sec=DEBOUNCE_SEC)

            def on_aiuto():
                on_keyword_detected(state)

            spotter.on_detect("aiuto", on_aiuto)
            log.info("✓ KeywordSpotting configured (keyword: 'aiuto')")
        except Exception as e:
            log.error(f"Failed to setup KeywordSpotting: {e}")

    # AudioClassification for danger sounds
    if state.sound_classification_enabled:
        try:
            classifier = AudioClassification(mic=mic, confidence=CONFIDENCE)

            def make_sound_callback(label: str):
                def callback():
                    on_sound_detected(state, label)
                return callback

            for label in ["crying_baby", "fall", "glass_breaking", "scream"]:
                classifier.on_detect(label, make_sound_callback(label))

            log.info("✓ AudioClassification configured")
        except Exception as e:
            log.error(f"Failed to setup AudioClassification: {e}")

    return mic
