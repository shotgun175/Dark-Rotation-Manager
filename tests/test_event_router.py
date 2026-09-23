"""Tests for the confirm cue EventRouter picks (chime for detection, voice for F9).

Engine events reach the router through a queued Qt signal, so a second confirm
on the keyboard or detection thread can land before the main thread handles
the first. The engine ignores that second confirm; the cue must not change.
"""

from modules.bot_controller import BotController
from modules.engine import RotationEngine
from modules.event_router import EventRouter
from modules.events import EngineEvent


class FakeAudio:
    def __init__(self):
        self.calls = []
        self.render_failures = 0

    def play_chime(self):
        self.calls.append("chime")

    def play_event(self, event_type, data):
        self.calls.append(event_type)


def _replay(*confirms):
    """Run the confirms back to back, then drain the queue like the main thread.

    Returns (accepted confirm count, confirm cues played).
    """
    queue = []  # stands in for the queued pyqtSignal
    ctrl = BotController(lambda et, data: queue.append((et, data)))
    eng = RotationEngine({"rotation": {}}, ctrl._on_engine_event)
    eng._start_timer_thread = lambda: None
    eng.set_players(["A", "B"])
    eng.start()
    ctrl.engine = eng
    ctrl.audio = FakeAudio()
    router = EventRouter(ctrl)

    for confirm in confirms:
        confirm(ctrl)
    accepted = sum(1 for et, _ in queue if et == EngineEvent.CONFIRMED)
    for et, data in queue:
        router.handle(et, data, lambda *args: None)
    cues = [c for c in ctrl.audio.calls if c in ("chime", EngineEvent.CONFIRMED)]
    return accepted, cues


def _detection(ctrl):
    ctrl._on_grenade_detected(is_splendid=False)


def _hotkey(ctrl):
    ctrl._hotkey_confirm()


def test_detection_confirm_then_late_f9_plays_the_chime():
    assert _replay(_detection, _hotkey) == (1, ["chime"])


def test_f9_confirm_then_detection_hit_plays_the_voice():
    assert _replay(_hotkey, _detection) == (1, [EngineEvent.CONFIRMED])


def test_single_confirms_pick_their_own_cue():
    assert _replay(_detection) == (1, ["chime"])
    assert _replay(_hotkey) == (1, [EngineEvent.CONFIRMED])


def test_voice_failure_notice_shows_once_per_run():
    from types import SimpleNamespace

    messages = []
    audio = FakeAudio()
    audio.render_failures = 1
    overlay = SimpleNamespace(set_status_message=lambda text, color: messages.append(text))
    ctrl = SimpleNamespace(detection=None, audio=audio, overlay=overlay)
    router = EventRouter(ctrl)

    router.handle(EngineEvent.ANNOUNCE, {"player": "A"}, lambda *args: None)
    router.handle(EngineEvent.ANNOUNCE, {"player": "B"}, lambda *args: None)

    assert messages == ["Voice cues failed to load - check internet (see logs)"]
