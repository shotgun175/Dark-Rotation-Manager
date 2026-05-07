"""
engine.py - Core rotation logic, timers, and state management

Two-phase timing model
----------------------
Phase 1 — Player window (_dark_active=False):
    A player has been announced. They have 4 seconds to throw before
    being called missed and the next player announced.

Phase 2 — Dark window (_dark_active=True):
    A dark grenade is active. The buff countdown runs for 20-25 s.
    No new player is announced until it expires, at which point the
    next player's Phase-1 window begins.
"""

import threading
import time
from enum import Enum, auto


class RotationState(Enum):
    IDLE    = auto()
    RUNNING = auto()
    PAUSED  = auto()


class RotationEngine:
    def __init__(self, config: dict, on_event):
        self.config = config
        self.on_event = on_event
        self.rot_config = config.get("rotation", {})
        self.warn_secs = self.rot_config.get("warning_seconds", 5)
        self.miss_secs = 20.0         # seconds before auto-miss fires
        self.cooldown_secs: float = self.rot_config.get("dark_cooldown_seconds", 30.0)

        self.max_throws: int = self.rot_config.get("max_throws_per_run", 3)

        self.state = RotationState.IDLE
        self.players: list[str] = []
        self._exhausted: set[str] = set()          # players who hit max_throws
        self.index = 0
        self._throw_times: dict[str, float] = {}   # player_lower -> last throw timestamp
        self._throw_counts: dict[str, int] = {}    # player_lower -> throws this run

        self._timer_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Phase-1 (player window) state
        self._player_window_start: float = 0
        self._miss_warned: bool = False
        self._phase1_warned: bool = False

        # Phase-2 (dark window) state
        self._dark_active: bool = False
        self._dark_start: float = 0
        self._dark_duration: int = 20
        self._dark_warned: bool = False   # warning callout during dark countdown
        self._dark_player: str = ""       # who threw the dark (shown on overlay during buff)

        # Pause state — frozen display values
        self._paused_remaining: float = 0.0
        self._paused_duration: float = 20.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_players(self, players: list[str]):
        self.players = list(players)
        self.index = 0

    def start(self):
        if not self.players:
            print("[Engine] No players loaded.")
            return
        if self.state == RotationState.RUNNING:
            return
        self._set_state(RotationState.RUNNING)
        self._stop_event.clear()
        self._dark_active = False
        self._throw_times.clear()
        self._throw_counts.clear()
        self._exhausted.clear()
        self._begin_player_window()
        self._start_timer_thread()

    def stop(self):
        self._stop_event.set()
        self._set_state(RotationState.IDLE)
        self.index = 0
        print("[Engine] Rotation stopped.")

    def pause(self):
        if self.state != RotationState.RUNNING:
            return
        # Capture current remaining time so the overlay bar stays frozen
        if self._dark_active:
            elapsed = time.time() - self._dark_start
            self._paused_remaining = max(0.0, self._dark_duration - elapsed)
            self._paused_duration = float(self._dark_duration)
        else:
            elapsed = time.time() - self._player_window_start
            self._paused_remaining = max(0.0, self.miss_secs - elapsed)
            self._paused_duration = self.miss_secs
        self._set_state(RotationState.PAUSED)
        print("[Engine] Paused.")

    def resume(self, dark_detected: bool = False, is_splendid: bool = False):
        if self.state != RotationState.PAUSED:
            return
        if dark_detected:
            # Dark is still active in-game — restart its countdown from now
            self._dark_active = True
            self._dark_start = time.time()
            self._dark_duration = 25 if is_splendid else 20
            self._dark_warned = False
        else:
            # No dark active — advance to next player and start their window
            self._advance()
            self._dark_active = False
        self._set_state(RotationState.RUNNING)
        self._stop_event.clear()
        if not dark_detected:
            self._begin_player_window()
        if not self._timer_thread or not self._timer_thread.is_alive():
            self._start_timer_thread()
        print("[Engine] Resumed.")

    def reset(self):
        """Reset rotation to player 1, clearing all counts. Returns to armed/idle state."""
        if self.state not in (RotationState.RUNNING, RotationState.PAUSED):
            return
        self._stop_event.set()
        self._dark_active = False
        self._throw_times.clear()
        self._throw_counts.clear()
        self._exhausted.clear()
        self.index = 0
        self._set_state(RotationState.IDLE)
        self.on_event("reset", {})
        print("[Engine] Rotation reset to player 1.")

    def on_dark_detected(self, player: str, is_splendid: bool):
        """Called when a dark grenade throw is confirmed (via hotkey)."""
        if self.state != RotationState.RUNNING:
            return
        if self._dark_active:
            return  # buff already running — ignore duplicate confirms

        duration = 25 if is_splendid else 20
        kind = "Splendid Dark" if is_splendid else "Dark"
        self.on_event("confirmed", {"player": player, "kind": kind, "duration": duration})

        # Record throw time and increment run count
        key = player.lower()
        self._throw_times[key] = time.time()
        self._throw_counts[key] = self._throw_counts.get(key, 0) + 1
        count = self._throw_counts[key]
        print(f"[Engine] {player} throw {count}/{self.max_throws}")

        # Mark exhausted when they hit the per-run cap
        if count >= self.max_throws:
            for p in self.players:
                if p.lower() == key:
                    self._exhausted.add(p)
                    break

        # A dark is now active regardless of who threw it.
        # Advance past the current expected slot and start the buff countdown.
        # The next player is NOT announced until the buff expires.
        self._dark_player = player        # remember thrower for overlay display
        self._advance()
        self._dark_active = True
        self._dark_start = time.time()
        self._dark_duration = duration
        self._dark_warned = False

    def on_dark_missed(self):
        """Called by F10 — counts the miss against the current player's throw
        limit, then immediately advances to the next player (no dark countdown)."""
        if self.state != RotationState.RUNNING:
            return

        player = self._current_player()
        key = player.lower()

        self._throw_times[key] = time.time()
        self._throw_counts[key] = self._throw_counts.get(key, 0) + 1
        count = self._throw_counts[key]
        print(f"[Engine] {player} MISSED — throw {count}/{self.max_throws}")

        self.on_event("missed", {"player": player})

        if count >= self.max_throws:
            for p in self.players:
                if p.lower() == key:
                    self._exhausted.add(p)
                    break

        self._advance()
        self._dark_active = False
        self._begin_player_window()

    # ------------------------------------------------------------------
    # Timing internals
    # ------------------------------------------------------------------

    def _start_timer_thread(self):
        self._timer_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._timer_thread.start()

    def _timer_loop(self):
        while not self._stop_event.is_set():
            if self.state == RotationState.RUNNING:
                self._tick()
            time.sleep(0.25)

    def _tick(self):
        if self._dark_active:
            # ── Phase 2: dark buff is running ──────────────────────────
            dark_elapsed = time.time() - self._dark_start
            dark_remaining = self._dark_duration - dark_elapsed

            # Warning callout before dark expires — resolve who will actually
            # be announced (skipping cooldown players) so the TTS is accurate.
            if not self._dark_warned and dark_remaining <= self.warn_secs:
                self._dark_warned = True
                next_up = self._next_non_cooldown_player()
                if next_up != "Nobody":
                    self.on_event("warning", {
                        "current": "Dark",
                        "next": next_up,
                        "seconds": int(dark_remaining),
                    })

            # Dark expired → announce the next player
            if dark_remaining <= 0:
                self._dark_active = False
                self._begin_player_window()

        else:
            # ── Phase 1: waiting for throw ─────────────────────────────
            elapsed = time.time() - self._player_window_start

            # Warning: alert the *next* player they're about to be called up
            if not self._phase1_warned and elapsed >= (self.miss_secs - self.warn_secs):
                self._phase1_warned = True
                current = self._current_player()
                next_up = self._next_active_player()
                if next_up != "Nobody" and next_up != current:
                    self.on_event("warning", {
                        "current": current,
                        "next": next_up,
                        "seconds": int(self.warn_secs),
                    })

            if not self._miss_warned and elapsed >= self.miss_secs:
                self._miss_warned = True
                self.on_event("missed", {"player": self._current_player()})
                self._advance()
                self._begin_player_window()

    def _begin_player_window(self):
        """Announce the current player and start the fast-miss countdown.
        Auto-skips cooldown players; stops the bot if everyone is exhausted."""
        # Stop if every player has hit the per-run throw cap
        if not self._active_players():
            print("[Engine] All players exhausted. Rotation complete.")
            self.on_event("rotation_complete", {})
            self.stop()
            return

        # Skip over anyone whose grenade is still on cooldown
        checked = 0
        while checked < len(self.players):
            player = self._current_player()
            if not self._is_on_cooldown(player):
                break
            print(f"[Engine] {player} is on cooldown — skipping.")
            self.on_event("cooldown_skip", {"player": player})
            self._advance()
            checked += 1
        else:
            print("[Engine] All active players on cooldown — announcing anyway.")

        self._player_window_start = time.time()
        self._miss_warned = False
        self._phase1_warned = False
        player = self._current_player()
        self.on_event("announce", {
            "player": player,
            "index": self.index,
            "total": len(self._active_players()),
        })

    def _is_on_cooldown(self, player: str) -> bool:
        last = self._throw_times.get(player.lower(), 0.0)
        return (time.time() - last) < self.cooldown_secs

    def _next_non_cooldown_player(self) -> str:
        """Return the first active, non-exhausted, non-cooldown player
        starting from the current index — mirrors what _begin_player_window
        will actually announce."""
        n = len(self.players)
        for i in range(n):
            p = self.players[(self.index + i) % n]
            if p in self._exhausted:
                continue
            if not self._is_on_cooldown(p):
                return p
        return "Nobody"

    def _advance(self):
        if not self._active_players():
            return
        self.index = (self.index + 1) % len(self.players)
        attempts = 0
        while self.players[self.index] in self._exhausted and attempts < len(self.players):
            self.index = (self.index + 1) % len(self.players)
            attempts += 1

    def _current_player(self) -> str:
        if not self._active_players():
            return "Nobody"
        return self.players[self.index % len(self.players)]

    def _next_active_player(self) -> str:
        active = self._active_players()
        if len(active) < 2:
            return active[0] if active else "Nobody"
        current = self._current_player()
        idx = active.index(current) if current in active else 0
        return active[(idx + 1) % len(active)]

    def _active_players(self) -> list[str]:
        return [p for p in self.players if p not in self._exhausted]

    def _set_state(self, new_state: RotationState):
        self.state = new_state
        self.on_event("state_change", {"state": new_state.name})

    # ------------------------------------------------------------------
    # Status (used by overlay)
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        if self.state == RotationState.PAUSED:
            remaining = self._paused_remaining
            duration = self._paused_duration
        elif self._dark_active:
            dark_elapsed = time.time() - self._dark_start
            remaining = max(0.0, self._dark_duration - dark_elapsed)
            duration = self._dark_duration
        elif self.state == RotationState.RUNNING:
            elapsed = time.time() - self._player_window_start
            remaining = max(0.0, self.miss_secs - elapsed)
            duration = self.miss_secs
        else:
            remaining = 0.0
            duration = self.miss_secs

        # During the buff countdown keep the thrower on "DARK NOW"
        # and show the upcoming player as "NEXT".
        if self._dark_active:
            current_display = self._dark_player or self._current_player()
            next_display    = self._current_player()
        else:
            current_display = self._current_player()
            next_display    = self._next_active_player()

        def _count(name: str) -> str:
            c = self._throw_counts.get(name.lower(), 0)
            return f"{c}/{self.max_throws}"

        return {
            "state": self.state.name,
            "current_player": current_display,
            "next_player": next_display,
            "current_count": _count(current_display),
            "next_count": _count(next_display),
            "remaining_seconds": remaining,
            "window_duration": duration,
            "dark_active": self._dark_active,
            "players": self._active_players(),
            "index": self.index,
        }
