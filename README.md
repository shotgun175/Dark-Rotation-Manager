# Dark Rotation Manager

Tracks and announces the Lost Ark dark grenade rotation with an always-on-top
overlay and configurable hotkeys. Confirms throws manually via hotkey.

---

## Features

- Always-on-top overlay shows current player, next player, and countdown bar
- Two-phase timing: player window → dark buff countdown (20 s normal / 25 s splendid)
- Auto-skips players whose grenade is still on cooldown
- Tracks per-player throw count; stops the rotation when everyone hits the cap
- Configurable hotkeys (works while Lost Ark is in focus)
- PyQt5 GUI for editing roster, rotation settings, hotkeys, and overlay — live while the bot is running
- Overlay position saves automatically when dragged; restores on next launch
- GUI window position also saves and restores on next launch
- Optional OpenCV auto-detection: scans boss debuff bar for Dark / Splendid Dark Grenade icon and auto-confirms with correct timer (20s / 25s)
- Detection region configurable via manual spinboxes or drag-to-draw tool in the Overlay tab
- **Pause / Resume (F8):** freeze the rotation mid-fight; on resume, scans for an active dark and either restarts the buff countdown or advances to the next player
- **Reset (F11):** clears all throw counts and returns to player 1 in an armed-but-not-started state, without closing the overlay
- TTS audio cues for all key events including reset confirmation
- `Dark Rotation Manager.exe` ships with the Splendid Dark Grenade as its icon

---

## Requirements

- Windows 10 or 11
- Python 3.11+ — https://www.python.org/downloads/

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/Dark-Rotation-Manager.git
cd Dark-Rotation-Manager
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the GUI

```bash
python gui.py
```

Edit your roster, hotkeys, and settings from the GUI. Click **Apply** to save,
then **▶ Launch** to arm the bot (overlay appears, audio pre-renders), then press **F8** to start the rotation.

---

## Hotkeys (defaults)

| Key | Action |
|-----|--------|
| F8  | Start → Pause → Resume rotation |
| F9  | Confirm dark thrown (starts 20–25 s buff countdown) |
| F10 | Dark missed (counts toward throw limit, advances to next player) |
| F11 | Reset rotation to player 1 (armed but not started) |

Rebind any key in the GUI under the **Hotkeys** tab, or directly in `config.yaml`.

---

## How it works

1. Click **▶ Launch** — the GUI hides, the overlay appears, and audio clips are pre-rendered in the background
2. Press **F8** when you're ready — the rotation starts and the first player is announced
3. **Phase 1 — Player window (20 s):**
   - Press **F9** when the player throws their dark grenade
   - If no confirm within 20 s, the bot fires a miss event automatically
4. **Phase 2 — Dark buff countdown:**
   - After a confirm, the buff timer runs (20 s normal / 25 s splendid)
   - A warning fires near the end, naming the next player
   - When the buff expires, the next player's window begins
5. Press **F10** if a player misses — counts the miss and advances to next player
6. Players on cooldown are skipped automatically
7. Once every player hits `max_throws_per_run`, the rotation ends
8. **Pause / Resume — F8 (while running):** freezes the overlay and stops the timer. On resume, the bot scans for an active dark grenade — if found, restarts the buff countdown; if not, advances to the next player
9. **Reset — F11:** clears all throw counts, returns to player 1, and returns to the armed state. Press **F8** to start again. The overlay stays visible; a TTS cue confirms the reset
10. **Stop — overlay ■ button:** tears down the bot entirely and restores the GUI

---

## Assumptions, scope, and open questions

This tool watches the screen and drives timers and hotkeys — it does **not** read
game memory or any Lost Ark API. The points below are what it assumes about your
setup, verified against the current code.

### Confirmed assumptions

- **English game client.** The app finds the game by looking for a visible window
  whose title contains `LOST ARK` (case-insensitive) — `LOSTARK_WINDOW_TITLE` in
  `modules/paths.py`. A localized client with a translated window title won't be
  found, so auto-detection and window-relative positioning won't work on it.
- **Window position and monitor are handled automatically.** The detection region
  is anchored to the Lost Ark window's client top-left and resolved to absolute
  screen coordinates, so the game can sit on any monitor, anywhere, windowed or
  borderless — detection follows it.
- **The detection region and icon templates assume a fixed resolution / UI scale.**
  The default scan region is a pixel rectangle offset from the window's top-left
  (`rel_x: 875, rel_y: 325, width: 456, height: 46`), and the bundled debuff
  templates are fixed **28×28 px** images matched with OpenCV at a `0.75`
  confidence threshold. Matching is **not** scale-invariant: the template is only
  shrunk if it is larger than the scan region, and is never enlarged. If your
  in-game resolution or UI scale differs from these capture defaults, the debuff
  bar won't line up with the default region and the on-screen icon may not match
  the template. Fix it by redrawing the region with the drag-to-draw tool in the
  **Overlay** tab (or by adjusting the spinboxes / threshold in `config.yaml`).
