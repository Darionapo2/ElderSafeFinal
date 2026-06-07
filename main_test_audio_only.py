#!/usr/bin/env python3
"""
main_test_audio_only.py - Test ONLY AudioClassification
Minimal linear code without function wrappers.
"""

import logging
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
CONFIDENCE = 0.80

# Create microphone with WebSocket
log.info(f"\nStarting WebSocket Microphone on ws://0.0.0.0:{WS_PORT}")
mic = Microphone(
    device=f"ws://0.0.0.0:{WS_PORT}",
    sample_rate=SAMPLE_RATE
)

# Setup AudioClassification
log.info("\n▶ Setting up AudioClassification...")
classifier = AudioClassification(mic=mic, confidence=CONFIDENCE)

def make_sound_handler(label: str):
    def handler():
        log.warning(f"🔴 SOUND DETECTED: '{label}'")
    return handler

labels = ["crying_baby", "fall", "glass_breaking", "scream"]
for label in labels:
    classifier.on_detect(label, make_sound_handler(label))

log.info("✓ AudioClassification configured")
log.info(f"  Labels: {', '.join(labels)}")

# Start
log.info("\n" + "=" * 70)
log.info("🟢 Ready to receive audio via WebSocket")
log.info("=" * 70)
log.info("\nTo test (RAW mode recommended):")
log.info(f"  python ../client_mic.py --ip localhost --port {WS_PORT} --raw")
log.info("\nPress Ctrl+C to stop\n")

App.run()
