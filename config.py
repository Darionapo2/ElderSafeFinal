"""
Configuration and constants for SafeNet.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Audio Parameters ───────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
CONFIDENCE = 0.80
DEBOUNCE_SEC = 3.0

# ── Server Ports ───────────────────────────────────────────────────────────────
WS_AUDIO_PORT = 8080
API_PORT = 8000

# ── File Paths ─────────────────────────────────────────────────────────────────
CSV_PATH = "door_log.csv"
CSV_HEADER = ["id", "datetime", "date", "time", "direction", "first_sensor", "delta_ms", "anomaly_score"]
MODEL_PATH = "isolation_forest_model.pkl"
ABSENCE_STATS_PATH = "absence_stats.pkl"
SYNTHETIC_CSV_PATH = "synthetic_habits.csv"

# ── External Services ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
FIREBASE_DB_URL = os.getenv("FIREBASE_DATABASE_URL", "")

# ── Anomaly Detection ──────────────────────────────────────────────────────────
# Isolation Forest (Detector A: unusual-time events)
ANOMALY_CHECK_INTERVAL = 60  # seconds between unusual-time checks

# Absence-duration model (Detector B: overdue-return alert)
ABSENCE_DEADLINE_CHECK_INTERVAL = 5  # seconds between overdue checks
MIN_BUCKET_SAMPLES = 3   # min absence samples in a bucket before its window is trusted

# Sliding-window training: events older than this are obsolete and dropped.
HABIT_WINDOW_DAYS = 120  # ~4 months

# Retraining schedule
RETRAIN_HOUR = 3  # local hour of day for the daily automatic retrain

# ── Sensitivity defaults (0..100, also stored in Firebase /config/anomaly) ───────
# Unusual-time sensitivity: higher -> lower IF score threshold -> flags more events.
DEFAULT_UNUSUAL_TIME_SENSITIVITY = 50
# Return-late sensitivity: higher -> smaller tolerance k -> alert fires sooner.
DEFAULT_RETURN_LATE_SENSITIVITY = 50

# Mapping ranges (sensitivity 0..100 -> internal parameter)
# Unusual-time: IF anomaly score threshold. Lower threshold = more sensitive.
UNUSUAL_TIME_THRESHOLD_MIN = 0.30  # at sensitivity 100
UNUSUAL_TIME_THRESHOLD_MAX = 0.75  # at sensitivity 0
# Return-late: tolerance multiplier k on deadline = expected + k * std.
RETURN_LATE_K_MIN = 0.5  # at sensitivity 100 (alert sooner)
RETURN_LATE_K_MAX = 3.0  # at sensitivity 0 (alert later)
# Fallback absence window (minutes) when a bucket has too few samples.
ABSENCE_FALLBACK_MEAN_MIN = 240.0   # 4h expected absence
ABSENCE_FALLBACK_STD_MIN = 120.0    # 2h spread


def unusual_time_threshold(sensitivity: float) -> float:
    """Map unusual-time sensitivity (0..100) to an IF anomaly score threshold."""
    s = max(0.0, min(100.0, float(sensitivity))) / 100.0
    return UNUSUAL_TIME_THRESHOLD_MAX - s * (UNUSUAL_TIME_THRESHOLD_MAX - UNUSUAL_TIME_THRESHOLD_MIN)


def return_late_k(sensitivity: float) -> float:
    """Map return-late sensitivity (0..100) to a tolerance multiplier k."""
    s = max(0.0, min(100.0, float(sensitivity))) / 100.0
    return RETURN_LATE_K_MAX - s * (RETURN_LATE_K_MAX - RETURN_LATE_K_MIN)
