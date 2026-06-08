"""
Logging setup for file output.
All logs written to file for remote monitoring via SSH.
"""

import logging
import logging.handlers
import os
from pathlib import Path

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "eldersafe.log")


def setup_logging():
    """Configure logging to file."""
    try:
        Path(LOG_DIR).mkdir(exist_ok=True)
    except Exception as e:
        print(f"Log directory creation failed: {e}")
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s - [%(threadName)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    try:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"File handler setup failed: {e}")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.getLogger("arduino.app_peripherals.microphone").setLevel(logging.INFO)
    logging.getLogger("websockets").setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)

    log = logging.getLogger(__name__)
    log.info(f"Logging to {LOG_FILE}")
