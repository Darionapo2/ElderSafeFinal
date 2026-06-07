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
    """Log entry/exit event."""
    now = datetime.now()
    event_id = state.increment_event()

    # Calculate delta from last event
    rows = read_csv()
    delta_ms = 0
    if rows:
        try:
            last_time = datetime.strptime(rows[-1]["datetime"], "%Y-%m-%d %H:%M:%S.%f")
            delta_ms = int((now - last_time).total_seconds() * 1000)
        except Exception as e:
            log.error(f"Error calculating delta: {e}")

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
    log.info(f"#{event_id} {direction.upper()} @ {now.strftime('%H:%M:%S')} (Δ {delta_ms} ms, anomaly={anomaly_score:.3f})")

    # Post to Firebase
    post_event({
        "id": event_id,
        "datetime": row[1],
        "direction": direction,
        "anomaly_score": anomaly_score,
        "timestamp": now.isoformat(),
    })


def save_alarm_event(state: SystemState, alarm_type: str):
    """Log alarm event."""
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
    log.warning(f"#{event_id} ALARM ({alarm_type}) @ {now.strftime('%H:%M:%S')}")

    # Post to Firebase
    post_event({
        "id": event_id,
        "datetime": row[1],
        "direction": "alarm",
        "alarm_type": alarm_type,
        "timestamp": now.isoformat(),
    })


def on_keyword_detected(state: SystemState):
    """Handler for keyword detection."""
    log.warning("🔴 KEYWORD 'aiuto' DETECTED!")
    save_alarm_event(state, "VOICE_AIUTO")
    send_alert("RICHIESTA DI AIUTO", "Parola 'aiuto' rilevata")


def on_sound_detected(state: SystemState, label: str):
    """Handler for dangerous sound detection."""
    if state.sound_classification_enabled:
        log.warning(f"🔴 SOUND DETECTED: '{label}'")
        save_alarm_event(state, f"SOUND_{label.upper()}")

        if label in ["scream", "crying_baby"]:
            send_alert(
                "SUONO PERICOLOSO",
                f"Rilevato: {label}",
                f"Orario: {datetime.now().strftime('%H:%M:%S')}"
            )


def on_anomaly_detected(state: SystemState, event: dict, anomaly_score: float):
    """Handler for anomaly detection."""
    log.warning(f"⚠️ ANOMALY DETECTED: {event['direction']} @ {event['time']} (score={anomaly_score:.3f})")
    send_alert(
        "ANOMALIA RILEVATA",
        f"{event['direction'].upper()} inusuale",
        f"Orario: {event['time']}\nPunteggio: {anomaly_score:.3f}"
    )
