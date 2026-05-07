"""
audio_tab.py - Audio cue settings: voice, per-cue toggles, volume
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QFrame, QCheckBox, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, pyqtSignal
from modules.styles import CARD_DARK, CHECKBOX_CUE_GOLD, CHECKBOX_GOLD, RADIO_GOLD, SLIDER_GOLD


class AudioTab(QWidget):
    test_requested  = pyqtSignal()
    volume_changed  = pyqtSignal(float)

    def __init__(self, config: dict):
        super().__init__()
        aud = config.get("audio", {})
        cues = aud.get("cues", {})
        self._build_ui(
            enabled=aud.get("enabled", True),
            voice=aud.get("voice", "Andrew"),
            volume=int(aud.get("volume", 0.8) * 100),
            announce=cues.get("announce", True),
            warning=cues.get("warning", True),
            confirmed=cues.get("confirmed", True),
            rotation_complete=cues.get("rotation_complete", True),
            chime=cues.get("chime", True),
            reset=cues.get("reset", True),
        )

    def _build_ui(self, enabled, voice, volume,
                  announce, warning, confirmed, rotation_complete, chime, reset):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # ── Master toggle card ────────────────────────────────────────
        master_card = QFrame()
        master_card.setStyleSheet(CARD_DARK)
        mc_layout = QVBoxLayout(master_card)
        mc_layout.setContentsMargins(12, 10, 12, 10)
        self._enabled = QCheckBox("Enable audio cues")
        self._enabled.setChecked(enabled)
        self._enabled.setStyleSheet(CHECKBOX_GOLD)
        mc_layout.addWidget(self._enabled)
        layout.addWidget(master_card)

        # ── Options container (grayed out when audio disabled) ────────
        self._options = QWidget()
        opt_layout = QVBoxLayout(self._options)
        opt_layout.setContentsMargins(0, 0, 0, 0)
        opt_layout.setSpacing(14)
        layout = opt_layout   # redirect remaining widgets into container

        # ── Voice selection ───────────────────────────────────────────
        layout.addWidget(self._section_label("VOICE"))
        self._voice_group = QButtonGroup(self)
        voice_row = QHBoxLayout()
        voice_row.setSpacing(20)
        for label, key in [("Andrew (Male)", "Andrew"), ("Jenny (Female)", "Jenny")]:
            rb = QRadioButton(label)
            rb.setChecked(voice == key)
            rb.setStyleSheet(RADIO_GOLD)
            rb.setProperty("voice_key", key)
            self._voice_group.addButton(rb)
            voice_row.addWidget(rb)
        voice_row.addStretch()
        layout.addLayout(voice_row)

        # ── Cues ─────────────────────────────────────────────────────
        layout.addWidget(self._section_label("CUES"))
        cue_card = QFrame()
        cue_card.setStyleSheet(
            "QFrame { background: #1a1a1a; border: 1px solid #3a3a3a; border-radius: 4px; }"
            "QFrame:disabled { background: #111; border-color: #222; }"
        )
        cc_layout = QVBoxLayout(cue_card)
        cc_layout.setContentsMargins(12, 10, 12, 10)
        cc_layout.setSpacing(8)

        self._cue_checks = {}
        cue_rows = [
            ("announce",          announce,          "[Player], throw dark",        "— on player window open"),
            ("warning",           warning,           "[Player], get ready",         "— before player window closes"),
            ("confirmed",         confirmed,         "Dark confirmed",               "— on manual F9"),
            ("rotation_complete", rotation_complete, "All darks used",              "— when rotation ends and all players have used their darks"),
            ("reset",             reset,             "Dark rotation reset",          "— on F11 reset to start a fresh rotation"),
            ("chime",             chime,             "Chime - Auto Dark detection", "— chime when dark is auto-detected (toggle detection in Overlay tab)"),
        ]
        for key, checked, label, hint in cue_rows:
            row = QHBoxLayout()
            row.setSpacing(8)
            cb = QCheckBox(label)
            cb.setChecked(checked)
            cb.setStyleSheet(CHECKBOX_CUE_GOLD)
            hint_lbl = QLabel(hint)
            hint_lbl.setStyleSheet(
                "QLabel { color: #555; font-size: 13px; font-family: Consolas; background: transparent; border: none; }"
                "QLabel:disabled { color: #333; }"
            )
            row.addWidget(cb)
            row.addWidget(hint_lbl)
            row.addStretch()
            cc_layout.addLayout(row)
            self._cue_checks[key] = cb

        layout.addWidget(cue_card)

        # ── Volume ────────────────────────────────────────────────────
        self._volume_label = QLabel(f"VOLUME  {volume}%")
        self._volume_label.setStyleSheet(
            "QLabel { color: #ccc; font-size: 14px; font-family: Consolas; }"
            "QLabel:disabled { color: #444; }"
        )
        layout.addWidget(self._volume_label)

        self._volume = QSlider(Qt.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(volume)
        self._volume.setFixedWidth(300)
        self._volume.setStyleSheet(
            SLIDER_GOLD
            + "QSlider::groove:horizontal:disabled { background: #222; }"
            + "QSlider::sub-page:horizontal:disabled { background: #2a2a2a; }"
            + "QSlider::handle:horizontal:disabled { background: #333; border-color: #3a3a3a; }"
        )
        self._volume.valueChanged.connect(self._on_volume_changed)
        vol_row = QHBoxLayout()
        vol_row.addWidget(self._volume)
        vol_row.addStretch()
        layout.addLayout(vol_row)

        # ── Test button ───────────────────────────────────────────────
        self._test_btn = QPushButton("⊹ Test Voice")
        self._test_btn.setFixedWidth(160)
        self._test_btn.setStyleSheet(
            "QPushButton { color: #88ccff; background: transparent; border: 1px solid #444; "
            "padding: 5px 10px; font-size: 14px; font-family: Consolas; }"
            "QPushButton:disabled { color: #333; border-color: #2a2a2a; }"
        )
        self._test_btn.clicked.connect(self.test_requested.emit)
        test_row = QHBoxLayout()
        test_row.addWidget(self._test_btn)
        test_row.addStretch()
        layout.addLayout(test_row)

        layout.addStretch()

        # ── Wire up outer layout ──────────────────────────────────────
        # `layout` now points to opt_layout (inside self._options).
        # Restore outer_layout reference to add the container.
        outer = self.layout()          # the QVBoxLayout set on self
        outer.addWidget(self._options)
        outer.addStretch()

        # Gray out all options when master toggle is off
        self._options.setEnabled(enabled)
        self._enabled.toggled.connect(self._options.setEnabled)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _on_volume_changed(self, v: int):
        self._volume_label.setText(f"VOLUME  {v}%")
        self.volume_changed.emit(v / 100.0)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "QLabel { color: #ccc; font-size: 14px; font-family: Consolas; }"
            "QLabel:disabled { color: #3a3a3a; }"
        )
        return lbl

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def get_values(self) -> dict:
        selected_voice = "Andrew"
        for btn in self._voice_group.buttons():
            if btn.isChecked():
                selected_voice = btn.property("voice_key")
                break
        return {
            "enabled": self._enabled.isChecked(),
            "voice":   selected_voice,
            "volume":  self._volume.value() / 100.0,
            "cues": {k: cb.isChecked() for k, cb in self._cue_checks.items()},
        }
