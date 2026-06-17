from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRect, QPoint
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QColor, QPen, QFont, QRegion, QBitmap
from PySide6.QtWidgets import QApplication, QWidget


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


class PickerOverlay(QWidget):
    HINT_BAR_HEIGHT = 56

    def __init__(self, dpr: Optional[float] = None):
        """Create a full-screen pick overlay.

        Parameters
        ----------
        dpr : float, optional
            Device pixel ratio to convert logical mouse positions to
            physical screen pixels. If None, queries primaryScreen() at
            click time. Inject explicitly in tests to avoid Qt screen deps.
        """
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        # True per-pixel transparency on Windows requires:
        # - WA_TranslucentBackground: allows the framebuffer to have alpha < 255
        # - WA_NoSystemBackground:   don't let Qt fill with the system bg color
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self._dpr_override = dpr
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)

        # WA_TranslucentBackground makes transparent pixels NON-hit-testable.
        # We want the whole screen to be hit-testable while visually transparent.
        # Solution: use setMask(QRegion) to mark the FULL widget rect as
        # hit-testable. Unlike QBitmap (which can be interpreted as alpha
        # and silently dropped on translucent widgets), QRegion defines
        # geometry directly and works reliably on Windows.
        from PySide6.QtGui import QRegion as QGuiRegion
        self.setMask(QGuiRegion(self.rect()))

        self._picked: Optional[Tuple[int, int]] = None
        self._mode: str = "point"
        self._press_pos: Optional[Tuple[int, int]] = None
        self._current_pos: Optional[Tuple[int, int]] = None
        self._region_result: Optional[PickedRegion] = None

    def _device_pixel_ratio(self) -> float:
        if self._dpr_override is not None:
            return self._dpr_override
        screen = QApplication.primaryScreen()
        return screen.devicePixelRatio() if screen else 1.0

    def set_mode(self, mode: str) -> None:
        assert mode in ("point", "region")
        self._mode = mode

    def showEvent(self, event):
        """When the overlay becomes visible, grab all mouse + keyboard input.

        This is the only reliable way to receive mouse events across the
        entire screen on Windows when using WA_TranslucentBackground, because
        the Windows window manager cannot see Qt's internal alpha mask and
        will route mouse events to the underlying app for any pixel that
        Qt has painted as fully transparent. grabMouse() forces the WM
        to send every mouse event to this widget regardless of position.
        """
        super().showEvent(event)
        self.grabMouse()
        self.grabKeyboard()
        self.setFocus(Qt.OtherFocusReason)

    def hideEvent(self, event):
        """Release the global mouse/keyboard grab when closing."""
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

        # 0) Sub-perceptual overlay covering the WHOLE screen.
        # Windows WM (winuser.h) routes mouse events based on the *system-level*
        # window bitmap. With WS_EX_LAYERED (which WA_TranslucentBackground
        # requires on Windows), the WM treats alpha=0 pixels as "see-through"
        # and forwards mouse events to the underlying app -- Qt's setMask()
        # and grabMouse() cannot override this, they only act at the Qt
        # level once the event has reached us.
        #
        # Solution: paint a 1/255-alpha fill over the entire widget. This is
        # completely invisible to the human eye (1/255 ~ 0.4%) but it makes
        # the WM treat the pixel as "opaque" and route events to OUR window.
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

        # 1) Translucent hint bar at the top -- the only opaque-ish UI element
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

        # 2) Region-mode selection rectangle (transparent everywhere else)
        # _press_pos / _current_pos are stored in PHYSICAL pixels (for mss).
        # QPainter draws in WIDGET-LOCAL LOGICAL pixels (DIPs), so we must
        # convert back before drawing -- otherwise the visible green box
        # is offset from the cursor by the devicePixelRatio factor.
        if self._mode == "region" and self._press_pos is not None and self._current_pos is not None:
            lx, ly = self._physical_to_widget(self._press_pos[0], self._press_pos[1])
            cx, cy = self._physical_to_widget(self._current_pos[0], self._current_pos[1])
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
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._mode == "region" and self._press_pos is not None:
            self._current_pos = self._to_physical(event.globalPosition())
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

    def _to_physical(self, gp) -> Tuple[int, int]:
        """Convert a global logical position (DIP) to physical screen pixels.

        On Windows with HiDPI scaling, Qt reports mouse positions in logical
        pixels (DIPs) while mss captures in physical pixels. The OS mouse
        cursor and the framebuffer are 1:1 in physical space, so we scale
        the pick coordinates by the devicePixelRatio before storing them.
        Storing physical pixels means the region/point maps directly to
        the mss coordinate system with no further conversion needed.
        """
        dpr = self._device_pixel_ratio()
        return (int(gp.x() * dpr), int(gp.y() * dpr))

    def _physical_to_widget(self, x: int, y: int) -> Tuple[int, int]:
        """Convert a physical pixel position to widget-local logical pixels.

        Mouse event positions are stored in physical pixels (matching the
        mss framebuffer). But QPainter in paintEvent uses the widget's own
        coordinate system, which is logical pixels (DIPs) for widgets
        with WA_TranslucentBackground. Without this conversion, the green
        selection rectangle gets drawn ~DPR times farther from the cursor
        than where the user actually clicked.
        """
        dpr = self._device_pixel_ratio()
        return (int(x / dpr), int(y / dpr))

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