- **Hotkeys are global.** They are registered system-wide (via the `keyboard`
  library), so they fire while Lost Ark has focus.

### Open questions

- **Exclusive fullscreen vs. borderless.** Capture uses `mss` (a desktop screen
  grab). Borderless windowed is the safe choice; exclusive-fullscreen capture
  behaviour has not been verified.
- **Multiple game windows.** If more than one visible window matches `LOST ARK`,
  the first one Windows enumerates is used — multi-client setups are unhandled.
- **Reference resolution.** The exact resolution / UI scale that the default region
  and templates were captured at isn't recorded; treat the defaults as a starting
  point and redraw the region for your own setup.

### Scope (out)

- **No auto-update.** The launch check only *notifies* you when a newer release
  exists; it never downloads or replaces the executable (the onefile build is
  unsigned).
- **No game integration.** No memory reading, packet inspection, or input
  automation into the game — it only reads the debuff icon from the screen and
  listens for your hotkeys.
- **Windows only.** Window discovery and global hotkeys rely on Windows APIs.

> Not affiliated with, endorsed by, or associated with Smilegate or Amazon Games.
> "Lost Ark" is the property of its respective owners.

---

## Config reference

```yaml
rotation:
  warning_seconds: 5            # warning callout N seconds before next window
  dark_cooldown_seconds: 30     # skip players whose grenade is still on cooldown
  max_throws_per_run: 3         # per-player throw cap; rotation ends when all reach it
  active_roster: example.yaml

hotkeys:
  start_stop: f8
  confirm: f9
  missed: f10
  reset: f11

overlay:
  position: {x: 0, y: 0}       # auto-saved when you drag the overlay
  width: 320
  height: 230
  opacity: 0.88
  font_size: 16

gui:
  position: {x: 100, y: 100}   # auto-saved when you move the GUI window
```

---

## Building a standalone .exe

