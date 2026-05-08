"""
roster_tab.py - Player list editor with add, remove, and reorder
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QLineEdit, QLabel
)
from modules.styles import (
    BUTTON_DANGER, BUTTON_NEUTRAL, BUTTON_PRIMARY_GREEN,
    LABEL_HINT, LINE_EDIT_DARK,
)


class RosterTab(QWidget):
    def __init__(self, players: list[str]):
        super().__init__()
        self._build_ui(players)

    def _build_ui(self, players: list[str]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header = QLabel("Drag rows or use ↑ ↓ to reorder. Changes take effect on Apply.")
        header.setStyleSheet(LABEL_HINT)
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setDragDropMode(QListWidget.InternalMove)
        self._list.setStyleSheet("""
            QListWidget {
                background: #111; border: 1px solid #2a2a2a; color: #fff;
                font-family: Consolas; font-size: 14px;
            }
            QListWidget::item { padding: 7px 10px; border-bottom: 1px solid #1a1a1a; }
            QListWidget::item:selected { background: #1a3a1a; }
        """)
        for p in players:
            self._list.addItem(p)
        layout.addWidget(self._list)

        # Per-row controls row (shown below selected item)
        btn_row = QHBoxLayout()
        up_btn = QPushButton("↑  Move Up")
        down_btn = QPushButton("↓  Move Down")
        del_btn = QPushButton("✕  Remove")
        for btn in (up_btn, down_btn):
            btn.setStyleSheet(BUTTON_NEUTRAL)
        del_btn.setStyleSheet(BUTTON_DANGER)
        up_btn.clicked.connect(lambda: self._move_selected(-1))
        down_btn.clicked.connect(lambda: self._move_selected(1))
        del_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        btn_row.addStretch()
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        # Add player row
        add_row = QHBoxLayout()
        self._add_input = QLineEdit()
        self._add_input.setPlaceholderText("+ Add player name...")
        self._add_input.setStyleSheet(LINE_EDIT_DARK)
        self._add_input.returnPressed.connect(self._add_player)
        add_btn = QPushButton("Add")
        add_btn.setStyleSheet(BUTTON_PRIMARY_GREEN)
        add_btn.clicked.connect(self._add_player)
        add_row.addWidget(self._add_input)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _add_player(self):
        name = self._add_input.text().strip()
        if name:
            self._list.addItem(name)
            self._add_input.clear()

    def _remove_selected(self):
        row = self._list.currentRow()
        if 0 <= row < self._list.count():
            self._list.takeItem(row)

    def _move_selected(self, direction: int):
        row = self._list.currentRow()
        new_row = row + direction
        if row < 0 or new_row < 0 or new_row >= self._list.count():
            return
        item = self._list.takeItem(row)
        self._list.insertItem(new_row, item)
        self._list.setCurrentRow(new_row)

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_players(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]
