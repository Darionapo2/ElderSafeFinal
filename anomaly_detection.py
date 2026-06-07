"""
Anomaly detection for entry/exit patterns using Isolation Forest.
"""

import logging
import time
import numpy as np
from csv_handler import read_csv
from models import SystemState
from config import ANOMALY_THRESHOLD, ANOMALY_CHECK_INTERVAL
from events import on_anomaly_detected
from datetime import datetime

log = logging.getLogger(__name__)


def extract_features(event):
    """Extract feature vector from event for Isolation Forest."""
    dt = datetime.strptime(event["datetime"], "%Y-%m-%d %H:%M:%S.%f")

    # Feature 1: hour of day (0-23)
    hour_of_day = dt.hour

    # Feature 2: day of week (0=Monday, 6=Sunday)
    day_of_week = dt.weekday()

    # Feature 3: time since last event (seconds)
    time_since_last = float(event["delta_ms"]) / 1000.0

    # Feature 4: event type (0=entry, 1=exit)
    event_type = 1 if event["direction"] == "exit" else 0

    # Feature 5: time of day bucket (0=6-12, 1=12-18, 2=18-00, 3=00-06)
    if 6 <= hour_of_day < 12:
        time_bucket = 0
    elif 12 <= hour_of_day < 18:
        time_bucket = 1
    elif 18 <= hour_of_day < 24:
        time_bucket = 2
    else:  # 00-06
        time_bucket = 3

    # Feature 6: is_weekend (0=no, 1=yes)
    is_weekend = 1 if day_of_week >= 5 else 0

    return np.array([[hour_of_day, day_of_week, time_since_last, event_type, time_bucket, is_weekend]])


def check_anomaly(isolation_forest, state: SystemState):
    """Check for anomalies in recent events."""
    if isolation_forest is None:
        return

    rows = read_csv()
    if len(rows) < 2:
        return

    # Get last entry/exit (skip alarms)
    recent_events = [r for r in rows[-10:] if r.get("direction") in ["entry", "exit"]]
    if not recent_events:
        return

    event = recent_events[-1]

    try:
        # Build feature vector
        feature = extract_features(event)

        # Predict anomaly
        prediction = isolation_forest.predict(feature)
        anomaly_score = -isolation_forest.score_samples(feature)[0]  # Convert to 0-1 score

        if prediction[0] == -1 and anomaly_score > ANOMALY_THRESHOLD:
            on_anomaly_detected(state, event, anomaly_score)

    except Exception as e:
        log.error(f"Anomaly detection error: {e}")


def anomaly_detector_loop(isolation_forest, state: SystemState):
    """Background thread: periodically check for anomalies."""
    if isolation_forest is None:
        log.warning("No Isolation Forest model loaded, skipping anomaly detection")
        return

    log.info("Anomaly detector started")

    while True:
        try:
            time.sleep(ANOMALY_CHECK_INTERVAL)

            if state.anomaly_detection_enabled:
                check_anomaly(isolation_forest, state)

        except Exception as e:
            log.error(f"Anomaly detector loop error: {e}")
