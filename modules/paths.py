"""
paths.py - Centralized path resolution and Lost Ark window discovery.

Both helpers tolerate frozen-vs-script execution (PyInstaller .exe vs python gui.py)
and the Lost Ark window not being open.
"""

import os
import sys


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
        print(f"[Paths] Lost Ark window find error: {e}")
        return None
