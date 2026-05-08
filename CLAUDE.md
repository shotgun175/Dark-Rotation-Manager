# Dark Rotation Manager

Lost Ark dark grenade rotation tracker — always-on-top PyQt5 overlay with hotkey confirms, auto-detection via OpenCV, and TTS audio cues.

## Stack
- Python 3.11+, PyQt5, OpenCV, edge-tts
- PyInstaller for standalone `.exe` builds
- GitHub Actions auto-builds and releases on version tags

## Directory layout
- `modules/` — core logic (roster, tabs, etc.)
- `rosters/` — YAML roster files
- `assets/` — icons, audio
- `build/`, `dist/` — PyInstaller output (not committed)

## Git workflow
Commit format: `vX.X.X - Short description`  
Body: 1-2 lines explaining what changed and why.  
Versions tracked via git tags only — tags trigger the GitHub Actions release pipeline.  
Changelog maintained manually in README under `## Changelog`.  
Push commit and tags separately: `git push && git push --tags`

## Versioning (SemVer)
Format: `vMAJOR.MINOR.PATCH`. **Default to PATCH bumps.** Never bump MINOR or MAJOR without explicit confirmation — propose the bump, explain the reasoning, then wait for the go-ahead.

- **PATCH** (`v1.1.0` → `v1.1.1`) — bug fixes, internal cleanup, refactors, performance, docs. No new user-visible behavior.
- **MINOR** (`v1.1.1` → `v1.2.0`) — new user-visible feature (new tab, new hotkey action, new audio cue, new config field, etc.). Confirm before bumping.
- **MAJOR** (`v1.x.x` → `v2.0.0`) — breaking changes: config schema breaks, removed features, default behavior changes that surprise existing users. Confirm before bumping.

Not every PR is a release. Only create and push a tag when the user explicitly asks — the GitHub Actions release pipeline fires on the tag push, not the commit.

## Build
```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --icon=assets/icon.ico --name="Dark Rotation Manager" --clean --hidden-import=edge_tts --hidden-import=aiohttp gui.py
```
