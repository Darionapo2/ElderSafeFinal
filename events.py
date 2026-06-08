"""
Event logging and processing (entry/exit/alarm).
"""

import logging
from datetime import datetime
from csv_handler import read_csv, append_csv
from firebase import post_event
from telegram import send_alert
from models import SystemState

log = logging.getLogger(__name__)


def save_entry_exit_event(state: SystemState, direction: str, sensor: str = "REED", anomaly_score: float = 0.0):
    """Log entry/exit event to CSV and Firebase."""
    now = datetime.now()
    event_id = state.increment_event()

    rows = read_csv()
    delta_ms = 0
    if rows:
        try:
            last_time = datetime.strptime(rows[-1]["datetime"], "%Y-%m-%d %H:%M:%S.%f")
            delta_ms = int((now - last_time).total_seconds() * 1000)
        except Exception as e:
            log.error(f"Delta calculation failed: {e}")

    row = [
        event_id,
        now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        direction,
        sensor,
        delta_ms,
        f"{anomaly_score:.3f}",
    ]

    append_csv(row)
    log.info(f"Event #{event_id}: {direction} at {now.strftime('%H:%M:%S')}")

    post_event({
        "id": event_id,
        "datetime": row[1],
        "direction": direction,
        "anomaly_score": anomaly_score,
        "timestamp": now.isoformat(),
    })


def save_alarm_event(state: SystemState, alarm_type: str):
    """Log alarm event to CSV and Firebase."""
    now = datetime.now()
    event_id = state.increment_event()

    row = [
        event_id,
        now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        "alarm",
        alarm_type,
        0,
        "1.0",
    ]

    append_csv(row)
    log.warning(f"Alarm event #{event_id}: {alarm_type} at {now.strftime('%H:%M:%S')}")

    post_event({
        "id": event_id,
        "datetime": row[1],
        "direction": "alarm",
        "alarm_type": alarm_type,
        "timestamp": now.isoformat(),
    })


def on_keyword_detected(state: SystemState):
    """Handler for 'aiuto' keyword detection."""
    if not state.armed:
        log.debug("Keyword 'aiuto' detected but system is disarmed - ignoring")
        return

    log.warning("Keyword 'aiuto' detected")
    save_alarm_event(state, "VOICE_AIUTO")
    send_alert("Help Request", "Keyword 'aiuto' detected")


def on_anomaly_detected(state: SystemState, event: dict, anomaly_score: float):
    """Handler for anomaly detection in entry/exit patterns."""
    log.warning(f"Anomaly detected: {event['direction']} at {event['time']} (score={anomaly_score:.3f})")
    send_alert(
        "Anomaly Detected",
        f"Unusual {event['direction']} pattern detected"
    )
