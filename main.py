#!/usr/bin/env python3
"""
ElderSafeFinal - Main Entry Point
Orchestrates all components: audio bricks, anomaly detection, REST API, Firebase.
"""

import logging
import threading
from config import API_PORT, WS_AUDIO_PORT
from models import SystemState, load_isolation_forest
from csv_handler import init_csv
from audio_bricks import setup_audio_bricks
from anomaly_detection import anomaly_detector_loop
from api import create_api
from arduino.app_utils import App

# ── Setup Logging ───────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - [%(threadName)s] %(message)s"
)
log = logging.getLogger(__name__)


def main():
    """Main entry point."""
    log.info("=" * 70)
    log.info("ElderSafeFinal Server - Arduino UNO Q")
    log.info("=" * 70)

    # Initialize CSV logging
    init_csv()

    # Load Isolation Forest model
    isolation_forest = load_isolation_forest()

    # Create system state
    state = SystemState()

    # Setup audio bricks (KeywordSpotting + AudioClassification)
    log.info(f"\nStarting WebSocket Microphone on port {WS_AUDIO_PORT}...")
    mic = setup_audio_bricks(state)

    # Start anomaly detector thread
    if isolation_forest is not None:
        log.info("Starting anomaly detector thread...")
        anomaly_thread = threading.Thread(
            target=anomaly_detector_loop,
            args=(isolation_forest, state),
            daemon=True
        )
        anomaly_thread.start()
    else:
        log.warning("⚠️ Isolation Forest not loaded - anomaly detection disabled")

    # Create and start Flask REST API (daemon thread)
    log.info(f"\nStarting REST API on port {API_PORT}...")
    api_app = create_api(state)
    api_thread = threading.Thread(
        target=lambda: api_app.run(host="0.0.0.0", port=API_PORT, debug=False),
        daemon=True
    )
    api_thread.start()

    # Start Arduino App (blocks main thread)
    log.info("\n" + "=" * 70)
    log.info("🟢 All systems ready. Press Ctrl+C to stop.\n")
    log.info("=" * 70)

    try:
        App.run()
    except KeyboardInterrupt:
        log.info("\n✓ Server stopped")


if __name__ == "__main__":
    main()
