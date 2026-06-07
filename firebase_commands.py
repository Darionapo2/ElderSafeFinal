"""
Firebase command listener with robust feedback.
Arduino listens for commands and sends responses back.
"""

import logging
import time
from datetime import datetime
from firebase_admin import db
from models import SystemState

log = logging.getLogger(__name__)


def setup_firebase_command_listener(state: SystemState):
    """
    Setup Firebase listener for control commands.

    Command structure:
    {
        "type": "set_armed" | "set_keyword_spotting" | "set_anomaly_detection",
        "value": true | false,
        "source": "telegram" | "dashboard",
        "timestamp": "2026-06-07T12:34:56Z",
        "status": "pending" | "executing" | "completed" | "failed"
    }
    """
    try:
        ref = db.reference("commands")

        def on_command_change(message):
            """Called when new commands appear in Firebase."""
            try:
                data = message.data
                if not data:
                    return

                # Process each command
                for cmd_id, cmd_data in data.items():
                    if not cmd_data:
                        continue

                    # Skip if already processed
                    if cmd_data.get("status") != "pending":
                        continue

                    execute_command(cmd_id, cmd_data, state)

            except Exception as e:
                log.error(f"Error in command listener: {e}")

        ref.listen(on_command_change)
        log.info("✓ Firebase command listener started")

    except Exception as e:
        log.error(f"Failed to setup Firebase listener: {e}")


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
            response = f"Sistema {'ATTIVATO' if value else 'DISATTIVATO'}"

        elif command_type == "set_keyword_spotting":
            state.set_keyword_spotting(bool(value))
            response = f"Keyword spotting {'ABILITATO' if value else 'DISABILITATO'}"

        elif command_type == "set_anomaly_detection":
            state.set_anomaly_detection(bool(value))
            response = f"Anomaly detection {'ABILITATO' if value else 'DISABILITATO'}"

        elif command_type == "set_sound_classification":
            state.set_sound_classification(bool(value))
            response = f"Sound classification {'ABILITATO' if value else 'DISABILITATO'}"

        else:
            raise ValueError(f"Unknown command type: {command_type}")

        # Mark as completed
        update_command_status(cmd_id, "completed", response)
        log.info(f"✓ Command {cmd_id} completed: {response}")

    except Exception as e:
        log.error(f"✗ Command {cmd_id} failed: {e}")
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
    """
    Delete commands older than max_age_hours.
    Run periodically to prevent Firebase bloat.
    """
    try:
        now = datetime.now()
        ref = db.reference("commands")
        commands = ref.get().val()

        if not commands:
            return

        for cmd_id, cmd_data in commands.items():
            if not cmd_data or "timestamp" not in cmd_data:
                continue

            try:
                cmd_time = datetime.fromisoformat(cmd_data["timestamp"].replace("Z", "+00:00"))
                age_hours = (now - cmd_time).total_seconds() / 3600

                if age_hours > max_age_hours:
                    db.reference(f"commands/{cmd_id}").delete()
                    log.debug(f"Cleaned up old command {cmd_id}")
            except Exception as e:
                log.debug(f"Error parsing command timestamp: {e}")

    except Exception as e:
        log.error(f"Cleanup failed: {e}")
