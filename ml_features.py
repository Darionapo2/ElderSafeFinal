"""
Shared feature engineering for the Isolation Forest (Detector A: unusual-time).

Keeping a single implementation guarantees that training (retraining.py,
dataset_generator.py) and inference (anomaly_detection.py) always use the exact
same feature layout.
"""

from datetime import datetime
import numpy as np

# Accepted datetime formats for the "datetime" CSV/event field.
_DATETIME_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S")


def parse_event_datetime(value: str) -> datetime:
    """Parse an event datetime string, tolerating presence/absence of microseconds."""
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized datetime format: {value!r}")


def time_of_day_bucket(hour_of_day: int) -> int:
    """Map an hour (0-23) to a coarse time bucket (0=6-12, 1=12-18, 2=18-00, 3=00-06)."""
    if 6 <= hour_of_day < 12:
        return 0
    if 12 <= hour_of_day < 18:
        return 1
    if 18 <= hour_of_day < 24:
        return 2
    return 3


def event_feature_row(event: dict) -> list:
    """Build the 6-element Isolation Forest feature row for a single event.

    Features:
        1. hour_of_day (0-23)
        2. day_of_week (0=Monday, 6=Sunday)
        3. time_since_last_event (seconds)
        4. event_type (0=entry, 1=exit)
        5. time_of_day_bucket (0-3)
        6. is_weekend (0/1)
    """
    dt = parse_event_datetime(event["datetime"])
    hour_of_day = dt.hour
    day_of_week = dt.weekday()
    time_since_last = float(event.get("delta_ms", 0) or 0) / 1000.0
    event_type = 1 if event.get("direction") == "exit" else 0
    bucket = time_of_day_bucket(hour_of_day)
    is_weekend = 1 if day_of_week >= 5 else 0
    return [hour_of_day, day_of_week, time_since_last, event_type, bucket, is_weekend]


def extract_if_features(event: dict) -> np.ndarray:
    """Return the feature matrix (1x6) for a single event, ready for IF predict."""
    return np.array([event_feature_row(event)])


def extract_if_feature_matrix(events: list) -> np.ndarray:
    """Return the feature matrix (Nx6) for a list of events."""
    return np.array([event_feature_row(e) for e in events])
