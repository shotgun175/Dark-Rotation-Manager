"""Smoke tests for the RotationEngine state machine.

Time is driven deterministically via a FakeClock that replaces the `time`
module reference inside modules.engine — no real sleeping, no timer thread.
The background timer thread is suppressed (_start_timer_thread -> no-op) so
tests drive transitions by calling _tick() / the public API directly.
"""

import pytest

from modules import engine
from modules.engine import RotationState
from modules.events import EngineEvent


class FakeClock:
    """Monotonic stand-in for the `time` module used by engine.py."""

    def __init__(self, start: float = 1000.0):
        self.now = start

    def time(self) -> float:
        return self.now

    def sleep(self, _seconds: float) -> None:  # only hit by the (suppressed) loop
        pass

    def advance(self, dt: float) -> None:
        self.now += dt


@pytest.fixture
def make_engine(monkeypatch):
    """Factory -> (engine, clock, events). Defaults mirror config.example.yaml."""

    def _make(players=None, **rot_overrides):
        clock = FakeClock()
        monkeypatch.setattr(engine, "time", clock)

        rot = {
            "warning_seconds": 5,
            "miss_seconds": 20,
            "dark_cooldown_seconds": 30,
            "max_throws_per_run": 3,
        }
        rot.update(rot_overrides)

        events: list[tuple] = []
        eng = engine.RotationEngine(
            {"rotation": rot}, lambda et, data: events.append((et, data))
        )
        # Never spawn the real daemon timer thread in tests.
        monkeypatch.setattr(eng, "_start_timer_thread", lambda: None)
        if players:
            eng.set_players(players)
        return eng, clock, events

    return _make


def events_of(events, etype):
    """All payloads emitted for a given event type, in order."""
    return [data for (t, data) in events if t == etype]


# ----------------------------------------------------------------------
# Thread-safety: confirm racing the auto-miss at the deadline
# ----------------------------------------------------------------------

def test_confirm_cannot_interleave_into_auto_miss(make_engine):
    """A hotkey confirm landing exactly at the miss deadline must serialize
    with the timer tick: pre-lock, the confirm ran mid-miss and the tick then
    destroyed the dark window with a second advance."""
    import threading as _threading

    eng, clock, events = make_engine(players=["A", "B", "C"])
    eng.start()
    clock.advance(20)  # exactly at the miss deadline

    tick_in_miss = _threading.Event()
    release_tick = _threading.Event()
    orig_on_event = eng.on_event

    def gated(etype, data):
        orig_on_event(etype, data)
        if etype is EngineEvent.MISSED:
            tick_in_miss.set()
            release_tick.wait(timeout=5)

    eng.on_event = gated

    t_tick = _threading.Thread(target=eng._tick)
    t_confirm = _threading.Thread(target=lambda: eng.on_dark_detected("A", False))
    try:
        t_tick.start()
        assert tick_in_miss.wait(timeout=5), "tick never reached the miss path"

        t_confirm.start()
        t_confirm.join(timeout=0.3)
        # While the tick is mid-miss the confirm must be blocked: no
        # CONFIRMED event may exist yet.
        assert events_of(events, EngineEvent.CONFIRMED) == []
    finally:
        release_tick.set()
        t_tick.join(timeout=5)
        t_confirm.join(timeout=5)
    assert not t_tick.is_alive() and not t_confirm.is_alive()

    # Serialized outcome: the miss completed first, then the confirm started
    # the dark window — which must survive (pre-lock it was overwritten by a
    # second _begin_player_window, double-advancing the rotation).
    assert eng.state is RotationState.RUNNING_DARK_WINDOW
    assert len(events_of(events, EngineEvent.MISSED)) == 1
    assert len(events_of(events, EngineEvent.CONFIRMED)) == 1


# ----------------------------------------------------------------------
# Construction / start guards
# ----------------------------------------------------------------------

def test_initial_state_is_idle(make_engine):
    eng, _clock, _events = make_engine(players=["A", "B"])
    assert eng.state is RotationState.IDLE
    assert eng.is_running is False


def test_default_timings_read_from_config(make_engine):
    eng, _clock, _events = make_engine(players=["A"])
    assert eng.miss_secs == 20
    assert eng.warn_secs == 5
    assert eng.cooldown_secs == 30
    assert eng.max_throws == 3


def test_start_with_no_players_stays_idle(make_engine):
    eng, _clock, events = make_engine(players=[])
    eng.start()
    assert eng.state is RotationState.IDLE
    assert events_of(events, EngineEvent.ANNOUNCE) == []


