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


def save_anomaly_event(state: SystemState, anomaly_type: str, anomaly_score: float = 1.0, detail: str = ""):
    """Log an anomaly event to CSV and Firebase (direction='anomaly').

    Anomaly rows are ignored by retraining (which only uses entry/exit), so this
    is safe to keep in the local door log alongside alarms.
    """
    now = datetime.now()
    event_id = state.increment_event()

    row = [
        event_id,
        now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M:%S"),
        "anomaly",
        anomaly_type,
        0,
        f"{anomaly_score:.3f}",
    ]

    append_csv(row)
    log.warning(f"Anomaly event #{event_id}: {anomaly_type} at {now.strftime('%H:%M:%S')}")

    post_event({
        "id": event_id,
        "datetime": row[1],
        "direction": "anomaly",
        "anomaly_type": anomaly_type,
        "anomaly_score": anomaly_score,
        "detail": detail,
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


def on_unusual_time_event(state: SystemState, event: dict, anomaly_score: float):
    """Handler for Detector A (Isolation Forest): unusual-time entry/exit event."""
    log.warning(
        f"Unusual-time event: {event['direction']} at {event.get('time')} "
        f"(score={anomaly_score:.3f})"
    )
    save_anomaly_event(
        state,
        "UNUSUAL_TIME",
        anomaly_score=anomaly_score,
        detail=f"Unusual {event['direction']} at {event.get('time')}",
    )
    send_alert("Anomaly: unusual time", f"Unusual {event['direction']} pattern detected")


def on_overdue_absence(state: SystemState, absence: dict):
    """Handler for Detector B: person has not returned within the expected window."""
    exit_time = absence.get("exit_time", "")
    expected = absence.get("expected_return_at", "")
    log.warning(f"Overdue absence: no return since {exit_time}")
    save_anomaly_event(
        state,
        "ABSENCE_OVERDUE",
        anomaly_score=1.0,
        detail=f"No return since {exit_time}",
    )
    send_alert(
        "Anomaly: overdue return",
        "Person has not returned within the expected time window.",
        details=f"Out since {exit_time}\nExpected back by {expected}",
    )
