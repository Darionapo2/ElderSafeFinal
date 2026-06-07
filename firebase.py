"""
Firebase Realtime Database integration using Admin SDK.
"""

import logging
from firebase_admin import db

log = logging.getLogger(__name__)


def post_event(event_data: dict):
    """
    Post event to Firebase Realtime Database.

    Events are appended to /events with auto-generated IDs.
    """
    try:
        ref = db.reference("events").push(event_data)
        log.debug(f"✓ Event posted to Firebase (ID: {ref.key})")
        return ref.key
    except Exception as e:
        log.error(f"Failed to post event to Firebase: {e}")
        return None


def post_status(status_data: dict):
    """
    Post system status to Firebase.

    Status is written to /status and overwrites previous status.
    """
    try:
        db.reference("status").set(status_data)
        log.debug("✓ Status posted to Firebase")
    except Exception as e:
        log.error(f"Failed to post status to Firebase: {e}")
