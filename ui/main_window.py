"""Main window: compact single-panel scan monitor UI."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import ScanConfig, load_config, save_config
from core.scheduler import Scheduler
from core.storage import clean_old_logs
from ui.picker import pick_coordinate, pick_region
from ui.point_panel import PointPanel
from ui.region_panel import RegionPanel

CONFIG_PATH = Path("config.json")
SAVE_DEBOUNCE_MS = 600


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("刷页监控")
        self.resize(800, 640)
        self._config = load_config(CONFIG_PATH)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._save_config)

        self.scheduler = Scheduler(self._config, parent=self)
        self.scheduler.log.connect(self._append_log)
        self.scheduler.status_changed.connect(self._on_status_changed)

        self._build_ui()
        self._load_into_ui()
        clean_old_logs()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # --- Top bar ---
        bar = QHBoxLayout()
        bar.setSpacing(6)

        self.start_btn = QPushButton("开始")
        self.start_btn.setMinimumWidth(70)
        self.start_btn.setStyleSheet("font-weight: bold;")
        self.start_btn.clicked.connect(self._on_start)
        bar.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumWidth(70)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._on_stop)
        bar.addWidget(self.stop_btn)

        bar.addSpacing(12)

        lbl1 = QLabel("扫描间隔(s):")
        lbl1.setStyleSheet("font-weight: bold;")
        bar.addWidget(lbl1)
        self.scan_interval_spin = QSpinBox()
        self.scan_interval_spin.setRange(1, 3600)
        self.scan_interval_spin.setValue(5)
        self.scan_interval_spin.valueChanged.connect(self._mark_dirty)
        bar.addWidget(self.scan_interval_spin)

        bar.addSpacing(6)
        lbl2 = QLabel("等待时间(s):")
        lbl2.setStyleSheet("font-weight: bold;")
        bar.addWidget(lbl2)
        self.wait_interval_spin = QSpinBox()
        self.wait_interval_spin.setRange(1, 300)
        self.wait_interval_spin.setValue(3)
        self.wait_interval_spin.valueChanged.connect(self._mark_dirty)
        bar.addWidget(self.wait_interval_spin)

        bar.addStretch()
        root.addLayout(bar)

        # --- Keyword bar ---
        kw_box = QHBoxLayout()
        kw_lbl = QLabel("关键词(多值用|分隔):")
        kw_lbl.setStyleSheet("font-weight: bold;")
        kw_box.addWidget(kw_lbl)
        self.kw_edit = QLineEdit()
        self.kw_edit.setPlaceholderText("成功|完成|已就绪")
        self.kw_edit.textChanged.connect(self._mark_dirty)
        kw_box.addWidget(self.kw_edit, 1)
        root.addLayout(kw_box)

        # --- Main area: points left, region right ---
        main = QHBoxLayout()
        main.setSpacing(10)

        # -- Point group --
        pt_box = QGroupBox("点击点")
        pt_glay = QGridLayout(pt_box)
        pt_glay.setSpacing(4)

        self._pt_x: list[QSpinBox] = []
        self._pt_y: list[QSpinBox] = []
        self._pt_pick: list[QPushButton] = []
        pt_labels = ["刷新点(p1)", "首行点(p2)", "页内点(p3)", "首页点(p4)"]

        for i, lbl in enumerate(pt_labels):
            row_lbl = QLabel(lbl)
            row_lbl.setStyleSheet("font-weight: bold;")
            pt_glay.addWidget(row_lbl, i, 0)

            x = QSpinBox()
            x.setRange(0, 10000)
            x.valueChanged.connect(self._mark_dirty)
            pt_glay.addWidget(x, i, 1)
            self._pt_x.append(x)

            y = QSpinBox()
            y.setRange(0, 10000)
            y.valueChanged.connect(self._mark_dirty)
            pt_glay.addWidget(y, i, 2)
            self._pt_y.append(y)

            pick = QPushButton("拾取")
            pid = lbl
            pick.clicked.connect(lambda _, p=pid: self._on_pick_point(p))
            pt_glay.addWidget(pick, i, 3)
            self._pt_pick.append(pick)

        main.addWidget(pt_box, 1)

        # -- Region group --
        self.region_panel = RegionPanel(self)
        self.region_panel.pick_requested.connect(self._on_pick_region)
        self.region_panel.name_edit.textChanged.connect(self._mark_dirty)
        for s in [self.region_panel.top_spin, self.region_panel.left_spin,
                  self.region_panel.width_spin, self.region_panel.height_spin]:
            s.valueChanged.connect(self._mark_dirty)
        main.addWidget(self.region_panel, 1)

        root.addLayout(main, 1)

        # --- Log panel ---
        log_box = QGroupBox("日志")
        log_lay = QVBoxLayout(log_box)
        log_lay.setContentsMargins(4, 4, 4, 4)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        mono = QFont("Consolas", 9)
        self.log_view.setFont(mono)
        self.log_view.setStyleSheet("background:#1a1a2e; color:#d4d4aa;")
        log_lay.addWidget(self.log_view)
        root.addWidget(log_box, 2)

    # ------------------------------------------------------------------ Config sync
    def _mark_dirty(self) -> None:
        self._save_timer.start(SAVE_DEBOUNCE_MS)

    def _save_config(self) -> None:
        kw_text = self.kw_edit.text().strip()
        keywords = [k.strip() for k in kw_text.split("|") if k.strip()]

        pt_x = [s.value() for s in self._pt_x]
        pt_y = [s.value() for s in self._pt_y]
        pt_names = ["刷新点", "首行点", "页内点", "首页点"]

        self._config.scan_interval = self.scan_interval_spin.value()
        self._config.wait_interval = self.wait_interval_spin.value()
        self._config.keywords = keywords
        self._config.refresh_point.x = pt_x[0]
        self._config.refresh_point.y = pt_y[0]
        self._config.first_line_point.x = pt_x[1]
        self._config.first_line_point.y = pt_y[1]
        self._config.page_click_point.x = pt_x[2]
        self._config.page_click_point.y = pt_y[2]
        self._config.home_point.x = pt_x[3]
        self._config.home_point.y = pt_y[3]

        reg = self.region_panel.collect()
        self._config.monitor_region.name = reg["name"]
        self._config.monitor_region.top = reg["top"]
        self._config.monitor_region.left = reg["left"]
        self._config.monitor_region.width = reg["width"]
        self._config.monitor_region.height = reg["height"]

        save_config(self._config, CONFIG_PATH)
        self.scheduler.update_config(self._config)

    def _load_into_ui(self) -> None:
        self.scan_interval_spin.setValue(self._config.scan_interval)
        self.wait_interval_spin.setValue(self._config.wait_interval)
        self.kw_edit.setText("|".join(self._config.keywords))

        pts = [
            self._config.refresh_point,
            self._config.first_line_point,
            self._config.page_click_point,
            self._config.home_point,
        ]
        for i, p in enumerate(pts):
            self._pt_x[i].setValue(p.x)
            self._pt_y[i].setValue(p.y)

        r = self._config.monitor_region
        self.region_panel.apply({
            "name": r.name,
            "top": r.top,
            "left": r.left,
            "width": r.width,
            "height": r.height,
        })

    # ------------------------------------------------------------------ Validation
    def _validate(self) -> bool:
        kw = self.kw_edit.text().strip()
        if not kw:
            QMessageBox.warning(self, "缺少关键词", "请输入至少一个关键词（多值用 | 分隔）")
            return False
        for i, x in enumerate(self._pt_x):
            if x.value() == 0 and self._pt_y[i].value() == 0:
                name = ["刷新点", "首行点", "页内点", "首页点"][i]
                QMessageBox.warning(self, "坐标未设置", f"{name} 坐标为 (0,0)，请先拾取有效坐标")
                return False
        reg = self.region_panel.collect()
        if reg["width"] < 10 or reg["height"] < 10:
            QMessageBox.warning(self, "区域无效", "监控区域宽高至少需要 10px，请先框选有效区域")
            return False
        return True

    # ------------------------------------------------------------------ Start/Stop
    def _on_start(self) -> None:
        if not self._validate():
            return
        self._save_config()
        self.scheduler.start()

    def _on_stop(self) -> None:
        self.scheduler.stop()

    def _on_status_changed(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        for w in self._pt_x + self._pt_y:
            w.setEnabled(not running)
        for b in self._pt_pick:
            b.setEnabled(not running)
        self.scan_interval_spin.setEnabled(not running)
        self.wait_interval_spin.setEnabled(not running)
        self.kw_edit.setEnabled(not running)
        self.region_panel.setEnabled(not running)

    # ------------------------------------------------------------------ Pickers
    def _on_pick_point(self, label: str) -> None:
        self.hide()
        QApplication.processEvents()
        QApplication.processEvents()
        result = pick_coordinate()
        self.show()
        self.raise_()
        self.activateWindow()
        if result is not None:
            x, y = result
            idx_map = {
                "刷新点(p1)": 0,
                "首行点(p2)": 1,
                "页内点(p3)": 2,
                "首页点(p4)": 3,
            }
            idx = idx_map.get(label, 0)
            self._pt_x[idx].setValue(x)
            self._pt_y[idx].setValue(y)
            self._mark_dirty()

    def _on_pick_region(self) -> None:
        self.hide()
        QApplication.processEvents()
        QApplication.processEvents()
        result = pick_region()
        self.show()
        self.raise_()
        self.activateWindow()
        if result is not None:
            self.region_panel.fill_from_pick(
                result.top, result.left, result.width, result.height
            )
            self._mark_dirty()

    # ------------------------------------------------------------------ Log
    def _append_log(self, msg: str) -> None:
        ts = self.log_view.textColor().name()
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(msg + "\n")
        self.log_view.setTextCursor(cursor)
        self.log_view.ensureCursorVisible()

    # ------------------------------------------------------------------ Close
    def closeEvent(self, event) -> None:
        self.scheduler.stop()
        self._save_config()
        event.accept()
