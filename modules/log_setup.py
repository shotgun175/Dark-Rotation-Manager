"""
log_setup.py - Centralized application logging.

The shipped .exe is built with console=False (see the .spec), so anything
written to stdout/stderr is discarded. setup_logging() routes log output to a
rotating file under <base_dir>/logs/ instead, keeping the build diagnosable.

Call setup_logging() exactly once, as early as possible at startup (see
gui.py). It is idempotent — repeat calls are no-ops.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from modules.paths import get_base_dir

LOG_FILENAME = "dark_rotation_manager.log"

_configured = False


def setup_logging() -> str:
    """Configure root logging to a rotating file; return the log file path.

    Writes to <base_dir>/logs/dark_rotation_manager.log, rotating at ~1 MB and
    keeping 5 backups. Safe to call more than once.
    """
    global _configured

    log_dir = os.path.join(get_base_dir(), "logs")
    log_path = os.path.join(log_dir, LOG_FILENAME)
    if _configured:
        return log_path

    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    _configured = True
    logging.getLogger(__name__).info("Logging initialized -> %s", log_path)
    return log_path
