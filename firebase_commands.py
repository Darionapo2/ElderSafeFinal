"""
Firebase command polling (NOT listener - more reliable for Arduino).
Polls Firebase for pending commands every 1-2 seconds.
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
    """
    Start background polling thread for Firebase commands.
    Polling is MORE RELIABLE than ref.listen() for embedded systems.

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
        # Start polling in background daemon thread
        poll_thread = threading.Thread(
            target=_command_polling_loop,
            args=(state,),
            daemon=True,
            name="CommandPoller"
        )
        poll_thread.start()
        log.info("✓ Firebase command polling thread started (checks every 2 seconds)")

    except Exception as e:
        log.error(f"Failed to setup Firebase command polling: {e}")


def _command_polling_loop(state: SystemState):
    """
    Background thread: poll Firebase /commands every 2 seconds.
    Much more reliable than listen() for Arduino with unstable connections.
    """
    log.info("Command polling loop started")

    while True:
        try:
            time.sleep(2)  # Poll every 2 seconds

            # Read all commands from Firebase
            commands_ref = db.reference("commands")
            result = commands_ref.get()

            # Handle both snapshot objects and direct dict returns
            # (Arduino SDK may return dict directly instead of snapshot)
            if hasattr(result, 'val'):
                commands = result.val()
            else:
                commands = result

            # No commands yet
            if not commands or not isinstance(commands, dict):
                continue

            # Process each pending command
            for cmd_id, cmd_data in commands.items():
                if not cmd_data or not isinstance(cmd_data, dict):
                    continue

                # Skip if already processed in this session
                if cmd_id in _processed_commands:
                    continue

                # Only process commands with status="pending"
                if cmd_data.get("status") != "pending":
                    continue

                # Skip commands older than 5 minutes (avoid stale commands on startup)
                try:
                    timestamp_str = cmd_data.get("timestamp", "")
                    if timestamp_str:
                        cmd_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        age_seconds = (datetime.now(datetime.timezone.utc) - cmd_timestamp).total_seconds()
                        if age_seconds > 300:  # 5 minutes
                            log.debug(f"Skipping old command {cmd_id} (age: {age_seconds:.0f}s)")
                            _processed_commands.add(cmd_id)
                            continue
                except Exception as e:
                    log.debug(f"Error parsing timestamp: {e}")

                # Execute the pending command
                log.info(f"📨 Found pending command {cmd_id}: {cmd_data.get('type')}")
                execute_command(cmd_id, cmd_data, state)
                _processed_commands.add(cmd_id)

        except Exception as e:
            log.error(f"Error in command polling loop: {e}")
            time.sleep(5)  # Back off on error


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
            # Update LED to match armed state
            try:
                from sensors import SensorMonitor
                monitor = SensorMonitor()
                monitor.set_led_armed(bool(value))
                log.info(f"🔦 LED updated via Firebase command")
            except Exception as e:
                log.debug(f"LED sync error: {e}")

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
        result = ref.get()

        # Handle both snapshot objects and direct dict returns
        if hasattr(result, 'val'):
            commands = result.val()
        else:
            commands = result

        # No commands to clean
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
                    log.debug(f"Cleaned up old command {cmd_id}")
            except Exception as e:
                log.debug(f"Error parsing command timestamp: {e}")

    except Exception as e:
        log.error(f"Cleanup failed: {e}")
