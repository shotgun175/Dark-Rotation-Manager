"""
bot_controller.py - Owns the runtime lifecycle of every bot subsystem.

ConfigApp delegates start/stop/apply/volume here so the QMainWindow stays
focused on UI concerns.
"""

from modules.engine    import RotationEngine, RotationState
from modules.overlay   import OverlayWindow
from modules.hotkeys   import HotkeyManager
from modules.detection import DetectionEngine
from modules.audio     import AudioManager


class BotController:
    def __init__(self, on_engine_event):
        """on_engine_event(event_type, data) — called from engine bg thread."""
        self._on_engine_event = on_engine_event
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
