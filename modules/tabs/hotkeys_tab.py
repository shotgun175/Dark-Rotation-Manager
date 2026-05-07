"""
hotkeys_tab.py - Click-to-rebind hotkey configuration rows
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from modules.styles import LABEL_DIM

ACTIONS = [
    ("start_stop", "Start / Pause rotation",  "Start, pause, or resume the rotation"),
    ("confirm",    "Confirm dark thrown",      "Starts the 20–25s buff countdown"),
    ("missed",     "Dark missed",              "Counts miss, advances to next player"),
    ("reset",      "Reset rotation",           "Restart from player 1, clear all counts"),
]

_STYLE_NORMAL   = ("background: #111; color: #ffd700; border: 1px solid #444; "
                   "padding: 5px; font-family: Consolas; font-size: 14px; font-weight: bold;")
_STYLE_LISTEN   = ("background: #1a3a1a; color: #44ff88; border: 1px solid #44ff88; "
                   "padding: 5px; font-family: Consolas; font-size: 14px; font-weight: bold;")
_STYLE_CONFLICT = ("background: #3a1a1a; color: #ff4444; border: 1px solid #ff4444; "
                   "padding: 5px; font-family: Consolas; font-size: 14px; font-weight: bold;")

_ROW_NORMAL  = "background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 3px;"
_ROW_LISTEN  = "background: #1a2a1a; border: 1px solid #3a4a3a; border-radius: 3px;"


class HotkeysTab(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        self._bindings: dict[str, str] = dict(config.get("hotkeys", {}))
        self._listening_action: str | None = None
        self._badges: dict[str, QPushButton] = {}
        self._rows: dict[str, QFrame] = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        for action, label, hint in ACTIONS:
            row = QFrame()
            row.setStyleSheet(_ROW_NORMAL)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(12, 10, 12, 10)

            text_col = QVBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #fff; font-size: 14px; font-family: Consolas;")
            hint_lbl = QLabel(hint)
            hint_lbl.setStyleSheet(LABEL_DIM)
            text_col.addWidget(lbl)
            text_col.addWidget(hint_lbl)
            row_layout.addLayout(text_col)
            row_layout.addStretch()

            badge = QPushButton(self._bindings.get(action, "?").upper())
            badge.setStyleSheet(_STYLE_NORMAL)
            badge.setMinimumWidth(100)
            badge.clicked.connect(lambda _checked, a=action: self._start_listen(a))
            self._badges[action] = badge
            self._rows[action] = row
            row_layout.addWidget(badge)
            layout.addWidget(row)

        layout.addStretch()
        footer = QLabel("Click a key badge to rebind. Press Escape to cancel.")
        footer.setStyleSheet(LABEL_DIM)
        layout.addWidget(footer)

    def _start_listen(self, action: str):
        if self._listening_action:
            self._cancel_listen()
        self._listening_action = action
        self._badges[action].setText("Press a key...")
        self._badges[action].setStyleSheet(_STYLE_LISTEN)
        self._rows[action].setStyleSheet(_ROW_LISTEN)

    def _cancel_listen(self):
        if not self._listening_action:
            return
        action = self._listening_action
        self._listening_action = None
        self._badges[action].setText(self._bindings.get(action, "?").upper())
        self._rows[action].setStyleSheet(_ROW_NORMAL)
        self._refresh_conflict_styles()  # restore correct conflict/normal badge style

    def on_key_pressed(self, key_name: str):
        """Called by ConfigApp.keyPressEvent when this tab is in listening mode."""
        if not self._listening_action:
            return
        if key_name.lower() == "escape":
            self._cancel_listen()
            return
        action = self._listening_action
        self._listening_action = None
        self._bindings[action] = key_name.lower()
        self._badges[action].setText(key_name.upper())
        self._rows[action].setStyleSheet(_ROW_NORMAL)
        self._refresh_conflict_styles()

    def _refresh_conflict_styles(self):
        counts: dict[str, int] = {}
        for key in self._bindings.values():
            counts[key] = counts.get(key, 0) + 1
        for action, badge in self._badges.items():
            if self._listening_action == action:
                continue
            key = self._bindings.get(action, "")
            style = _STYLE_CONFLICT if counts.get(key, 0) > 1 else _STYLE_NORMAL
            badge.setStyleSheet(style)

    def get_bindings(self) -> dict[str, str]:
        return dict(self._bindings)

    def has_conflicts(self) -> bool:
        counts: dict[str, int] = {}
        for key in self._bindings.values():
            counts[key] = counts.get(key, 0) + 1
        return any(v > 1 for v in counts.values())
