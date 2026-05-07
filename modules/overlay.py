"""
overlay.py - Always-on-top countdown and rotation display (PyQt5)
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QFont

BG_COLOR      = "#0d0d0d"
TEXT_SECONDARY = "#aaaaaa"
TEXT_CURRENT   = "#ffd700"
TEXT_NEXT      = "#88ccff"
TEXT_PRIMARY   = "#ffffff"
BAR_BG         = "#333333"
BAR_FG         = "#ffd700"
BAR_WARN       = "#ff8800"
BAR_CRITICAL   = "#ff4444"


class OverlayWindow(QWidget):
    def __init__(self, config: dict, get_status_fn=None, save_position_callback=None,
                 stop_callback=None):
        super().__init__()
        self.config = config
        self.get_status = get_status_fn
        self.save_position_callback = save_position_callback
        self.stop_callback = stop_callback
        self.font_size = config.get("font_size", 16)

        pos = config.get("position", {"x": 0, "y": 0})
        self.setGeometry(pos.get("x", 0), pos.get("y", 0),
                         config.get("width", 320), config.get("height", 230))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setWindowOpacity(config.get("opacity", 0.88))
        self.setStyleSheet(f"background-color: {BG_COLOR};")

        self._drag_pos: QPoint | None = None
        self._last_bar_ratio: float = 0.0
        self._update_timer: QTimer | None = None

        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._clear_flash)

        self._build_ui()

        if self.get_status:
            self._update_timer = QTimer(self)
            self._update_timer.timeout.connect(self._update)
            self._update_timer.start(150)

    def _build_ui(self):
        fs = self.font_size
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(2)

        # Header row: state label left, stop button right
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        self._lbl_state = self._label("IDLE", fs - 4, TEXT_SECONDARY)
        header_row.addWidget(self._lbl_state)
        header_row.addStretch()
        self._stop_btn = QPushButton("■")
        self._stop_btn.setFixedSize(22, 22)
        self._stop_btn.setToolTip("Stop bot")
        self._stop_btn.setStyleSheet(
            "QPushButton { color: #ff4444; background: transparent; border: 1px solid #444;"
            " font-size: 11px; font-family: Consolas; border-radius: 3px; }"
            "QPushButton:hover { background: #3a1a1a; border-color: #ff4444; }"
        )
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        self._stop_btn.setVisible(self.stop_callback is not None)
        header_row.addWidget(self._stop_btn)
        layout.addLayout(header_row)

        self._lbl_current_label = self._label("DARK NOW", fs - 4, TEXT_SECONDARY)
        layout.addWidget(self._lbl_current_label)

        self._lbl_current = self._label("—", fs + 4, TEXT_CURRENT, bold=True)
        layout.addWidget(self._lbl_current)

        self._lbl_next_label = self._label("NEXT", fs - 4, TEXT_SECONDARY)
        layout.addWidget(self._lbl_next_label)

        self._lbl_next = self._label("—", fs, TEXT_NEXT)
        layout.addWidget(self._lbl_next)

        layout.addSpacing(4)

        self._bar = QFrame(self)
        self._bar.setFixedHeight(18)
        self._bar.setStyleSheet(f"background-color: {BAR_BG}; border-radius: 2px;")
        self._bar_fill = QFrame(self._bar)
        self._bar_fill.setFixedHeight(18)
        self._bar_fill.move(0, 0)
        self._bar_fill.setFixedWidth(0)
        self._bar_fill.setStyleSheet(f"background-color: {BAR_FG}; border-radius: 2px;")
        layout.addWidget(self._bar)

        self._lbl_timer = self._label("0.0s", fs - 2, TEXT_PRIMARY)
        layout.addWidget(self._lbl_timer)

        self._lbl_status = self._label("", fs - 3, TEXT_SECONDARY)
        layout.addWidget(self._lbl_status)

        layout.addStretch()

    def _label(self, text: str, size: int, color: str, bold: bool = False) -> QLabel:
        lbl = QLabel(text)
        font = QFont("Consolas", size)
        font.setBold(bold)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color: {color}; background-color: transparent;")
        return lbl

    # ------------------------------------------------------------------
    # Public API (matches old tkinter interface)
    # ------------------------------------------------------------------

    def _on_stop_clicked(self):
        if self.stop_callback:
            self.stop_callback()

    def start(self):
        self.show()

    def stop(self):
        if self._update_timer is not None:
            self._update_timer.stop()
        self.hide()

    def flash(self, color: str, duration: float = 0.6):
        self.setStyleSheet(f"background-color: {color};")
        self._flash_timer.start(int(duration * 1000))

    def set_status_message(self, msg: str, color: str = "#44ff88"):
        self._lbl_status.setText(msg)
        self._lbl_status.setStyleSheet(f"color: {color};")

    # ------------------------------------------------------------------
    # Internal rendering
    # ------------------------------------------------------------------

    def _update(self):
        if not self.get_status:
            return
        try:
            self._render(self.get_status())
        except Exception as e:
            print(f"[Overlay] Render error: {e}")

    def _render(self, status: dict):
        state = status.get("state", "IDLE")
        if state == "PAUSED":
            self._lbl_state.setText("⏸ PAUSED")
            self._lbl_state.setStyleSheet("color: #ffaa00; background-color: transparent;")
        else:
            self._lbl_state.setText(state)
            self._lbl_state.setStyleSheet(f"color: {TEXT_SECONDARY}; background-color: transparent;")

        phase = status.get("phase")
        if phase == "dark_window":
            self._lbl_current_label.setText("DARK NOW")
        elif phase == "player_window":
            self._lbl_current_label.setText("UP NEXT")
        # else: leave the current text untouched (idle/paused preserves whichever phase was last shown)

        current = status.get("current_player", "—")
        current_count = status.get("current_count", "")
        self._lbl_current.setText(f"{current}  {current_count}" if current_count else current)

        next_p = status.get("next_player", "—")
        next_count = status.get("next_count", "")
        self._lbl_next.setText(f"{next_p}  {next_count}" if next_count else next_p)
        remaining = status.get("remaining_seconds", 0.0)
        duration = status.get("window_duration", 20)
        self._lbl_timer.setText(f"{remaining:.1f}s")

        ratio = max(0.0, min(1.0, remaining / max(duration, 1)))
        self._last_bar_ratio = ratio
        fill_w = int(self._bar.width() * ratio)
        self._bar_fill.setFixedWidth(max(0, fill_w))
        bar_color = BAR_FG if ratio > 0.35 else (BAR_WARN if ratio > 0.15 else BAR_CRITICAL)
        self._bar_fill.setStyleSheet(f"background-color: {bar_color}; border-radius: 2px;")

    def _clear_flash(self):
        self.setStyleSheet(f"background-color: {BG_COLOR};")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fill_w = int(self._bar.width() * getattr(self, "_last_bar_ratio", 0.0))
        self._bar_fill.setFixedWidth(max(0, fill_w))

    # ------------------------------------------------------------------
    # Drag to move
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            if self.save_position_callback:
                p = self.pos()
                self.save_position_callback(p.x(), p.y())
