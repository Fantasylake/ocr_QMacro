"""Single monitor region form panel."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class RegionPanel(QWidget):
    pick_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setContentsMargins(0, 0, 0, 0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("监控区域")
        flay = QFormLayout(box)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("区域名称")
        flay.addRow("名称", self.name_edit)

        self.top_spin = QSpinBox()
        self.top_spin.setRange(0, 30000)
        self.left_spin = QSpinBox()
        self.left_spin.setRange(0, 30000)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(0, 15000)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(0, 15000)
        flay.addRow("top", self.top_spin)
        flay.addRow("left", self.left_spin)
        flay.addRow("width", self.width_spin)
        flay.addRow("height", self.height_spin)

        pick_btn = QPushButton("框选区域")
        pick_btn.clicked.connect(self.pick_requested.emit)
        flay.addRow("", pick_btn)

        lay.addWidget(box)

    def fill_from_pick(self, top: int, left: int, width: int, height: int) -> None:
        self.top_spin.setValue(top)
        self.left_spin.setValue(left)
        self.width_spin.setValue(abs(width))
        self.height_spin.setValue(abs(height))
        if not self.name_edit.text().strip():
            self.name_edit.setText("a1")

    def collect(self) -> dict:
        return {
            "name": self.name_edit.text().strip() or "a1",
            "top": self.top_spin.value(),
            "left": self.left_spin.value(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
        }

    def apply(self, data: dict) -> None:
        self.name_edit.setText(data.get("name", ""))
        self.top_spin.setValue(int(data.get("top", 0)))
        self.left_spin.setValue(int(data.get("left", 0)))
        self.width_spin.setValue(int(data.get("width", 0)))
        self.height_spin.setValue(int(data.get("height", 0)))