def test_start_announces_first_player(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.start()
    assert eng.state is RotationState.RUNNING_PLAYER_WINDOW
    announces = events_of(events, EngineEvent.ANNOUNCE)
    assert len(announces) == 1
    assert announces[0]["player"] == "A"


def test_start_is_noop_when_already_running(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.start()  # second call must be ignored
    assert len(events_of(events, EngineEvent.ANNOUNCE)) == 1


# ----------------------------------------------------------------------
# Phase 1 — player window timing (miss_secs / warn_secs)
# ----------------------------------------------------------------------

def test_phase1_warning_fires_at_miss_minus_warn(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    eng.start()
    clock.advance(15)  # miss_secs(20) - warn_secs(5)
    eng._tick()
    warnings = events_of(events, EngineEvent.WARNING)
    assert len(warnings) == 1
    assert warnings[0]["current"] == "A"
    assert warnings[0]["next"] == "B"
    assert warnings[0]["seconds"] == 5
    # No miss yet.
    assert events_of(events, EngineEvent.MISSED) == []


def test_phase1_warning_fires_only_once(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    eng.start()
    clock.advance(15)
    eng._tick()
    clock.advance(1)
    eng._tick()  # still before miss; must not re-warn
    assert len(events_of(events, EngineEvent.WARNING)) == 1


def test_phase1_auto_miss_fires_at_miss_secs_and_advances(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    eng.start()
    clock.advance(20)  # reach miss_secs exactly
    eng._tick()
    missed = events_of(events, EngineEvent.MISSED)
    assert len(missed) == 1
    assert missed[0]["player"] == "A"
    # Advanced to next player, new window opened.
    assert eng._current_player() == "B"
    assert eng.state is RotationState.RUNNING_PLAYER_WINDOW


def test_auto_miss_does_not_fire_before_deadline(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    eng.start()
    clock.advance(19.9)
    eng._tick()
    assert events_of(events, EngineEvent.MISSED) == []


def test_custom_miss_seconds_changes_deadline(make_engine):
    eng, clock, events = make_engine(players=["A", "B"], miss_seconds=10)
    eng.start()
    clock.advance(9.9)
    eng._tick()
    assert events_of(events, EngineEvent.MISSED) == []
    clock.advance(0.1)  # now at 10.0
    eng._tick()
    assert len(events_of(events, EngineEvent.MISSED)) == 1


# ----------------------------------------------------------------------
# Confirm -> dark window (Phase 2)
# ----------------------------------------------------------------------

def test_confirm_enters_dark_window_normal_duration(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=False)
    assert eng.state is RotationState.RUNNING_DARK_WINDOW
    assert eng._dark_duration == 20
    confirmed = events_of(events, EngineEvent.CONFIRMED)
    assert confirmed[0] == {"player": "A", "kind": "Dark", "duration": 20}


def test_confirm_splendid_duration_is_25(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=True)
    assert eng._dark_duration == 25
    confirmed = events_of(events, EngineEvent.CONFIRMED)
    assert confirmed[0]["kind"] == "Splendid Dark"
    assert confirmed[0]["duration"] == 25


def test_confirm_ignored_outside_player_window(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    # Engine never started — state is IDLE.
    eng.on_dark_detected("A", is_splendid=False)
    assert eng.state is RotationState.IDLE
    assert events_of(events, EngineEvent.CONFIRMED) == []


def test_confirm_increments_throw_count(make_engine):
    eng, _clock, _events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=False)
    assert eng._throw_counts["a"] == 1


# ----------------------------------------------------------------------
# Dark window timing (warn before expiry, expiry -> next player)
# ----------------------------------------------------------------------

def test_dark_window_warns_before_expiry(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=False)  # dark_duration 20
    clock.advance(15)  # remaining == 5 == warn_secs
    eng._tick()
    warnings = events_of(events, EngineEvent.WARNING)
    assert len(warnings) == 1
    assert warnings[0]["current"] == "Dark"
    assert warnings[0]["next"] == "B"


def test_dark_window_expiry_opens_next_player_window(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=False)
    clock.advance(15)
    eng._tick()  # warning
    clock.advance(5)  # remaining == 0
    eng._tick()  # expiry
    assert eng.state is RotationState.RUNNING_PLAYER_WINDOW
    announces = events_of(events, EngineEvent.ANNOUNCE)
    # First announce was A at start; the post-expiry announce is B.
    assert announces[-1]["player"] == "B"


# ----------------------------------------------------------------------
# Missed hotkey (F10)
# ----------------------------------------------------------------------

def test_missed_hotkey_counts_and_advances(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_missed()
    missed = events_of(events, EngineEvent.MISSED)
    assert missed[0]["player"] == "A"
    assert eng._throw_counts["a"] == 1
    assert eng._current_player() == "B"


def test_missed_hotkey_ignored_outside_player_window(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.on_dark_missed()  # IDLE
    assert events_of(events, EngineEvent.MISSED) == []


# ----------------------------------------------------------------------
# Throw cap / exhaustion / rotation complete
# ----------------------------------------------------------------------

def test_player_exhausts_after_max_throws_and_rotation_completes(make_engine):
    eng, clock, events = make_engine(players=["Solo"], max_throws_per_run=1)
    eng.start()
    eng.on_dark_detected("Solo", is_splendid=False)  # 1/1 -> exhausted
    assert "Solo" in eng._exhausted
    assert eng._active_players() == []
    clock.advance(20)  # dark expires -> _begin_player_window finds nobody
    eng._tick()
    assert events_of(events, EngineEvent.ROTATION_COMPLETE) != []
    assert eng.state is RotationState.IDLE


# ----------------------------------------------------------------------
# Cooldown skipping (cooldown_secs)
# ----------------------------------------------------------------------

def test_cooldown_player_is_skipped(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    # A threw "just now" -> on cooldown; B has never thrown.
    eng._throw_times["a"] = clock.now
    eng._begin_player_window()
    skips = events_of(events, EngineEvent.COOLDOWN_SKIP)
    assert [s["player"] for s in skips] == ["A"]
    announces = events_of(events, EngineEvent.ANNOUNCE)
    assert announces[-1]["player"] == "B"
    assert eng._current_player() == "B"


def test_is_on_cooldown_boundary(make_engine):
    eng, clock, _events = make_engine(players=["A"])
    eng._throw_times["a"] = 1000.0
    clock.now = 1029.0  # 29s elapsed < 30s cooldown
    assert eng._is_on_cooldown("A") is True
    clock.now = 1030.0  # exactly cooldown_secs elapsed
    assert eng._is_on_cooldown("A") is False


# ----------------------------------------------------------------------
# Reset
# ----------------------------------------------------------------------

def test_reset_clears_counts_and_returns_to_idle(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=False)
    eng.reset()
    assert eng.state is RotationState.IDLE
    assert eng._throw_counts == {}
    assert eng._exhausted == set()
    assert eng.index == 0
    assert events_of(events, EngineEvent.RESET) != []


def test_reset_ignored_from_idle(make_engine):
    eng, _clock, events = make_engine(players=["A", "B"])
    eng.reset()
    assert events_of(events, EngineEvent.RESET) == []


# ----------------------------------------------------------------------
# Pause / resume
# ----------------------------------------------------------------------

def test_pause_freezes_remaining_in_player_window(make_engine):
    eng, clock, _events = make_engine(players=["A", "B"])
    eng.start()
    clock.advance(5)
    eng.pause()
    assert eng.state is RotationState.PAUSED
    assert eng._paused_remaining == pytest.approx(15.0)  # miss_secs - 5
    assert eng._paused_duration == 20


def test_pause_freezes_remaining_in_dark_window(make_engine):
    eng, clock, _events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=False)  # dark_duration 20
    clock.advance(7)
    eng.pause()
    assert eng.state is RotationState.PAUSED
    assert eng._paused_remaining == pytest.approx(13.0)
    assert eng._paused_duration == 20


def test_resume_with_dark_detected_restarts_dark_window(make_engine):
    eng, clock, _events = make_engine(players=["A", "B"])
    eng.start()
    clock.advance(5)
    eng.pause()
    eng.resume(dark_detected=True, is_splendid=True)
    assert eng.state is RotationState.RUNNING_DARK_WINDOW
    assert eng._dark_duration == 25


def test_resume_without_dark_advances_to_next_player(make_engine):
    eng, clock, events = make_engine(players=["A", "B"])
    eng.start()
    eng.pause()
    eng.resume(dark_detected=False)
    assert eng.state is RotationState.RUNNING_PLAYER_WINDOW
    assert eng._current_player() == "B"


# ----------------------------------------------------------------------
# get_status (overlay-facing snapshot)
# ----------------------------------------------------------------------

def test_get_status_player_window(make_engine):
    eng, clock, _events = make_engine(players=["A", "B"])
    eng.start()
    clock.advance(4)
    status = eng.get_status()
    assert status["state"] == "RUNNING_PLAYER_WINDOW"
    assert status["phase"] == "player_window"
    assert status["current_player"] == "A"
    assert status["next_player"] == "B"
    assert status["remaining_seconds"] == pytest.approx(16.0)
    assert status["window_duration"] == 20
    assert status["current_count"] == "0/3"


def test_get_status_dark_window_keeps_thrower_as_current(make_engine):
    eng, _clock, _events = make_engine(players=["A", "B"])
    eng.start()
    eng.on_dark_detected("A", is_splendid=False)
    status = eng.get_status()
    assert status["phase"] == "dark_window"
    assert status["current_player"] == "A"   # thrower stays on DARK NOW
    assert status["next_player"] == "B"
    assert status["window_duration"] == 20


# ----------------------------------------------------------------------
# Index helpers
# ----------------------------------------------------------------------

def test_advance_skips_exhausted_players(make_engine):
    eng, _clock, _events = make_engine(players=["A", "B", "C"])
    eng._exhausted.add("B")
    eng.index = 0
    eng._advance()  # 0 -> (1=B exhausted) -> 2=C
    assert eng._current_player() == "C"


def test_next_active_player_single_roster(make_engine):
    eng, _clock, _events = make_engine(players=["A"])
    assert eng._next_active_player() == "A"


def test_current_player_nobody_when_all_exhausted(make_engine):
    eng, _clock, _events = make_engine(players=["A"])
    eng._exhausted.add("A")
    assert eng._current_player() == "Nobody"
