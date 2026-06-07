#!/usr/bin/env python3
"""
main_test1.py - Minimal test for KeywordSpotting + AudioClassification
Tests only the audio bricks with WebSocket microphone.
"""

import logging
from arduino.app_bricks.keyword_spotting import KeywordSpotting
from arduino.app_bricks.audio_classification import AudioClassification
from arduino.app_peripherals.microphone import Microphone
from arduino.app_utils import App

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

# Configuration
WS_PORT = 8080
SAMPLE_RATE = 16000
CHANNELS = 1
CONFIDENCE = 0.80
DEBOUNCE_SEC = 2.0


def main():
    log.info("=" * 70)
    log.info("ElderSafeFinal - Test 1: KeywordSpotting + AudioClassification")
    log.info("=" * 70)

    # Create microphone with WebSocket
    log.info(f"\nStarting WebSocket Microphone on ws://0.0.0.0:{WS_PORT}")
    mic = Microphone(
        device=f"ws://0.0.0.0:{WS_PORT}",
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )

    # Setup KeywordSpotting for "aiuto"
    log.info("\n▶ Setting up KeywordSpotting (keyword: 'aiuto')...")
    try:
        spotter = KeywordSpotting(mic=mic, confidence=CONFIDENCE, debounce_sec=DEBOUNCE_SEC)

        def on_aiuto():
            log.warning("🔴 KEYWORD 'aiuto' DETECTED!")

        spotter.on_detect("aiuto", on_aiuto)
        log.info("✓ KeywordSpotting configured")
    except Exception as e:
        log.error(f"✗ KeywordSpotting failed: {e}")

    # Setup AudioClassification for danger sounds
    log.info("\n▶ Setting up AudioClassification...")
    try:
        classifier = AudioClassification(mic=mic, confidence=CONFIDENCE)

        def make_sound_handler(label: str):
            def handler():
                log.warning(f"🔴 SOUND DETECTED: '{label}'")
            return handler

        for label in ["crying_baby", "fall", "glass_breaking", "scream"]:
            classifier.on_detect(label, make_sound_handler(label))

        log.info("✓ AudioClassification configured")
        log.info("  Labels: crying_baby, fall, glass_breaking, scream")
    except Exception as e:
        log.error(f"✗ AudioClassification failed: {e}")

    # Start
    log.info("\n" + "=" * 70)
    log.info("🟢 Ready to receive audio via WebSocket")
    log.info("=" * 70)
    log.info("\nTo test:")
    log.info(f"  python client_mic.py --ip localhost --port {WS_PORT}")
    log.info("\nPress Ctrl+C to stop\n")

    App.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n✓ Test stopped")
