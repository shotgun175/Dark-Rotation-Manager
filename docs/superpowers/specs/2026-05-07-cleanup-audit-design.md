# Dark Rotation Manager — Cleanup & Refactor Spec

**Date:** 2026-05-07
**Branch:** `chore/cleanup-audit`
**Status:** Approved — pending implementation plan

## Goal

Apply the full cleanup order from the 2026-05-07 audit. End state: no dead code, no duplicated path/window logic, single source of truth for engine events and Qt styles, a cleaner state machine, a smaller `gui_app.py`, and a tunable `miss_seconds`. Plus two small UX features (live volume slider, accurate overlay phase label).

Nothing ships to GitHub until the entire branch is reviewed at the end.

## Removals

### Engine (`modules/engine.py`)
- `RotationEngine.skip()`
- `RotationEngine.add_player(name)`
- `RotationEngine.remove_player(name)`
- `self.skipped: set[str]` field and every read of it (`_active_players`, `_advance`, `_next_non_cooldown_player`, `set_players`, `start`)
- `RotationState.STOPPED`
- `ThrowEvent` dataclass
- `self.throw_history: list[ThrowEvent]` field and the append in `on_dark_detected`
- `"history"` key in `get_status()`
- `self.on_event("confirmed_out_of_order", ...)` emit (L191)
- `self.on_event("player_exhausted", ...)` emits (L208, L241) and the `_exhausted` notify branches that wrap them — but **keep `self._exhausted: set[str]`**, it's load-bearing for stopping the rotation when everyone has thrown their cap.

### Roster (`modules/roster.py`)
- `RosterManager.list_rosters()`
- `RosterManager.set_players()`
- `RosterManager.add_player()`
- `RosterManager.remove_player()`
- `RosterManager.move_player()`
- `RosterManager.get_players()`
- `self.players` instance field

End state: `RosterManager` is `__init__`, `load(filename) -> list[str]`, `save(filename, name, players)`, and the `current_roster_name` attribute. Nothing else.

### Audio (`modules/audio.py`)
- `prerender(players, on_done=None)` — drop the `on_done` parameter
- `_render_all(players, on_done=None)` — drop the `on_done` parameter and the trailing `if on_done: on_done()` block

**Keep `set_volume()`** — wired up live (see Features).

### Detection (`modules/detection.py`)
- `import win32con` (L37) — unused

### Region selector (`modules/region_selector.py`)
- `cancelled = pyqtSignal()` (L38) and the `self.cancelled.emit()` in `keyPressEvent` (L148). Escape still closes the window.

### Assets
- `assets/dark_timer_icon.png`

## New modules

### `modules/paths.py`
```python
def get_base_dir() -> str:
    """Frozen-aware project root. Returns the dir containing config.yaml."""

def find_lostark_window() -> tuple[int, int] | None:
    """Returns (left, top) of Lost Ark client area, or None."""
```
Replaces the four duplicated `BASE_DIR` blocks (`gui.py`, `gui_app.py`, `audio.py`, `detection.py`) and the two `_find_lostark_window` / `_get_lostark_origin` copies (`detection.py`, `region_selector.py`).

### `modules/events.py`
```python
class EngineEvent(str, Enum):
    STATE_CHANGE      = "state_change"
    ANNOUNCE          = "announce"
    WARNING           = "warning"
    CONFIRMED         = "confirmed"
    MISSED            = "missed"
    RESET             = "reset"
    ROTATION_COMPLETE = "rotation_complete"
    COOLDOWN_SKIP     = "cooldown_skip"
```
String-Enum so existing `event_type == "confirmed"` style consumers keep working during transition. Engine emits members; `EVENT_TO_CUE` in `audio.py` keys off members; `gui_app` / event router branch on members.

### `modules/styles.py`
Named QSS string constants extracted from the tab files. Initial pass — pull the most-repeated ones:
- `INPUT_DARK` (spinbox / line edit field background)
- `BUTTON_GHOST` (transparent ghost button used by Preview / Test / Draw Region)
- `BUTTON_PRIMARY_GREEN` (Apply, Add)
- `BUTTON_DANGER` (Stop, Remove)
- `CHECKBOX_GOLD`
- `LABEL_HINT` (gray hint text)
- `LABEL_SECTION` (section headers)
- `SLIDER_GOLD`
- `CARD_DARK` (the bordered detection / cue card)
- `TAB_BAR` (the tab bar QSS already in `gui_app._build_ui`)

