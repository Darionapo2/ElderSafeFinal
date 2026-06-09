#!/usr/bin/env python3
"""
SafeNet - Main Entry Point
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
from absence_tracker import AbsenceTracker, deadline_loop
from retraining import retrain_all, retraining_loop
from sensor_loop import sensor_monitor_loop
from api import create_api
from firebase_commands import setup_firebase_command_listener, cleanup_old_commands
from firebase import push_status_now, push_model_status, read_anomaly_config
from arduino.app_utils import App

try:
    import firebase_admin
    from firebase_admin import credentials, db
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

setup_logging()
log = logging.getLogger(__name__)

log.info("SafeNet system starting")

init_csv()

isolation_forest = load_isolation_forest()

state = SystemState()

# Build both detector models from the current windowed history (synthetic seed +
# real CSV). This also creates absence_stats.pkl on first run.
log.info("Building anomaly models from windowed history")
initial_model_status = retrain_all(push_status=False)

absence_tracker = AbsenceTracker(state)

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
                setup_firebase_command_listener(state, absence_tracker)
                push_status_now(state)
                push_model_status(initial_model_status)
                # Load dashboard-configured sensitivities, if already present.
                initial_config = read_anomaly_config()
                if initial_config:
                    if "unusual_time_sensitivity" in initial_config:
                        state.set_unusual_time_sensitivity(initial_config["unusual_time_sensitivity"])
                    if "return_late_sensitivity" in initial_config:
                        state.set_return_late_sensitivity(initial_config["return_late_sensitivity"])
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
    args=(state, absence_tracker),
    daemon=True
)
sensor_thread.start()

log.info("Starting absence deadline thread")
deadline_thread = threading.Thread(
    target=deadline_loop,
    args=(absence_tracker,),
    daemon=True
)
deadline_thread.start()

# Reload the IF model that retrain_all just rebuilt at startup.
isolation_forest = load_isolation_forest()
if isolation_forest is not None:
    log.info("Starting unusual-time detector thread")
    anomaly_thread = threading.Thread(
        target=anomaly_detector_loop,
        args=(isolation_forest, state),
        daemon=True
    )
    anomaly_thread.start()
else:
    log.info("Isolation Forest not loaded - unusual-time detection disabled")

log.info("Starting daily retraining thread")
retrain_thread = threading.Thread(target=retraining_loop, daemon=True)
retrain_thread.start()

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
        import time
        while True:
            time.sleep(10)
            push_status_now(state)

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

