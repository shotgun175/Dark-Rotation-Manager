"""
rotation_tab.py - Rotation timing settings (max throws, cooldown, warning)
"""

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox
from modules.styles import INPUT_DARK, LABEL_HINT


class RotationTab(QWidget):
    def __init__(self, config: dict):
        super().__init__()
        rot = config.get("rotation", {})
        self._build_ui(
            max_throws=rot.get("max_throws_per_run", 3),
            cooldown=rot.get("dark_cooldown_seconds", 30),
            warning=rot.get("warning_seconds", 5),
        )

    def _build_ui(self, max_throws: int, cooldown: int, warning: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        # Minimum 1 for all timing/count fields — the engine does not support zero values
        # (zero cooldown would skip all players; zero throws would end rotation immediately).
        self._max_throws = self._field(
            layout, "MAX THROWS PER RUN", max_throws, 1, 99,
            "How many darks each player can throw before being retired. "
            "Rotation ends when all players hit this cap.",
        )
        self._cooldown = self._field(
            layout, "DARK COOLDOWN (seconds)", cooldown, 1, 300,
            "Players who threw within this window are skipped when it's their turn.",
        )
        self._warning = self._field(
            layout, "WARNING (seconds before next window)", warning, 1, 60,
            "How early to fire the warning callout before the next player's window.",
        )
        layout.addStretch()

    def _field(self, parent: QVBoxLayout, label: str, value: int,
               min_v: int, max_v: int, hint: str) -> QSpinBox:
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #ccc; font-size: 14px;")
        parent.addWidget(lbl)

        row = QHBoxLayout()
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(value)
        spin.setStyleSheet(INPUT_DARK)
        row.addWidget(spin)

        hint_lbl = QLabel(hint)
        hint_lbl.setStyleSheet(LABEL_HINT)
        hint_lbl.setWordWrap(True)
        row.addWidget(hint_lbl, stretch=1)
        parent.addLayout(row)
        return spin

    def get_values(self) -> dict:
        return {
            "max_throws_per_run": self._max_throws.value(),
            "dark_cooldown_seconds": self._cooldown.value(),
            "warning_seconds": self._warning.value(),
        }
