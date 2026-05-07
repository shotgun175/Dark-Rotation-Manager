# Cleanup Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the full cleanup-audit spec — remove dead code, centralize duplicated logic, collapse the engine state machine, split `ConfigApp` into focused units, add live volume + phase-aware overlay label + tunable `miss_seconds`, and clean up config/repo hygiene.

**Architecture:** Single branch `chore/cleanup-audit` (already created). Each task = one commit, each commit independently revertable. The app must launch and run after every commit. No GitHub push until user gives explicit go-ahead at the end.

**Tech Stack:** Python 3.11+, PyQt5, OpenCV, edge-tts, pygame, mss, win32gui. No test infrastructure exists — verification is manual smoke-launch via `python gui.py`.

**Spec:** `docs/superpowers/specs/2026-05-07-cleanup-audit-design.md`

---

## File Structure

### New files
- `modules/paths.py` — `get_base_dir()`, `find_lostark_window()` (consolidates 4 BASE_DIR copies + 2 window-finder copies)
- `modules/events.py` — `EngineEvent(str, Enum)` — single source of truth for engine event names
- `modules/styles.py` — Named QSS string constants
- `modules/bot_controller.py` — Owns engine/hotkeys/overlay/detection/audio lifecycle; exposes `start/stop/apply/set_audio_volume`
- `modules/event_router.py` — Dispatch table replacing the 30-line `_on_engine_event_ui` cascade
- `config.example.yaml` — Neutral default config (shipped in repo)
- `rosters/example.yaml` — Sample roster (shipped in repo)

### Modified files
- `gui.py` — Use `paths.get_base_dir()`; first-run bootstrap of config/roster from examples
- `modules/audio.py` — Use `paths.get_base_dir()`; drop `on_done` plumbing
- `modules/detection.py` — Use `paths.get_base_dir()` and `paths.find_lostark_window()`; drop `import win32con`
- `modules/region_selector.py` — Use `paths.find_lostark_window()`; drop `cancelled` signal
- `modules/engine.py` — Collapse state machine; remove dead methods/fields/events; read `miss_seconds` from config
- `modules/roster.py` — Drop dead methods + `self.players` field
- `modules/overlay.py` — Phase-aware `_lbl_current_label` (DARK NOW / UP NEXT)
- `modules/gui_app.py` — Slim down to UI shell; delegate lifecycle to `BotController`, events to `EventRouter`
- `modules/tabs/audio_tab.py` — Emit `volume_changed(float)` signal from slider
- `modules/tabs/rotation_tab.py` — Add MISS SECONDS spinbox
- `.gitignore` — Add `config.yaml`, `rosters/*.yaml` (with `!rosters/example.yaml`); remove `*.spec`
- `README.md` — Final changelog entry

### Deleted files
- `assets/dark_timer_icon.png`

---

## Task 1: Remove dead engine, roster, and audio API

**Files:**
- Modify: `modules/engine.py`
- Modify: `modules/roster.py`
- Modify: `modules/audio.py`

**Rationale:** Pure deletions of confirmed-dead code (audit Section 1). No behavior change. Lowest risk first commit.

- [ ] **Step 1: Remove dead methods from `RotationEngine`**

In `modules/engine.py`:
- Delete `skip()` method (currently L156–162)
- Delete `add_player(name)` method (currently L168–170)
- Delete `remove_player(name)` method (currently L164–166)
- Delete `self.skipped: set[str] = set()` initialization in `__init__` (currently L50)
- Delete `self.skipped = set()` reset in `set_players()` (currently L83)
- Update `_active_players()` to drop the `p not in self.skipped` clause:
  ```python
  def _active_players(self) -> list[str]:
      return [p for p in self.players if p not in self._exhausted]
  ```
- Update `_advance()` to drop the `self.skipped` clause:
  ```python
  def _advance(self):
      if not self._active_players():
          return
      self.index = (self.index + 1) % len(self.players)
      attempts = 0
      while self.players[self.index] in self._exhausted and attempts < len(self.players):
          self.index = (self.index + 1) % len(self.players)
          attempts += 1
  ```
- Update `_next_non_cooldown_player()` to drop the `p in self.skipped` check:
  ```python
  def _next_non_cooldown_player(self) -> str:
      n = len(self.players)
      for i in range(n):
          p = self.players[(self.index + i) % n]
          if p in self._exhausted:
              continue
          if not self._is_on_cooldown(p):
              return p
      return "Nobody"
  ```

- [ ] **Step 2: Remove `RotationState.STOPPED`**

In `modules/engine.py`:
- Delete `STOPPED = auto()` from the `RotationState` enum
- In `stop()`, change `self._set_state(RotationState.STOPPED)` to `self._set_state(RotationState.IDLE)`
- In `reset()`, change `if self.state not in (RotationState.RUNNING, RotationState.PAUSED)` so it stays correct (no STOPPED in tuple — already absent, no edit needed)

- [ ] **Step 3: Remove `ThrowEvent` and `throw_history`**

In `modules/engine.py`:
- Delete the `from dataclasses import dataclass` import
- Delete the `@dataclass class ThrowEvent` block (currently L29–34)
- Delete `self.throw_history: list[ThrowEvent] = []` from `__init__` (currently L53)
- Delete the `self.throw_history.append(ThrowEvent(...))` block in `on_dark_detected` (currently L180–183)
- Delete `"history": self.throw_history[-5:],` from `get_status()` (currently L432)

- [ ] **Step 4: Remove unused engine event emits**

In `modules/engine.py`, `on_dark_detected`:
- Delete the entire `else: self.on_event("confirmed_out_of_order", ...)` branch (currently L190–194). Keep the `if player.lower() == current.lower(): self.on_event("confirmed", ...)` branch but remove the `else` so out-of-order confirms still emit `"confirmed"`:
  ```python
  current = self._current_player()
  kind = "Splendid Dark" if is_splendid else "Dark"
  self.on_event("confirmed", {"player": player, "kind": kind, "duration": duration})
  ```
- In `on_dark_detected`, delete the `_exhausted` notify block (currently L204–209):
  ```python
  if count >= self.max_throws:
      for p in self.players:
          if p.lower() == key and p not in self._exhausted:
              self._exhausted.add(p)
              self.on_event("player_exhausted", {"player": p, "count": count})
              break
  ```
  Replace with:
  ```python
  if count >= self.max_throws:
      for p in self.players:
          if p.lower() == key:
              self._exhausted.add(p)
              break
  ```
- Same for `on_dark_missed` (currently L237–242). Replace the notify block with the silent `_exhausted.add` version above.

- [ ] **Step 5: Remove dead `RosterManager` methods**

In `modules/roster.py`:
- Delete `list_rosters()`, `set_players()`, `add_player()`, `remove_player()`, `move_player()`, `get_players()` methods (L41–74)
- Delete the `self.players = []` initialization from `__init__` (L13)
- Update `load()` to not assign `self.players`:
  ```python
  def load(self, filename: str) -> list[str]:
      path = os.path.join(self.rosters_dir, filename)
      if not os.path.exists(path):
          raise FileNotFoundError(f"Roster file not found: {path}")
      with open(path, "r") as f:
          data = yaml.safe_load(f)
      players = [str(p) for p in data.get("players", [])]
      self.current_roster_name = data.get("name", filename)
      print(f"[Roster] Loaded '{self.current_roster_name}': {players}")
      return players
  ```
- Delete the comment block `# Player management (runtime edits, not persisted until save())`

- [ ] **Step 6: Drop `on_done` plumbing from `AudioManager`**

