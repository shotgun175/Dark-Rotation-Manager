"""
gui_app.py - ConfigApp: main window, tabs, bottom bar, Apply.

Runtime concerns (engine/hotkeys/overlay/detection/audio) live in
BotController. Engine event dispatch lives in EventRouter. ConfigApp is
a UI shell that builds tabs and delegates.
"""

import logging
import os
import yaml
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLabel, QFrame
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFontMetrics, QFont

from modules.tabs.roster_tab   import RosterTab
from modules.tabs.rotation_tab import RotationTab
from modules.tabs.hotkeys_tab  import HotkeysTab
from modules.tabs.overlay_tab  import OverlayTab
from modules.tabs.audio_tab    import AudioTab
from modules.roster            import RosterManager
from modules.bot_controller    import BotController
from modules.event_router      import EventRouter
from modules.styles            import BUTTON_LAUNCH_GREEN, BUTTON_LAUNCH_RED
from modules.paths             import get_base_dir, atomic_write_text
from modules.update_check       import check_for_update_async, GITHUB_RELEASES_URL
from modules.version           import __version__

logger = logging.getLogger(__name__)

BASE_DIR = get_base_dir()


class ConfigApp(QMainWindow):
    _engine_event_signal = pyqtSignal(object, object)
    _update_available_signal = pyqtSignal(str)

    def __init__(self, config_path: str):
        super().__init__()
        self._config_path = config_path
        self._config = self._load_config()

        self._controller = BotController(self._on_engine_event)
        self._router = EventRouter(self._controller)
        self._preview_overlay = None

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

        # Non-blocking "update available" check (daemon thread -> signal).
        self._update_available_signal.connect(self._show_update_available)
        check_for_update_async(self._update_available_signal.emit)

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_status_bar)
        self._status_timer.start(300)

    # ------------------------------------------------------------------
    # Config I/O
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        with open(self._config_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _save_config(self):
        atomic_write_text(
            self._config_path,
            yaml.dump(self._config, default_flow_style=False, allow_unicode=True),
        )

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

        roster_file = self._config.get("rotation", {}).get("active_roster", "example.yaml")
        self._roster_mgr = RosterManager(os.path.join(BASE_DIR, "rosters"))
        players = self._roster_mgr.load(roster_file)

        self._roster_tab   = RosterTab(players)
        self._rotation_tab = RotationTab(self._config)
        self._hotkeys_tab  = HotkeysTab(self._config)
        self._overlay_tab  = OverlayTab(self._config)
        self._overlay_tab.preview_requested.connect(self._handle_preview)
        self._overlay_tab.region_selector_requested.connect(self._handle_region_selector)

        self._audio_tab = AudioTab(self._config)
        self._audio_tab.test_requested.connect(self._handle_audio_test)
        self._audio_tab.volume_changed.connect(self._handle_volume_changed)

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
        self._launch_btn.setStyleSheet(BUTTON_LAUNCH_GREEN)
        self._launch_btn.clicked.connect(self._toggle_bot)

        version_label = QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: #555; font-size: 12px;")

        hub_link = QLabel(
            '<a href="https://shotgun175.github.io/" '
            'style="color:#f0b94d;text-decoration:none;">Part of Lost Ark Tools ↗</a>'
        )
        hub_link.setStyleSheet("font-size: 12px;")
        hub_link.setOpenExternalLinks(True)
        hub_link.setToolTip("Open the Lost Ark Tools hub in your browser")

        self._update_label = QLabel("")
        self._update_label.setStyleSheet("color: #ffcc44; font-size: 12px;")
        self._update_label.setOpenExternalLinks(True)
        self._update_label.setToolTip("A newer release is available on GitHub.")
        self._update_label.setVisible(False)

        layout.addWidget(self._status_dot)
        layout.addWidget(self._status_text)
        layout.addStretch()
        layout.addWidget(hub_link)
        layout.addWidget(self._update_label)
        layout.addWidget(version_label)
        layout.addWidget(self._apply_btn)
        layout.addWidget(self._launch_btn)
        return bar

    def _show_update_available(self, tag: str):
        """Slot for _update_available_signal — reveal the clickable banner.

        The banner links to that release's GitHub page (where the .exe asset
        lives); the click is handled by the label via setOpenExternalLinks.
        """
        url = f"{GITHUB_RELEASES_URL}/tag/{tag}"
        self._update_label.setText(
            f'<a href="{url}" style="color:#ffcc44;text-decoration:none;">'
            f'Update available: {tag} ↗</a>'
        )
        self._update_label.setToolTip(f"Click to open the {tag} release on GitHub")
        self._update_label.setVisible(True)

    def _set_status_text(self, text: str, color: str):
        self._status_dot.setStyleSheet(f"color: {color}; font-size: 16px;")
        self._status_text.setText(text)
        self._status_text.setStyleSheet(f"color: {color}; font-size: 14px;")

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
            self._set_status_text("Fix duplicate hotkeys before applying", "#ff4444")
            return

        rot_vals = self._rotation_tab.get_values()
        ov_vals  = self._overlay_tab.get_values()
        hk_vals  = self._hotkeys_tab.get_bindings()
        players  = self._roster_tab.get_players()

        self._config.setdefault("rotation", {}).update(rot_vals)
        self._config["overlay"] = ov_vals
        self._config["hotkeys"] = hk_vals
        det_region = self._overlay_tab.get_detection_region()
        self._config.setdefault("detection", {}).update(det_region)
        self._config["detection"]["enabled"] = self._overlay_tab.get_detection_enabled()
        self._config["audio"] = self._audio_tab.get_values()

        self._save_config()

        roster_file = self._config.get("rotation", {}).get("active_roster", "example.yaml")
        self._roster_mgr.save(
            roster_file,
            self._roster_mgr.current_roster_name or roster_file,
            players,
        )

        if self._controller.is_running:
            self._controller.apply(self._config, players)

        self._apply_btn.setEnabled(False)
        self._apply_btn.setText("Saved ✓")
        QTimer.singleShot(1200, self._restore_apply_btn)

    def _restore_apply_btn(self):
        self._apply_btn.setEnabled(True)
        self._apply_btn.setText("Apply")
        if not self._controller.is_running:
            self._status_text.setStyleSheet("color: #999; font-size: 14px;")

    # ------------------------------------------------------------------
    # Bot lifecycle (thin wrappers around BotController)
    # ------------------------------------------------------------------

    def _toggle_bot(self):
        if self._controller.is_running:
            self._stop_bot()
        else:
            self._start_bot()

    def _start_bot(self):
        self._config = self._load_config()
        roster_file = self._config.get("rotation", {}).get("active_roster", "example.yaml")
        players = self._roster_mgr.load(roster_file)

        self._controller.start(
            self._config, players,
            overlay_save_position_cb=self._on_overlay_moved,
            overlay_stop_cb=self._handle_overlay_stop,
        )

        self._launch_btn.setText("■  Stop")
        self._launch_btn.setStyleSheet(BUTTON_LAUNCH_RED)
        self._set_status_text("Armed  —  press F8 to start", "#ffaa00")
        self.hide()

    def _stop_bot(self):
        self._controller.stop()
        self._launch_btn.setText("▶  Launch")
        self._launch_btn.setStyleSheet(BUTTON_LAUNCH_GREEN)
        self._set_status_text("Bot not running", "#999")

    def _handle_overlay_stop(self):
        """Called from the overlay's stop button — tears down the bot and shows the GUI."""
        self._stop_bot()
        self.show()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # Engine event handler (signal marshaller + router dispatch)
    # ------------------------------------------------------------------

    def _on_engine_event(self, event_type, data: dict):
        """Called from engine background thread — marshal to main thread via signal."""
        self._engine_event_signal.emit(event_type, data)

    def _on_engine_event_ui(self, event_type, data: dict):
        self._router.handle(event_type, data, self._set_status_text)

    # ------------------------------------------------------------------
    # Audio tab callbacks
    # ------------------------------------------------------------------

    def _handle_volume_changed(self, volume: float):
        self._controller.set_audio_volume(volume)

    def _handle_audio_test(self):
        """Play a sample TTS line for the currently selected voice."""
        from modules.audio import AudioManager
        test_config = dict(self._config)
        test_config["audio"] = self._audio_tab.get_values()
        if self._controller.audio:
            self._controller.audio.update_config(test_config)
            self._controller.audio.play_test()
        else:
            tmp = AudioManager(test_config)
            tmp.play_test()

    # ------------------------------------------------------------------
    # Detection region selector
    # ------------------------------------------------------------------

    def _handle_region_selector(self):
        from modules.region_selector import RegionSelectorWindow
        self._region_selector = RegionSelectorWindow()
        self._region_selector.region_selected.connect(self._on_region_selected)
        self._region_selector.show()

    def _on_region_selected(self, rel_x: int, rel_y: int, w: int, h: int):
        """Fills spinboxes with drawn region — user still clicks Apply to save."""
        self._overlay_tab.set_detection_region(rel_x, rel_y, w, h)
        logger.info(f"[Detection] Region drawn: rel_x={rel_x} rel_y={rel_y} w={w} h={h}")

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
        if self._controller.is_running and self._controller.overlay:
            self._controller.overlay.show()
            self._controller.overlay.raise_()
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
        if not self._controller.is_running or not self._controller.engine:
            return
        status = self._controller.engine.get_status()
        current = status.get("current_player", "")
        if current and current != "Nobody":
            self._status_text.setText(f"Running — {current}")

    # ------------------------------------------------------------------
    # Window close
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._controller.is_running:
            self._stop_bot()
        if self._preview_overlay:
            self._preview_overlay.close()
        p = self.pos()
        self._config.setdefault("gui", {})["position"] = {"x": p.x(), "y": p.y()}
        self._save_config()
        event.accept()
