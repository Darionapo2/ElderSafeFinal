"""
Firebase Realtime Database integration.
"""

import logging
import requests
from config import FIREBASE_DB_URL

log = logging.getLogger(__name__)


def is_configured():
    """Check if Firebase is properly configured."""
    return bool(FIREBASE_DB_URL)


def post_event(event_data: dict):
    """Post event to Firebase Realtime Database."""
    if not is_configured():
        log.debug("Firebase not configured, skipping sync")
        return

    try:
        url = f"{FIREBASE_DB_URL}/events.json"
        requests.post(url, json=event_data, timeout=5)
        log.debug("✓ Posted to Firebase")
    except Exception as e:
        log.warning(f"Firebase sync failed: {e}")


def post_status(status_data: dict):
    """Post system status to Firebase."""
    if not is_configured():
        log.debug("Firebase not configured, skipping status sync")
        return

    try:
        url = f"{FIREBASE_DB_URL}/status.json"
        requests.put(url, json=status_data, timeout=5)
        log.debug("✓ Posted status to Firebase")
    except Exception as e:
        log.warning(f"Firebase status sync failed: {e}")
