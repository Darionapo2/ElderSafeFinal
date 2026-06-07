"""
REST API endpoints using Flask.
"""

import logging
from datetime import datetime
from flask import Flask, jsonify, request
from csv_handler import read_csv
from models import SystemState
from firebase import post_status

log = logging.getLogger(__name__)

app = Flask(__name__)


def create_api(state: SystemState):
    """Create and configure Flask API app."""

    @app.route("/api/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
        }), 200

    @app.route("/api/status", methods=["GET"])
    def status():
        """Get system status."""
        rows = read_csv()
        status_data = {
            "armed": state.armed,
            "sound_classification": state.sound_classification_enabled,
            "keyword_spotting": state.keyword_spotting_enabled,
            "anomaly_detection": state.anomaly_detection_enabled,
            "total_events": len(rows),
            "entries": sum(1 for r in rows if r.get("direction") == "entry"),
            "exits": sum(1 for r in rows if r.get("direction") == "exit"),
            "alarms": sum(1 for r in rows if r.get("direction") == "alarm"),
            "timestamp": datetime.now().isoformat(),
        }
        post_status(status_data)
        return jsonify(status_data), 200

    @app.route("/api/events", methods=["GET"])
    def events():
        """Get recent events with optional filtering."""
        limit = request.args.get("limit", 50, type=int)
        event_type = request.args.get("type", None)

        rows = read_csv()
        rows = list(reversed(rows))  # Most recent first

        if event_type:
            rows = [r for r in rows if r.get("direction") in event_type.split(",")]

        return jsonify({"rows": rows[:limit]}), 200

    @app.route("/api/control", methods=["POST"])
    def control():
        """Control system features."""
        data = request.get_json()

        if "armed" in data:
            state.set_armed(bool(data["armed"]))
            log.info(f"System {'ARMED' if state.armed else 'DISARMED'}")

        if "sound_classification" in data:
            state.set_sound_classification(bool(data["sound_classification"]))
            log.info(f"Sound classification: {state.sound_classification_enabled}")

        if "keyword_spotting" in data:
            state.set_keyword_spotting(bool(data["keyword_spotting"]))
            log.info(f"Keyword spotting: {state.keyword_spotting_enabled}")

        if "anomaly_detection" in data:
            state.set_anomaly_detection(bool(data["anomaly_detection"]))
            log.info(f"Anomaly detection: {state.anomaly_detection_enabled}")

        return jsonify({"success": True}), 200

    return app
