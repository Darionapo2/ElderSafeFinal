#!/usr/bin/env python3
"""
ElderSafeFinal - Main Entry Point
KeywordSpotting only version.
"""

import logging
import threading
from logging_setup import setup_logging
from config import API_PORT, WS_AUDIO_PORT
from models import SystemState, load_isolation_forest
from csv_handler import init_csv
from audio_bricks import setup_audio_bricks
from anomaly_detection import anomaly_detector_loop
from sensor_loop import sensor_monitor_loop
from api import create_api
from arduino.app_utils import App

setup_logging()
log = logging.getLogger(__name__)


log.info("ElderSafeFinal - KeywordSpotting Mode")

init_csv()

isolation_forest = load_isolation_forest()

state = SystemState()

log.info(f"\nStarting WebSocket Microphone on port {WS_AUDIO_PORT}")
mic = setup_audio_bricks(state)

log.info("Starting sensor monitor thread")
sensor_thread = threading.Thread(
    target=sensor_monitor_loop,
    args=(state,),
    daemon=True
)
sensor_thread.start()

if isolation_forest is not None:
    log.info("Starting anomaly detector thread")
    anomaly_thread = threading.Thread(
        target=anomaly_detector_loop,
        args=(isolation_forest, state),
        daemon=True
    )
    anomaly_thread.start()
else:
    log.info("Isolation Forest not loaded - anomaly detection disabled")

log.info(f"\nStarting REST API on port {API_PORT}")
api_app = create_api(state)
api_thread = threading.Thread(
    target=lambda: api_app.run(host="0.0.0.0", port=API_PORT, debug=False),
    daemon=True
)
api_thread.start()

log.info("All systems ready. Press Ctrl+C to stop.\n")


App.run()

