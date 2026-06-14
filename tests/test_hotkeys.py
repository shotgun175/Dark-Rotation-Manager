"""Tests for HotkeyManager registry bookkeeping (no real keyboard hooks)."""

import pytest

from modules import hotkeys
from modules.hotkeys import HotkeyManager


class FakeKeyboard:
    """Records add/remove calls; mimics keyboard's KeyError on unknown remove."""

    def __init__(self):
        self.active = {}  # key -> handler

    def add_hotkey(self, key, fn, suppress=False):
        self.active.setdefault(key, []).append(fn)

    def remove_hotkey(self, key):
        if key not in self.active or not self.active[key]:
            raise KeyError(key)
        self.active[key].pop()
        if not self.active[key]:
            del self.active[key]


@pytest.fixture
def fake(monkeypatch):
    fake = FakeKeyboard()
    monkeypatch.setattr(hotkeys, "keyboard", fake)
    return fake


def test_start_registers_all_configured_keys(fake):
    mgr = HotkeyManager(
        {"start_stop": "f8", "confirm": "f9"},
        {"start_stop": lambda: None, "confirm": lambda: None},
    )
    mgr.start()
    assert {k: len(v) for k, v in fake.active.items()} == {"f8": 1, "f9": 1}


def test_stop_unregisters_everything(fake):
    mgr = HotkeyManager({"start_stop": "f8"}, {"start_stop": lambda: None})
    mgr.start()
    mgr.stop()
    assert fake.active == {}
