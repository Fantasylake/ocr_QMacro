from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QColor, QPen, QFont, QRegion
from PySide6.QtWidgets import QApplication, QWidget

from core.coords import clear_coord_cache, global_logical_to_physical


@dataclass
class PickedRegion:
    top: int
    left: int
    width: int
    height: int


def _norm_rect(x0: int, y0: int, x1: int, y1: int) -> PickedRegion:
    """Normalize two diagonal points into a region with positive width/height."""
    left = min(x0, x1)
    top = min(y0, y1)
    width = abs(x1 - x0)
    height = abs(y1 - y0)
    return PickedRegion(top=top, left=left, width=width, height=height)


def _virtual_desktop_geometry() -> QRect:
    """Union of all connected screens (supports multi-monitor picking)."""
    screens = QGuiApplication.screens()
    if not screens:
        return QRect(0, 0, 1920, 1080)
    geo = screens[0].geometry()
    for screen in screens[1:]:
        geo = geo.united(screen.geometry())
    return geo


class PickerOverlay(QWidget):
    HINT_BAR_HEIGHT = 56

    def __init__(self, dpr: Optional[float] = None):
        """Create a full-screen pick overlay.

        Parameters
        ----------
        dpr : float, optional
            Device pixel ratio to convert logical mouse positions to
            physical screen pixels. If None, uses the screen under the
            cursor (required for mixed-DPI multi-monitor setups). Inject
            explicitly in tests to avoid Qt screen deps.
        """
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self._dpr_override = dpr
        clear_coord_cache()
        self.setGeometry(_virtual_desktop_geometry())

        from PySide6.QtGui import QRegion as QGuiRegion
        self.setMask(QGuiRegion(self.rect()))

        self._picked: Optional[Tuple[int, int]] = None
        self._mode: str = "point"
        self._press_pos: Optional[Tuple[int, int]] = None
        self._current_pos: Optional[Tuple[int, int]] = None
        self._press_local: Optional[Tuple[int, int]] = None
        self._current_local: Optional[Tuple[int, int]] = None
        self._region_result: Optional[PickedRegion] = None

    def set_mode(self, mode: str) -> None:
        assert mode in ("point", "region")
        self._mode = mode

    def showEvent(self, event):
        super().showEvent(event)
        self.grabMouse()
        self.grabKeyboard()
        self.setFocus(Qt.OtherFocusReason)

    def hideEvent(self, event):
        try:
            self.releaseMouse()
            self.releaseKeyboard()
        except RuntimeError:
            pass
        super().hideEvent(event)

    def _hint_text(self) -> str:
        if self._mode == "point":
            return "单击屏幕拾取坐标 · 按 ESC 取消"
        return "按住鼠标左键拖拽框选区域 · 松开确认 · ESC 取消"

    def _hint_rect(self) -> QRect:
        return QRect(0, 0, self.width(), self.HINT_BAR_HEIGHT)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        hint_rect = self._hint_rect()
        painter.fillRect(hint_rect, QColor(0, 0, 0, 160))
        painter.setPen(QPen(QColor(255, 215, 0), 1))
        painter.drawLine(hint_rect.bottomLeft(), hint_rect.bottomRight())

        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(hint_rect, Qt.AlignCenter, self._hint_text())

        if (
            self._mode == "region"
            and self._press_local is not None
            and self._current_local is not None
        ):
            lx, ly = self._press_local
            cx, cy = self._current_local
            rect = QRect(
                min(lx, cx),
                min(ly, cy),
                abs(cx - lx),
                abs(cy - ly),
            )
            painter.fillRect(rect, QColor(0, 200, 80, 50))
            painter.setPen(QPen(QColor(0, 220, 90, 255), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            label = f"{rect.width()} x {rect.height()}"
            label_font = QFont()
            label_font.setPointSize(10)
            label_font.setBold(True)
            painter.setFont(label_font)
            metrics = painter.fontMetrics()
            label_w = metrics.horizontalAdvance(label) + 12
            label_h = metrics.height() + 6
            label_x = rect.left()
            label_y = max(self.HINT_BAR_HEIGHT + 2, rect.top() - label_h - 2)
            label_rect = QRect(label_x, label_y, label_w, label_h)
            painter.fillRect(label_rect, QColor(0, 0, 0, 200))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(label_rect, Qt.AlignCenter, label)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.LeftButton:
            return
        if self._mode == "point":
            self._picked = self._to_physical(event.globalPosition())
            self.close()
        else:
            self._press_pos = self._to_physical(event.globalPosition())
            self._current_pos = self._press_pos
            self._press_local = self._local_pos(event)
            self._current_local = self._press_local
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._mode == "region" and self._press_pos is not None:
            self._current_pos = self._to_physical(event.globalPosition())
            self._current_local = self._local_pos(event)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._mode != "region":
            return
        if event.button() != Qt.LeftButton or self._press_pos is None:
            return
        end = self._to_physical(event.globalPosition())
        region = _norm_rect(self._press_pos[0], self._press_pos[1], end[0], end[1])
        if region.width >= 3 and region.height >= 3:
            self._region_result = region
        self.close()

    def _local_pos(self, event: QMouseEvent) -> Tuple[int, int]:
        pos = event.position()
        return int(pos.x()), int(pos.y())

    def _to_physical(self, gp) -> Tuple[int, int]:
        """Convert Qt global logical position to mss physical pixels."""
        return global_logical_to_physical(
            gp.x(),
            gp.y(),
            dpr_override=self._dpr_override,
        )

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self._picked = None
            self._region_result = None
            self.close()

    def picked_point(self) -> Optional[Tuple[int, int]]:
        return self._picked

    def picked_region(self) -> Optional[PickedRegion]:
        return self._region_result


def pick_coordinate() -> Optional[Tuple[int, int]]:
    """Block until user clicks (or ESC). Returns (x, y) or None."""
    overlay = PickerOverlay()
    overlay.set_mode("point")
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()
    app = QApplication.instance()
    while overlay.isVisible():
        app.processEvents()
    return overlay.picked_point()


def pick_region() -> Optional[PickedRegion]:
    """Block until user drags a rectangle (or ESC). Returns PickedRegion or None.

    If the dragged rectangle is smaller than 3x3, returns None (treated as cancel).
    """
    overlay = PickerOverlay()
    overlay.set_mode("region")
    overlay.show()
    overlay.raise_()
    overlay.activateWindow()
    app = QApplication.instance()
    while overlay.isVisible():
        app.processEvents()
    return overlay.picked_region()
