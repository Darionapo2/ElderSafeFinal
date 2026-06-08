"""
CSV logging for entry/exit events.
"""

import csv
import logging
from pathlib import Path
from config import CSV_PATH, CSV_HEADER

log = logging.getLogger(__name__)


def init_csv():
    """Initialize CSV file if not exists."""
    try:
        if not Path(CSV_PATH).exists() or Path(CSV_PATH).stat().st_size == 0:
            with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(CSV_HEADER)
            log.info(f"CSV initialized: {CSV_PATH}")
    except Exception as e:
        log.error(f"CSV initialization failed: {e}")


def read_csv():
    """Read all CSV rows."""
    try:
        if not Path(CSV_PATH).exists():
            return []
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        log.error(f"CSV read failed: {e}")
        return []


def append_csv(row):
    """Append row to CSV."""
    try:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
    except Exception as e:
        log.error(f"CSV write failed: {e}")


def get_last_entry_exit():
    """Get last entry/exit event (skip alarms)."""
    rows = read_csv()
    for row in reversed(rows):
        if row.get("direction") in ["entry", "exit"]:
            return row
    return None
