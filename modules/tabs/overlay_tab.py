"""
overlay_tab.py - Overlay position, size, opacity, font, and preview controls
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSlider,
    QPushButton, QFrame, QCheckBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen
from modules.styles import (
    BUTTON_GHOST, CARD_DARK, CHECKBOX_GOLD,
    INPUT_DARK, LABEL_DIM, LABEL_HINT, LABEL_SECTION, SLIDER_GOLD,
)


class RegionPreviewWidget(QFrame):
    """Mini screen diagram showing the detection region as a yellow rectangle."""

    _REF_W = 2560
    _REF_H = 1440

    def __init__(self, rel_x=875, rel_y=325, w=456, h=46, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 113)   # 16:9 compact
        self.setStyleSheet("background: #0a0a0a; border: 1px solid #333;")
        self._rel_x = rel_x
        self._rel_y = rel_y
        self._w = w
        self._h = h

    def set_region(self, rel_x: int, rel_y: int, w: int, h: int):
        self._rel_x, self._rel_y, self._w, self._h = rel_x, rel_y, w, h
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0a0a0a"))

        sw = self.width()  / self._REF_W
        sh = self.height() / self._REF_H

        rx = int(self._rel_x * sw)
        ry = int(self._rel_y * sh)
        rw = max(2, int(self._w * sw))
        rh = max(2, int(self._h * sh))

        painter.fillRect(rx, ry, rw, rh, QColor(255, 215, 0, 60))
        painter.setPen(QPen(QColor("#ffd700"), 1))
        painter.drawRect(rx, ry, rw, rh)

        painter.setPen(QPen(QColor("#333"), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)


class OverlayTab(QWidget):
    preview_requested         = pyqtSignal()
    region_selector_requested = pyqtSignal()

    def __init__(self, config: dict):
        super().__init__()
        ov = config.get("overlay", {})
        pos = ov.get("position", {"x": 0, "y": 0})
        det = config.get("detection", {})
        self._build_ui(
            x=pos.get("x", 0),
            y=pos.get("y", 0),
            width=ov.get("width", 320),
            height=ov.get("height", 230),
            opacity_pct=int(round(ov.get("opacity", 0.88) * 100)),
            font_size=ov.get("font_size", 16),
            detection_enabled=det.get("enabled", True),
            det_rel_x=det.get("rel_x", 875),
            det_rel_y=det.get("rel_y", 325),
            det_w=det.get("width", 456),
            det_h=det.get("height", 46),
        )

    def _build_ui(self, x, y, width, height, opacity_pct, font_size,
                  detection_enabled=True, det_rel_x=875, det_rel_y=325, det_w=456, det_h=46):

        # Single scrollable column — no competing right panel
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        left = QVBoxLayout(scroll_content)
        left.setContentsMargins(18, 18, 18, 18)
        left.setSpacing(14)

        # ── POSITION + SIZE + inline appearance preview ───────────────────
        left.addWidget(self._section_label("POSITION / SIZE (pixels)"))

        pos_and_preview = QHBoxLayout()
        pos_and_preview.setSpacing(16)

        # Controls column: X/Y, W/H, button, hint — matches detection region layout
        pos_col = QVBoxLayout()
        pos_col.setSpacing(6)

        pos_row = QHBoxLayout()
        pos_row.setSpacing(6)
        pos_row.addWidget(self._dim_label("X"))
        self._x = self._spinbox(x, -9999, 9999)
        pos_row.addWidget(self._x)
        pos_row.addWidget(self._dim_label("Y"))
        self._y = self._spinbox(y, -9999, 9999)
        pos_row.addWidget(self._y)
        pos_col.addLayout(pos_row)

        size_row = QHBoxLayout()
        size_row.setSpacing(6)
        size_row.addWidget(self._dim_label("W"))
        self._width = self._spinbox(width, 100, 1920)
        size_row.addWidget(self._width)
        size_row.addWidget(self._dim_label("H"))
        self._height = self._spinbox(height, 100, 1080)
        size_row.addWidget(self._height)
        pos_col.addLayout(size_row)

        self._preview_btn = QPushButton("⊹ Preview on screen")
        self._preview_btn.setFixedWidth(210)
        self._preview_btn.setStyleSheet(BUTTON_GHOST)
        self._preview_btn.clicked.connect(self.preview_requested.emit)
        pos_col.addWidget(self._preview_btn)

        pos_and_preview.addLayout(pos_col)

        # Right: static appearance preview box
        preview_frame = QFrame()
        preview_frame.setFixedWidth(110)
        preview_frame.setStyleSheet("background: #0a0a0a; border: 1px solid #333;")
        pf_layout = QVBoxLayout(preview_frame)
        pf_layout.setContentsMargins(8, 8, 8, 8)
        pf_layout.setSpacing(2)
        for text, color, bold in [
            ("RUNNING",   "#aaa",    False),
            ("DARK NOW",  "#aaa",    False),
            ("Valslayer", "#ffd700", True),
            ("NEXT",      "#aaa",    False),
            ("Mabi",      "#88ccff", False),
        ]:
            lbl = QLabel(text)
            size = "14px" if bold else "13px"
            weight = "bold" if bold else "normal"
            lbl.setStyleSheet(f"color: {color}; font-size: {size}; font-weight: {weight};")
            pf_layout.addWidget(lbl)
        pos_and_preview.addWidget(preview_frame)
        pos_and_preview.addStretch()

        left.addLayout(pos_and_preview)

        drag_hint = QLabel("Drag the preview window to set position — fields update automatically.")
        drag_hint.setStyleSheet("color: #777; font-size: 14px;")
        left.addWidget(drag_hint)

        # ── OPACITY ───────────────────────────────────────────────────────
        self._opacity_label = QLabel(f"OPACITY  {opacity_pct}%")
        self._opacity_label.setStyleSheet("color: #ccc; font-size: 14px;")
        left.addWidget(self._opacity_label)
        self._opacity = QSlider(Qt.Horizontal)
        self._opacity.setRange(10, 100)
        self._opacity.setValue(opacity_pct)
        self._opacity.setFixedWidth(300)
        self._opacity.setStyleSheet(SLIDER_GOLD)
        self._opacity.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"OPACITY  {v}%")
        )
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self._opacity)
        opacity_row.addStretch()
        left.addLayout(opacity_row)

        # ── FONT SIZE ─────────────────────────────────────────────────────
        left.addWidget(self._section_label("FONT SIZE"))
        font_row = QHBoxLayout()
        self._font_size = self._spinbox(font_size, 8, 32)
        font_row.addWidget(self._font_size)
        px_lbl = QLabel("px")
        px_lbl.setStyleSheet(LABEL_HINT)
        font_row.addWidget(px_lbl)
        font_row.addStretch()
        left.addLayout(font_row)

        # ── AUTO-DETECTION ────────────────────────────────────────────────
        left.addWidget(self._section_label("AUTO-DETECTION"))
        det_card = QFrame()
        det_card.setStyleSheet(CARD_DARK)
        det_card_layout = QVBoxLayout(det_card)
        det_card_layout.setContentsMargins(12, 10, 12, 10)
        det_card_layout.setSpacing(4)
        self._detection_enabled = QCheckBox("Enable grenade auto-detect (requires OpenCV + Lost Ark running)")
        self._detection_enabled.setChecked(detection_enabled)
        self._detection_enabled.setStyleSheet(CHECKBOX_GOLD)
        det_card_layout.addWidget(self._detection_enabled)
        det_hint = QLabel("Scans boss debuff bar to confirm Dark / Splendid Dark automatically.")
        det_hint.setStyleSheet("color: #888; font-size: 13px; font-family: Consolas; border: none; background: transparent;")
        det_hint.setWordWrap(True)
        det_card_layout.addWidget(det_hint)
        left.addWidget(det_card)

        # Detection region controls + region preview side by side
        det_and_preview = QHBoxLayout()
        det_and_preview.setSpacing(16)

        # Controls column (no internal stretches so it stays as narrow as its content)
        det_col = QVBoxLayout()
        det_col.setSpacing(6)

        det_row1 = QHBoxLayout()
        det_row1.setSpacing(6)
        det_row1.addWidget(self._dim_label("X"))
        self._det_x = self._spinbox(det_rel_x, -9999, 9999)
        det_row1.addWidget(self._det_x)
        det_row1.addWidget(self._dim_label("Y"))
        self._det_y = self._spinbox(det_rel_y, -9999, 9999)
        det_row1.addWidget(self._det_y)
        det_col.addLayout(det_row1)

        det_row2 = QHBoxLayout()
        det_row2.setSpacing(6)
        det_row2.addWidget(self._dim_label("W"))
        self._det_w = self._spinbox(det_w, 1, 3840)
        det_row2.addWidget(self._det_w)
        det_row2.addWidget(self._dim_label("H"))
        self._det_h = self._spinbox(det_h, 1, 2160)
        det_row2.addWidget(self._det_h)
        det_col.addLayout(det_row2)

        self._set_region_btn = QPushButton("⊹ Draw Region on Screen")
        self._set_region_btn.setStyleSheet(BUTTON_GHOST)
        self._set_region_btn.setSizePolicy(
            self._set_region_btn.sizePolicy().horizontalPolicy(),
            self._set_region_btn.sizePolicy().verticalPolicy(),
        )
        self._set_region_btn.setFixedWidth(235)
        self._set_region_btn.clicked.connect(self.region_selector_requested.emit)
        det_col.addWidget(self._set_region_btn)

        region_hint = QLabel("Relative to Lost Ark window. Apply to save.")
        region_hint.setStyleSheet(LABEL_HINT)
        det_col.addWidget(region_hint)

        det_and_preview.addLayout(det_col)

        # Region preview column
        rp_col = QVBoxLayout()
        rp_col.setSpacing(2)
        self._region_preview = RegionPreviewWidget(det_rel_x, det_rel_y, det_w, det_h)
        rp_col.addWidget(self._region_preview)
        scan_lbl = QLabel("Yellow = scan area")
        scan_lbl.setStyleSheet("color: #777; font-size: 14px;")
        rp_col.addWidget(scan_lbl)
        rp_col.addStretch()
        det_and_preview.addLayout(rp_col)

        det_and_preview.addStretch()   # everything left-anchored
        left.addLayout(det_and_preview)

        # Connect spinboxes → live preview
        self._det_x.valueChanged.connect(self._update_region_preview)
        self._det_y.valueChanged.connect(self._update_region_preview)
        self._det_w.valueChanged.connect(self._update_region_preview)
        self._det_h.valueChanged.connect(self._update_region_preview)

        left.addStretch()
        scroll.setWidget(scroll_content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _spinbox(self, value: int, min_v: int, max_v: int) -> QSpinBox:
        s = QSpinBox()
        s.setRange(min_v, max_v)
        s.setValue(value)
        s.setStyleSheet(INPUT_DARK)
        return s

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(LABEL_SECTION)
        return lbl

    def _dim_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(LABEL_DIM)
        return lbl

    # ── Data access ───────────────────────────────────────────────────────

    def get_values(self) -> dict:
        return {
            "position": {"x": self._x.value(), "y": self._y.value()},
            "width": self._width.value(),
            "height": self._height.value(),
            "opacity": self._opacity.value() / 100.0,
            "font_size": self._font_size.value(),
        }

    def get_detection_enabled(self) -> bool:
        return self._detection_enabled.isChecked()

    def get_detection_region(self) -> dict:
        return {
            "rel_x":  self._det_x.value(),
            "rel_y":  self._det_y.value(),
            "width":  self._det_w.value(),
            "height": self._det_h.value(),
        }

    def set_detection_region(self, rel_x: int, rel_y: int, w: int, h: int):
        """Update detection region spinboxes and preview."""
        self._det_x.setValue(rel_x)
        self._det_y.setValue(rel_y)
        self._det_w.setValue(w)
        self._det_h.setValue(h)
        self._region_preview.set_region(rel_x, rel_y, w, h)

    def _update_region_preview(self):
        self._region_preview.set_region(
            self._det_x.value(), self._det_y.value(),
            self._det_w.value(), self._det_h.value(),
        )

    def set_position(self, x: int, y: int):
        """Called when overlay window is dragged — updates X/Y spinboxes."""
        self._x.setValue(x)
        self._y.setValue(y)
