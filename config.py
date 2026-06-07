"""
Configuration and constants for ElderSafeFinal.
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

# ── External Services ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
FIREBASE_DB_URL = os.getenv("FIREBASE_DATABASE_URL", "")

# ── Anomaly Detection ──────────────────────────────────────────────────────────
ANOMALY_THRESHOLD = 0.5
ANOMALY_CHECK_INTERVAL = 60  # seconds
