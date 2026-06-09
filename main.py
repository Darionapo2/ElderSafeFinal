#!/usr/bin/env python3
"""
ElderSafeFinal - Main Entry Point
KeywordSpotting only version.
"""

import logging
import threading
import os
from logging_setup import setup_logging
from config import API_PORT, WS_AUDIO_PORT
from models import SystemState, load_isolation_forest
from csv_handler import init_csv
from audio_bricks import setup_audio_bricks
from anomaly_detection import anomaly_detector_loop
from sensor_loop import sensor_monitor_loop
from api import create_api
from firebase_commands import setup_firebase_command_listener, cleanup_old_commands
from arduino.app_utils import App

try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

setup_logging()
log = logging.getLogger(__name__)

log.info("ElderSafeFinal system starting")

init_csv()

isolation_forest = load_isolation_forest()

state = SystemState()

try:
    from sensors import SensorMonitor
    monitor = SensorMonitor()
    state.set_armed(False)
    monitor.set_system_armed(False)
    log.info("System initialized in disarmed state")
except Exception as e:
    log.warning(f"MCU initialization failed: {e}")

if FIREBASE_AVAILABLE:
    try:
        if not firebase_admin._apps:
            # Build credentials dict from environment variables
            cred_dict = {
                "type": os.getenv("FIREBASE_TYPE", "service_account"),
                "project_id": os.getenv("FIREBASE_PROJECT_ID"),
                "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
                "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
                "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
                "client_id": os.getenv("FIREBASE_CLIENT_ID"),
                "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
                "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
                "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL"),
                "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
            }
            db_url = os.getenv("FIREBASE_DATABASE_URL")

            # Check if all required fields are present
            if all([cred_dict.get(k) for k in ["project_id", "private_key", "client_email"]]) and db_url:
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, {"databaseURL": db_url})
                setup_firebase_command_listener(state)
                log.info("Firebase initialized")
            else:
                log.info("Firebase credentials not configured - NFC sync will be skipped")
    except Exception as e:
        log.warning(f"Firebase init failed: {e} - continuing without Cloud features")

log.info(f"Starting WebSocket microphone on port {WS_AUDIO_PORT}")
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

log.info(f"Starting REST API on port {API_PORT}")
api_app = create_api(state)
api_thread = threading.Thread(
    target=lambda: api_app.run(host="0.0.0.0", port=API_PORT, debug=False),
    daemon=True
)
api_thread.start()

if FIREBASE_AVAILABLE and firebase_admin._apps:
    log.info("Starting periodic status sync thread")
    def sync_status_loop():
        from datetime import datetime
        from csv_handler import read_csv
        import time

        while True:
            try:
                rows = read_csv()
                status = {
                    "armed": state.armed,
                    "keyword_spotting": state.keyword_spotting_enabled,
                    "anomaly_detection": state.anomaly_detection_enabled,
                    "total_events": len(rows),
                    "entries": sum(1 for r in rows if r.get("direction") == "entry"),
                    "exits": sum(1 for r in rows if r.get("direction") == "exit"),
                    "alarms": sum(1 for r in rows if r.get("direction") == "alarm"),
                    "last_update": datetime.now().isoformat()
                }
                db.reference("status").set(status)
                log.debug("Status synced")
            except Exception as e:
                log.debug(f"Status sync error: {e}")

            time.sleep(10)

    status_thread = threading.Thread(target=sync_status_loop, daemon=True)
    status_thread.start()

    log.info("Starting periodic command cleanup thread")
    def cleanup_loop():
        import time
        while True:
            try:
                cleanup_old_commands(max_age_hours=24)
                log.debug("Old commands cleaned")
            except Exception as e:
                log.debug(f"Cleanup error: {e}")

            time.sleep(3600)  # Every hour

    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()

log.info("System ready. Press Ctrl+C to stop.")


App.run()

