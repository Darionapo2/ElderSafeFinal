"""
Detector A: unusual-time entry/exit events using the Isolation Forest.

Scores the most recent entry/exit event and, when it looks anomalous for its
time of day, raises an alert. The expected-return logic lives in the
absence-duration model (Detector B); this detector only flags events whose
timing is unusual relative to the learned baseline.
"""

import logging
import time

from csv_handler import read_csv
from models import SystemState, load_isolation_forest
from config import ANOMALY_CHECK_INTERVAL, unusual_time_threshold
from events import on_unusual_time_event
from ml_features import extract_if_features

log = logging.getLogger(__name__)

# Avoid re-alerting on the same event across consecutive checks.
_last_alerted_event_id = None


def check_anomaly(isolation_forest, state: SystemState):
    """Check the most recent entry/exit event for an unusual-time anomaly."""
    global _last_alerted_event_id

    if isolation_forest is None:
        return

    rows = read_csv()
    if len(rows) < 2:
        return

    recent_events = [r for r in rows[-10:] if r.get("direction") in ("entry", "exit")]
    if not recent_events:
        return

    event = recent_events[-1]
    event_id = event.get("id")

    # Skip if we already alerted on this exact event.
    if event_id is not None and event_id == _last_alerted_event_id:
        return

    threshold = unusual_time_threshold(state.unusual_time_sensitivity)

    try:
        feature = extract_if_features(event)
        prediction = isolation_forest.predict(feature)
        anomaly_score = -isolation_forest.score_samples(feature)[0]

        if prediction[0] == -1 and anomaly_score > threshold:
            _last_alerted_event_id = event_id
            on_unusual_time_event(state, event, anomaly_score)

    except Exception as e:
        log.error(f"Unusual-time detection failed: {e}")


def anomaly_detector_loop(isolation_forest, state: SystemState):
    """Periodically check for unusual-time anomalies in entry/exit patterns."""
    if isolation_forest is None:
        log.warning("Isolation Forest model not loaded - unusual-time detection disabled")
        return

    log.info("Unusual-time detector started")

    model = isolation_forest
    while True:
        try:
            time.sleep(ANOMALY_CHECK_INTERVAL)
            if state.anomaly_detection_enabled:
                # Reload from disk so retrained models take effect without restart.
                reloaded = load_isolation_forest()
                if reloaded is not None:
                    model = reloaded
                check_anomaly(model, state)
        except Exception as e:
            log.error(f"Unusual-time detector failed: {e}")
