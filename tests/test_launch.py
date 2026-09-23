"""Launch runs what the settings window shows (offscreen Qt)."""

import os
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import yaml
from PyQt5.QtWidgets import QApplication

from modules import bot_controller, gui_app
from modules.bot_controller import BotController
from modules.tabs.overlay_tab import OverlayTab


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    """-> (window, config_path, start_calls) with BotController.start recorded, not run."""
    monkeypatch.setattr(gui_app, "check_for_update_async", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_app, "BASE_DIR", str(tmp_path))
    rosters = tmp_path / "rosters"
    rosters.mkdir()
    here = os.path.dirname(__file__)
    shutil.copy(os.path.join(here, "..", "rosters", "example.yaml"), rosters / "example.yaml")
    cfg = tmp_path / "config.yaml"
    shutil.copy(os.path.join(here, "..", "config.example.yaml"), cfg)

    w = gui_app.ConfigApp(str(cfg))
    starts = []
    monkeypatch.setattr(
        w._controller, "start",
        lambda config, players, **_k: starts.append((config, players)),
    )
    w.show()
    yield w, cfg, starts
    if w._preview_overlay:
        w._preview_overlay.close()
    w.deleteLater()


def test_launch_uses_unapplied_tab_edits(window):
    w, _, starts = window
    w._roster_tab._add_input.setText("NewGuy")
    w._roster_tab._add_player()
    w._rotation_tab._max_throws.setValue(7)

    w._start_bot()

    config, players = starts[-1]
    assert "NewGuy" in players
    assert config["rotation"]["max_throws_per_run"] == 7


def test_duplicate_hotkey_blocks_launch_and_keeps_window(window):
    w, _, starts = window
    w._hotkeys_tab._bindings["confirm"] = w._hotkeys_tab._bindings["start_stop"]

    w._start_bot()

    assert starts == []
    assert w.isVisible()


def test_hand_edited_threshold_reaches_launch(window):
    w, cfg, starts = window
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    data["detection"]["threshold"] = 0.9
    cfg.write_text(yaml.dump(data), encoding="utf-8")

    w._start_bot()

    assert starts[-1][0]["detection"]["threshold"] == 0.9


def test_launch_closes_the_position_preview(window):
    w, _, _ = window
    w._handle_preview()
    preview = w._preview_overlay
    assert preview is not None and preview.isVisible()

    w._start_bot()

    assert w._preview_overlay is None
    assert not preview.isVisible()


def test_missing_detection_enabled_shows_unticked(app):
    assert OverlayTab({}).get_detection_enabled() is False


def test_missing_detection_enabled_builds_no_detection(monkeypatch):
    built = []

    class Fake:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, name):
            return lambda *a, **k: None

    class FakeDetection(Fake):
        def __init__(self, *a, **k):
            built.append(self)

    for name in ("RotationEngine", "OverlayWindow", "HotkeyManager", "AudioManager"):
        monkeypatch.setattr(bot_controller, name, Fake)
    monkeypatch.setattr(bot_controller, "DetectionEngine", FakeDetection)

    ctrl = BotController(lambda *a: None)
    ctrl.start({}, ["A"], None, None)

    assert built == []
    assert ctrl.detection is None