Tab files keep small, locally-specific styles inline. Goal is reduction, not zero-inline-QSS purity.

## State-machine merge (`modules/engine.py`)

```python
class RotationState(Enum):
    IDLE                  = auto()
    RUNNING_PLAYER_WINDOW = auto()
    RUNNING_DARK_WINDOW   = auto()
    PAUSED                = auto()
```

- `_dark_active: bool` removed.
- New helper: `@property is_running` returns `state in (RUNNING_PLAYER_WINDOW, RUNNING_DARK_WINDOW)`.
- `_tick`, `pause`, `resume`, `_begin_player_window`, `on_dark_detected`, `on_dark_missed`, `reset`, `get_status` all branch on the explicit state instead of the boolean.
- `get_status()`'s public surface is unchanged for consumers that don't read `dark_active`. The `dark_active` key is replaced by `phase: "player_window" | "dark_window" | None` (used by the overlay for the new label — see Features).
- `state_change` events now emit one of `IDLE` / `RUNNING_PLAYER_WINDOW` / `RUNNING_DARK_WINDOW` / `PAUSED`. The router maps both RUNNING substates to the same UI status string ("Running" / "Running — Dark active") in the bottom bar.

## ConfigApp split (`modules/gui_app.py` → 3 modules)

### `modules/bot_controller.py` (new)
Owns the lifecycle of `RotationEngine`, `HotkeyManager`, `OverlayWindow`, `DetectionEngine`, `AudioManager`. Public surface:
```python
class BotController:
    def __init__(self, on_engine_event): ...
    def start(self, config: dict, players: list[str]) -> None: ...
    def stop(self) -> None: ...
    def apply(self, config: dict, players: list[str]) -> None: ...
    def set_audio_volume(self, volume: float) -> None: ...   # live volume hook
    @property
    def is_running(self) -> bool: ...
    @property
    def engine(self) -> RotationEngine | None: ...
    @property
    def overlay(self) -> OverlayWindow | None: ...
    @property
    def detection(self) -> DetectionEngine | None: ...
    @property
    def audio(self) -> AudioManager | None: ...
```
Hotkey callbacks (`_hotkey_start_stop`, `_hotkey_confirm`, `_hotkey_missed`, `_hotkey_reset`) move here.

### `modules/event_router.py` (new)
```python
class EventRouter:
    def __init__(self, controller: BotController): ...
    def handle(self, event: EngineEvent, data: dict) -> None: ...
```
Internally a dispatch table `{EngineEvent.CONFIRMED: self._on_confirmed, ...}` replacing the `_on_engine_event_ui` cascade. Manages overlay flashes/messages, detection pause/resume, and audio cue dispatch.

### `modules/gui_app.py` (slimmed)
QMainWindow shell only. Builds tabs, owns Apply / Launch buttons, status bar, hotkey-capture passthrough to `HotkeysTab`, region-selector handler, preview-overlay handler, and the engine-event signal that marshals from background thread to main thread (then forwards to `EventRouter`).

Target line count: ~250 lines (down from ~570).

## Feature additions

### Live volume slider (`modules/tabs/audio_tab.py` + `bot_controller.py`)
- `AudioTab` adds `volume_changed = pyqtSignal(float)` and emits it from the slider's `valueChanged` handler (value / 100.0).
- `ConfigApp` connects this signal to `BotController.set_audio_volume(v)` (a thin wrapper that calls `self.audio.set_volume(v)` if `self.audio` is alive, else no-op).
- Apply still saves the value to disk via the existing `update_config` path.

### Overlay phase label (`modules/overlay.py`)
- `_lbl_current_label` is no longer static. `_render` updates it based on `status["phase"]`:
  - `"dark_window"` → `"DARK NOW"`
  - `"player_window"` → `"UP NEXT"`
  - `None` (idle/paused) → `"DARK NOW"` (preserve current text in non-running states)

## Config schema changes

