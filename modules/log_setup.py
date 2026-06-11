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
import sys
import threading
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
    install_excepthooks(log_path)
    logging.getLogger(__name__).info("Logging initialized -> %s", log_path)
    return log_path


def install_excepthooks(log_path: str) -> None:
    """Route unhandled exceptions (main and worker threads) into the log.

    The exe is built with console=False, so without these hooks any unhandled
    exception kills the app with nothing written anywhere.
    """

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger(__name__).critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
        )
        _show_crash_dialog(log_path)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_hook(args):
        thread_name = args.thread.name if args.thread else "<unknown>"
        logging.getLogger(__name__).critical(
            "Unhandled exception in thread %s",
            thread_name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _hook
    threading.excepthook = _thread_hook


def _show_crash_dialog(log_path: str) -> None:
    """Point the user at the log file, but only if Qt is already running."""
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return
        QMessageBox.critical(
            None,
            "Dark Rotation Manager",
            "An unexpected error occurred.\nDetails were written to:\n" + log_path,
        )
    except Exception:
        pass  # never let the crash reporter crash the crash path
