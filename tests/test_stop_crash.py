"""Regression: clicking STOP must not crash the GUI."""
import sys
import time
import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

import core.scheduler as sched_mod
from core.scheduler import Scheduler
from core.config import ScanConfig, ClickPoint, MonitorRegion


@pytest.fixture
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a


def _make_cfg() -> ScanConfig:
    return ScanConfig(
        scan_interval=1,
        wait_interval=1,
        keywords=["命中"],
        refresh_point=ClickPoint("刷新点", 10, 10),
        first_line_point=ClickPoint("首行点", 20, 20),
        page_click_point=ClickPoint("页内点", 30, 30),
        home_point=ClickPoint("首页点", 40, 40),
        monitor_region=MonitorRegion("a1", top=0, left=0, width=100, height=100),
    )


def _pump(app, duration_s: float, slice_ms: int = 20) -> None:
    end = time.time() + duration_s
    while time.time() < end:
        app.processEvents()
        time.sleep(slice_ms / 1000.0)


def test_stop_during_busy_round_does_not_crash(app, tmp_path, monkeypatch):
    """stop() while a round is mid-flight must not crash the process."""
    import core.storage as storage_mod
    monkeypatch.setattr(storage_mod, "LOG_DIR", tmp_path / "log")
    monkeypatch.setattr(storage_mod, "CSV_DIR", tmp_path / "csv")
    monkeypatch.setattr(storage_mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(storage_mod, "PIC_DIR", tmp_path / "pic")
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 0)
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 0)

    def slow_click(x, y):
        time.sleep(0.05)
        return True, ""

    def slow_capture(region):
        time.sleep(0.05)
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8

    def slow_ocr(png):
        time.sleep(0.05)
        return "命中 文本"

    monkeypatch.setattr(sched_mod, "click_point", slow_click)
    monkeypatch.setattr(sched_mod, "capture_region", slow_capture)
    monkeypatch.setattr(sched_mod, "recognize_text", slow_ocr)
    monkeypatch.setattr(sched_mod, "save_screenshot",
                        lambda *a, **k: tmp_path / "fake.png")
    monkeypatch.setattr(sched_mod, "append_csv_row", lambda *a, **k: tmp_path / "fake.csv")
    monkeypatch.setattr(sched_mod, "append_jsonl_record", lambda *a, **k: tmp_path / "fake.json")
    monkeypatch.setattr(sched_mod, "append_log_txt", lambda *a, **k: tmp_path / "log.txt")

    sched = Scheduler(_make_cfg())
    status_history = []
    sched.status_changed.connect(lambda running: status_history.append(running))
    log_messages = []
    sched.log.connect(lambda m: log_messages.append(m))

    try:
        sched.start()
        assert sched.is_running

        # Trigger stop ~200ms in, while a round is in flight
        QTimer.singleShot(200, sched.stop)

        deadline = time.time() + 6.0
        while time.time() < deadline and sched.is_running:
            _pump(app, 0.05)

        assert not sched.is_running, "Scheduler did not report stopped"
        assert status_history and status_history[-1] is False
        assert any("已停止监控" in m for m in log_messages), log_messages
        assert sched._thread is None
        assert sched._worker is None
        assert sched._timer is None
    finally:
        if sched.is_running:
            sched.stop()


@pytest.mark.parametrize("delay_ms", [50, 150, 300, 500])
def test_stop_at_various_points_does_not_crash(app, tmp_path, monkeypatch, delay_ms):
    """stop() called at any point in a round must not crash."""
    import core.storage as storage_mod
    monkeypatch.setattr(storage_mod, "LOG_DIR", tmp_path / "log")
    monkeypatch.setattr(storage_mod, "CSV_DIR", tmp_path / "csv")
    monkeypatch.setattr(storage_mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(storage_mod, "PIC_DIR", tmp_path / "pic")
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 0)
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 0)

    def slow_click(x, y):
        time.sleep(0.05)
        return True, ""

    def slow_capture(region):
        time.sleep(0.05)
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * 8

    def slow_ocr(png):
        time.sleep(0.05)
        return "命中 文本"

    monkeypatch.setattr(sched_mod, "click_point", slow_click)
    monkeypatch.setattr(sched_mod, "capture_region", slow_capture)
    monkeypatch.setattr(sched_mod, "recognize_text", slow_ocr)
    monkeypatch.setattr(sched_mod, "save_screenshot",
                        lambda *a, **k: tmp_path / "fake.png")
    monkeypatch.setattr(sched_mod, "append_csv_row", lambda *a, **k: tmp_path / "fake.csv")
    monkeypatch.setattr(sched_mod, "append_jsonl_record", lambda *a, **k: tmp_path / "fake.json")
    monkeypatch.setattr(sched_mod, "append_log_txt", lambda *a, **k: tmp_path / "log.txt")

    sched = Scheduler(_make_cfg())
    try:
        sched.start()
        QTimer.singleShot(delay_ms, sched.stop)
        deadline = time.time() + 6.0
        while time.time() < deadline and sched.is_running:
            _pump(app, 0.05)
        assert not sched.is_running, f"stop did not finish within 6s (delay={delay_ms})"
    finally:
        if sched.is_running:
            sched.stop()
