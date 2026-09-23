"""Tests for find_lostark_window against a fake win32gui."""

import sys
import types

from modules.paths import find_lostark_window


def _fake_win32gui(windows):
    """windows: list of (title, (left, top)) in top-to-bottom stacking order."""
    return types.SimpleNamespace(
        EnumWindows=lambda cb, extra: [cb(hwnd, extra) for hwnd in range(len(windows))],
        IsWindowVisible=lambda hwnd: True,
        GetWindowText=lambda hwnd: windows[hwnd][0],
        GetClientRect=lambda hwnd: (0, 0, 1920, 1080),
        ClientToScreen=lambda hwnd, pt: windows[hwnd][1],
    )


def test_matches_the_game_client_not_other_windows_named_after_it(monkeypatch):
    fake = _fake_win32gui([
        ("Lost Ark Tools - Google Chrome", (200, 50)),
        ("Lost Ark", (300, 80)),  # an Explorer folder
        ("LOST ARK (64-bit, DX11) v.3.23.1.1", (0, 0)),
    ])
    monkeypatch.setitem(sys.modules, "win32gui", fake)

    assert find_lostark_window() == (0, 0)


def test_returns_none_when_only_lookalike_windows_are_open(monkeypatch):
    fake = _fake_win32gui([("Lost Ark - Visual Studio Code", (10, 10))])
    monkeypatch.setitem(sys.modules, "win32gui", fake)

    assert find_lostark_window() is None
