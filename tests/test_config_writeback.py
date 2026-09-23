"""ConfigApp config write-back keeps hand edits made while the app is open (offscreen Qt)."""

import logging
import os
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
import yaml
from PyQt5.QtWidgets import QApplication

from modules import gui_app


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def make_window(app, tmp_path, monkeypatch):
    """Factory -> (window, config_path, rosters_dir) on a tmp copy of the example config."""
    monkeypatch.setattr(gui_app, "check_for_update_async", lambda *_a, **_k: None)
    monkeypatch.setattr(gui_app, "BASE_DIR", str(tmp_path))
    rosters = tmp_path / "rosters"
    rosters.mkdir()
    shutil.copy(os.path.join(os.path.dirname(__file__), "..", "rosters", "example.yaml"),
                rosters / "example.yaml")
    cfg = tmp_path / "config.yaml"
    shutil.copy(os.path.join(os.path.dirname(__file__), "..", "config.example.yaml"), cfg)
    windows = []

    def _make():
        w = gui_app.ConfigApp(str(cfg))
        windows.append(w)
        return w, cfg, rosters

    yield _make
    for w in windows:
        w.deleteLater()


def _read(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _hand_edit(path, mutate):
    data = _read(path)
    mutate(data)
    path.write_text(yaml.dump(data), encoding="utf-8")


def test_hand_edited_threshold_survives_close(make_window):
    w, cfg, _ = make_window()
    _hand_edit(cfg, lambda d: d["detection"].__setitem__("threshold", 0.9))

    w.close()

    assert _read(cfg)["detection"]["threshold"] == 0.9


def test_apply_saves_players_to_loaded_roster_after_active_roster_hand_edit(make_window):
    w, cfg, rosters = make_window()
    (rosters / "other.yaml").write_text(
        yaml.dump({"name": "Other", "players": ["X"]}), encoding="utf-8"
    )
    tab_players = w._roster_tab.get_players()
    _hand_edit(cfg, lambda d: d["rotation"].__setitem__("active_roster", "other.yaml"))

    w._apply()

    # The tab's players land in the roster that was loaded into the tab...
    assert _read(rosters / "example.yaml")["players"] == tab_players
    assert _read(rosters / "other.yaml")["players"] == ["X"]
    # ...and the hand-picked roster stays selected for the next Launch.
    assert _read(cfg)["rotation"]["active_roster"] == "other.yaml"

    # A second Apply still saves to the tab's roster, not the hand-picked one.
    w._apply()

    assert _read(rosters / "example.yaml")["players"] == tab_players
    assert _read(rosters / "other.yaml") == {"name": "Other", "players": ["X"]}


def test_apply_after_launch_reloads_roster_keeps_tab_roster_file_and_name(make_window):
    w, cfg, rosters = make_window()
    (rosters / "other.yaml").write_text(
        yaml.dump({"name": "Other", "players": ["X"]}), encoding="utf-8"
    )
    tab_players = w._roster_tab.get_players()
    # Launch re-reads active_roster and loads it, but the Roster tab is not refreshed.
    w._roster_mgr.load("other.yaml")

    w._apply()

    assert _read(rosters / "example.yaml") == {"name": "Example Raid", "players": tab_players}
    assert _read(rosters / "other.yaml") == {"name": "Other", "players": ["X"]}


def test_non_dict_reread_keeps_in_memory_copy_and_warns(make_window, caplog):
    w, cfg, _ = make_window()
    cfg.write_text("- not\n- a mapping\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="modules.gui_app"):
        w.close()

    saved = _read(cfg)
    assert isinstance(saved, dict)
    assert saved["detection"]["threshold"] == 0.75
    assert any(r.levelno == logging.WARNING for r in caplog.records)
