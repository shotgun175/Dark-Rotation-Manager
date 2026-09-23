"""Tests for HotkeyManager registration and press handling (no real keyboard hooks)."""

import logging
from types import SimpleNamespace

import pytest

from modules import hotkeys
from modules.hotkeys import HotkeyManager


class FakeKeyboard:
    """Mimics the parts of keyboard 0.13.5 that HotkeyManager uses.

    Like the real library, hook_key rejects combos with ValueError, and
    remove_hotkey/unhook raise KeyError for unknown handles.
    """

    KEY_DOWN = "down"
    KEY_UP = "up"

    def __init__(self):
        self.active = {}  # combo key -> add_hotkey handlers
        self.hooks = []   # (key, callback) handles from hook_key

    def parse_hotkey(self, key):
        return tuple(tuple(step.split("+")) for step in key.split(", "))

    def add_hotkey(self, key, fn, suppress=False):
        self.active.setdefault(key, []).append(fn)
        return key

    def remove_hotkey(self, key):
        if key not in self.active or not self.active[key]:
            raise KeyError(key)
        self.active[key].pop()
        if not self.active[key]:
            del self.active[key]

    def hook_key(self, key, fn, suppress=False):
        if "+" in key or "," in key:
            raise ValueError(f"Key {key!r} is not mapped to any known key.")
        handle = (key, fn)
        self.hooks.append(handle)
        return handle

    def unhook(self, handle):
        if handle not in self.hooks:
            raise KeyError(handle)
        self.hooks.remove(handle)

    def hooked(self):
        return sorted(key for key, _ in self.hooks)

    def _send(self, key, event_type):
        for k, fn in list(self.hooks):
            if k == key:
                fn(SimpleNamespace(event_type=event_type))

    def down(self, key):
        self._send(key, self.KEY_DOWN)

    def up(self, key):
        self._send(key, self.KEY_UP)


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
    assert fake.hooked() == ["f8", "f9"]
    assert fake.active == {}


def test_single_keys_use_key_hooks_and_combos_use_add_hotkey(fake):
    calls = []
    mgr = HotkeyManager(
        {"confirm": "f9", "missed": "ctrl+f9", "reset": "a, s"},
        {
            "confirm": lambda: calls.append("confirm"),
            "missed": lambda: calls.append("missed"),
            "reset": lambda: calls.append("reset"),
        },
    )
    mgr.start()
    assert fake.hooked() == ["f9"]
    assert sorted(fake.active) == ["a, s", "ctrl+f9"]
    fake.active["ctrl+f9"][0]()
    fake.active["a, s"][0]()
    assert calls == ["missed", "reset"]


def test_stop_unregisters_everything(fake):
    mgr = HotkeyManager(
        {"start_stop": "f8", "confirm": "ctrl+f9"},
        {"start_stop": lambda: None, "confirm": lambda: None},
    )
    mgr.start()
    mgr.stop()
    assert fake.hooks == []
    assert fake.active == {}


def test_stop_survives_a_handle_that_is_already_gone(fake):
    mgr = HotkeyManager(
        {"start_stop": "f8", "confirm": "f9", "missed": "ctrl+f10"},
        {"start_stop": lambda: None, "confirm": lambda: None, "missed": lambda: None},
    )
    mgr.start()
    fake.hooks.pop(0)  # unhook() of this handle now raises KeyError
    mgr.stop()
    assert fake.hooks == []
    assert fake.active == {}


def test_held_key_fires_once_per_press(fake):
    calls = []
    mgr = HotkeyManager({"missed": "f10"}, {"missed": lambda: calls.append(1)})
    mgr.start()
    fake.down("f10")
    fake.down("f10")  # OS auto-repeat: a second KEY_DOWN with no KEY_UP
    assert calls == [1]
    fake.up("f10")
    fake.down("f10")
    assert calls == [1, 1]


def test_raising_action_is_logged_and_does_not_propagate(fake, caplog):
    def boom():
        raise RuntimeError("boom")

    mgr = HotkeyManager({"confirm": "f9"}, {"confirm": boom})
    mgr.start()
    with caplog.at_level(logging.ERROR, logger="modules.hotkeys"):
        fake.down("f9")
    assert "confirm handler failed" in caplog.text
    assert "RuntimeError: boom" in caplog.text