### `rotation.miss_seconds: 20`
- Added to `config.example.yaml` with default `20`.
- `RotationEngine.__init__` reads `rot.get("miss_seconds", 20)` into `self.miss_secs` (replacing the hard-coded `20.0`).
- `RotationTab` adds a 4th field "PLAYER WINDOW (seconds before auto-miss)", spin range 5–60, default 20. `get_values()` returns `miss_seconds`.
- `gui_app._apply` and the `_engine.miss_secs` push-to-running-bot block include the new field.

### Gitignored personal files
- `.gitignore` adds: `config.yaml`, `rosters/*.yaml` (with `!rosters/example.yaml` exception).
- Repo ships `config.example.yaml` (copied from current `config.yaml` reset to neutral defaults) and `rosters/example.yaml` (small sample roster).
- First-run bootstrap: if `config.yaml` doesn't exist next to the script/exe, copy `config.example.yaml` to `config.yaml`. Same for the active roster.
- Migration order in the `chore: gitignore personal config and roster, ship examples` commit: (1) add `config.example.yaml` and `rosters/example.yaml` and the bootstrap loader, (2) update `.gitignore`, (3) `git rm --cached config.yaml rosters/my_raid.yaml`. The on-disk personal copies are left untouched so the user's local setup keeps working.

### `.gitignore` cleanup
- Remove `*.spec` (the build spec is intentionally tracked).

## Branch + commit strategy

Single branch `chore/cleanup-audit`. Conventional Commits for intermediate commits. Final commit on the branch (only after user review) bumps the README changelog and creates a `vX.X.X - Cleanup audit` commit matching the project convention. Tag is **not** pushed until the user explicitly says go.

Commit order (each independently revertable):

1. `chore: remove dead engine, roster, and audio API`
2. `chore: remove unused win32con import and orphan icon`
3. `refactor: centralize BASE_DIR and lostark window finder in paths module`
4. `refactor: introduce EngineEvent enum`
5. `refactor: extract Qt stylesheets into styles module`
6. `refactor: collapse engine state machine into explicit phases`
7. `feat: live volume slider in Audio tab`
8. `feat: overlay current label reflects active phase`
9. `refactor: split ConfigApp into BotController and EventRouter`
10. `feat: surface miss_seconds as rotation.miss_seconds in config`
11. `chore: gitignore personal config and roster, ship examples`
12. `chore: remove *.spec from gitignore`
13. `vX.X.X - Cleanup audit` (final, version bump + README changelog entry)

## Out of scope

- Adding tests / wiring `pytest-qt`. Test deps stay in `requirements.txt` for future use.
- Caching `_active_players()` — micro-optimization not worth the bug surface.
- Replacing `self._paused` boolean in detection with `threading.Event` — CPython-safe today, comment-only fix.
- Reworking `_timer_thread` lifecycle.
- Adding a "recent throws" panel (out per delete-history decision).
- Wiring `confirmed_out_of_order` / `player_exhausted` to UI cues (out per delete decision).
- Auto-Apply on Launch / "unsaved changes" warning.
- `RegionPreviewWidget` dynamic reference resolution.
- Renaming `audio_tab._build_ui`'s shadowed `layout` variable.

## Acceptance criteria

- All 12 commits land on `chore/cleanup-audit`.
- The app launches and runs after **each individual commit** — no commit leaves the tree in a broken state. (Manual smoke check after the higher-risk commits: state-machine merge, ConfigApp split, miss_seconds.)
- `gui.py`, `modules/audio.py`, `modules/detection.py`, `modules/gui_app.py` no longer contain duplicate `BASE_DIR` / window-finder blocks.
- `grep -r "RotationState.STOPPED\|throw_history\|self.skipped\|win32con\|cancelled" modules/` returns no hits.
- `RotationEngine` has the four-state enum and no `_dark_active` field.
- Dragging the Audio tab's volume slider while the bot is running changes audio output volume immediately, without requiring Apply.
- Overlay shows "UP NEXT" during the player window and "DARK NOW" during the dark buff window.
- `config.yaml` and `rosters/my_raid.yaml` no longer appear in `git ls-files`.
- `git status` is clean after the bot is launched and exited (assuming `config.yaml` exists from the example).
- Bot launches, runs through a full rotation (announce → warning → confirm → dark countdown → next player) without errors. Manual smoke test by user — no automated tests.
