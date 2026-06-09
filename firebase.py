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
