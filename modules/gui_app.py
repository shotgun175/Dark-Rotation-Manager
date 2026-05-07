"""
gui_app.py - ConfigApp: main window, tabs, bottom bar, bot lifecycle, Apply
"""

import os
import yaml
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFontMetrics, QFont

from modules.tabs.roster_tab import RosterTab
from modules.tabs.rotation_tab import RotationTab
from modules.tabs.hotkeys_tab import HotkeysTab
from modules.tabs.overlay_tab import OverlayTab
from modules.tabs.audio_tab import AudioTab
from modules.roster import RosterManager

from modules.paths import get_base_dir
from modules.events import EngineEvent

BASE_DIR = get_base_dir()


class ConfigApp(QMainWindow):
    _engine_event_signal = pyqtSignal(str, object)

    def __init__(self, config_path: str):
        super().__init__()
        self._config_path = config_path
        self._config = self._load_config()

        self._bot_running = False
        self._engine = None
        self._hotkeys_mgr = None
        self._overlay_win = None
        self._preview_overlay = None
        self._detection_engine = None
        self._audio_mgr = None
        self._last_confirm_source = "hotkey"   # "hotkey" or "detection"

        self.setWindowTitle("Dark Rotation Manager")
        gui_pos = self._config.get("gui", {}).get("position", {})
        self.resize(800, 500)
        self.setMaximumSize(1050, 680)
        if gui_pos:
            self.move(gui_pos.get("x", 100), gui_pos.get("y", 100))
        self.setStyleSheet(
            "QMainWindow { background: #0d0d0d; }"
            "QWidget { background: #0d0d0d; color: #fff; font-family: Consolas; }"
        )

        self._build_ui()
        self._engine_event_signal.connect(self._on_engine_event_ui)

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status_bar)
        self._status_timer.start(300)

    # ------------------------------------------------------------------
    # Config I/O
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        with open(self._config_path) as f:
            return yaml.safe_load(f)

    def _save_config(self):
        with open(self._config_path, "w") as f:
            yaml.dump(self._config, f, default_flow_style=False)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        _tab_font_size = 12
        _tab_font = QFont("Consolas", _tab_font_size)
        _fm = QFontMetrics(_tab_font)
        # "Rotation" is the longest tab label; add 44px for horizontal padding
        _tab_min_w = _fm.horizontalAdvance("Rotation") + 44

        self._tabs = QTabWidget()
        self._tabs.tabBar().setExpanding(False)
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: #0d0d0d; }}
            QTabBar::tab {{
                background: #111; color: #aaa; padding: 8px 22px;
                min-width: {_tab_min_w}px;
                border: none; font-family: Consolas; font-size: {_tab_font_size}px;
            }}
            QTabBar::tab:selected {{
                color: #44ff88; border-bottom: 2px solid #44ff88; background: #0d0d0d;
            }}
        """)

        roster_file = self._config.get("rotation", {}).get("active_roster", "my_raid.yaml")
        roster_mgr = RosterManager(os.path.join(BASE_DIR, "rosters"))
        players = roster_mgr.load(roster_file)

        self._roster_tab   = RosterTab(players)
        self._rotation_tab = RotationTab(self._config)
        self._hotkeys_tab  = HotkeysTab(self._config)
        self._overlay_tab  = OverlayTab(self._config)
        self._overlay_tab.preview_requested.connect(self._handle_preview)
        self._overlay_tab.region_selector_requested.connect(self._handle_region_selector)

        self._audio_tab = AudioTab(self._config)
        self._audio_tab.test_requested.connect(self._handle_audio_test)

        self._tabs.addTab(self._roster_tab,   "Roster")
        self._tabs.addTab(self._rotation_tab, "Rotation")
        self._tabs.addTab(self._hotkeys_tab,  "Hotkeys")
        self._tabs.addTab(self._audio_tab,    "Audio")
        self._tabs.addTab(self._overlay_tab,  "Overlay")
        root.addWidget(self._tabs)
        root.addWidget(self._build_bottom_bar())

    def _build_bottom_bar(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(44)
        bar.setStyleSheet("background: #0a0a0a; border-top: 1px solid #222;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(8)

        self._status_dot  = QLabel("●")
        self._status_dot.setStyleSheet("color: #777; font-size: 16px;")
        self._status_text = QLabel("Bot not running")
        self._status_text.setStyleSheet("color: #999; font-size: 14px;")

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setStyleSheet(
            "color: #ccc; background: transparent; border: 1px solid #333; "
            "padding: 4px 14px; font-family: Consolas; font-size: 14px;"
        )
        self._apply_btn.clicked.connect(self._apply)

        self._launch_btn = QPushButton("▶  Launch")
        self._launch_btn.setStyleSheet(
            "background: #1a4a1a; color: #44ff88; border: none; "
            "padding: 5px 16px; font-family: Consolas; font-size: 14px; font-weight: bold;"
        )
        self._launch_btn.clicked.connect(self._toggle_bot)

        layout.addWidget(self._status_dot)
        layout.addWidget(self._status_text)
        layout.addStretch()
        layout.addWidget(self._apply_btn)
        layout.addWidget(self._launch_btn)
        return bar

    # ------------------------------------------------------------------
    # Hotkey capture delegation
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        if self._hotkeys_tab._listening_action:
            key_name = self._qt_key_to_name(event.key()) or event.text().lower()
            if key_name:
                self._hotkeys_tab.on_key_pressed(key_name)
        else:
            super().keyPressEvent(event)

    @staticmethod
    def _qt_key_to_name(qt_key: int) -> str:
        from PyQt5.QtCore import Qt
        mapping = {
            Qt.Key_F1: "f1",   Qt.Key_F2:  "f2",  Qt.Key_F3:  "f3",  Qt.Key_F4:  "f4",
            Qt.Key_F5: "f5",   Qt.Key_F6:  "f6",  Qt.Key_F7:  "f7",  Qt.Key_F8:  "f8",
            Qt.Key_F9: "f9",   Qt.Key_F10: "f10", Qt.Key_F11: "f11", Qt.Key_F12: "f12",
            Qt.Key_Escape: "escape",
        }
        return mapping.get(qt_key, "")

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def _apply(self):
        if self._hotkeys_tab.has_conflicts():
            self._status_text.setText("Fix duplicate hotkeys before applying")
            self._status_text.setStyleSheet("color: #ff4444; font-size: 14px;")
            return

        # Gather values from all tabs
        rot_vals = self._rotation_tab.get_values()
        ov_vals  = self._overlay_tab.get_values()
        hk_vals  = self._hotkeys_tab.get_bindings()
        players  = self._roster_tab.get_players()

        # Update in-memory config
        self._config.setdefault("rotation", {}).update(rot_vals)
        self._config["overlay"] = ov_vals
        self._config["hotkeys"] = hk_vals
        det_region = self._overlay_tab.get_detection_region()
        self._config.setdefault("detection", {}).update(det_region)
        self._config["detection"]["enabled"] = self._overlay_tab.get_detection_enabled()
        if self._detection_engine:
            self._detection_engine.update_config(self._config)

        audio_vals = self._audio_tab.get_values()
        self._config["audio"] = audio_vals
        if self._audio_mgr:
            players = self._roster_tab.get_players()
            self._audio_mgr.update_config(self._config, players)

        # Save to disk
        self._save_config()

        # Save roster to disk (load first to preserve the existing roster name)
        roster_file = self._config.get("rotation", {}).get("active_roster", "my_raid.yaml")
        roster_mgr = RosterManager(os.path.join(BASE_DIR, "rosters"))
        roster_mgr.load(roster_file)  # sets current_roster_name from the YAML
        roster_mgr.save(roster_file, roster_mgr.current_roster_name or roster_file, players)

        # Push to running bot if active
        if self._bot_running:
            if self._engine:
                self._engine.warn_secs      = rot_vals["warning_seconds"]
                self._engine.cooldown_secs  = rot_vals["dark_cooldown_seconds"]
                self._engine.max_throws     = rot_vals["max_throws_per_run"]
                self._engine.set_players(players)
            if self._hotkeys_mgr:
                for action, key in hk_vals.items():
                    self._hotkeys_mgr.update_key(action, key)
            if self._overlay_win:
                self._overlay_win.setWindowOpacity(ov_vals["opacity"])

        # Brief visual confirmation
        self._apply_btn.setEnabled(False)
        self._apply_btn.setText("Saved ✓")
        QTimer.singleShot(1200, self._restore_apply_btn)

    def _restore_apply_btn(self):
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("Apply")
        if not self._bot_running:
            self._status_text.setStyleSheet("color: #999; font-size: 14px;")

    # ------------------------------------------------------------------
    # Bot lifecycle
    # ------------------------------------------------------------------

    def _toggle_bot(self):
        if self._bot_running:
            self._stop_bot()
        else:
            self._start_bot()

    def _start_bot(self):
        from modules.engine  import RotationEngine
        from modules.overlay import OverlayWindow
        from modules.hotkeys import HotkeyManager

        self._config = self._load_config()
        roster_file = self._config.get("rotation", {}).get("active_roster", "my_raid.yaml")
        roster_mgr = RosterManager(os.path.join(BASE_DIR, "rosters"))
        players = roster_mgr.load(roster_file)

        self._engine = RotationEngine(self._config, self._on_engine_event)
        self._engine.set_players(players)

        self._overlay_win = OverlayWindow(
            self._config.get("overlay", {}),
            get_status_fn=self._engine.get_status,
            save_position_callback=self._on_overlay_moved,
            stop_callback=self._handle_overlay_stop,
        )
        self._overlay_win.start()

        self._hotkeys_mgr = HotkeyManager(
            self._config.get("hotkeys", {}),
            callbacks={
                "start_stop": self._hotkey_start_stop,
                "confirm":    self._hotkey_confirm,
                "missed":     self._hotkey_missed,
                "reset":      self._hotkey_reset,
            },
        )
        self._hotkeys_mgr.start()
        # Engine is NOT started here — user presses F8 when ready.
        # This gives pre-render time to finish so the first announce plays.

        # Start auto-detection if enabled (paused until engine starts via F8)
        if self._config.get("detection", {}).get("enabled", False):
            from modules.detection import DetectionEngine
            self._detection_engine = DetectionEngine(
                self._config,
                on_detected=self._on_grenade_detected,
            )
            self._detection_engine.start()
            self._detection_engine.pause()

        # Start audio manager and kick off pre-render in background
        if self._config.get("audio", {}).get("enabled", True):
            from modules.audio import AudioManager
            self._audio_mgr = AudioManager(self._config)
            self._audio_mgr.prerender(players)

        self._bot_running = True
        self._launch_btn.setText("■  Stop")
        self._launch_btn.setStyleSheet(
            "background: #4a1a1a; color: #ff4444; border: none; "
            "padding: 5px 16px; font-family: Consolas; font-size: 14px; font-weight: bold;"
        )
        self._status_dot.setStyleSheet("color: #ffaa00; font-size: 16px;")
        self._status_text.setText("Armed  —  press F8 to start")
        self._status_text.setStyleSheet("color: #ffaa00; font-size: 14px;")
        self.hide()

    def _stop_bot(self):
        if self._engine:
            self._engine.stop()
        if self._hotkeys_mgr:
            self._hotkeys_mgr.stop()
        if self._overlay_win:
            self._overlay_win.stop()
        if self._detection_engine:
            self._detection_engine.stop()
        if self._audio_mgr:
            self._audio_mgr.shutdown()

        self._engine            = None
        self._hotkeys_mgr       = None
        self._overlay_win       = None
        self._detection_engine  = None
        self._audio_mgr         = None
        self._bot_running       = False

        self._launch_btn.setText("▶  Launch")
        self._launch_btn.setStyleSheet(
            "background: #1a4a1a; color: #44ff88; border: none; "
            "padding: 5px 16px; font-family: Consolas; font-size: 14px; font-weight: bold;"
        )
        self._status_dot.setStyleSheet("color: #777; font-size: 16px;")
        self._status_text.setText("Bot not running")
        self._status_text.setStyleSheet("color: #999; font-size: 14px;")

    def _handle_overlay_stop(self):
        """Called from the overlay's stop button — tears down the bot and shows the GUI."""
        self._stop_bot()
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # Hotkey callbacks
    # ------------------------------------------------------------------

    def _hotkey_start_stop(self):
        if not self._engine:
            return
        from modules.engine import RotationState
        state = self._engine.state
        if state == RotationState.RUNNING:
            self._engine.pause()
            if self._detection_engine:
                self._detection_engine.pause()
        elif state == RotationState.PAUSED:
            dark_found, is_splendid = False, False
            if self._detection_engine:
                dark_found, is_splendid = self._detection_engine.check_now()
            self._engine.resume(dark_detected=dark_found, is_splendid=is_splendid)
            if self._detection_engine:
                if dark_found:
                    self._detection_engine.pause()
                else:
                    self._detection_engine.resume()
        else:
            # IDLE — first start after launch
            self._engine.start()
            if self._detection_engine:
                self._detection_engine.resume()

    def _hotkey_confirm(self):
        if self._engine:
            self._last_confirm_source = "hotkey"
            status = self._engine.get_status()
            player = status.get("current_player", "Unknown")
            self._engine.on_dark_detected(player, is_splendid=False)

    def _hotkey_missed(self):
        if self._engine:
            self._engine.on_dark_missed()

    def _hotkey_reset(self):
        if self._engine:
            self._engine.reset()
            if self._detection_engine:
                self._detection_engine.pause()

    # ------------------------------------------------------------------
    # Auto-detection callback
    # ------------------------------------------------------------------

    def _on_grenade_detected(self, is_splendid: bool):
        """Called from DetectionEngine background thread when icon is matched."""
        if not self._engine:
            return
        self._last_confirm_source = "detection"
        status = self._engine.get_status()
        player = status.get("current_player", "Unknown")
        kind = "Splendid Dark" if is_splendid else "Dark"
        print(f"[Detection] Auto-confirmed: {player} ({kind})")
        self._engine.on_dark_detected(player, is_splendid=is_splendid)

    # ------------------------------------------------------------------
    # Engine event handler
    # ------------------------------------------------------------------

    def _on_engine_event(self, event_type: str, data: dict):
        """Called from engine background thread — marshal to main thread via signal."""
        self._engine_event_signal.emit(event_type, data)

    def _on_engine_event_ui(self, event_type: str, data: dict):
        if event_type == EngineEvent.STATE_CHANGE:
            new_state = data.get("state", "")
            if new_state == "PAUSED":
                self._status_dot.setStyleSheet("color: #ffaa00; font-size: 16px;")
                self._status_text.setText("Paused  —  press F8 to resume")
                self._status_text.setStyleSheet("color: #ffaa00; font-size: 14px;")
            elif new_state == "RUNNING":
                self._status_dot.setStyleSheet("color: #44ff88; font-size: 16px;")
                self._status_text.setText("Running")
                self._status_text.setStyleSheet("color: #44ff88; font-size: 14px;")
            elif new_state == "IDLE":
                self._status_dot.setStyleSheet("color: #ffaa00; font-size: 16px;")
                self._status_text.setText("Armed  —  press F8 to start")
                self._status_text.setStyleSheet("color: #ffaa00; font-size: 14px;")
            return

        if event_type == EngineEvent.RESET and self._overlay_win:
            self._overlay_win.set_status_message("Rotation reset", "#88ccff")

        if event_type == EngineEvent.CONFIRMED and self._overlay_win:
            self._overlay_win.flash("#1a4a1a")
            self._overlay_win.set_status_message(f"OK {data['player']} confirmed", "#44ff88")
        elif event_type == EngineEvent.MISSED and self._overlay_win:
            self._overlay_win.flash("#4a1a1a")
            self._overlay_win.set_status_message(f"X {data['player']} missed", "#ff4444")
        elif event_type == EngineEvent.WARNING and self._overlay_win:
            self._overlay_win.set_status_message(
                f"Next up: {data['next']} in {data['seconds']}s", "#ffdd44"
            )
        elif event_type == EngineEvent.ROTATION_COMPLETE and self._overlay_win:
            self._overlay_win.set_status_message("Rotation complete", "#aaaaaa")
        elif event_type == EngineEvent.COOLDOWN_SKIP and self._overlay_win:
            self._overlay_win.set_status_message(f"{data['player']} on cooldown", "#ffaa00")

        # Pause detection during buff countdown, resume when next player window starts
        if self._detection_engine:
            if event_type == EngineEvent.CONFIRMED:
                self._detection_engine.pause()
            elif event_type in (EngineEvent.ANNOUNCE, EngineEvent.MISSED, EngineEvent.COOLDOWN_SKIP):
                self._detection_engine.resume()

        # Audio cues
        if self._audio_mgr:
            if event_type == EngineEvent.CONFIRMED:
                if self._last_confirm_source == "detection":
                    self._audio_mgr.play_chime()
                else:
                    self._audio_mgr.play_event(EngineEvent.CONFIRMED, data)
                self._last_confirm_source = "hotkey"   # reset
            else:
                self._audio_mgr.play_event(event_type, data)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Detection region selector
    # ------------------------------------------------------------------

    def _handle_audio_test(self):
        """Play a sample TTS line for the currently selected voice."""
        from modules.audio import AudioManager
        # Use a temporary manager with the current (unsaved) tab values
        test_config = dict(self._config)
        test_config["audio"] = self._audio_tab.get_values()
        if self._audio_mgr:
            self._audio_mgr.update_config(test_config)
            self._audio_mgr.play_test()
        else:
            tmp = AudioManager(test_config)
            tmp.play_test()

    def _handle_region_selector(self):
        from modules.region_selector import RegionSelectorWindow
        self._region_selector = RegionSelectorWindow()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.show()

    def _on_region_selected(self, rel_x: int, rel_y: int, w: int, h: int):
        """Fills spinboxes with drawn region — user still clicks Apply to save."""
        self._overlay_tab.set_detection_region(rel_x, rel_y, w, h)
        print(f"[Detection] Region drawn: rel_x={rel_x} rel_y={rel_y} w={w} h={h}")

    # ------------------------------------------------------------------
    # Overlay auto-save position
    # ------------------------------------------------------------------

    def _on_overlay_moved(self, x: int, y: int):
        """Called when user drags the live overlay — persists position immediately."""
        self._config.setdefault("overlay", {}).setdefault("position", {})
        self._config["overlay"]["position"] = {"x": x, "y": y}
        self._save_config()
        self._overlay_tab.set_position(x, y)

    # ------------------------------------------------------------------
    # Preview on screen
    # ------------------------------------------------------------------

    def _handle_preview(self):
        if self._bot_running and self._overlay_win:
            self._overlay_win.show()
            self._overlay_win.raise_()
            return

        if self._preview_overlay and self._preview_overlay.isVisible():
            self._preview_overlay.close()
            self._preview_overlay = None
            return

        ov_vals = self._overlay_tab.get_values()
        from modules.overlay import OverlayWindow

        def _on_preview_moved(x: int, y: int):
            self._overlay_tab.set_position(x, y)

        self._preview_overlay = OverlayWindow(
            ov_vals,
            save_position_callback=_on_preview_moved,
        )
        self._preview_overlay.set_status_message("← Drag to position", "#88ccff")
        self._preview_overlay.show()

    # ------------------------------------------------------------------
    # Status bar refresh
    # ------------------------------------------------------------------

    def _refresh_status_bar(self):
        if not self._bot_running or not self._engine:
            return
        status = self._engine.get_status()
        current = status.get("current_player", "")
        if current and current != "Nobody":
            self._status_text.setText(f"Running — {current}")

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._bot_running:
            self._stop_bot()
        if self._preview_overlay:
            self._preview_overlay.close()
        p = self.pos()
        self._config.setdefault("gui", {})["position"] = {"x": p.x(), "y": p.y()}
        self._save_config()
        event.accept()
