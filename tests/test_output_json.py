"""Verify output_json controls whether intermediate files are written.

``output_json`` was repurposed: it now means "output intermediate files",
gating both the per-round PNG save (src/pic/...) and the JSON Lines
record (src/output/...). When off, screenshots stay in memory and are
discarded after OCR; JSON records are not written at all.
"""
import sys
import time
from datetime import datetime
from pathlib import Path

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


def _pump(app, duration_s: float, slice_ms: int = 20) -> None:
    end = time.time() + duration_s
    while time.time() < end:
        app.processEvents()
        time.sleep(slice_ms / 1000.0)


def _make_cfg(output_json: bool, scan_interval: int = 1) -> ScanConfig:
    return ScanConfig(
        scan_interval=scan_interval,
        wait_interval=1,
        keywords=["命中"],
        output_json=output_json,
        refresh_point=ClickPoint("刷新点", 10, 10),
        first_line_point=ClickPoint("首行点", 20, 20),
        page_click_point=ClickPoint("页内点", 30, 30),
        home_point=ClickPoint("首页点", 40, 40),
        monitor_region=MonitorRegion("a1", top=0, left=0, width=100, height=100),
    )


def _patch_scheduler(monkeypatch, tmp_path):
    import core.storage as storage_mod
    monkeypatch.setattr(storage_mod, "LOG_DIR", tmp_path / "log")
    monkeypatch.setattr(storage_mod, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(storage_mod, "PIC_DIR", tmp_path / "pic")
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 0)
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 0)
    monkeypatch.setattr(sched_mod, "click_point", lambda x, y: (True, ""))
    monkeypatch.setattr(
        sched_mod, "capture_region",
        lambda region: b"\x89PNG\r\n\x1a\n" + b"\x00" * 8,
    )
    monkeypatch.setattr(sched_mod, "recognize_text", lambda png: "命中 文本")
    monkeypatch.setattr(
        sched_mod, "save_screenshot",
        lambda *a, **k: tmp_path / "pic_fake.png",
    )
    monkeypatch.setattr(
        sched_mod, "append_jsonl_record",
        lambda *a, **k: tmp_path / "out_fake.json",
    )
    monkeypatch.setattr(
        sched_mod, "append_log_txt", lambda *a, **k: tmp_path / "log.txt",
    )


def test_output_json_false_does_not_save_screenshot(app, tmp_path, monkeypatch):
    """When output_json is False, save_screenshot must not be called
    and the JSON record must not be written — only the in-memory PNG
    is used for OCR, then discarded."""
    _patch_scheduler(monkeypatch, tmp_path)
    save_calls = []
    monkeypatch.setattr(
        sched_mod, "save_screenshot",
        lambda *a, **k: save_calls.append(a) or (tmp_path / "should_not_exist.png"),
    )
    jsonl_calls = []
    monkeypatch.setattr(
        sched_mod, "append_jsonl_record",
        lambda *a, **k: jsonl_calls.append(a) or (tmp_path / "should_not_exist.json"),
    )

    sched = Scheduler(_make_cfg(output_json=False))
    log_messages = []
    sched.log.connect(log_messages.append)
    try:
        sched.start()
        # One round should be enough; force it directly.
        sched._worker.run_once()
        # Wait for it to finish.
        deadline = time.time() + 2.0
        while time.time() < deadline and sched._worker._busy:
            _pump(app, 0.05)
    finally:
        sched.stop()

    assert save_calls == [], f"save_screenshot was called: {save_calls}"
    assert jsonl_calls == [], f"append_jsonl_record was called: {jsonl_calls}"
    # The log should mention the no-output path
    assert any("未开启中间文件输出" in m for m in log_messages), log_messages


def test_output_json_true_saves_screenshot_and_json(app, tmp_path, monkeypatch):
    """When output_json is True, both save_screenshot and append_jsonl_record
    must run on a hit round."""
    _patch_scheduler(monkeypatch, tmp_path)
    save_calls = []
    monkeypatch.setattr(
        sched_mod, "save_screenshot",
        lambda *a, **k: save_calls.append(a) or (tmp_path / "should_exist.png"),
    )
    jsonl_calls = []
    monkeypatch.setattr(
        sched_mod, "append_jsonl_record",
        lambda *a, **k: jsonl_calls.append(a) or (tmp_path / "should_exist.json"),
    )

    sched = Scheduler(_make_cfg(output_json=True))
    try:
        sched.start()
        sched._worker.run_once()
        deadline = time.time() + 2.0
        while time.time() < deadline and sched._worker._busy:
            _pump(app, 0.05)
    finally:
        sched.stop()

    assert len(save_calls) == 1, f"save_screenshot was called {len(save_calls)} times: {save_calls}"
    assert len(jsonl_calls) == 1, f"append_jsonl_record was called {len(jsonl_calls)} times"
    # Hit message should be present
    assert jsonl_calls[0][3] == "命中"  # the keyword arg


def test_baseline_round_does_not_save_screenshot(app, tmp_path, monkeypatch):
    """Even when output_json is True, the baseline-establishment round
    must not save a screenshot — it only needs the OCR text."""
    _patch_scheduler(monkeypatch, tmp_path)
    save_calls = []
    monkeypatch.setattr(
        sched_mod, "save_screenshot",
        lambda *a, **k: save_calls.append(a) or (tmp_path / "should_not_exist.png"),
    )

    cfg = _make_cfg(output_json=True)
    cfg.use_baseline = True
    cfg.monitor_region = MonitorRegion("a1", top=0, left=0, width=100, height=100)
    sched = Scheduler(cfg)
    log_messages = []
    sched.log.connect(log_messages.append)
    try:
        sched.start()
        sched._worker.run_once()  # baseline round
        deadline = time.time() + 2.0
        while time.time() < deadline and sched._worker._busy:
            _pump(app, 0.05)
    finally:
        sched.stop()

    assert save_calls == [], f"baseline round saved a screenshot: {save_calls}"
    assert any("基准确立完成" in m for m in log_messages), log_messages
