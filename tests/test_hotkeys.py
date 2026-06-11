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


def test_update_key_then_stop_unregisters_everything(fake):
    mgr = HotkeyManager({"start_stop": "f8"}, {"start_stop": lambda: None})
    mgr.start()
    mgr.update_key("start_stop", "f5")
    mgr.stop()
    assert fake.active == {}


def test_rebound_key_has_single_handler_after_restart(fake):
    mgr = HotkeyManager({"start_stop": "f8"}, {"start_stop": lambda: None})
    mgr.start()
    mgr.update_key("start_stop", "f5")
    mgr.stop()
    mgr.start()
    assert {k: len(v) for k, v in fake.active.items()} == {"f5": 1}