In `modules/audio.py`:
- `prerender()`: drop `on_done=None` parameter and the arg in `args=(list(players), on_done)`:
  ```python
  def prerender(self, players: list[str]):
      self._ready = False
      self._render_thread = threading.Thread(
          target=self._render_all,
          args=(list(players),),
          daemon=True,
      )
      self._render_thread.start()
  ```
- `_render_all()`: drop the `on_done=None` parameter and the trailing `if on_done: on_done()` block:
  ```python
  def _render_all(self, players: list[str]):
      ...
      self._ready = True
      print(f"[Audio] Pre-render complete — {len(self._cache)} clips ready.")
  ```

- [ ] **Step 7: Smoke-launch**

Run: `python gui.py`
Expected: GUI opens, Roster tab shows 4 players from `rosters/my_raid.yaml`. Click Launch, press F8, F9 once, F11. No tracebacks in console. Close window.

- [ ] **Step 8: Commit**

```bash
git add modules/engine.py modules/roster.py modules/audio.py
git commit -m "chore: remove dead engine, roster, and audio API"
```

---

## Task 2: Remove unused win32con import and orphan icon

**Files:**
- Modify: `modules/detection.py`
- Modify: `modules/region_selector.py`
- Delete: `assets/dark_timer_icon.png`

- [ ] **Step 1: Drop `import win32con` from detection.py**

In `modules/detection.py`, in `_find_lostark_window()`, delete the line `import win32con` (currently L37). Only `win32gui` is used.

- [ ] **Step 2: Drop `cancelled` signal from region_selector.py**

In `modules/region_selector.py`:
- Delete the line `cancelled       = pyqtSignal()` (L38)
- In `keyPressEvent`, delete the line `self.cancelled.emit()` (L148). The `self.close()` line stays — Escape still closes the window.

- [ ] **Step 3: Delete orphan icon asset**

```bash
rm "assets/dark_timer_icon.png"
```

Verify nothing references it:
```bash
grep -r "dark_timer_icon" .
```
Expected: no matches.

- [ ] **Step 4: Smoke-launch**

Run: `python gui.py`
Expected: GUI opens normally. The Overlay tab's "Draw Region on Screen" button still opens the region selector; pressing Escape closes it cleanly.

- [ ] **Step 5: Commit**

```bash
git add modules/detection.py modules/region_selector.py assets/dark_timer_icon.png
git commit -m "chore: remove unused win32con import and orphan icon"
```

---

## Task 3: Centralize BASE_DIR and Lost Ark window finder

**Files:**
- Create: `modules/paths.py`
- Modify: `gui.py`
- Modify: `modules/gui_app.py`
- Modify: `modules/audio.py`
- Modify: `modules/detection.py`
- Modify: `modules/region_selector.py`

- [ ] **Step 1: Create `modules/paths.py`**

```python
"""
paths.py - Centralized path resolution and Lost Ark window discovery.

Both helpers tolerate frozen-vs-script execution (PyInstaller .exe vs python gui.py)
and the Lost Ark window not being open.
"""

import os
import sys


LOSTARK_WINDOW_TITLE = "LOST ARK"


def get_base_dir() -> str:
    """Return the directory that contains config.yaml.

    When frozen (PyInstaller), this is the directory containing the .exe
    (one level up from `dist/` if the exe lives there). When running as a
    script, this is the project root.
    """
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        if os.path.basename(exe_dir).lower() == "dist":
            return os.path.dirname(exe_dir)
        return exe_dir
    # __file__ is .../modules/paths.py — go up two levels
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_lostark_window() -> tuple[int, int] | None:
    """Return (left, top) of the Lost Ark window's client area, or None
    if Lost Ark is not visible on any monitor."""
    try:
        import win32gui

        def _cb(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if LOSTARK_WINDOW_TITLE.lower() in title.lower():
                    rect = win32gui.GetClientRect(hwnd)
                    pt = win32gui.ClientToScreen(hwnd, (rect[0], rect[1]))
                    results.append(pt)

        found = []
        win32gui.EnumWindows(_cb, found)
        return found[0] if found else None
    except Exception as e:
        print(f"[Paths] Lost Ark window find error: {e}")
        return None
```

- [ ] **Step 2: Update `gui.py` to use `paths.get_base_dir()`**

In `gui.py`, replace the BASE_DIR block with:
```python
from modules.paths import get_base_dir

BASE_DIR = get_base_dir()
```
Delete the `import sys` (kept for `sys.argv`/`sys.exit`/`sys.executable` — wait: `sys.executable` is no longer needed after this change, but `sys.argv` and `sys.exit` are still used).

Final top-of-file:
```python
import sys
import os
import ctypes
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from modules.gui_app import ConfigApp
from modules.paths import get_base_dir

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DarkRotationBot.DarkTimer")
except Exception:
    pass

BASE_DIR = get_base_dir()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = os.path.join(BASE_DIR, "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    config_path = os.path.join(BASE_DIR, "config.yaml")
    window = ConfigApp(config_path)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Update `modules/gui_app.py` BASE_DIR**

Replace the `import sys as _sys ... BASE_DIR = ...` block at the top with:
```python
from modules.paths import get_base_dir

BASE_DIR = get_base_dir()
```

- [ ] **Step 4: Update `modules/audio.py` BASE_DIR**

Replace the `if getattr(sys, "frozen", False): ... _BASE_DIR = ...` block with:
```python
from modules.paths import get_base_dir

_BASE_DIR = get_base_dir()
```
The `import sys` line can stay (used by `import asyncio` etc — actually no, `sys` was only for the BASE_DIR resolution). Verify and delete `import sys` if unused.

- [ ] **Step 5: Update `modules/detection.py` to use both helpers**

Replace the BASE_DIR block AND the `_find_lostark_window` function with imports:
```python
from modules.paths import get_base_dir, find_lostark_window

BASE_DIR = get_base_dir()
TEMPLATE_DIR = os.path.join(BASE_DIR, "assets", "templates")
```

Delete the entire `def _find_lostark_window():` block. In `_scan` and `check_now`, replace `_find_lostark_window()` calls with `find_lostark_window()` (no underscore prefix).

Also delete `import sys as _sys` — no longer needed.

- [ ] **Step 6: Update `modules/region_selector.py` to use `find_lostark_window`**

Replace:
```python
def _get_lostark_origin():
    ...
```
with no function (delete the whole helper).

In `RegionSelectorWindow.__init__`, change:
```python
self._lostark_origin = _get_lostark_origin()
```
to:
```python
from modules.paths import find_lostark_window
self._lostark_origin = find_lostark_window()
```

- [ ] **Step 7: Smoke-launch**

Run: `python gui.py`
Expected: GUI opens; everything works the same as before. Detection (if Lost Ark is running and detection enabled) still finds the window.

- [ ] **Step 8: Commit**

```bash
git add modules/paths.py gui.py modules/gui_app.py modules/audio.py modules/detection.py modules/region_selector.py
git commit -m "refactor: centralize BASE_DIR and lostark window finder in paths module"
```

---

## Task 4: Introduce `EngineEvent` enum

**Files:**
- Create: `modules/events.py`
- Modify: `modules/engine.py`
- Modify: `modules/audio.py`
- Modify: `modules/gui_app.py`

**Rationale:** Single source of truth for engine event names. String-Enum so existing `event_type == "confirmed"` comparisons in dispatch code keep working unchanged — we just replace the bare string literals at the emit site and the consumer site.

- [ ] **Step 1: Create `modules/events.py`**

```python
"""
events.py - Engine event names.

String-Enum: members compare equal to their string value, so consumers
can branch on either `event == EngineEvent.CONFIRMED` or `event == "confirmed"`.
"""

from enum import Enum


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

- [ ] **Step 2: Use `EngineEvent` at every engine emit site**