To create a double-clickable executable (no terminal, no Python required):

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --icon=assets/icon.ico --name="Dark Rotation Manager" --clean --hidden-import=edge_tts --hidden-import=aiohttp gui.py
```

Output: `dist/Dark Rotation Manager.exe` — run it directly from the `dist/` folder. Re-run this command any time you update the code.
`config.yaml`, `rosters/`, and `assets/` are read from the project root automatically.

---

## Multiple Rosters

Create additional `.yaml` files in the `rosters/` folder using the same format.
Change `active_roster` in `config.yaml` (or via the GUI) to switch between them.

---

## License

MIT

---

## Changelog

### v1.2.0 - Update notifications + crash-safe saves
- **New: update check.** On launch the app quietly checks GitHub for a newer release and, if one exists, shows a small "Update available: vX.Y.Z" note in the bottom-right of the GUI. It never downloads or installs anything itself, and if you're offline it simply does nothing
- **Reliability: crash-safe saves.** Your `config.yaml` and roster files are now written atomically — if the app or PC dies mid-save, the existing file is left intact instead of being corrupted. Nothing changes about how saving works day-to-day
- **Under the hood:** added an automated test suite for the rotation timing and state logic, plus a CI check that runs it on every change. No effect on the app itself

### v1.1.3 - Diagnostic log file
- **New:** the app now writes a rotating log file to a `logs/` folder next to the `.exe`. Since the released build runs with no console window, this is where startup errors, detection problems, and audio failures get recorded — attach it when reporting an issue
- Older builds sent those messages to a console that the packaged `.exe` threw away, so they were invisible. Nothing about how the app runs day-to-day changes

### v1.1.2 - Standalone .exe + version label
- **Fix:** the released `.exe` now ships with everything it needs (config example, default roster, icon, OpenCV detection templates, chime sound) bundled inside. Previous releases shipped just the binary and crashed on launch in any folder that didn't already have those files
- **New:** the current version number is shown in the bottom-right corner of the GUI, next to the Apply button
- First-run behavior unchanged: a fresh `config.yaml` and `rosters/example.yaml` are created next to the `.exe` on the first launch

### v1.1.1 - Auto-detect on by default
- **Default change:** "Enable grenade auto-detect" is now on by default for fresh installs. Existing `config.yaml` files are not modified — your current setting is preserved
- Detection still no-ops gracefully if OpenCV templates are missing or Lost Ark isn't running, so the default-on is safe

### v1.1.0 - Cleanup audit, live volume, phase-aware overlay, tunable miss_seconds
- **New: live volume slider** — drag the Audio tab volume slider while the bot is running for instant changes (no Apply needed)
- **New: overlay current-slot label** now reads "DARK NOW" during the buff window and "UP NEXT" during the player window, instead of always saying "DARK NOW"
- **New: tunable `miss_seconds`** in the Rotation tab — controls how long a player has to throw before auto-miss fires (was hard-coded to 20s)
- **Polish:** overlay state header now reads "▶ DARK ROTATION RUNNING" / "● ARMED" / "⏸ PAUSED" with matching colors, instead of the raw internal state name. Confirm/missed status messages use ✓/✗ instead of OK/X prefixes.
- **Cleanup:** removed dead engine, roster, and audio API; centralized BASE_DIR and Lost Ark window-finder helpers; collapsed the engine state machine into explicit phase substates; split the GUI shell from runtime lifecycle (`BotController`) and event routing (`EventRouter`)
- **Repo:** `config.yaml` and `rosters/<your_roster>.yaml` are now gitignored — first run copies from `config.example.yaml` and `rosters/example.yaml`
- **Repo:** `Dark Rotation Manager.spec` is now tracked (was previously gitignored despite being needed for builds)

### v1.0.14 - Pause, reset, and path fixes
- **F8 pause / resume:** pressing F8 while running now pauses the rotation (overlay shows ⏸ PAUSED, bar freezes). Press F8 again to resume — the bot scans for an active dark grenade and either restarts the buff countdown or advances to the next player
- **F11 reset:** clears all throw counts and returns to player 1 in the armed-but-not-started state without closing the overlay. TTS announces "Dark rotation reset" as confirmation
- **Overlay stop button** is now the only way to fully shut down and restore the GUI
- **Audio:** new "Dark rotation reset" TTS cue (toggleable in Audio tab)
- **Path fix:** exe running from `dist/` now correctly resolves `config.yaml`, `rosters/`, and `assets/` from the project root

### v1.0.13 - Rename to Dark Rotation Manager
- Project renamed from **Dark Rotation Bot** to **Dark Rotation Manager**
- Exe and window title updated to match

### v1.0.12 - Audio cue system, GUI hide on launch, overlay stop button
- **Audio cue system:** TTS voice callouts via Microsoft Edge neural voices (Andrew / Jenny selectable in Audio tab). Announces the current player's name, warns the next player, confirms throws, and plays an optional chime on auto-detection
- **Audio tab:** New GUI tab with master enable toggle, per-cue checkboxes (announce, warning, confirmed, rotation complete, chime), voice selector, volume slider, and Test Voice button. All options gray out visually when audio is disabled
- **Phase 1 warning:** `[Player], get ready` now fires 5 seconds before a player's window closes - even if no dark was confirmed - so the next player always gets a heads-up
- **Launch / F8 split:** Clicking **Launch** arms the bot (overlay shows, audio pre-renders) but does not start the timer. Press **F8** when ready - audio clips are guaranteed loaded by then, so the first announce always plays
- **GUI hides on Launch:** Config window disappears when the bot is armed, freeing screen space and preventing accidental roster resets. A stop button in the top-right of the overlay tears down the bot and restores the GUI
- **Tab reorder:** Audio tab moved before Overlay tab
- **Removed:** Dark missed TTS cue (F10 advances the rotation silently)
- **Cleanup:** Removed legacy `main.py` headless entry point; removed unused `mutagen` dependency

### v1.0.11 - Throw counts, spam fix, taskbar icon
- **Throw counts on overlay:** player names now show their throw count inline (e.g. `Valslayer 1/3`, `Mabi 0/3`)
- **Spam protection:** duplicate confirms are ignored while the dark buff is active - throw count can no longer exceed the cap
- **Window icon:** title bar and taskbar now show the grenade icon at runtime
- **Taskbar fix:** app registers its own Windows App User Model ID so it gets a dedicated taskbar button instead of grouping under Python

### v1.0.1 - UI overhaul, detection improvements, buff display fix
- **Overlay tab redesign:** single scrollable left column replaces the fixed right panel - controls never clip or stretch as the window is resized
- **Appearance preview moved inline:** sits next to the Position/Size spinboxes; Region preview sits next to the detection region controls
- **Window resize cap:** maximum window size capped at 1050x680 to prevent excessive stretching
- **Text contrast pass:** all gray text lifted across every tab
- **Font size pass:** UI-wide bump (9->11px, 11->13px, 13->14px); spinboxes now render at 14px
- **Auto-detection card:** checkbox is wrapped in a styled card with a gold indicator when enabled - much easier to notice and toggle
- **Buff display fix:** DARK NOW stays on the thrower for the full 20/25s buff countdown; switches to next player only when buff expires
- **Auto-detection:** Optional OpenCV-based grenade detection scans the boss debuff bar automatically - detects Dark (20s) and Splendid Dark (25s) automatically
- **Visual region selector:** drag-to-draw tool covering all monitors, relative to Lost Ark window
- **Renamed executable:** `gui.exe` -> `Dark Timer.exe`

### Initial release
- PyQt5 tabbed config GUI (Roster, Rotation, Hotkeys, Overlay)
- Always-on-top overlay HUD with countdown bar
- Live Apply: push config changes to running bot without restart
- Overlay and GUI window positions auto-save on drag/move
- Hotkey rebinding via click-to-capture UI
- Standalone `Dark Timer.exe` build
