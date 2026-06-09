"""
Absence tracker (Detector B runtime).

Owns the authoritative "is the person currently out?" state machine:
  - on an exit, opens an absence and computes the expected return window/deadline
  - on an entry, closes the absence
  - a background loop checks the deadline and fires the overdue alert

Tracking and the dashboard clock always run regardless of the anomaly-detection
toggle. The toggle only gates alert emission, and it is evaluated continuously:
if detection is off when the deadline passes and is turned back on while the
person is still out (and no alert has fired yet), the alert fires at that moment.
"""

import logging
import threading
import time
from datetime import datetime

from absence_model import load_absence_stats, predict_return_window
from events import on_overdue_absence
from firebase import push_absence_state, clear_absence_state
from config import ABSENCE_DEADLINE_CHECK_INTERVAL, return_late_k

log = logging.getLogger(__name__)


class AbsenceTracker:
    """State machine tracking the current absence and gating its overdue alert."""

    def __init__(self, state):
        self.state = state
        self.lock = threading.Lock()
        self.absence = None  # current absence dict, or None when home
        self.stats = load_absence_stats()

    def on_exit(self, exit_dt: datetime = None):
        """Open a new absence and publish its expected return window."""
        exit_dt = exit_dt or datetime.now()

        # Reload stats so we always use the freshest model after a retrain.
        self.stats = load_absence_stats()
        k = return_late_k(self.state.return_late_sensitivity)
        window = predict_return_window(exit_dt, self.stats, k)

        with self.lock:
            self.absence = {
                "active": True,
                "exit_time": exit_dt.isoformat(),
                "status": "out",
                "alerted": False,
                "dismissed": False,
                **window,
            }
            snapshot = dict(self.absence)

        push_absence_state(snapshot)
        log.info(
            f"Absence opened: out at {exit_dt.strftime('%H:%M:%S')}, "
            f"expected back by {window['expected_return_at']}, "
            f"deadline {window['late_deadline_at']} ({window['confidence']} confidence)"
        )

    def on_entry(self):
        """Close the current absence (person returned)."""
        with self.lock:
            if not self.absence or not self.absence.get("active"):
                return
            self.absence = None

        clear_absence_state()
        log.info("Absence closed: person returned")

    def dismiss(self) -> bool:
        """Manually dismiss the current absence alert (cancel-only, no model change)."""
        with self.lock:
            if not self.absence or not self.absence.get("active"):
                return False
            self.absence["dismissed"] = True
            self.absence["status"] = "dismissed"
            snapshot = dict(self.absence)

        push_absence_state(snapshot)
        log.info("Absence alert dismissed by user")
        return True

    def check_deadline(self):
        """Evaluate the overdue deadline and fire the alert when due and enabled."""
        fire_snapshot = None
        changed_snapshot = None

        with self.lock:
            if not self.absence or not self.absence.get("active"):
                return
            if self.absence.get("dismissed"):
                return

            deadline = datetime.fromisoformat(self.absence["late_deadline_at"])
            is_overdue = datetime.now() >= deadline

            # Visual transition out -> overdue happens regardless of the toggle.
            if is_overdue and self.absence.get("status") == "out":
                self.absence["status"] = "overdue"
                changed_snapshot = dict(self.absence)

            # Continuous gating: fire once when overdue, not yet alerted, enabled.
            should_fire = (
                is_overdue
                and not self.absence.get("alerted")
                and self.state.anomaly_detection_enabled
            )
            if should_fire:
                self.absence["alerted"] = True
                fire_snapshot = dict(self.absence)
                changed_snapshot = None  # fire_snapshot already carries latest state

        if changed_snapshot:
            push_absence_state(changed_snapshot)
        if fire_snapshot:
            push_absence_state(fire_snapshot)
            on_overdue_absence(self.state, fire_snapshot)


def deadline_loop(tracker: AbsenceTracker):
    """Background loop that periodically checks the absence deadline."""
    log.info("Absence deadline loop started")
    while True:
        try:
            tracker.check_deadline()
        except Exception as e:
            log.error(f"Absence deadline check failed: {e}")
        time.sleep(ABSENCE_DEADLINE_CHECK_INTERVAL)