In `modules/engine.py`:
- Add import: `from modules.events import EngineEvent`
- Replace every `self.on_event("xxx", ...)` with `self.on_event(EngineEvent.XXX, ...)`. Specifically:
  - `"reset"` → `EngineEvent.RESET`
  - `"confirmed"` → `EngineEvent.CONFIRMED`
  - `"missed"` → `EngineEvent.MISSED`
  - `"warning"` → `EngineEvent.WARNING`
  - `"announce"` → `EngineEvent.ANNOUNCE`
  - `"cooldown_skip"` → `EngineEvent.COOLDOWN_SKIP`
  - `"rotation_complete"` → `EngineEvent.ROTATION_COMPLETE`
- In `_set_state`, the event uses `EngineEvent.STATE_CHANGE`:
  ```python
  def _set_state(self, new_state: RotationState):
      self.state = new_state
      self.on_event(EngineEvent.STATE_CHANGE, {"state": new_state.name})
  ```

- [ ] **Step 3: Update `EVENT_TO_CUE` in audio.py to use enum members**

In `modules/audio.py`:
- Add import: `from modules.events import EngineEvent`
- Replace:
  ```python
  EVENT_TO_CUE = {
      "announce":          "announce",
      "warning":           "warning",
      "confirmed":         "confirmed",
      "rotation_complete": "rotation_complete",
      "reset":             "reset",
  }
  ```
  with:
  ```python
  EVENT_TO_CUE = {
      EngineEvent.ANNOUNCE:          "announce",
      EngineEvent.WARNING:           "warning",
      EngineEvent.CONFIRMED:         "confirmed",
      EngineEvent.ROTATION_COMPLETE: "rotation_complete",
      EngineEvent.RESET:             "reset",
  }
  ```
The `play_event(event_type, data)` lookup `EVENT_TO_CUE.get(event_type)` still works because `EngineEvent` members hash and compare equal to their string values.

- [ ] **Step 4: Update `gui_app._on_engine_event_ui` branches**

In `modules/gui_app.py`:
- Add import: `from modules.events import EngineEvent`
- Replace string comparisons in `_on_engine_event_ui` with enum comparisons:
  ```python
  if event_type == EngineEvent.STATE_CHANGE:
      ...
  if event_type == EngineEvent.RESET and self._overlay_win:
      ...
  if event_type == EngineEvent.CONFIRMED and self._overlay_win:
      ...
  elif event_type == EngineEvent.MISSED and self._overlay_win:
      ...
  elif event_type == EngineEvent.WARNING and self._overlay_win:
      ...
  elif event_type == EngineEvent.ROTATION_COMPLETE and self._overlay_win:
      ...
  elif event_type == EngineEvent.COOLDOWN_SKIP and self._overlay_win:
      ...
  if self._detection_engine:
      if event_type == EngineEvent.CONFIRMED:
          self._detection_engine.pause()
      elif event_type in (EngineEvent.ANNOUNCE, EngineEvent.MISSED, EngineEvent.COOLDOWN_SKIP):
          self._detection_engine.resume()
  if self._audio_mgr:
      if event_type == EngineEvent.CONFIRMED:
          ...
  ```
Leave the inner `data["player"]`/`data["next"]` reads alone.

- [ ] **Step 5: Smoke-launch**

Run: `python gui.py`. Click Launch, press F8, run through one announce → confirm cycle. Audio cues fire as before. No tracebacks.

- [ ] **Step 6: Commit**

```bash
git add modules/events.py modules/engine.py modules/audio.py modules/gui_app.py
git commit -m "refactor: introduce EngineEvent enum"
```

---

## Task 5: Extract Qt stylesheets into styles module

**Files:**
- Create: `modules/styles.py`
- Modify: `modules/gui_app.py`
- Modify: `modules/tabs/roster_tab.py`
- Modify: `modules/tabs/rotation_tab.py`
- Modify: `modules/tabs/hotkeys_tab.py`
- Modify: `modules/tabs/audio_tab.py`
- Modify: `modules/tabs/overlay_tab.py`

**Rationale:** Pull the most-repeated QSS strings into named constants. Goal is reduction (~30% per tab file), not zero-inline purity.

- [ ] **Step 1: Create `modules/styles.py`**

```python
"""
styles.py - Reusable QSS strings.

Tab files keep small, locally-specific styles inline. These are the
strings repeated 3+ times across the codebase.
"""

# ─── Backgrounds & cards ───────────────────────────────────────────────
APP_BG    = "background: #0d0d0d;"
CARD_DARK = (
    "QFrame { background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 4px; }"
)

# ─── Inputs ────────────────────────────────────────────────────────────
INPUT_DARK = (
    "background: #1a1a1a; color: #fff; border: 1px solid #333; "
    "padding: 4px 8px; min-width: 60px; font-family: Consolas; font-size: 14px;"
)

LINE_EDIT_DARK = (
    "background: #111; color: #ccc; border: 1px dashed #333; "
    "padding: 6px; font-family: Consolas; font-size: 14px;"
)

# ─── Buttons ───────────────────────────────────────────────────────────
BUTTON_GHOST = (
    "color: #88ccff; background: transparent; border: 1px solid #444; "
    "padding: 5px 10px; font-size: 14px; font-family: Consolas;"
)

BUTTON_PRIMARY_GREEN = (
    "background: #1a3a1a; color: #44ff88; border: none; "
    "padding: 6px 16px; font-family: Consolas; font-size: 14px;"
)

BUTTON_DANGER = (
    "background: #2a1a1a; color: #ff4444; border: 1px solid #3a2a2a; "
    "padding: 4px 10px; font-family: Consolas; font-size: 14px;"
)

BUTTON_NEUTRAL = (
    "background: #1a1a1a; color: #ccc; border: 1px solid #333; "
    "padding: 4px 10px; font-family: Consolas; font-size: 14px;"
)

# ─── Labels ────────────────────────────────────────────────────────────
LABEL_HINT    = "color: #888; font-size: 14px;"
LABEL_SECTION = "color: #ccc; font-size: 14px; font-family: Consolas;"
LABEL_DIM     = "color: #888; font-size: 14px; font-family: Consolas;"

# ─── Slider ────────────────────────────────────────────────────────────
SLIDER_GOLD = (
    "QSlider::groove:horizontal { background: #333; height: 6px; border-radius: 3px; }"
    "QSlider::sub-page:horizontal { background: #ffd700; border-radius: 3px; }"
    "QSlider::handle:horizontal { background: #fff; border: 2px solid #ffd700; "
    "width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; }"
)

# ─── Checkbox ──────────────────────────────────────────────────────────
CHECKBOX_GOLD = (
    "QCheckBox { color: #ccc; font-size: 14px; font-family: Consolas; "
    "border: none; background: transparent; }"
    "QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #555; "
    "border-radius: 3px; background: #111; }"
    "QCheckBox::indicator:checked { background: #ffd700; border-color: #ffd700; }"
    "QCheckBox::indicator:hover { border-color: #ffd700; }"
)
```

- [ ] **Step 2: Replace duplicated styles in tab files**

Add `from modules.styles import ...` at top of each tab file, then replace the inline string with the constant. Examples:

In `modules/tabs/roster_tab.py`:
```python
from modules.styles import INPUT_DARK, LINE_EDIT_DARK, BUTTON_PRIMARY_GREEN, BUTTON_NEUTRAL, BUTTON_DANGER

# ...
self._add_input.setStyleSheet(LINE_EDIT_DARK)
add_btn.setStyleSheet(BUTTON_PRIMARY_GREEN)
for btn in (up_btn, down_btn):
    btn.setStyleSheet(BUTTON_NEUTRAL)
del_btn.setStyleSheet(BUTTON_DANGER)
```

