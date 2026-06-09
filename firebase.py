"""
Firebase Realtime Database integration using Admin SDK.
"""

import logging

log = logging.getLogger(__name__)


def is_firebase_initialized():
    """Check if Firebase Admin SDK is initialized."""
    try:
        import firebase_admin
        return bool(firebase_admin._apps)
    except Exception:
        return False


def post_event(event_data: dict):
    """Post event to Firebase Realtime Database."""
    if not is_firebase_initialized():
        log.debug("Firebase not initialized - event post skipped")
        return None

    try:
        from firebase_admin import db
        ref = db.reference("events").push(event_data)
        log.debug(f"Event posted to Firebase: {ref.key}")
        return ref.key
    except Exception as e:
        log.error(f"Firebase event post failed: {e}")
        return None


def post_status(status_data: dict):
    """Post system status to Firebase."""
    if not is_firebase_initialized():
        log.debug("Firebase not initialized - status post skipped")
        return

    try:
        from firebase_admin import db
        db.reference("status").set(status_data)
        log.debug("Status posted to Firebase")
    except Exception as e:
        log.error(f"Firebase status post failed: {e}")


def push_status_now(state):
    """Push current system state flags to Firebase status immediately."""
    if not is_firebase_initialized():
        log.debug("Firebase not initialized - status push skipped")
        return

    try:
        from firebase_admin import db
        from datetime import datetime
        status = {
            "armed": state.armed,
            "keyword_spotting": state.keyword_spotting_enabled,
            "anomaly_detection": state.anomaly_detection_enabled,
            "last_update": datetime.now().isoformat(),
        }
        db.reference("status").set(status)
        log.debug("Status pushed to Firebase")
    except Exception as e:
        log.error(f"Firebase status push failed: {e}")


def push_absence_state(absence: dict):
    """Push the current absence-tracking state to Firebase /monitoring/absence."""
    if not is_firebase_initialized():
        return

    try:
        from firebase_admin import db
        db.reference("monitoring/absence").set(absence)
        log.debug("Absence state pushed to Firebase")
    except Exception as e:
        log.error(f"Firebase absence push failed: {e}")


def clear_absence_state():
    """Mark the absence node inactive (person is home / no active absence)."""
    if not is_firebase_initialized():
        return

    try:
        from firebase_admin import db
        db.reference("monitoring/absence").set({"active": False})
        log.debug("Absence state cleared in Firebase")
    except Exception as e:
        log.error(f"Firebase absence clear failed: {e}")


def push_model_status(status: dict):
    """Push model/training status to Firebase /model/status."""
    if not is_firebase_initialized():
        return

    try:
        from firebase_admin import db
        db.reference("model/status").set(status)
        log.debug("Model status pushed to Firebase")
    except Exception as e:
        log.error(f"Firebase model status push failed: {e}")


def read_anomaly_config():
    """Read /config/anomaly sensitivities from Firebase. Returns dict or None."""
    if not is_firebase_initialized():
        return None

    try:
        from firebase_admin import db
        result = db.reference("config/anomaly").get()
        if hasattr(result, "val"):
            result = result.val()
        return result if isinstance(result, dict) else None
    except Exception as e:
        log.debug(f"Firebase anomaly config read failed: {e}")
        return None
