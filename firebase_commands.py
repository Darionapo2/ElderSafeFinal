"""
Firebase command polling.
Polls Firebase for pending commands every 2 seconds.
"""

import logging
import time
import threading
from datetime import datetime, timezone
from firebase_admin import db
from models import SystemState

log = logging.getLogger(__name__)

# Track which commands we've already processed (prevent duplicates)
_processed_commands = set()

# Absence tracker reference, set at setup so dismiss commands can reach it.
_absence_tracker = None


def setup_firebase_command_listener(state: SystemState, absence_tracker=None):
    """Start background polling thread for Firebase commands."""
    global _absence_tracker
    _absence_tracker = absence_tracker
    try:
        poll_thread = threading.Thread(
            target=_command_polling_loop,
            args=(state,),
            daemon=True,
            name="CommandPoller"
        )
        poll_thread.start()
        log.info("Firebase command polling thread started")

    except Exception as e:
        log.error(f"Firebase command polling setup failed: {e}")


def _sync_anomaly_config(state: SystemState):
    """Mirror /config/anomaly sensitivities into the live system state."""
    try:
        from firebase import read_anomaly_config
        config = read_anomaly_config()
        if not config:
            return
        if "unusual_time_sensitivity" in config:
            state.set_unusual_time_sensitivity(config["unusual_time_sensitivity"])
        if "return_late_sensitivity" in config:
            state.set_return_late_sensitivity(config["return_late_sensitivity"])
    except Exception as e:
        log.debug(f"Anomaly config sync failed: {e}")


def _command_polling_loop(state: SystemState):
    """Poll Firebase /commands every 2 seconds for pending commands."""
    log.info("Command polling started")

    while True:
        try:
            time.sleep(2)

            # Keep live sensitivities in sync with the dashboard sliders.
            _sync_anomaly_config(state)

            commands_ref = db.reference("commands")
            result = commands_ref.get()

            if hasattr(result, 'val'):
                commands = result.val()
            else:
                commands = result

            if not commands or not isinstance(commands, dict):
                continue

            for cmd_id, cmd_data in commands.items():
                if not cmd_data or not isinstance(cmd_data, dict):
                    continue

                if cmd_id in _processed_commands:
                    continue

                if cmd_data.get("status") != "pending":
                    continue

                try:
                    timestamp_str = cmd_data.get("timestamp", "")
                    if timestamp_str:
                        cmd_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        age_seconds = (datetime.now(timezone.utc) - cmd_timestamp).total_seconds()
                        if age_seconds > 300:
                            log.debug(f"Skipping old command {cmd_id}")
                            _processed_commands.add(cmd_id)
                            continue
                except Exception as e:
                    log.debug(f"Timestamp parsing failed: {e}")

                log.info(f"Found pending command {cmd_id}: {cmd_data.get('type')}")
                execute_command(cmd_id, cmd_data, state)
                _processed_commands.add(cmd_id)

        except Exception as e:
            log.error(f"Command polling failed: {e}")
            time.sleep(5)


def execute_command(cmd_id: str, cmd_data: dict, state: SystemState):
    """Execute command, sync hardware state, and push status to Firebase."""
    try:
        command_type = cmd_data.get("type")
        value = cmd_data.get("value")

        update_command_status(cmd_id, "executing", None)
        log.info(f"Executing command {cmd_id}: {command_type} = {value}")

        try:
            from sensors import SensorMonitor
            monitor = SensorMonitor()
        except Exception as e:
            log.debug(f"SensorMonitor unavailable: {e}")
            monitor = None

        if command_type == "set_armed":
            new_armed = bool(value)
            old_armed = state.armed
            state.set_armed(new_armed)
            state.set_keyword_spotting(new_armed)
            state.set_anomaly_detection(new_armed)
            if monitor and old_armed != new_armed:
                monitor.set_system_armed(new_armed)
            response = f"System {'armed' if new_armed else 'disarmed'}"

        elif command_type == "set_keyword_spotting":
            old_armed = state.armed
            state.set_keyword_spotting(bool(value))
            new_armed = state.keyword_spotting_enabled or state.anomaly_detection_enabled
            state.set_armed(new_armed)
            if monitor and old_armed != new_armed:
                monitor.set_system_armed(new_armed)
            response = f"Keyword spotting {'enabled' if value else 'disabled'}"

        elif command_type == "set_anomaly_detection":
            old_armed = state.armed
            state.set_anomaly_detection(bool(value))
            new_armed = state.keyword_spotting_enabled or state.anomaly_detection_enabled
            state.set_armed(new_armed)
            if monitor and old_armed != new_armed:
                monitor.set_system_armed(new_armed)
            response = f"Anomaly detection {'enabled' if value else 'disabled'}"

        elif command_type == "set_sound_classification":
            state.set_sound_classification(bool(value))
            response = f"Sound classification {'enabled' if value else 'disabled'}"

        elif command_type == "retrain_model":
            from retraining import retrain_all
            result = retrain_all()
            response = (
                f"Model retrained: {result['training_samples']} samples "
                f"(real={result['real_events_in_window']}, "
                f"synthetic={result['synthetic_in_window']})"
                if result.get("trained")
                else "Not enough data to retrain; existing model kept"
            )

        elif command_type == "dismiss_absence":
            if _absence_tracker and _absence_tracker.dismiss():
                response = "Absence alert dismissed"
            else:
                response = "No active absence to dismiss"

        else:
            raise ValueError(f"Unknown command type: {command_type}")

        from firebase import push_status_now
        push_status_now(state)

        update_command_status(cmd_id, "completed", response)
        log.info(f"Command {cmd_id} completed: {response}")

    except Exception as e:
        log.error(f"Command {cmd_id} failed: {e}")
        update_command_status(cmd_id, "failed", str(e))


def update_command_status(cmd_id: str, status: str, response: str = None):
    """Update command status in Firebase."""
    try:
        update_data = {
            "status": status,
            "updated_at": datetime.now().isoformat()
        }

        if response:
            update_data["response"] = response

        db.reference(f"commands/{cmd_id}").update(update_data)
    except Exception as e:
        log.error(f"Failed to update command status: {e}")


def cleanup_old_commands(max_age_hours: int = 24):
    """Delete commands older than max_age_hours to prevent database bloat."""
    try:
        now = datetime.now(timezone.utc)
        ref = db.reference("commands")
        result = ref.get()

        if hasattr(result, 'val'):
            commands = result.val()
        else:
            commands = result

        if not commands or not isinstance(commands, dict):
            return

        for cmd_id, cmd_data in commands.items():
            if not cmd_data or not isinstance(cmd_data, dict) or "timestamp" not in cmd_data:
                continue

            try:
                cmd_time = datetime.fromisoformat(cmd_data["timestamp"].replace("Z", "+00:00"))
                age_hours = (now - cmd_time).total_seconds() / 3600

                if age_hours > max_age_hours:
                    db.reference(f"commands/{cmd_id}").delete()
                    log.debug(f"Old command deleted: {cmd_id}")
            except Exception as e:
                log.debug(f"Timestamp parsing failed: {e}")

    except Exception as e:
        log.error(f"Command cleanup failed: {e}")