Apply analogous replacements in `rotation_tab.py`, `hotkeys_tab.py`, `audio_tab.py`, `overlay_tab.py`. Where existing strings have additional rules (e.g. font-weight: bold), append them inline:
```python
some_btn.setStyleSheet(BUTTON_GHOST + " font-weight: bold;")
```

Do NOT replace tab-specific styles that only appear once (e.g. the listening-state hotkey badge, the dimmed-disabled cue card). Goal is reduction, not zero inline.

- [ ] **Step 3: Smoke-launch**

Run: `python gui.py`. All tabs render correctly. Visual diff against memory: gold sliders, dark inputs, green Add button, red Remove button, ghost-style preview/test/draw buttons.

- [ ] **Step 4: Commit**

```bash
git add modules/styles.py modules/gui_app.py modules/tabs/
git commit -m "refactor: extract Qt stylesheets into styles module"
```

---

## Task 6: Collapse engine state machine

**Files:**
- Modify: `modules/engine.py`
- Modify: `modules/gui_app.py`

**Rationale:** Replace the `_dark_active` boolean (a hidden second state machine) with explicit `RUNNING_PLAYER_WINDOW` / `RUNNING_DARK_WINDOW` substates. Public surface (events, status keys) preserved except `dark_active` → `phase`. **High-risk task** — manual smoke check after.

- [ ] **Step 1: Update `RotationState` and remove `_dark_active`**

In `modules/engine.py`:

Replace the enum:
```python
class RotationState(Enum):
    IDLE                  = auto()
    RUNNING_PLAYER_WINDOW = auto()
    RUNNING_DARK_WINDOW   = auto()
    PAUSED                = auto()
```

In `__init__`, delete `self._dark_active: bool = False` (currently L66).

Add helper after `__init__`:
```python
@property
def is_running(self) -> bool:
    return self.state in (
        RotationState.RUNNING_PLAYER_WINDOW,
        RotationState.RUNNING_DARK_WINDOW,
    )
```

- [ ] **Step 2: Update `start()`**

```python
def start(self):
    if not self.players:
        print("[Engine] No players loaded.")
        return
    if self.is_running:
        return
    self._stop_event.clear()
    self._throw_times.clear()
    self._throw_counts.clear()
    self._exhausted.clear()
    self._begin_player_window()
    self._start_timer_thread()
```
Note: `_set_state` is now called from inside `_begin_player_window` (Step 4), not from `start`.

- [ ] **Step 3: Update `pause()` and `resume()`**

```python
def pause(self):
    if not self.is_running:
        return
    if self.state == RotationState.RUNNING_DARK_WINDOW:
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
        self._dark_start = time.time()
        self._dark_duration = 25 if is_splendid else 20
        self._dark_warned = False
        self._set_state(RotationState.RUNNING_DARK_WINDOW)
    else:
        self._advance()
        self._set_state(RotationState.RUNNING_PLAYER_WINDOW)
        self._begin_player_window()
    self._stop_event.clear()
    if not self._timer_thread or not self._timer_thread.is_alive():
        self._start_timer_thread()
    print("[Engine] Resumed.")
```

- [ ] **Step 4: Update `_begin_player_window` and `on_dark_detected` and `on_dark_missed`**

`_begin_player_window` (existing logic, but ends with state set):
```python
def _begin_player_window(self):
    if not self._active_players():
        print("[Engine] All players exhausted. Rotation complete.")
        self.on_event(EngineEvent.ROTATION_COMPLETE, {})
        self.stop()
        return

    checked = 0
    while checked < len(self.players):
        player = self._current_player()
        if not self._is_on_cooldown(player):
            break
        print(f"[Engine] {player} is on cooldown — skipping.")
        self.on_event(EngineEvent.COOLDOWN_SKIP, {"player": player})
        self._advance()
        checked += 1
    else:
        print("[Engine] All active players on cooldown — announcing anyway.")

    self._player_window_start = time.time()
    self._miss_warned = False
    self._phase1_warned = False
    self._set_state(RotationState.RUNNING_PLAYER_WINDOW)
    player = self._current_player()
    self.on_event(EngineEvent.ANNOUNCE, {
        "player": player,
        "index": self.index,
        "total": len(self._active_players()),
    })
```

`on_dark_detected`: replace the trailing block that flipped `_dark_active`:
```python
self._dark_player = player
self._advance()
self._dark_start = time.time()
self._dark_duration = duration
self._dark_warned = False
self._set_state(RotationState.RUNNING_DARK_WINDOW)
```

`on_dark_missed`: replace the early-return guard and the trailing block:
```python
def on_dark_missed(self):
    if self.state != RotationState.RUNNING_PLAYER_WINDOW:
        return
    # ... existing body up to ...
    self._advance()
    self._begin_player_window()
```

(The `self._dark_active = False` line is gone — `_begin_player_window` sets state explicitly.)

- [ ] **Step 5: Update `_tick`**

```python
def _tick(self):
    if self.state == RotationState.RUNNING_DARK_WINDOW:
        dark_elapsed = time.time() - self._dark_start
        dark_remaining = self._dark_duration - dark_elapsed

        if not self._dark_warned and dark_remaining <= self.warn_secs:
            self._dark_warned = True
            next_up = self._next_non_cooldown_player()
            if next_up != "Nobody":
                self.on_event(EngineEvent.WARNING, {
                    "current": "Dark",
                    "next": next_up,
                    "seconds": int(dark_remaining),
                })

        if dark_remaining <= 0:
            self._begin_player_window()
        return

    # RUNNING_PLAYER_WINDOW
    elapsed = time.time() - self._player_window_start
    if not self._phase1_warned and elapsed >= (self.miss_secs - self.warn_secs):
        self._phase1_warned = True
        current = self._current_player()
        next_up = self._next_active_player()
        if next_up != "Nobody" and next_up != current:
            self.on_event(EngineEvent.WARNING, {
                "current": current,
                "next": next_up,
                "seconds": int(self.warn_secs),
            })

    if not self._miss_warned and elapsed >= self.miss_secs:
        self._miss_warned = True
        self.on_event(EngineEvent.MISSED, {"player": self._current_player()})
        self._advance()
        self._begin_player_window()
```

Also update `_timer_loop`:
```python
def _timer_loop(self):
    while not self._stop_event.is_set():
        if self.is_running:
            self._tick()
        time.sleep(0.25)
```

- [ ] **Step 6: Update `reset()` and `stop()` and `on_dark_detected` early-return**

`stop()`:
```python
def stop(self):
    self._stop_event.set()
    self._set_state(RotationState.IDLE)
    self.index = 0
    print("[Engine] Rotation stopped.")
```

`reset()`:
```python
def reset(self):
    if self.state not in (RotationState.RUNNING_PLAYER_WINDOW, RotationState.RUNNING_DARK_WINDOW, RotationState.PAUSED):
        return
    self._stop_event.set()
    self._throw_times.clear()
    self._throw_counts.clear()
    self._exhausted.clear()
    self.index = 0
    self._set_state(RotationState.IDLE)
    self.on_event(EngineEvent.RESET, {})
    print("[Engine] Rotation reset to player 1.")
```

`on_dark_detected` early-return:
```python
def on_dark_detected(self, player: str, is_splendid: bool):
    if self.state != RotationState.RUNNING_PLAYER_WINDOW:
        return
    # ... rest unchanged ...
```
(Replaces the old `if self.state != RotationState.RUNNING: return; if self._dark_active: return` two-check pattern.)

- [ ] **Step 7: Update `get_status` to expose `phase` instead of `dark_active`**

