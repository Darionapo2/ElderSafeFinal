"""
Firebase command polling.
Polls Firebase for pending commands every 2 seconds.
"""

import logging
import time
import threading
from datetime import datetime
from firebase_admin import db
from models import SystemState

log = logging.getLogger(__name__)

# Track which commands we've already processed (prevent duplicates)
_processed_commands = set()


def setup_firebase_command_listener(state: SystemState):
    """Start background polling thread for Firebase commands."""
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


def _command_polling_loop(state: SystemState):
    """Poll Firebase /commands every 2 seconds for pending commands."""
    log.info("Command polling started")

    while True:
        try:
            time.sleep(2)

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
                        age_seconds = (datetime.now(datetime.timezone.utc) - cmd_timestamp).total_seconds()
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
    """Execute command and update status in Firebase."""
    try:
        command_type = cmd_data.get("type")
        value = cmd_data.get("value")

        # Mark as executing
        update_command_status(cmd_id, "executing", None)
        log.info(f"Executing command {cmd_id}: {command_type} = {value}")

        # Execute based on type
        if command_type == "set_armed":
            state.set_armed(bool(value))
            response = f"System {'armed' if value else 'disarmed'}"
            try:
                from sensors import SensorMonitor
                monitor = SensorMonitor()
                monitor.set_led_armed(bool(value))
                log.info("LED updated")
            except Exception as e:
                log.debug(f"LED update failed: {e}")

        elif command_type == "set_keyword_spotting":
            state.set_keyword_spotting(bool(value))
            response = f"Keyword spotting {'enabled' if value else 'disabled'}"

        elif command_type == "set_anomaly_detection":
            state.set_anomaly_detection(bool(value))
            response = f"Anomaly detection {'enabled' if value else 'disabled'}"

        elif command_type == "set_sound_classification":
            state.set_sound_classification(bool(value))
            response = f"Sound classification {'enabled' if value else 'disabled'}"

        else:
            raise ValueError(f"Unknown command type: {command_type}")

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
        now = datetime.now()
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
