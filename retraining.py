"""
Model retraining pipeline (shared by both detectors).

Rebuilds, from the same windowed event history:
  - the Isolation Forest model (Detector A: unusual-time events)
  - the absence-duration statistics (Detector B: overdue-return alert)

Training data = synthetic seed + all real CSV events, keeping only events within
the last HABIT_WINDOW_DAYS (sliding obsolescence window). The synthetic seed
stands in for real habits up to deploy time and ages out of the window naturally
as real events accumulate.

Runs once a day at RETRAIN_HOUR and on demand from the dashboard.
"""

import csv
import logging
import pickle
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from sklearn.ensemble import IsolationForest

from ml_features import parse_event_datetime, extract_if_feature_matrix
from absence_model import build_absence_stats, save_absence_stats
from config import (
    CSV_PATH,
    SYNTHETIC_CSV_PATH,
    MODEL_PATH,
    HABIT_WINDOW_DAYS,
    RETRAIN_HOUR,
)

log = logging.getLogger(__name__)

# Minimum events required to (re)train the Isolation Forest meaningfully.
_MIN_IF_SAMPLES = 10

# Guard so automatic and on-demand retrains never overlap.
_retrain_lock = threading.Lock()


def _read_events_file(path: str) -> list:
    """Read entry/exit events from a CSV file, ignoring missing files."""
    if not Path(path).exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [r for r in csv.DictReader(f) if r.get("direction") in ("entry", "exit")]
    except Exception as e:
        log.error(f"Failed reading events from {path}: {e}")
        return []


def _within_window(event: dict, cutoff: datetime) -> bool:
    """True if the event is recent enough to still be relevant for training."""
    try:
        return parse_event_datetime(event["datetime"]) >= cutoff
    except Exception:
        return False


def load_windowed_events() -> tuple:
    """Return (combined_events, real_count, synthetic_count) inside the window."""
    cutoff = datetime.now() - timedelta(days=HABIT_WINDOW_DAYS)

    real = [e for e in _read_events_file(CSV_PATH) if _within_window(e, cutoff)]
    synthetic = [e for e in _read_events_file(SYNTHETIC_CSV_PATH) if _within_window(e, cutoff)]

    combined = real + synthetic
    return combined, len(real), len(synthetic)


def _train_isolation_forest(events: list):
    """Train an Isolation Forest on the event feature matrix."""
    features = extract_if_feature_matrix(events)
    model = IsolationForest(
        contamination=0.05,
        max_samples=min(100, len(features)),
        n_estimators=50,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(features)
    return model


def retrain_all(push_status: bool = True) -> dict:
    """Rebuild both models from the windowed history. Returns a status dict."""
    with _retrain_lock:
        combined, real_count, synthetic_count = load_windowed_events()
        total = len(combined)
        log.info(
            f"Retraining on {total} windowed events "
            f"(real={real_count}, synthetic={synthetic_count})"
        )

        if total < _MIN_IF_SAMPLES:
            log.warning(
                f"Only {total} events in window (< {_MIN_IF_SAMPLES}); "
                f"keeping existing models"
            )
            status = _build_status(real_count, synthetic_count, total, trained=False)
            if push_status:
                _push_status(status)
            return status

        # Detector A: Isolation Forest
        try:
            model = _train_isolation_forest(combined)
            with open(MODEL_PATH, "wb") as f:
                pickle.dump(model, f)
            log.info(f"Isolation Forest retrained and saved: {MODEL_PATH}")
        except Exception as e:
            log.error(f"Isolation Forest retraining failed: {e}")

        # Detector B: absence-duration statistics
        try:
            stats = build_absence_stats(combined)
            save_absence_stats(stats)
        except Exception as e:
            log.error(f"Absence stats rebuild failed: {e}")

        status = _build_status(real_count, synthetic_count, total, trained=True)
        if push_status:
            _push_status(status)
        return status


def _build_status(real_count: int, synthetic_count: int, total: int, trained: bool) -> dict:
    """Assemble the model-status payload for Firebase/logging."""
    return {
        "last_trained_at": datetime.now().isoformat(),
        "training_window_days": HABIT_WINDOW_DAYS,
        "real_events_in_window": real_count,
        "synthetic_in_window": synthetic_count,
        "training_samples": total,
        "trained": trained,
        "retrain_in_progress": False,
    }


def _push_status(status: dict):
    """Best-effort push of model status to Firebase."""
    try:
        from firebase import push_model_status
        push_model_status(status)
    except Exception as e:
        log.debug(f"Model status push skipped: {e}")


def retraining_loop():
    """Daily automatic retrain at RETRAIN_HOUR (local time)."""
    log.info(f"Retraining scheduler started (daily at {RETRAIN_HOUR:02d}:00)")
    last_trained_date = None

    while True:
        try:
            now = datetime.now()
            if now.hour == RETRAIN_HOUR and now.date() != last_trained_date:
                log.info("Daily retrain triggered")
                retrain_all()
                last_trained_date = now.date()
        except Exception as e:
            log.error(f"Daily retrain failed: {e}")

        # Check a few times per hour; the date guard prevents duplicate runs.
        time.sleep(600)