```python
def get_status(self) -> dict:
    if self.state == RotationState.PAUSED:
        remaining = self._paused_remaining
        duration = self._paused_duration
    elif self.state == RotationState.RUNNING_DARK_WINDOW:
        dark_elapsed = time.time() - self._dark_start
        remaining = max(0.0, self._dark_duration - dark_elapsed)
        duration = self._dark_duration
    elif self.state == RotationState.RUNNING_PLAYER_WINDOW:
        elapsed = time.time() - self._player_window_start
        remaining = max(0.0, self.miss_secs - elapsed)
        duration = self.miss_secs
    else:
        remaining = 0.0
        duration = self.miss_secs

    if self.state == RotationState.RUNNING_DARK_WINDOW:
        current_display = self._dark_player or self._current_player()
        next_display    = self._current_player()
        phase = "dark_window"
    elif self.state == RotationState.RUNNING_PLAYER_WINDOW:
        current_display = self._current_player()
        next_display    = self._next_active_player()
        phase = "player_window"
    else:
        current_display = self._current_player()
        next_display    = self._next_active_player()
        phase = None

    def _count(name: str) -> str:
        c = self._throw_counts.get(name.lower(), 0)
        return f"{c}/{self.max_throws}"

    return {
        "state": self.state.name,
        "phase": phase,
        "current_player": current_display,
        "next_player": next_display,
        "current_count": _count(current_display),
        "next_count": _count(next_display),
        "remaining_seconds": remaining,
        "window_duration": duration,
    }
```
(Note: `dark_active`, `players`, `index` keys removed — confirmed unread in audit.)

- [ ] **Step 8: Update `gui_app._on_engine_event_ui` for new state names**

In `modules/gui_app.py`, the STATE_CHANGE branch currently maps `"PAUSED" / "RUNNING" / "IDLE"` to status messages. Replace with:
```python
if event_type == EngineEvent.STATE_CHANGE:
    new_state = data.get("state", "")
    if new_state == "PAUSED":
        self._status_dot.setStyleSheet("color: #ffaa00; font-size: 16px;")
        self._status_text.setText("Paused  —  press F8 to resume")
        self._status_text.setStyleSheet("color: #ffaa00; font-size: 14px;")
    elif new_state in ("RUNNING_PLAYER_WINDOW", "RUNNING_DARK_WINDOW"):
        self._status_dot.setStyleSheet("color: #44ff88; font-size: 16px;")
        self._status_text.setText("Running")
        self._status_text.setStyleSheet("color: #44ff88; font-size: 14px;")
    elif new_state == "IDLE":
        self._status_dot.setStyleSheet("color: #ffaa00; font-size: 16px;")
        self._status_text.setText("Armed  —  press F8 to start")
        self._status_text.setStyleSheet("color: #ffaa00; font-size: 14px;")
    return
```

- [ ] **Step 9: Update `_hotkey_start_stop` in `gui_app.py`**

```python
def _hotkey_start_stop(self):
    if not self._engine:
        return
    from modules.engine import RotationState
    state = self._engine.state
    if state in (RotationState.RUNNING_PLAYER_WINDOW, RotationState.RUNNING_DARK_WINDOW):
        self._engine.pause()
        if self._detection_engine:
            self._detection_engine.pause()
    elif state == RotationState.PAUSED:
        # ... unchanged ...
    else:
        # IDLE — first start after launch
        self._engine.start()
        if self._detection_engine:
            self._detection_engine.resume()
```

- [ ] **Step 10: Smoke-launch — full rotation cycle**

Run: `python gui.py`. Click Launch. Press F8 to start.
- Verify announce fires for player 1.
- Press F9 — confirmed cue plays, dark window begins (overlay timer counts down from 20s).
- Wait for dark window to expire — next player announced automatically.
- Press F8 to pause; press F8 again to resume. Both phases pause/resume correctly.
- Press F11 to reset. Rotation returns to player 1, "Armed" status shown.
- Close window cleanly.

- [ ] **Step 11: Commit**

```bash
git add modules/engine.py modules/gui_app.py
git commit -m "refactor: collapse engine state machine into explicit phases"
```

---

## Task 7: Live volume slider

**Files:**
- Modify: `modules/tabs/audio_tab.py`
- Modify: `modules/gui_app.py`

- [ ] **Step 1: Add `volume_changed` signal to `AudioTab`**

In `modules/tabs/audio_tab.py`:

Class header:
```python
class AudioTab(QWidget):
    test_requested  = pyqtSignal()
    volume_changed  = pyqtSignal(float)
```

Replace the slider's `valueChanged.connect` with a method that does both label update and signal emit:
```python
self._volume.valueChanged.connect(self._on_volume_changed)
```

Add the method (anywhere in the class, e.g. below `_section_label`):
```python
def _on_volume_changed(self, v: int):
    self._volume_label.setText(f"VOLUME  {v}%")
    self.volume_changed.emit(v / 100.0)
```

- [ ] **Step 2: Connect signal in `ConfigApp`**

In `modules/gui_app.py`, in `_build_ui` where the audio tab is wired:
```python
self._audio_tab.test_requested.connect(self._handle_audio_test)
self._audio_tab.volume_changed.connect(self._handle_volume_changed)
```

Add the handler method:
```python
def _handle_volume_changed(self, volume: float):
    """Called when user drags the Audio tab volume slider — applies live."""
    if self._audio_mgr:
        self._audio_mgr.set_volume(volume)
```

- [ ] **Step 3: Smoke-launch**

