"""
paths.py - Centralized path resolution and Lost Ark window discovery.

Both helpers tolerate frozen-vs-script execution (PyInstaller .exe vs python gui.py)
and the Lost Ark window not being open.
"""

import logging
import os
import shutil
import sys

logger = logging.getLogger(__name__)

LOSTARK_WINDOW_TITLE = "LOST ARK"


def get_base_dir() -> str:
    """Return the directory that contains config.yaml.

    When frozen (PyInstaller), this is the directory containing the .exe
    (one level up from `dist/` if the exe lives there). When running as a
    script, this is the project root.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.basename(exe_dir).lower() == "dist":
            return os.path.dirname(exe_dir)
        return exe_dir
    # __file__ is .../modules/paths.py — go up two levels
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource(rel_path: str) -> str:
    """Resolve a read-only bundled resource (templates, examples, icons, sounds).

    When frozen, files declared in PyInstaller's `datas=` are extracted to
    `sys._MEIPASS`. When running as a script, they live in the project root.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel_path)
    return os.path.join(get_base_dir(), rel_path)


def find_lostark_window() -> tuple[int, int] | None:
    """Return (left, top) of the Lost Ark window's client area, or None
    if Lost Ark is not visible on any monitor."""
    try:
        import win32gui

        def _cb(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if LOSTARK_WINDOW_TITLE.lower() in title.lower():
                    rect = win32gui.GetClientRect(hwnd)
                    pt = win32gui.ClientToScreen(hwnd, (rect[0], rect[1]))
                    results.append(pt)

        found = []
        win32gui.EnumWindows(_cb, found)
        return found[0] if found else None
    except Exception as e:
        logger.warning(f"[Paths] Lost Ark window find error: {e}")
        return None


def ensure_user_files(base_dir: str) -> None:
    """If config.yaml or the active roster don't exist, copy from bundled examples."""
    config = os.path.join(base_dir, "config.yaml")
    config_example = get_resource("config.example.yaml")
    if not os.path.exists(config) and os.path.exists(config_example):
        shutil.copy(config_example, config)
        logger.info(f"[Paths] Created {config} from example.")

    # Determine active roster from the (possibly newly-copied) config
    try:
        import yaml
        with open(config) as f:
            data = yaml.safe_load(f) or {}
        active = data.get("rotation", {}).get("active_roster", "example.yaml")
    except Exception:
        active = "example.yaml"

    rosters_dir = os.path.join(base_dir, "rosters")
    os.makedirs(rosters_dir, exist_ok=True)
    roster = os.path.join(rosters_dir, active)
    roster_example = get_resource(os.path.join("rosters", "example.yaml"))
    if not os.path.exists(roster) and os.path.exists(roster_example):
        shutil.copy(roster_example, roster)
        logger.info(f"[Paths] Created {roster} from example.")
