#!/usr/bin/env python3
"""
main_test_keyword_only.py - Test KeywordSpotting only
"""

import logging
from arduino.app_bricks.keyword_spotting import KeywordSpotting
from arduino.app_peripherals.microphone import Microphone
from arduino.app_utils import App

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

WS_PORT = 8080
SAMPLE_RATE = 16000
CONFIDENCE = 0.80
DEBOUNCE_SEC = 1.0

log.info(f"Starting WebSocket Microphone on ws://0.0.0.0:{WS_PORT}")
mic = Microphone(
    device=f"ws://0.0.0.0:{WS_PORT}",
    sample_rate=SAMPLE_RATE
)

def on_aiuto():
    log.warning("KEYWORD 'aiuto' DETECTED!")

log.info("Setting up KeywordSpotting")
spotter = KeywordSpotting(mic=mic, confidence=CONFIDENCE, debounce_sec=DEBOUNCE_SEC)
spotter.on_detect("aiuto", on_aiuto)
log.info("KeywordSpotting configured")

log.info("\n" + "=" * 70)
log.info("Ready to receive audio via WebSocket")
log.info("=" * 70)
log.info("\nTo test with RAW mode:")
log.info(f"  python ../client_mic.py --ip localhost --port {WS_PORT} --raw")
log.info("\nPress Ctrl+C to stop\n")

App.run()
