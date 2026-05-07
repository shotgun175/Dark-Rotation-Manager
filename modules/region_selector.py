"""
region_selector.py - Full-screen drag-to-select region tool.

Opens a translucent overlay over all monitors. User clicks and drags
to draw a rectangle. On mouse release, emits region_selected(x, y, w, h)
with coordinates relative to the Lost Ark window (if found), or absolute
screen coordinates if Lost Ark is not running.
"""

from PyQt5.QtWidgets import QWidget, QApplication, QLabel
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QPen, QFont


def _get_lostark_origin():
    """Return (left, top) of the Lost Ark window client area, or None."""
    try:
        import win32gui

        def _cb(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                if "LOST ARK" in win32gui.GetWindowText(hwnd).upper():
                    rect = win32gui.GetClientRect(hwnd)
                    pt = win32gui.ClientToScreen(hwnd, (rect[0], rect[1]))
                    results.append(pt)

        found = []
        win32gui.EnumWindows(_cb, found)
        return found[0] if found else None
    except Exception:
        return None


class RegionSelectorWindow(QWidget):
    """Full-screen transparent drag-to-select widget."""

    region_selected = pyqtSignal(int, int, int, int)   # rel_x, rel_y, w, h

    def __init__(self):
        super().__init__()
        self._start: QPoint | None = None
        self._end:   QPoint | None = None
        self._lostark_origin = _get_lostark_origin()

        # Cover all monitors combined
        combined = QRect()
        for i in range(QApplication.desktop().screenCount()):
            combined = combined.united(QApplication.desktop().screenGeometry(i))
        self.setGeometry(combined)

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)

        # Instruction label
        self._hint = QLabel(
            "Click and drag to select the boss debuff region.  "
            "Press Escape to cancel.",
            self
        )
        self._hint.setStyleSheet(
            "color: #ffffff; background: rgba(0,0,0,180); "
            "padding: 10px 18px; font-family: Consolas; font-size: 14px;"
        )
        self._hint.adjustSize()
        self._hint.move(
            (self.width() - self._hint.width()) // 2,
            40
        )

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)

        # Dark translucent overlay
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._start and self._end:
            rect = self._selection_rect()

            # Cut out (clear) the selected area so it looks "highlighted"
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(rect, QColor(0, 0, 0, 255))

            # Draw bright border around selection
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QColor("#ffd700"), 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # Draw dimensions label inside selection
            w, h = rect.width(), rect.height()
            if w > 60 and h > 20:
                painter.setPen(QColor("#ffd700"))
                painter.setFont(QFont("Consolas", 10))
                painter.drawText(
                    rect.adjusted(4, 4, -4, -4),
                    Qt.AlignTop | Qt.AlignLeft,
                    f"{w} × {h}"
                )

    def _selection_rect(self) -> QRect:
        return QRect(self._start, self._end).normalized()

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start = event.globalPos() - self.geometry().topLeft()
            self._end   = self._start
            self.update()

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._end = event.globalPos() - self.geometry().topLeft()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._start and self._end:
            rect = self._selection_rect()
            if rect.width() > 5 and rect.height() > 5:
                # Convert to absolute screen coords
                abs_x = rect.x() + self.geometry().x()
                abs_y = rect.y() + self.geometry().y()

                # Make relative to Lost Ark window if available
                if self._lostark_origin:
                    rel_x = abs_x - self._lostark_origin[0]
                    rel_y = abs_y - self._lostark_origin[1]
                else:
                    rel_x, rel_y = abs_x, abs_y

                self.region_selected.emit(rel_x, rel_y, rect.width(), rect.height())
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
