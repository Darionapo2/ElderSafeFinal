#!/usr/bin/env python3
"""
main_test2.py - Test KeywordSpotting + AudioClassification + REST API
Tests bricks + Flask running together in separate threads.
"""

import logging
import threading
from datetime import datetime
from flask import Flask, jsonify
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
API_PORT = 8000
SAMPLE_RATE = 16000
CHANNELS = 1
CONFIDENCE = 0.80
DEBOUNCE_SEC = 2.0

# Flask app
app = Flask(__name__)


@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
    }), 200


@app.route("/api/test", methods=["GET"])
def test():
    """Test endpoint."""
    return jsonify({
        "message": "ElderSafeFinal Test 2 - Audio Bricks + API",
        "timestamp": datetime.now().isoformat(),
    }), 200


def main():
    log.info("=" * 70)
    log.info("ElderSafeFinal - Test 2: Bricks + REST API")
    log.info("=" * 70)

    # Create microphone with WebSocket
    log.info(f"\nStarting WebSocket Microphone on ws://0.0.0.0:{WS_PORT}")
    mic = Microphone(
        device=f"ws://0.0.0.0:{WS_PORT}",
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )

    # Setup KeywordSpotting
    log.info("\n▶ Setting up KeywordSpotting (keyword: 'aiuto')...")
    try:
        spotter = KeywordSpotting(mic=mic, confidence=CONFIDENCE, debounce_sec=DEBOUNCE_SEC)

        def on_aiuto():
            log.warning("🔴 KEYWORD 'aiuto' DETECTED!")

        spotter.on_detect("aiuto", on_aiuto)
        log.info("✓ KeywordSpotting configured")
    except Exception as e:
        log.error(f"✗ KeywordSpotting failed: {e}")

    # Setup AudioClassification
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
    except Exception as e:
        log.error(f"✗ AudioClassification failed: {e}")

    # Start Flask API in daemon thread
    log.info(f"\n▶ Starting REST API on port {API_PORT}...")
    api_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=API_PORT, debug=False),
        daemon=True
    )
    api_thread.start()
    log.info("✓ REST API started")

    # Start
    log.info("\n" + "=" * 70)
    log.info("🟢 Ready to receive audio via WebSocket")
    log.info("=" * 70)
    log.info("\nTest endpoints:")
    log.info(f"  curl http://localhost:{API_PORT}/api/health")
    log.info(f"  curl http://localhost:{API_PORT}/api/test")
    log.info("\nTo test audio:")
    log.info(f"  python client_mic.py --ip localhost --port {WS_PORT}")
    log.info("\nPress Ctrl+C to stop\n")

    App.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n✓ Test stopped")
