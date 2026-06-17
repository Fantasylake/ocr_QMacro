"""4-point form panel."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class PointPanel(QWidget):
    pick_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setContentsMargins(0, 0, 0, 0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("点击点")
        glay = QGridLayout(box)

        labels = ["刷新点(p1)", "首行点(p2)", "页内点(p3)", "首页点(p4)"]
        self.x_spins: list[QSpinBox] = []
        self.y_spins: list[QSpinBox] = []
        self.pick_btns: list[QPushButton] = []

        for row, label in enumerate(labels):
            x_spin = QSpinBox()
            x_spin.setRange(0, 10000)
            y_spin = QSpinBox()
            y_spin.setRange(0, 10000)
            pick_btn = QPushButton("拾取")
            pid = labels[row]
            pick_btn.clicked.connect(lambda _, p=pid: self.pick_requested.emit(p))

            glay.addWidget(QLabel(label), row, 0)
            glay.addWidget(x_spin, row, 1)
            glay.addWidget(y_spin, row, 2)
            glay.addWidget(pick_btn, row, 3)

            self.x_spins.append(x_spin)
            self.y_spins.append(y_spin)
            self.pick_btns.append(pick_btn)

        lay.addWidget(box)

    def fill_from_pick(self, idx: int, x: int, y: int) -> None:
        if 0 <= idx < 4:
            self.x_spins[idx].setValue(x)
            self.y_spins[idx].setValue(y)

    def collect(self) -> list[dict]:
        labels = ["刷新点", "首行点", "页内点", "首页点"]
        return [
            {"name": labels[i], "x": self.x_spins[i].value(), "y": self.y_spins[i].value()}
            for i in range(4)
        ]

    def apply(self, points: list[dict]) -> None:
        for i, p in enumerate(points):
            if i < 4:
                self.x_spins[i].setValue(int(p.get("x", 0)))
                self.y_spins[i].setValue(int(p.get("y", 0)))
