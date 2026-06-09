"""Tests for the atomic_write_text helper and its roster.save call site."""

import pytest

from modules import paths
from modules.paths import atomic_write_text
from modules.roster import RosterManager


def test_creates_file_with_content(tmp_path):
    target = tmp_path / "f.txt"
    atomic_write_text(str(target), "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_overwrites_existing_file(tmp_path):
    target = tmp_path / "f.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(str(target), "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_leaves_no_temp_files_behind(tmp_path):
    target = tmp_path / "f.yaml"
    atomic_write_text(str(target), "x: 1\n")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f.yaml"]


def test_failed_replace_preserves_original_and_cleans_temp(tmp_path, monkeypatch):
    target = tmp_path / "f.txt"
    target.write_text("ORIGINAL", encoding="utf-8")

    def _boom(*_a, **_k):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(paths.os, "replace", _boom)

    with pytest.raises(OSError):
        atomic_write_text(str(target), "NEW")

    # Original survives a mid-write crash, and no temp file is orphaned.
    assert target.read_text(encoding="utf-8") == "ORIGINAL"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f.txt"]


def test_roster_save_is_atomic_and_clean(tmp_path):
    mgr = RosterManager(str(tmp_path))
    mgr.save("r.yaml", "Raid", ["Alice", "Bob"])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["r.yaml"]
    assert RosterManager(str(tmp_path)).load("r.yaml") == ["Alice", "Bob"]
