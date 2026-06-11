"""Tests for the global excepthooks that keep the noconsole exe diagnosable."""

import logging
import sys
import threading

import pytest

from modules.log_setup import install_excepthooks


@pytest.fixture
def capture_hooks(caplog):
    """Install the hooks, restore the originals afterwards."""
    orig_sys_hook = sys.excepthook
    orig_thread_hook = threading.excepthook
    install_excepthooks("C:/fake/logs/app.log")
    with caplog.at_level(logging.CRITICAL, logger="modules.log_setup"):
        yield caplog
    sys.excepthook = orig_sys_hook
    threading.excepthook = orig_thread_hook


def _raise_for_traceback():
    raise ValueError("boom from test")


def test_sys_excepthook_logs_traceback(capture_hooks, capsys):
    try:
        _raise_for_traceback()
    except ValueError:
        sys.excepthook(*sys.exc_info())

    records = [r for r in capture_hooks.records if r.levelno == logging.CRITICAL]
    assert len(records) == 1
    text = capture_hooks.text
    assert "boom from test" in text
    assert "_raise_for_traceback" in text  # full traceback, not just the message


def test_sys_excepthook_passes_keyboardinterrupt_through(capture_hooks):
    try:
        raise KeyboardInterrupt()
    except KeyboardInterrupt:
        sys.excepthook(*sys.exc_info())

    assert not [r for r in capture_hooks.records if r.levelno == logging.CRITICAL]


def test_threading_excepthook_logs_traceback(capture_hooks):
    thread = threading.Thread(target=_raise_for_traceback, name="worker-x")
    thread.start()
    thread.join()

    records = [r for r in capture_hooks.records if r.levelno == logging.CRITICAL]
    assert len(records) == 1
    text = capture_hooks.text
    assert "boom from test" in text
    assert "worker-x" in text
