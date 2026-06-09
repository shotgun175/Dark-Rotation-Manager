"""Tests for the update-available check (parsing, comparison, error handling).

The network layer (_fetch_latest_tag) is monkeypatched so no real HTTP
request is made.
"""

import pytest

from modules import update_check


@pytest.mark.parametrize(
    "tag,expected",
    [
        ("v1.1.3", (1, 1, 3)),
        ("1.1.3", (1, 1, 3)),
        ("V2.0.0", (2, 0, 0)),
        ("v1.2", (1, 2)),
    ],
)
def test_parse_version_valid(tag, expected):
    assert update_check._parse_version(tag) == expected


@pytest.mark.parametrize("tag", ["", "latest", "v1.x.0", None])
def test_parse_version_invalid_returns_none(tag):
    assert update_check._parse_version(tag) is None


def _patch_tag(monkeypatch, tag):
    monkeypatch.setattr(update_check, "_fetch_latest_tag", lambda url, timeout: tag)


def test_newer_release_triggers_callback(monkeypatch):
    _patch_tag(monkeypatch, "v9.9.9")
    seen = []
    update_check.check_for_update(seen.append, current_version="1.1.3")
    assert seen == ["v9.9.9"]


def test_same_version_does_not_trigger_callback(monkeypatch):
    _patch_tag(monkeypatch, "v1.1.3")
    seen = []
    update_check.check_for_update(seen.append, current_version="1.1.3")
    assert seen == []


def test_older_release_does_not_trigger_callback(monkeypatch):
    _patch_tag(monkeypatch, "v1.0.0")
    seen = []
    update_check.check_for_update(seen.append, current_version="1.1.3")
    assert seen == []


def test_network_error_is_swallowed(monkeypatch):
    def _boom(url, timeout):
        raise OSError("no network")

    monkeypatch.setattr(update_check, "_fetch_latest_tag", _boom)
    seen = []
    # Must not raise.
    update_check.check_for_update(seen.append, current_version="1.1.3")
    assert seen == []


def test_unparseable_tag_does_not_trigger_callback(monkeypatch):
    _patch_tag(monkeypatch, "garbage")
    seen = []
    update_check.check_for_update(seen.append, current_version="1.1.3")
    assert seen == []


def test_missing_tag_does_not_trigger_callback(monkeypatch):
    _patch_tag(monkeypatch, None)
    seen = []
    update_check.check_for_update(seen.append, current_version="1.1.3")
    assert seen == []
