"""Scan loop scheduler with the new 4-point + 1-region flow."""
from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QEventLoop, QObject, QThread, QTimer, Signal

from core.capture import capture_region, CaptureError
from core.clicker import click_point
from core.config import ScanConfig
from core.matcher import match_keywords, texts_equal
from core.ocr import recognize_text
from core.storage import append_csv_row, append_jsonl_record, append_log_txt, save_screenshot


@dataclass
class ScanResult:
    timestamp: datetime
    region: str
    text: str
    matched_keyword: str
    image_path: str
    success: bool
    error: str = ""


class ScanWorker(QObject):
    finished_round = Signal(list)
    log = Signal(str)

    def __init__(self, config: ScanConfig, stop_event: threading.Event):
        super().__init__()
        self._config = config
        self._stop_event = stop_event
        self._busy = False
        self._last_text = ""

    def run_once(self) -> None:
        if self._busy:
            return
        if self._stop_event.is_set():
            # Stop requested: leave the worker thread's event loop so
            # the QThread can shut down cleanly.
            QThread.currentThread().quit()
            return
        self._busy = True
        try:
            results = self._do_round()
            self.finished_round.emit(results)
        finally:
            self._busy = False
            if self._stop_event.is_set():
                QThread.currentThread().quit()

    def _do_round(self) -> List[ScanResult]:
        ts = datetime.now()
        cfg = self._config

        # Step 1: click refresh point p1
        self.log.emit(f"点击刷新点，等待{cfg.wait_interval}s...")
        append_log_txt(f"点击刷新点，等待{cfg.wait_interval}s...")
        ok, err = click_point(cfg.refresh_point.x, cfg.refresh_point.y)
        if not ok:
            self.log.emit(f"  刷新点点击失败: {err}")
            append_log_txt(f"刷新点点击失败: {err}")

        # Wait T2 for page to refresh
        self._wait(cfg.wait_interval)

        # Step 2: capture + OCR
        region = cfg.monitor_region
        try:
            png = capture_region(region.bbox)
            img_path = str(save_screenshot(png, region.name, 1, ts))
        except CaptureError as e:
            self.log.emit(f"[截图失败] {region.name}: {e}")
            append_log_txt(f"截图失败: {region.name}: {e}")
            return [ScanResult(ts, region.name, "", "", "", False, str(e))]

        text = ""
        try:
            text = recognize_text(png)
        except Exception as e:
            self.log.emit(f"[OCR错误] {e}")
            append_log_txt(f"OCR错误: {e}")
            return [ScanResult(ts, region.name, "", "", "", False, str(e))]

        matched, kw = match_keywords(text, cfg.keywords)

        self.log.emit(f"OCR: {text[:80] or '(空)'}")
        append_log_txt(f"OCR: {text[:80] or '(空)'}")

        # Always skip if text is unchanged (whitespace-insensitive; whether
        # or not it matched a keyword). OCR can shift line breaks or spaces
        # on the same image, so we compare on a normalized form.
        if texts_equal(text, self._last_text):
            self.log.emit("文本未变化，跳过点击，等待下一轮")
            append_log_txt("文本未变化，跳过点击，等待下一轮")
            return [ScanResult(ts, region.name, text, kw, img_path, False)]

        # New text
        self._last_text = text

        if not matched:
            self.log.emit("未命中关键词")
            append_log_txt("未命中关键词")
            return [ScanResult(ts, region.name, text, kw, img_path, False)]

        # matched + new text → write record + click
        self.log.emit(f"命中「{kw}」: 文本已更新")
        append_log_txt(f"命中「{kw}」: 文本已更新")

        append_csv_row(ts, region.name, text, kw)
        if cfg.output_json:
            append_jsonl_record(ts, region.name, text, kw, img_path)
            self.log.emit(f"写入记录: {img_path}")
            append_log_txt(f"写入记录: {img_path}")

        # Click first-line point p2
        self.log.emit(f"点击首行点，等待{cfg.wait_interval}s...")
        append_log_txt(f"点击首行点，等待{cfg.wait_interval}s...")
        ok, err = click_point(cfg.first_line_point.x, cfg.first_line_point.y)
        if not ok:
            self.log.emit(f"  首行点点击失败: {err}")
            append_log_txt(f"首行点点击失败: {err}")
        self._wait(cfg.wait_interval)

        # Click page-click point p3
        self.log.emit(f"点击页内点，等待{cfg.wait_interval}s...")
        append_log_txt(f"点击页内点，等待{cfg.wait_interval}s...")
        ok, err = click_point(cfg.page_click_point.x, cfg.page_click_point.y)
        if not ok:
            self.log.emit(f"  页内点点击失败: {err}")
            append_log_txt(f"页内点点击失败: {err}")
        self._wait(cfg.wait_interval)

        # Click home point p4
        self.log.emit(f"点击首页点，等待{cfg.wait_interval}s...")
        append_log_txt(f"点击首页点，等待{cfg.wait_interval}s...")
        ok, err = click_point(cfg.home_point.x, cfg.home_point.y)
        if not ok:
            self.log.emit(f"  首页点点击失败: {err}")
            append_log_txt(f"首页点点击失败: {err}")
        self._wait(cfg.wait_interval)

        return [ScanResult(ts, region.name, text, kw, img_path, True)]

    def _wait(self, seconds: int) -> None:
        """Sleep while keeping the worker's Qt event loop alive.

        A plain ``threading.Event.wait`` blocks the worker thread's event
        loop, so cross-thread ``QTimer`` callbacks queued during the wait
        (e.g. the scan-interval timer firing on the GUI thread and
        dispatching ``run_once`` into the worker) pile up. Once the wait
        returns they all run back-to-back, defeating the ``_busy`` guard.

        Using a nested ``QEventLoop`` lets queued signals be delivered and
        discarded by ``_busy`` while we still wait the requested time.

        ``stop_event`` short-circuits the wait so stop() can interrupt
        without racing the thread teardown.
        """
        if self._stop_event.is_set():
            return
        loop = QEventLoop()
        QTimer.singleShot(max(1, int(seconds * 1000)), loop.quit)
        # Periodically check stop_event so STOP can interrupt the wait.
        # The QTimer is parented to ``self`` so it is torn down safely
        # with the worker, and its slot only runs on the worker thread.
        stopper = QTimer(self)
        stopper.setInterval(100)
        stopper.timeout.connect(self._check_stop_in_wait, loop=loop)
        stopper.start()
        try:
            loop.exec()
        finally:
            stopper.stop()

    def _check_stop_in_wait(self, loop: QEventLoop) -> None:
        """Slot for the periodic stop-check timer inside ``_wait``."""
        if self._stop_event.is_set():
            loop.quit()


