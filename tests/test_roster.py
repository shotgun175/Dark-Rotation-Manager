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


def test_load_empty_file_returns_empty(tmp_path):
    (tmp_path / "r.yaml").write_text("", encoding="utf-8")
    mgr = RosterManager(str(tmp_path))
    assert mgr.load("r.yaml") == []
    assert mgr.current_roster_name == "r.yaml"


def test_load_hand_edited_utf8_names(tmp_path):
    # Hand-edited file with literal non-ASCII names; must be read as UTF-8,
    # not the Windows locale codepage (cp1252).
    _write(tmp_path / "r.yaml", "name: Süß Raid\nplayers:\n- José\n- Łukasz\n")
    mgr = RosterManager(str(tmp_path))
    assert mgr.load("r.yaml") == ["José", "Łukasz"]
    assert mgr.current_roster_name == "Süß Raid"


def test_save_keeps_unicode_names_human_readable(tmp_path):
    mgr = RosterManager(str(tmp_path))
    mgr.save("r.yaml", "Raid", ["José"])
    raw = (tmp_path / "r.yaml").read_bytes()
    # allow_unicode=True -> the name is stored as UTF-8 text, not \xJJ escapes.
    assert "José".encode("utf-8") in raw
    assert RosterManager(str(tmp_path)).load("r.yaml") == ["José"]


def test_config_load_empty_file_returns_empty_dict(tmp_path):
    from types import SimpleNamespace

    from modules.gui_app import ConfigApp

    cfg = tmp_path / "config.yaml"
    cfg.write_text("", encoding="utf-8")
    fake = SimpleNamespace(_config_path=str(cfg))
    assert ConfigApp._load_config(fake) == {}


def test_config_load_reads_utf8(tmp_path):
    from types import SimpleNamespace

    from modules.gui_app import ConfigApp

    cfg = tmp_path / "config.yaml"
    cfg.write_text("overlay:\n  title: Süß\n", encoding="utf-8")
    fake = SimpleNamespace(_config_path=str(cfg))
    assert ConfigApp._load_config(fake)["overlay"]["title"] == "Süß"
