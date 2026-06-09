"""
System state and model management.
"""

import pickle
import logging
import threading
from pathlib import Path
from config import MODEL_PATH

log = logging.getLogger(__name__)


class SystemState:
    """System state management with thread safety."""

    def __init__(self):
        self.armed = False
        self.sound_classification_enabled = True
        self.keyword_spotting_enabled = True
        self.anomaly_detection_enabled = True
        self.event_count = 0
        self.lock = threading.Lock()

    def increment_event(self):
        """Get next event ID."""
        with self.lock:
            self.event_count += 1
            return self.event_count

    def set_armed(self, armed: bool):
        """Set armed state."""
        with self.lock:
            self.armed = armed

    def set_sound_classification(self, enabled: bool):
        """Enable/disable sound classification."""
        with self.lock:
            self.sound_classification_enabled = enabled

    def set_keyword_spotting(self, enabled: bool):
        """Enable/disable keyword spotting."""
        with self.lock:
            self.keyword_spotting_enabled = enabled

    def set_anomaly_detection(self, enabled: bool):
        """Enable/disable anomaly detection."""
        with self.lock:
            self.anomaly_detection_enabled = enabled

    def to_dict(self):
        """Return state as dictionary."""
        with self.lock:
            return {
                "armed": self.armed,
                "sound_classification": self.sound_classification_enabled,
                "keyword_spotting": self.keyword_spotting_enabled,
                "anomaly_detection": self.anomaly_detection_enabled,
                "event_count": self.event_count,
            }


def load_isolation_forest():
    """Load trained Isolation Forest model from disk."""
    try:
        if Path(MODEL_PATH).exists():
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            log.info(f"Isolation Forest loaded: {MODEL_PATH}")
            return model
    except Exception as e:
        log.error(f"Model load failed: {e}")
    return None