class Scheduler(QObject):
    log = Signal(str)
    status_changed = Signal(bool)

    def __init__(self, config: ScanConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._config = config
        self._timer: Optional[QTimer] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[ScanWorker] = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._timer is not None and self._timer.isActive()

    def update_config(self, config: ScanConfig) -> None:
        self._config = config
        if self._timer is not None:
            self._timer.setInterval(max(1, config.scan_interval) * 1000)

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = QThread()
        self._worker = ScanWorker(self._config, self._stop_event)
        self._worker.moveToThread(self._thread)
        self._worker.log.connect(self._on_log)
        self._worker.finished_round.connect(lambda _: None)
        self._thread.start()
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, self._config.scan_interval) * 1000)
        self._timer.timeout.connect(self._worker.run_once)
        self._timer.start()
        msg = f"[启动] 扫描间隔 {self._config.scan_interval}s，等待时间 {self._config.wait_interval}s"
        self.log.emit(msg)
        append_log_txt(msg)
        self.status_changed.emit(True)

    def stop(self) -> None:
        """Request the worker to stop, then wait for the QThread to exit.

        We never destroy the QThread object while the worker is still
        running. Instead:

        1. Set ``stop_event`` and stop the scan-interval timer so no new
           rounds are kicked off.
        2. The worker's ``_wait`` notices the event within ~100ms and
           short-circuits.
        3. The worker's next ``run_once`` (or the tail of the current
           round) sees the event, emits ``finished_round`` and quits the
           QThread's event loop.
        4. We ``wait`` for the thread to actually finish, then release
           QObject references on the GUI thread.
        """
        if not self.is_running:
            return
        timer = self._timer
        thread = self._thread
        self._stop_event.set()
        if timer is not None:
            timer.stop()
        if thread is not None:
            # Wait for the worker to finish its current round and quit
            # the QThread's event loop. Bounded so a regression cannot
            # hang the GUI forever.
            if not thread.wait(5000):
                # Hard fallback: the worker is wedged. Terminate is
                # unsafe in general, but here the alternative is a
                # frozen UI, so accept the risk and clean up.
                thread.terminate()
                thread.wait(2000)
        # Only now that the thread is fully stopped, drop the references.
        self._timer = None
        self._thread = None
        self._worker = None
        msg = "[停止] 已停止监控"
        self.log.emit(msg)
        append_log_txt(msg)
        self.status_changed.emit(False)

    def _on_log(self, msg: str) -> None:
        self.log.emit(msg)
