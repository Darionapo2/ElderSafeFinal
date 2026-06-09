"""
Absence-duration model (Detector B: overdue-return alert).

Learns, per time bucket (hour-bucket x weekend), the distribution of how long the
person stays out between an exit and the following entry. From this it predicts,
for a new exit, an expected return window and a "late deadline" beyond which the
absence is considered an anomaly.

This is intentionally a simple statistical model (mean/std per bucket with a
global fallback): the Isolation Forest cannot produce an expected-return time, so
the return window is derived here instead.
"""

import logging
import pickle
from datetime import timedelta
from pathlib import Path
import statistics

from ml_features import parse_event_datetime, time_of_day_bucket
from config import (
    ABSENCE_STATS_PATH,
    MIN_BUCKET_SAMPLES,
    ABSENCE_FALLBACK_MEAN_MIN,
    ABSENCE_FALLBACK_STD_MIN,
)

log = logging.getLogger(__name__)


def _bucket_key(dt) -> str:
    """Build the grouping key for an exit datetime."""
    is_weekend = 1 if dt.weekday() >= 5 else 0
    return f"{time_of_day_bucket(dt.hour)}_{is_weekend}"


def _absence_durations(events: list) -> dict:
    """Pair each exit with the following entry and collect absence durations (minutes).

    Returns a dict bucket_key -> list[float minutes]. Events must be entry/exit
    dicts; they are sorted chronologically before pairing.
    """
    ordered = sorted(
        (e for e in events if e.get("direction") in ("entry", "exit")),
        key=lambda e: parse_event_datetime(e["datetime"]),
    )

    durations = {}
    open_exit_dt = None

    for e in ordered:
        dt = parse_event_datetime(e["datetime"])
        if e["direction"] == "exit":
            # A new exit; if one was already open, the previous absence had no
            # matching entry (missed/overnight) so we drop it and restart.
            open_exit_dt = dt
        elif e["direction"] == "entry" and open_exit_dt is not None:
            minutes = (dt - open_exit_dt).total_seconds() / 60.0
            if minutes > 0:
                durations.setdefault(_bucket_key(open_exit_dt), []).append(minutes)
            open_exit_dt = None

    return durations


def build_absence_stats(events: list) -> dict:
    """Compute per-bucket absence-duration statistics with a global fallback."""
    durations = _absence_durations(events)

    buckets = {}
    all_values = []
    for key, values in durations.items():
        all_values.extend(values)
        if len(values) >= 1:
            buckets[key] = {
                "mean_min": statistics.fmean(values),
                "std_min": statistics.pstdev(values) if len(values) > 1 else 0.0,
                "count": len(values),
            }

    if all_values:
        global_stats = {
            "mean_min": statistics.fmean(all_values),
            "std_min": statistics.pstdev(all_values) if len(all_values) > 1 else 0.0,
            "count": len(all_values),
        }
    else:
        global_stats = {"mean_min": 0.0, "std_min": 0.0, "count": 0}

    stats = {"buckets": buckets, "global": global_stats}
    log.info(
        f"Absence stats built: {len(buckets)} buckets, "
        f"{global_stats['count']} total absence samples"
    )
    return stats


def save_absence_stats(stats: dict, path: str = ABSENCE_STATS_PATH):
    """Persist absence stats to disk."""
    with open(path, "wb") as f:
        pickle.dump(stats, f)
    log.info(f"Absence stats saved: {path}")


def load_absence_stats(path: str = ABSENCE_STATS_PATH):
    """Load absence stats from disk, or None if missing."""
    try:
        if Path(path).exists():
            with open(path, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        log.error(f"Absence stats load failed: {e}")
    return None


def _resolve_distribution(exit_dt, stats: dict):
    """Pick the most specific trusted (mean, std, confidence) for an exit time.

    Prefers the matching bucket, falls back to the global distribution, then to
    configured constants. Confidence is "high" only when the matching bucket has
    enough samples.
    """
    if stats:
        key = _bucket_key(exit_dt)
        bucket = stats.get("buckets", {}).get(key)
        if bucket and bucket["count"] >= MIN_BUCKET_SAMPLES:
            return bucket["mean_min"], bucket["std_min"], "high"

        global_stats = stats.get("global")
        if global_stats and global_stats["count"] >= MIN_BUCKET_SAMPLES:
            return global_stats["mean_min"], global_stats["std_min"], "low"

    return ABSENCE_FALLBACK_MEAN_MIN, ABSENCE_FALLBACK_STD_MIN, "low"


def predict_return_window(exit_dt, stats: dict, k: float) -> dict:
    """Predict the expected return window and late deadline for an exit.

    Args:
        exit_dt: datetime of the exit event.
        stats: absence statistics from build_absence_stats (may be None).
        k: tolerance multiplier; late_deadline = exit + mean + k * std.

    Returns a dict of ISO datetimes plus a confidence label.
    """
    mean_min, std_min, confidence = _resolve_distribution(exit_dt, stats)

    expected_return_at = exit_dt + timedelta(minutes=mean_min)
    window_start = exit_dt + timedelta(minutes=max(0.0, mean_min - std_min))
    window_end = exit_dt + timedelta(minutes=mean_min + std_min)
    late_deadline_at = exit_dt + timedelta(minutes=mean_min + k * std_min)

    return {
        "expected_return_at": expected_return_at.isoformat(),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "late_deadline_at": late_deadline_at.isoformat(),
        "confidence": confidence,
        "expected_minutes": round(mean_min, 1),
    }
