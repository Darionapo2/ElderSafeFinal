#!/usr/bin/env python3
"""
ElderSafeFinal Server - Arduino UNO Q
Main server combining:
- KeywordSpotting (aiuto detection)
- AudioClassification (crying_baby, scream)
- Anomaly detection for entry/exit patterns
- REST API + Firebase sync
- Telegram alerting
"""

import os
import json
import csv
import time
import pickle
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request
from arduino.app_bricks.keyword_spotting import KeywordSpotting
from arduino.app_bricks.audio_classification import AudioClassification
from arduino.app_peripherals.microphone import Microphone
from arduino.app_utils import App
import requests

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - [%(threadName)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
WS_AUDIO_PORT = 8080
API_PORT = 8000
CSV_PATH = "door_log.csv"
MODEL_PATH = "isolation_forest_model.pkl"

# External services
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
FIREBASE_DB_URL = os.getenv("FIREBASE_DATABASE_URL", "")

# Audio parameters
SAMPLE_RATE = 16000
CHANNELS = 1
CONFIDENCE = 0.80
DEBOUNCE_SEC = 3.0

# Anomaly detection
ANOMALY_THRESHOLD = 0.5
ANOMALY_CHECK_INTERVAL = 60  # seconds

# ── CSV Setup ──────────────────────────────────────────────────────────────────
CSV_HEADER = ["id", "datetime", "date", "time", "direction", "first_sensor", "delta_ms", "anomaly_score"]

def init_csv():
    """Initialize CSV file if not exists."""
    if not Path(CSV_PATH).exists() or Path(CSV_PATH).stat().st_size == 0:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(CSV_HEADER)
        log.info(f"✓ CSV initialized: {CSV_PATH}")


def read_csv():
    """Read all CSV rows."""
    try:
        if not Path(CSV_PATH).exists():
            return []
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        log.error(f"Error reading CSV: {e}")
        return []


def append_csv(row):
    """Append row to CSV."""
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        log.error(f"Error writing CSV: {e}")


# ── Model Loading ──────────────────────────────────────────────────────────────
def load_model():
    """Load Isolation Forest model."""
    try:
        if Path(MODEL_PATH).exists():
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            log.info(f"✓ Loaded Isolation Forest from {MODEL_PATH}")
            return model
    except Exception as e:
        log.error(f"Error loading model: {e}")
    return None


# ── Telegram Alerting ──────────────────────────────────────────────────────────
def send_telegram_alert(alert_type: str, message: str, details: str = ""):
    """Send alert to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram not configured, skipping alert")
        return

    text = f"🚨 {alert_type}\n{message}"
    if details:
        text += f"\n\n{details}"

    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=5
        )
        log.info(f"✓ Telegram alert sent: {alert_type}")
    except Exception as e:
        log.error(f"Failed to send Telegram alert: {e}")


# ── Firebase Sync ──────────────────────────────────────────────────────────────
def post_to_firebase(event_data: dict):
    """Post event to Firebase Realtime Database."""
    if not FIREBASE_DB_URL:
        log.debug("Firebase not configured, skipping sync")
        return

    try:
        url = f"{FIREBASE_DB_URL}/events.json"
        requests.post(url, json=event_data, timeout=5)
        log.debug("✓ Posted to Firebase")
    except Exception as e:
        log.warning(f"Firebase sync failed: {e}")


# ── State ──────────────────────────────────────────────────────────────────────
class SystemState:
    def __init__(self):
        self.armed = True
        self.sound_classification_enabled = True
        self.keyword_spotting_enabled = True
        self.anomaly_detection_enabled = True
        self.event_count = 0
        self.last_update = datetime.now()
        self.lock = threading.Lock()

    def increment_event(self):
        with self.lock:
            self.event_count += 1
            return self.event_count


state = SystemState()
isolation_forest = load_model()


# ── Entry/Exit Detection ────────────────────────────────────────────────────────
def save_entry_exit_event(direction: str, sensor: str = "REED", anomaly_score: float = 0.0):
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
    post_to_firebase({
        "id": event_id,
        "datetime": row[1],
        "direction": direction,
        "anomaly_score": anomaly_score,
        "timestamp": now.isoformat(),
    })


def save_alarm_event(alarm_type: str):
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
    post_to_firebase({
        "id": event_id,
        "datetime": row[1],
        "direction": "alarm",
        "alarm_type": alarm_type,
        "timestamp": now.isoformat(),
    })


# ── Audio Bricks (KeywordSpotting + AudioClassification) ─────────────────────
def setup_audio_bricks():
    """Setup KeywordSpotting and AudioClassification bricks."""
    log.info("Initializing audio bricks...")

    # Create shared microphone for both bricks
    mic = Microphone(
        device=f"ws://0.0.0.0:{WS_AUDIO_PORT}",
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
    )

    # KeywordSpotting for "aiuto"
    if state.keyword_spotting_enabled:
        try:
            spotter = KeywordSpotting(mic=mic, confidence=CONFIDENCE, debounce_sec=DEBOUNCE_SEC)

            def on_aiuto_detected():
                log.warning("🔴 KEYWORD 'aiuto' DETECTED!")
                save_alarm_event("VOICE_AIUTO")
                send_telegram_alert("RICHIESTA DI AIUTO", "Parola 'aiuto' rilevata")

            spotter.on_detect("aiuto", on_aiuto_detected)
            log.info("✓ KeywordSpotting configured (keyword: 'aiuto')")
        except Exception as e:
            log.error(f"Failed to setup KeywordSpotting: {e}")

    # AudioClassification for danger sounds
    if state.sound_classification_enabled:
        try:
            classifier = AudioClassification(mic=mic, confidence=CONFIDENCE)

            def on_sound_detect(label: str):
                if state.sound_classification_enabled:
                    log.warning(f"🔴 SOUND DETECTED: '{label}'")
                    save_alarm_event(f"SOUND_{label.upper()}")

                    if label in ["scream", "crying_baby"]:
                        send_telegram_alert(
                            "SUONO PERICOLOSO",
                            f"Rilevato: {label}",
                            f"Orario: {datetime.now().strftime('%H:%M:%S')}"
                        )

            for label in ["crying_baby", "fall", "glass_breaking", "scream"]:
                classifier.on_detect(label, lambda l=label: on_sound_detect(l))

            log.info("✓ AudioClassification configured")
        except Exception as e:
            log.error(f"Failed to setup AudioClassification: {e}")

    return mic


# ── Anomaly Detection Thread ───────────────────────────────────────────────────
def anomaly_detector_loop():
    """Periodically check for anomalies in entry/exit patterns."""
    if isolation_forest is None:
        log.warning("No Isolation Forest model loaded, skipping anomaly detection")
        return

    log.info("Anomaly detector started")

    while True:
        try:
            time.sleep(ANOMALY_CHECK_INTERVAL)

            if not state.anomaly_detection_enabled:
                continue

            rows = read_csv()
            if len(rows) < 2:
                continue

            # Get last entry/exit (skip alarms)
            recent_events = [r for r in rows[-10:] if r.get("direction") in ["entry", "exit"]]
            if not recent_events:
                continue

            event = recent_events[-1]
            dt = datetime.strptime(event["datetime"], "%Y-%m-%d %H:%M:%S.%f")

            # Build feature vector
            hour = dt.hour
            day = dt.weekday()
            delta_sec = float(event["delta_ms"]) / 1000.0
            event_type = 1 if event["direction"] == "exit" else 0
            time_bucket = (hour // 6) if hour < 24 else 3
            is_weekend = 1 if day >= 5 else 0

            feature = np.array([[hour, day, delta_sec, event_type, time_bucket, is_weekend]])

            # Predict anomaly
            prediction = isolation_forest.predict(feature)
            anomaly_score = -isolation_forest.score_samples(feature)[0]  # Convert to 0-1 score

            if prediction[0] == -1 and anomaly_score > ANOMALY_THRESHOLD:
                log.warning(f"⚠️ ANOMALY DETECTED: {event['direction']} @ {event['time']} (score={anomaly_score:.3f})")
                send_telegram_alert(
                    "ANOMALIA RILEVATA",
                    f"{event['direction'].upper()} inusuale",
                    f"Orario: {event['time']}\nPunteggio: {anomaly_score:.3f}"
                )

        except Exception as e:
            log.error(f"Anomaly detector error: {e}")


# ── Flask REST API ─────────────────────────────────────────────────────────────
app = Flask(__name__)


@app.route("/api/status", methods=["GET"])
def api_status():
    """Get system status."""
    rows = read_csv()
    return jsonify({
        "armed": state.armed,
        "sound_classification": state.sound_classification_enabled,
        "keyword_spotting": state.keyword_spotting_enabled,
        "anomaly_detection": state.anomaly_detection_enabled,
        "total_events": len(rows),
        "entries": sum(1 for r in rows if r.get("direction") == "entry"),
        "exits": sum(1 for r in rows if r.get("direction") == "exit"),
        "alarms": sum(1 for r in rows if r.get("direction") == "alarm"),
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/events", methods=["GET"])
def api_events():
    """Get recent events."""
    limit = request.args.get("limit", 50, type=int)
    event_type = request.args.get("type", None)  # Filter by type: entry, exit, alarm

    rows = read_csv()
    rows = list(reversed(rows))  # Most recent first

    if event_type:
        rows = [r for r in rows if r.get("direction") in event_type.split(",")]

    return jsonify({"rows": rows[:limit]})


@app.route("/api/control", methods=["POST"])
def api_control():
    """Control system features."""
    data = request.get_json()

    if "armed" in data:
        state.armed = bool(data["armed"])
        log.info(f"System {'ARMED' if state.armed else 'DISARMED'}")

    if "sound_classification" in data:
        state.sound_classification_enabled = bool(data["sound_classification"])
        log.info(f"Sound classification: {state.sound_classification_enabled}")

    if "keyword_spotting" in data:
        state.keyword_spotting_enabled = bool(data["keyword_spotting"])
        log.info(f"Keyword spotting: {state.keyword_spotting_enabled}")

    if "anomaly_detection" in data:
        state.anomaly_detection_enabled = bool(data["anomaly_detection"])
        log.info(f"Anomaly detection: {state.anomaly_detection_enabled}")

    return jsonify({"success": True}), 200


@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "model_loaded": isolation_forest is not None,
    })


# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 70)
    log.info("ElderSafeFinal Server - Arduino UNO Q")
    log.info("=" * 70)

    # Initialize
    init_csv()

    # Setup audio bricks
    mic = setup_audio_bricks()

    # Start anomaly detector thread
    if isolation_forest is not None:
        anomaly_thread = threading.Thread(target=anomaly_detector_loop, daemon=True)
        anomaly_thread.start()
    else:
        log.warning("⚠️  Isolation Forest not loaded - anomaly detection disabled")

    # Start Flask API
    log.info(f"Starting REST API on port {API_PORT}...")
    api_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=API_PORT, debug=False),
        daemon=True
    )
    api_thread.start()

    # Run Arduino App (blocks)
    log.info(f"Starting Arduino App... WebSocket Microphone on port {WS_AUDIO_PORT}")
    log.info("\nPress Ctrl+C to stop\n")
    App.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("\n✓ Server stopped")
