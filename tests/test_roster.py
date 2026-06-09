"""Tests for RosterManager YAML load/save parsing."""

import pytest

from modules.roster import RosterManager


def _write(path, text: str):
    path.write_text(text, encoding="utf-8")


def test_load_returns_players_and_name(tmp_path):
    _write(tmp_path / "r.yaml", "name: Raid Night\nplayers:\n- Alice\n- Bob\n")
    mgr = RosterManager(str(tmp_path))
    players = mgr.load("r.yaml")
    assert players == ["Alice", "Bob"]
    assert mgr.current_roster_name == "Raid Night"


def test_load_missing_file_raises(tmp_path):
    mgr = RosterManager(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        mgr.load("nope.yaml")


def test_load_coerces_players_to_str(tmp_path):
    _write(tmp_path / "r.yaml", "name: N\nplayers:\n- 1\n- 2\n- Bob\n")
    mgr = RosterManager(str(tmp_path))
    assert mgr.load("r.yaml") == ["1", "2", "Bob"]


def test_load_without_name_falls_back_to_filename(tmp_path):
    _write(tmp_path / "r.yaml", "players:\n- Alice\n")
    mgr = RosterManager(str(tmp_path))
    mgr.load("r.yaml")
    assert mgr.current_roster_name == "r.yaml"


def test_load_without_players_returns_empty(tmp_path):
    _write(tmp_path / "r.yaml", "name: Empty\n")
    mgr = RosterManager(str(tmp_path))
    assert mgr.load("r.yaml") == []


def test_save_then_load_roundtrip(tmp_path):
    mgr = RosterManager(str(tmp_path))
    mgr.save("r.yaml", "My Roster", ["Alice", "Bob", "Carol"])
    reloaded = RosterManager(str(tmp_path))
    assert reloaded.load("r.yaml") == ["Alice", "Bob", "Carol"]
    assert reloaded.current_roster_name == "My Roster"


def test_save_uses_block_style(tmp_path):
    mgr = RosterManager(str(tmp_path))
    mgr.save("r.yaml", "N", ["Alice", "Bob"])
    text = (tmp_path / "r.yaml").read_text(encoding="utf-8")
    # default_flow_style=False -> block sequence, not inline "[Alice, Bob]".
    assert "- Alice" in text
    assert "[" not in text
