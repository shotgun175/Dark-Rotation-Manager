"""Tests for BotController.apply restart-needed reporting."""

from types import SimpleNamespace

from modules.bot_controller import BotController


def _controller_with_running_engine():
    c = BotController(lambda et, data: None)
    c.engine = SimpleNamespace(
        warn_secs=5,
        cooldown_secs=30,
        max_throws=3,
        miss_secs=20,
        set_players=lambda players: None,
    )
    return c


def _config(detection_enabled: bool, audio_enabled: bool) -> dict:
    return {
        "detection": {"enabled": detection_enabled},
        "audio": {"enabled": audio_enabled},
    }


def test_apply_reports_enabling_absent_subsystems_needs_restart():
    c = _controller_with_running_engine()  # launched with detection+audio off
    pending = c.apply(_config(detection_enabled=True, audio_enabled=True), [])
    assert pending == ["detection", "audio"]


def test_apply_reports_nothing_when_subsystems_match():
    c = _controller_with_running_engine()
    c.detection = SimpleNamespace(update_config=lambda cfg: None)
    c.audio = SimpleNamespace(update_config=lambda cfg, players=None: None)
    pending = c.apply(_config(detection_enabled=True, audio_enabled=True), [])
    assert pending == []


def test_apply_reports_disabling_running_detection_needs_restart():
    c = _controller_with_running_engine()
    c.detection = SimpleNamespace(update_config=lambda cfg: None)
    pending = c.apply(_config(detection_enabled=False, audio_enabled=False), [])
    assert pending == ["detection"]


def test_apply_disabled_audio_stays_silent_without_restart():
    # play_event consults the live config, so audio off with no manager
    # is already in effect — no restart message.
    c = _controller_with_running_engine()
    pending = c.apply(_config(detection_enabled=False, audio_enabled=False), [])
    assert pending == []
