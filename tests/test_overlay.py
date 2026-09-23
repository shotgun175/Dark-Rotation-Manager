"""Tests for OverlayWindow placement and close handling (offscreen Qt)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication

from modules.overlay import OverlayWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_offscreen_position_moves_onto_a_screen(app):
    ov = OverlayWindow({"position": {"x": 99999, "y": 200}})
    assert app.screenAt(ov.geometry().center()) is not None


def test_onscreen_position_is_unchanged(app):
    ov = OverlayWindow({"position": {"x": 10, "y": 20}})
    assert (ov.geometry().x(), ov.geometry().y()) == (10, 20)


def test_close_on_live_overlay_calls_stop_callback_once(app):
    calls = []
    ov = OverlayWindow({}, stop_callback=lambda: (calls.append(1), ov.stop()))
    ov.show()
    ov.close()
    assert calls == [1]


def test_close_on_preview_overlay_does_not_raise(app):
    ov = OverlayWindow({})
    ov.show()
    ov.close()
    assert not ov.isVisible()