Run: `python gui.py`. Click Launch (do NOT press F8 — let pre-render finish, then trigger a test cue via the Audio tab's "Test Voice" button). Drag the volume slider while a cue plays — volume changes live without clicking Apply.

- [ ] **Step 4: Commit**

```bash
git add modules/tabs/audio_tab.py modules/gui_app.py
git commit -m "feat: live volume slider in Audio tab"
```

---

## Task 8: Overlay current label reflects active phase

**Files:**
- Modify: `modules/overlay.py`

- [ ] **Step 1: Update `_render` to set `_lbl_current_label` from phase**

In `modules/overlay.py`, in `_render`, after the existing `state` handling and before the `current = status.get("current_player", ...)` block, add:
```python
phase = status.get("phase")
if phase == "dark_window":
    self._lbl_current_label.setText("DARK NOW")
elif phase == "player_window":
    self._lbl_current_label.setText("UP NEXT")
# else: leave the current text untouched (idle/paused preserves whichever phase was last shown)
```

- [ ] **Step 2: Smoke-launch**

Run: `python gui.py`. Launch, F8.
- Initial state: overlay shows "UP NEXT — [player 1]" (player window).
- Press F9: overlay flips to "DARK NOW — [player 1]" with the dark countdown.
- After dark expires: flips back to "UP NEXT — [next player]".

- [ ] **Step 3: Commit**

```bash
git add modules/overlay.py
git commit -m "feat: overlay current label reflects active phase"
```

---

## Task 9: Split `ConfigApp` into `BotController` and `EventRouter`

**Files:**
- Create: `modules/bot_controller.py`
- Create: `modules/event_router.py`
- Modify: `modules/gui_app.py`

**Rationale:** `gui_app.py` is a 570-line god-object. Extract lifecycle to `BotController`, event routing to `EventRouter`. `ConfigApp` becomes UI shell. **High-risk task** — manual smoke check after.

- [ ] **Step 1: Create `modules/bot_controller.py`**

```python
"""
bot_controller.py - Owns the runtime lifecycle of every bot subsystem.

ConfigApp delegates start/stop/apply/volume here so the QMainWindow stays
focused on UI concerns.
"""

import os

from modules.engine    import RotationEngine, RotationState
from modules.overlay   import OverlayWindow
from modules.hotkeys   import HotkeyManager
from modules.detection import DetectionEngine
from modules.audio     import AudioManager


class BotController:
    def __init__(self, on_engine_event, base_dir: str):
        """on_engine_event(event_type, data) — called from engine bg thread."""
        self._on_engine_event = on_engine_event
        self._base_dir = base_dir
        self._last_confirm_source = "hotkey"

        self.engine: RotationEngine | None = None
        self.hotkeys: HotkeyManager | None = None
        self.overlay: OverlayWindow | None = None
        self.detection: DetectionEngine | None = None
        self.audio: AudioManager | None = None

    # ── Lifecycle ────────────────────────────────────────────────────
    @property
    def is_running(self) -> bool:
        return self.engine is not None

    def start(self, config: dict, players: list[str],
              overlay_save_position_cb, overlay_stop_cb):
        self.engine = RotationEngine(config, self._on_engine_event)
        self.engine.set_players(players)

        self.overlay = OverlayWindow(
            config.get("overlay", {}),
            get_status_fn=self.engine.get_status,
            save_position_callback=overlay_save_position_cb,
            stop_callback=overlay_stop_cb,
        )
        self.overlay.start()

        self.hotkeys = HotkeyManager(
            config.get("hotkeys", {}),
            callbacks={
                "start_stop": self._hotkey_start_stop,
                "confirm":    self._hotkey_confirm,
                "missed":     self._hotkey_missed,
                "reset":      self._hotkey_reset,
            },
        )
        self.hotkeys.start()

        if config.get("detection", {}).get("enabled", False):
            self.detection = DetectionEngine(
                config,
                on_detected=self._on_grenade_detected,
            )
            self.detection.start()
            self.detection.pause()

        if config.get("audio", {}).get("enabled", True):
            self.audio = AudioManager(config)
            self.audio.prerender(players)

    def stop(self):
        if self.engine:    self.engine.stop()
        if self.hotkeys:   self.hotkeys.stop()
        if self.overlay:   self.overlay.stop()
        if self.detection: self.detection.stop()
        if self.audio:     self.audio.shutdown()
        self.engine = self.hotkeys = self.overlay = self.detection = self.audio = None

    def apply(self, config: dict, players: list[str]):
        if self.engine:
            rot = config.get("rotation", {})
            self.engine.warn_secs     = rot.get("warning_seconds", 5)
            self.engine.cooldown_secs = rot.get("dark_cooldown_seconds", 30)
            self.engine.max_throws    = rot.get("max_throws_per_run", 3)
            self.engine.miss_secs     = rot.get("miss_seconds", 20)
            self.engine.set_players(players)
        if self.detection:
            self.detection.update_config(config)
        if self.audio:
            self.audio.update_config(config, players)
        if self.hotkeys:
            for action, key in config.get("hotkeys", {}).items():
                self.hotkeys.update_key(action, key)
        if self.overlay:
            self.overlay.setWindowOpacity(config.get("overlay", {}).get("opacity", 1.0))

    def set_audio_volume(self, volume: float):
        if self.audio:
            self.audio.set_volume(volume)

    # ── Hotkey callbacks ─────────────────────────────────────────────
    def _hotkey_start_stop(self):
        if not self.engine:
            return
        s = self.engine.state
        if s in (RotationState.RUNNING_PLAYER_WINDOW, RotationState.RUNNING_DARK_WINDOW):
            self.engine.pause()
            if self.detection:
                self.detection.pause()
        elif s == RotationState.PAUSED:
            dark_found, is_splendid = (False, False)
            if self.detection:
                dark_found, is_splendid = self.detection.check_now()
            self.engine.resume(dark_detected=dark_found, is_splendid=is_splendid)
            if self.detection:
                if dark_found:
                    self.detection.pause()
                else:
                    self.detection.resume()
        else:
            self.engine.start()
            if self.detection:
                self.detection.resume()

    def _hotkey_confirm(self):
        if not self.engine:
            return
        self._last_confirm_source = "hotkey"
        status = self.engine.get_status()
        player = status.get("current_player", "Unknown")
        self.engine.on_dark_detected(player, is_splendid=False)

    def _hotkey_missed(self):
        if self.engine:
            self.engine.on_dark_missed()

    def _hotkey_reset(self):
        if not self.engine:
            return
        self.engine.reset()
        if self.detection:
            self.detection.pause()

    def _on_grenade_detected(self, is_splendid: bool):
        if not self.engine:
            return
        self._last_confirm_source = "detection"
        status = self.engine.get_status()
        player = status.get("current_player", "Unknown")
        kind = "Splendid Dark" if is_splendid else "Dark"
        print(f"[Detection] Auto-confirmed: {player} ({kind})")
        self.engine.on_dark_detected(player, is_splendid=is_splendid)

    # ── Used by EventRouter ──────────────────────────────────────────
    @property
    def last_confirm_source(self) -> str:
        return self._last_confirm_source

    def reset_last_confirm_source(self):
        self._last_confirm_source = "hotkey"
```

- [ ] **Step 2: Create `modules/event_router.py`**

```python
"""
event_router.py - Dispatches engine events to overlay, detection, and audio.
"""

from modules.events import EngineEvent


class EventRouter:
    def __init__(self, controller):
        self._ctrl = controller
        self._handlers = {
            EngineEvent.STATE_CHANGE:      self._on_state_change,
            EngineEvent.RESET:             self._on_reset,
            EngineEvent.CONFIRMED:         self._on_confirmed,
            EngineEvent.MISSED:            self._on_missed,
            EngineEvent.WARNING:           self._on_warning,
            EngineEvent.ROTATION_COMPLETE: self._on_rotation_complete,
            EngineEvent.COOLDOWN_SKIP:     self._on_cooldown_skip,
            EngineEvent.ANNOUNCE:          self._on_announce,
        }

    def handle(self, event_type, data: dict, status_text_cb):
        """Main entry. status_text_cb is a callable (text, color) used
        by state_change events to update the bottom-bar status."""
        if event_type == EngineEvent.STATE_CHANGE:
            self._on_state_change(data, status_text_cb)
            return

        handler = self._handlers.get(event_type)
        if handler:
            handler(data)

        # Detection pause/resume around the buff window
        det = self._ctrl.detection
        if det:
            if event_type == EngineEvent.CONFIRMED:
                det.pause()
            elif event_type in (EngineEvent.ANNOUNCE, EngineEvent.MISSED, EngineEvent.COOLDOWN_SKIP):
                det.resume()

        # Audio cues
        audio = self._ctrl.audio
        if audio:
            if event_type == EngineEvent.CONFIRMED:
                if self._ctrl.last_confirm_source == "detection":
                    audio.play_chime()
                else:
                    audio.play_event(event_type, data)
                self._ctrl.reset_last_confirm_source()
            else:
                audio.play_event(event_type, data)

    # ── Per-event handlers ───────────────────────────────────────────
    def _on_state_change(self, data, status_text_cb):
        new_state = data.get("state", "")
        if new_state == "PAUSED":
            status_text_cb("Paused  —  press F8 to resume", "#ffaa00")
        elif new_state in ("RUNNING_PLAYER_WINDOW", "RUNNING_DARK_WINDOW"):
            status_text_cb("Running", "#44ff88")
        elif new_state == "IDLE":
            status_text_cb("Armed  —  press F8 to start", "#ffaa00")

    def _on_reset(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message("Rotation reset", "#88ccff")

    def _on_confirmed(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.flash("#1a4a1a")
            self._ctrl.overlay.set_status_message(f"OK {data['player']} confirmed", "#44ff88")

    def _on_missed(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.flash("#4a1a1a")
            self._ctrl.overlay.set_status_message(f"X {data['player']} missed", "#ff4444")

    def _on_warning(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message(
                f"Next up: {data['next']} in {data['seconds']}s", "#ffdd44"
            )

    def _on_rotation_complete(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message("Rotation complete", "#aaaaaa")

    def _on_cooldown_skip(self, data):
        if self._ctrl.overlay:
            self._ctrl.overlay.set_status_message(f"{data['player']} on cooldown", "#ffaa00")

    def _on_announce(self, data):
        # No overlay/UI side-effect — handled by overlay's polled status read.
        pass
```

- [ ] **Step 3: Slim down `gui_app.py`**

Replace the body of `modules/gui_app.py` with a UI-shell version that delegates lifecycle to `BotController` and event handling to `EventRouter`. Concretely:

- Delete: all `_engine`, `_hotkeys_mgr`, `_overlay_win`, `_detection_engine`, `_audio_mgr` direct fields. Replace with `self._controller = BotController(...)`.
- Delete: `_hotkey_start_stop`, `_hotkey_confirm`, `_hotkey_missed`, `_hotkey_reset`, `_on_grenade_detected` methods. They're now inside `BotController`.
- Delete: the body of `_on_engine_event_ui` after the signal-marshalling. Replace with one call to `self._router.handle(event_type, data, self._set_status_text)`.
- Add helper:
  ```python
  def _set_status_text(self, text: str, color: str):
      self._status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
      self._status_text.setText(text)
      self._status_text.setStyleSheet(f"color: {color}; font-size: 14px;")
  ```
- `_start_bot` becomes:
  ```python
  def _start_bot(self):
      self._config = self._load_config()
      roster_file = self._config.get("rotation", {}).get("active_roster", "my_raid.yaml")
      roster_mgr = RosterManager(os.path.join(BASE_DIR, "rosters"))
      players = roster_mgr.load(roster_file)

      self._controller.start(
          self._config, players,
          overlay_save_position_cb=self._on_overlay_moved,
          overlay_stop_cb=self._handle_overlay_stop,
      )

      self._launch_btn.setText("■  Stop")
      self._launch_btn.setStyleSheet(
          "background: #4a1a1a; color: #ff4444; border: none; "
          "padding: 5px 16px; font-family: Consolas; font-size: 14px; font-weight: bold;"
      )
      self._set_status_text("Armed  —  press F8 to start", "#ffaa00")
      self.hide()
  ```
- `_stop_bot` becomes:
  ```python
  def _stop_bot(self):
      self._controller.stop()
      self._launch_btn.setText("▶  Launch")
      self._launch_btn.setStyleSheet(
          "background: #1a4a1a; color: #44ff88; border: none; "
          "padding: 5px 16px; font-family: Consolas; font-size: 14px; font-weight: bold;"
      )
      self._set_status_text("Bot not running", "#999")
  ```
- `_apply` keeps its tab-gathering and config-save logic (that's UI-coupled) but ends with `self._controller.apply(self._config, players)` instead of inline pushes.
- `_handle_volume_changed` becomes:
  ```python
  def _handle_volume_changed(self, volume: float):
      self._controller.set_audio_volume(volume)
  ```
- `__init__` instantiates the controller and router:
  ```python
  self._controller = BotController(self._on_engine_event, BASE_DIR)
  self._router = EventRouter(self._controller)
  ```
- `_on_engine_event_ui`:
  ```python
  def _on_engine_event_ui(self, event_type, data: dict):
      self._router.handle(event_type, data, self._set_status_text)
  ```
- `_refresh_status_bar`:
  ```python
  def _refresh_status_bar(self):
      if not self._controller.is_running or not self._controller.engine:
          return
      status = self._controller.engine.get_status()
      current = status.get("current_player", "")
      if current and current != "Nobody":
          self._status_text.setText(f"Running — {current}")
  ```
- `closeEvent` uses `self._controller.is_running` instead of the deleted `_bot_running`.
- `_handle_audio_test` uses `self._controller.audio` instead of `self._audio_mgr`.

Imports at top of `gui_app.py`:
```python
from modules.bot_controller import BotController
from modules.event_router   import EventRouter
from modules.events         import EngineEvent
from modules.paths          import get_base_dir
from modules.roster         import RosterManager
# tab imports unchanged
```

- [ ] **Step 4: Smoke-launch — full lifecycle**

Run: `python gui.py`.
- Launch → F8 → announce fires → F9 → confirm → dark window → next player.
- F8 to pause, F8 to resume.
- F11 to reset.
- F9, F10, F11, F8 hotkeys all still work.
- Stop button on overlay tears down cleanly.
- Apply with tab edits while running pushes new values to engine.
- Live volume drag during a cue still applies live.
- Region selector and overlay preview both still work.

- [ ] **Step 5: Commit**

```bash
git add modules/bot_controller.py modules/event_router.py modules/gui_app.py
git commit -m "refactor: split ConfigApp into BotController and EventRouter"
```

---

## Task 10: Surface `miss_seconds` as `rotation.miss_seconds` in config

**Files:**
- Modify: `modules/engine.py`
- Modify: `modules/tabs/rotation_tab.py`
- Modify: `modules/gui_app.py`
- Modify: `modules/bot_controller.py`
- Modify: `config.yaml`

- [ ] **Step 1: Read `miss_seconds` from config in `RotationEngine.__init__`**

In `modules/engine.py`, change:
```python
self.miss_secs = 20.0
```
to:
```python
self.miss_secs = float(self.rot_config.get("miss_seconds", 20))
```

- [ ] **Step 2: Add the field to `RotationTab`**

In `modules/tabs/rotation_tab.py`, in `__init__`:
```python
def __init__(self, config: dict):
    super().__init__()
    rot = config.get("rotation", {})
    self._build_ui(
        max_throws=rot.get("max_throws_per_run", 3),
        cooldown=rot.get("dark_cooldown_seconds", 30),
        warning=rot.get("warning_seconds", 5),
        miss_seconds=rot.get("miss_seconds", 20),
    )
```

In `_build_ui`:
```python
def _build_ui(self, max_throws: int, cooldown: int, warning: int, miss_seconds: int):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(16)

    self._max_throws = self._field(
        layout, "MAX THROWS PER RUN", max_throws, 1, 99,
        "How many darks each player can throw before being retired. "
        "Rotation ends when all players hit this cap.",
    )
    self._cooldown = self._field(
        layout, "DARK COOLDOWN (seconds)", cooldown, 1, 300,
        "Players who threw within this window are skipped when it's their turn.",
    )
    self._miss_seconds = self._field(
        layout, "PLAYER WINDOW (seconds before auto-miss)", miss_seconds, 5, 60,
        "How long a player has to throw their dark before the bot auto-counts a miss.",
    )
    self._warning = self._field(
        layout, "WARNING (seconds before next window)", warning, 1, 60,
        "How early to fire the warning callout before the next player's window.",
    )
    layout.addStretch()
```

In `get_values`:
```python
def get_values(self) -> dict:
    return {
        "max_throws_per_run": self._max_throws.value(),
        "dark_cooldown_seconds": self._cooldown.value(),
        "warning_seconds": self._warning.value(),
        "miss_seconds": self._miss_seconds.value(),
    }
```

- [ ] **Step 3: Push `miss_seconds` to running engine in `BotController.apply`**

This was already added in Task 9 Step 1 (`self.engine.miss_secs = rot.get("miss_seconds", 20)`). Verify the line exists.

- [ ] **Step 4: Add to current `config.yaml`**

In `config.yaml`, add `miss_seconds: 20` under the `rotation:` section so the running app picks it up. Final rotation block:
```yaml
rotation:
  active_roster: my_raid.yaml
  dark_cooldown_seconds: 30
  max_throws_per_run: 3
  miss_seconds: 20
  warning_seconds: 5
```

- [ ] **Step 5: Smoke-launch — verify miss_seconds works**

Run: `python gui.py`.
- Rotation tab shows the new "PLAYER WINDOW" spinbox at 20.
- Change to 10, click Apply, click Launch, F8 — auto-miss fires after 10s instead of 20s.
- Restore to 20, Apply.

- [ ] **Step 6: Commit**

```bash
git add modules/engine.py modules/tabs/rotation_tab.py modules/bot_controller.py config.yaml
git commit -m "feat: surface miss_seconds as rotation.miss_seconds in config"
```

---

## Task 11: Gitignore personal config and roster, ship examples

**Files:**
- Create: `config.example.yaml`
- Create: `rosters/example.yaml`
- Modify: `gui.py` (first-run bootstrap)
- Modify: `.gitignore`
- Untrack: `config.yaml`, `rosters/my_raid.yaml`

- [ ] **Step 1: Create `config.example.yaml` with neutral defaults**

```yaml
audio:
  cues:
    announce: true
    chime: true
    confirmed: true
    reset: true
    rotation_complete: true
    warning: true
  enabled: true
  voice: Andrew
  volume: 0.8
detection:
  enabled: false
  height: 35
  rel_x: 875
  rel_y: 325
  scan_interval_ms: 500
  threshold: 0.75
  width: 281
gui:
  position:
    x: 100
    y: 100
hotkeys:
  confirm: f9
  missed: f10
  reset: f11
  start_stop: f8
overlay:
  font_size: 16
  height: 230
  opacity: 1.0
  position:
    x: 100
    y: 100
  width: 320
rotation:
  active_roster: example.yaml
  dark_cooldown_seconds: 30
  max_throws_per_run: 3
  miss_seconds: 20
  warning_seconds: 5
```

- [ ] **Step 2: Create `rosters/example.yaml`**

```yaml
name: Example Raid
players:
- Player1
- Player2
- Player3
- Player4
```

- [ ] **Step 3: Add first-run bootstrap to `gui.py`**

In `modules/paths.py`, add a helper:
```python
import shutil

def ensure_user_files(base_dir: str):
    """If config.yaml or the active roster don't exist, copy from examples."""
    config = os.path.join(base_dir, "config.yaml")
    config_example = os.path.join(base_dir, "config.example.yaml")
    if not os.path.exists(config) and os.path.exists(config_example):
        shutil.copy(config_example, config)
        print(f"[Paths] Created {config} from example.")

    # Determine active roster from the (possibly newly-copied) config
    try:
        import yaml
        with open(config) as f:
            data = yaml.safe_load(f) or {}
        active = data.get("rotation", {}).get("active_roster", "example.yaml")
    except Exception:
        active = "example.yaml"

    roster = os.path.join(base_dir, "rosters", active)
    roster_example = os.path.join(base_dir, "rosters", "example.yaml")
    if not os.path.exists(roster) and os.path.exists(roster_example):
        shutil.copy(roster_example, roster)
        print(f"[Paths] Created {roster} from example.")
```

In `gui.py`, in `main()` before constructing `ConfigApp`:
```python
from modules.paths import get_base_dir, ensure_user_files

BASE_DIR = get_base_dir()

def main():
    ensure_user_files(BASE_DIR)
    app = QApplication(sys.argv)
    # ... rest unchanged ...
```

- [ ] **Step 4: Update `.gitignore`**

Append:
```
config.yaml
rosters/*.yaml
!rosters/example.yaml
```

- [ ] **Step 5: Untrack the personal files (keep on disk)**

```bash
git rm --cached config.yaml rosters/my_raid.yaml
```

- [ ] **Step 6: Smoke-launch**

Run: `python gui.py`. App opens with your existing `config.yaml` and `rosters/my_raid.yaml` (still on disk, just untracked). Verify nothing changed visually.

Optional secondary check: rename `config.yaml` to `config.yaml.bak`, run `python gui.py` — should print "Created … from example." and load the example. Then restore your real `config.yaml.bak` to `config.yaml`.

- [ ] **Step 7: Commit**

```bash
git add config.example.yaml rosters/example.yaml modules/paths.py gui.py .gitignore
git commit -m "chore: gitignore personal config and roster, ship examples"
```

---

## Task 12: Remove `*.spec` from `.gitignore`

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Remove `*.spec` line from `.gitignore`**

In `.gitignore`, delete the line `*.spec`. The `Dark Rotation Manager.spec` file stays tracked (it's already in the repo and is part of the build).

- [ ] **Step 2: Verify spec is tracked**

```bash
git ls-files | grep spec
```
Expected: `Dark Rotation Manager.spec`

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: remove *.spec from gitignore"
```

---

## Task 13: Version bump and changelog

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Pick version**

Current latest tag: `v1.0.14`. This branch adds 2 user-visible features (live volume, phase-aware overlay label, tunable miss_seconds) and substantial internal refactor — recommend a minor bump to `v1.1.0`.

If user prefers patch-track only, use `v1.0.15`.

- [ ] **Step 2: Add changelog entry to README**

In `README.md`'s `## Changelog` section, prepend:
```markdown
### v1.1.0
- New: live volume slider — drag the Audio tab volume slider while the bot is running for instant changes (no Apply needed).
- New: overlay current-slot label now reads "DARK NOW" during the buff window and "UP NEXT" during the player window, instead of always saying "DARK NOW".
- New: tunable `miss_seconds` in the Rotation tab — controls how long a player has to throw before auto-miss fires.
- Cleanup: removed dead engine, roster, and audio API; centralized BASE_DIR and Lost Ark window-finder helpers; collapsed the engine state machine; split the GUI shell from runtime lifecycle (`BotController`) and event routing (`EventRouter`).
- Repo: `config.yaml` and `rosters/<your_roster>.yaml` are now gitignored — first run copies from `config.example.yaml` and `rosters/example.yaml`.
```

- [ ] **Step 3: Commit and tag locally (do NOT push)**

```bash
git add README.md
git commit -m "v1.1.0 - Cleanup audit, live volume, phase-aware overlay, tunable miss_seconds"
git tag v1.1.0
```

- [ ] **Step 4: Show user the branch state for final review**

```bash
git log --oneline main..chore/cleanup-audit
git status
```

Stop here. Wait for user to review and explicitly say "push it" before running `git push -u origin chore/cleanup-audit && git push --tags`.

---

## Self-Review Notes

Coverage check vs spec:
- Removals: ✓ (Task 1, 2)
- New modules: paths ✓ (Task 3), events ✓ (Task 4), styles ✓ (Task 5), bot_controller ✓ (Task 9), event_router ✓ (Task 9)
- State-machine merge: ✓ (Task 6, plus get_status `phase` key in same task)
- ConfigApp split: ✓ (Task 9)
- Live volume: ✓ (Task 7, re-routed through BotController in Task 9)
- Overlay phase label: ✓ (Task 8)
- `miss_seconds`: ✓ (Task 10)
- Gitignore + examples + bootstrap: ✓ (Task 11)
- `*.spec` removal: ✓ (Task 12)
- Version bump (no push): ✓ (Task 13)

Type/name consistency:
- `EngineEvent` members used consistently across engine.py, audio.py, gui_app.py, event_router.py.
- `RotationState` four-member enum used consistently in engine, gui_app, bot_controller.
- `BotController.set_audio_volume` matches signal `volume_changed(float)`.
- `phase` key in `get_status()` returned with values `"player_window"` / `"dark_window"` / `None` and consumed by overlay with the same strings.
