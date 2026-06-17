"""Settings dialog: write JSON output, enable baseline OCR, manage baseline."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from core.config import ScanConfig, region_hash


class ConfigDialog(QDialog):
    """Modal dialog for advanced settings not exposed in the main window.

    The dialog is purely a *view* over a `ScanConfig` instance: it never
    touches `config.json` directly. On accept, the changes are written
    back to the `ScanConfig` object the caller passed in; the caller is
    responsible for persisting it (via the main window's debounced save).
    """

    def __init__(self, config: ScanConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("配置")
        self.setModal(True)
        self.resize(560, 420)

        self._config = config
        # Snapshot of the baseline fields, so "取消" can roll them back.
        self._baseline_text_snapshot = config.baseline_text
        self._baseline_region_hash_snapshot = config.baseline_region_hash
        self._baseline_timestamp_snapshot = config.baseline_timestamp
        # Flag: did the user click "清空基准" inside this dialog? If yes,
        # we honour that change even on "确定"; on "取消" we still roll back
        # the rest, but the explicit "clear" intent is the safer behaviour
        # to keep (mirrors what they just asked for).
        self._baseline_cleared = False

        self._build_ui()
        self._load_from_config()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(12, 12, 12, 12)

        # --- Output options ---
        # ``output_json`` is repurposed: it now means "output intermediate
        # files" (screenshots + JSON Lines). When off, PNG bytes stay in
        # memory and are discarded after each round; JSON records are not
        # written. The field name is preserved for backward compatibility
        # with existing config.json files.
        output_box = QGroupBox("输出选项")
        out_lay = QFormLayout(output_box)
        self.output_json_chk = QCheckBox("输出中间文件（截图保存到 src/pic/，命中记录写入 src/output/）")
        out_lay.addRow(self.output_json_chk)
        root.addWidget(output_box)

        # --- Baseline options ---
        baseline_box = QGroupBox("基准 OCR")
        b_lay = QVBoxLayout(baseline_box)
        b_lay.setSpacing(6)

        self.use_baseline_chk = QCheckBox(
            "启用基准 OCR（每次「开始」时先扫描一次作为基准，后续与基准对比）"
        )
        b_lay.addWidget(self.use_baseline_chk)

        # Baseline metadata
        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)
        meta_row.addWidget(QLabel("基准时间:"))
        self.baseline_ts_label = QLabel("(未建立)")
        self.baseline_ts_label.setStyleSheet("color: #666;")
        meta_row.addWidget(self.baseline_ts_label, 1)

        meta_row.addWidget(QLabel("区域哈希:"))
        self.baseline_hash_label = QLabel("(无)")
        self.baseline_hash_label.setStyleSheet("color: #666; font-family: Consolas, monospace;")
        meta_row.addWidget(self.baseline_hash_label)
        b_lay.addLayout(meta_row)

        # Baseline text preview
        self.baseline_view = QPlainTextEdit()
        self.baseline_view.setReadOnly(True)
        self.baseline_view.setPlaceholderText("(尚未建立基准)")
        mono = QFont("Consolas", 9)
        self.baseline_view.setFont(mono)
        self.baseline_view.setStyleSheet("background:#f4f4f0; color:#333;")
        self.baseline_view.setMaximumBlockCount(1)  # hint: big lines wrap fine
        b_lay.addWidget(self.baseline_view, 1)

        clear_row = QHBoxLayout()
        clear_row.addStretch()
        self.clear_baseline_btn = QPushButton("清空基准")
        self.clear_baseline_btn.clicked.connect(self._on_clear_baseline)
        clear_row.addWidget(self.clear_baseline_btn)
        b_lay.addLayout(clear_row)

        root.addWidget(baseline_box, 1)

        # --- OK / Cancel ---
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btns.button(QDialogButtonBox.Ok).setText("确定")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self._on_reject)
        root.addWidget(btns)

    # ------------------------------------------------------------------ Data
    def _load_from_config(self) -> None:
        """Populate widgets from the config snapshot at dialog open time."""
        self.output_json_chk.setChecked(self._config.output_json)
        self.use_baseline_chk.setChecked(self._config.use_baseline)
        self._refresh_baseline_view()

    def _refresh_baseline_view(self) -> None:
        cfg = self._config
        if cfg.baseline_timestamp:
            self.baseline_ts_label.setText(cfg.baseline_timestamp)
        else:
            self.baseline_ts_label.setText("(未建立)")
        if cfg.baseline_region_hash:
            self.baseline_hash_label.setText(cfg.baseline_region_hash[:8])
        else:
            self.baseline_hash_label.setText("(无)")
        if cfg.baseline_text:
            self.baseline_view.setPlainText(cfg.baseline_text)
        else:
            self.baseline_view.setPlainText("")

    def _on_clear_baseline(self) -> None:
        """Forget the saved baseline. Marks a flag so accept() honours it."""
        self._baseline_cleared = True
        self._config.baseline_text = ""
        self._config.baseline_region_hash = ""
        self._config.baseline_timestamp = ""
        self._refresh_baseline_view()

    def _on_accept(self) -> None:
        """Commit widget values back to the config and close."""
        self._config.output_json = self.output_json_chk.isChecked()
        self._config.use_baseline = self.use_baseline_chk.isChecked()
        # Baseline fields were already mutated in-place by
        # _on_clear_baseline (if used) or left as-is (rolled forward).
        self.accept()

    def _on_reject(self) -> None:
        """Restore the baseline snapshot before closing (other fields stay)."""
        if not self._baseline_cleared:
            self._config.baseline_text = self._baseline_text_snapshot
            self._config.baseline_region_hash = self._baseline_region_hash_snapshot
            self._config.baseline_timestamp = self._baseline_timestamp_snapshot
        self.reject()
