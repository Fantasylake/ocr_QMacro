"""Scan loop scheduler with the new 4-point + 1-region flow."""
from __future__ import annotations

import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import List, Optional

from PySide6.QtCore import QEventLoop, QObject, QThread, QTimer, Signal

from core.capture import capture_region, CaptureError
from core.clicker import click_point
from core.config import ScanConfig, region_hash
from core.matcher import match_keywords, normalize_text, texts_equal
from core.ocr import recognize_text
from core.storage import append_jsonl_record, append_log_txt, save_screenshot


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
    # Emitted when the worker updates baseline state. Carries the new
    # (use_baseline, baseline_text, baseline_region_hash, baseline_timestamp)
    # values; the GUI thread is expected to persist them to config.json.
    baseline_updated = Signal(bool, str, str, str)

    def __init__(self, config: ScanConfig, stop_event: threading.Event):
        super().__init__()
        self._config = config
        self._stop_event = stop_event
        self._busy = False
        # ``_last_text`` is the per-process running value (mirrors the
        # previous behaviour for the non-baseline path). When
        # ``use_baseline`` is on, comparison is against ``_baseline_text``
        # instead, which mirrors ``config.baseline_text`` at start time.
        self._last_text = ""
        self._baseline_text = ""
        self._baseline_established = False
        self._baseline_failed = False  # sticky: don't retry every round

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

        # Step 0 (one-shot): establish baseline at the start of a run.
        # We do this *before* clicking p1 so the baseline reflects the
        # actual current page state, not a state we just triggered.
        if cfg.use_baseline and not self._baseline_established and not self._baseline_failed:
            return self._establish_baseline(ts)

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
        except CaptureError as e:
            self.log.emit(f"[截图失败] {region.name}: {e}")
            append_log_txt(f"截图失败: {region.name}: {e}")
            return [ScanResult(ts, region.name, "", "", "", False, str(e))]

        # Persist the screenshot only if intermediate-file output is on.
        # Otherwise the PNG bytes stay in memory and are discarded after
        # this round — disk never sees them.
        img_path = ""
        if cfg.output_json:
            try:
                img_path = str(save_screenshot(png, region.name, 1, ts))
            except OSError as e:
                self.log.emit(f"[保存截图失败] {e}")
                append_log_txt(f"保存截图失败: {e}")
                img_path = ""

        text = ""
        try:
            text = recognize_text(png)
        except Exception as e:
            self.log.emit(f"[OCR错误] {e}")
            append_log_txt(f"OCR错误: {e}")
            return [ScanResult(ts, region.name, "", "", img_path, False, str(e))]

        matched, kw = match_keywords(text, cfg.keywords)

        self.log.emit(f"OCR: {text[:80] or '(空)'}")
        append_log_txt(f"OCR: {text[:80] or '(空)'}")

        # Step 2.5: region changed since baseline was set → auto-reset.
        if cfg.use_baseline and cfg.baseline_region_hash and region_hash(region) != cfg.baseline_region_hash:
            self.log.emit("监控区域已变更，重建基准")
            append_log_txt("监控区域已变更，重建基准")
            self._baseline_text = text
            self._baseline_established = True
            self._baseline_failed = False
            ts_iso = ts.isoformat(timespec="seconds")
            cfg.baseline_text = text
            cfg.baseline_region_hash = region_hash(region)
            cfg.baseline_timestamp = ts_iso
            self.baseline_updated.emit(True, text, cfg.baseline_region_hash, ts_iso)
            return [ScanResult(ts, region.name, text, "", img_path, False, "baseline-rebuilt")]

        # Pick the reference text: baseline if enabled, else last round.
        if cfg.use_baseline:
            ref = self._baseline_text
            ref_label = "基准"
        else:
            ref = self._last_text
            ref_label = "上一轮"

        # Always skip if text is unchanged (whitespace-insensitive; whether
        # or not it matched a keyword). OCR can shift line breaks or spaces
        # on the same image, so we compare on a normalized form.
        if texts_equal(text, ref):
            self.log.emit(f"文本未变化（对比{ref_label}），跳过点击，等待下一轮")
            append_log_txt(f"文本未变化（对比{ref_label}），跳过点击，等待下一轮")
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

        if cfg.output_json:
            if img_path:
                append_jsonl_record(ts, region.name, text, kw, img_path)
                self.log.emit(f"写入记录: {img_path}")
                append_log_txt(f"写入记录: {img_path}")
            else:
                # Screenshot save failed earlier; still log the hit.
                self.log.emit("命中但无图片路径，跳过 JSON 写入")
                append_log_txt("命中但无图片路径，跳过 JSON 写入")
        else:
            self.log.emit("命中（未开启中间文件输出）")
            append_log_txt("命中（未开启中间文件输出）")

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
        # PySide6 Signal.connect() does not accept ``loop=`` (that was a
        # PyQt4-era keyword). Bind the loop argument via functools.partial
        # instead so the slot receives it positionally.
        stopper.timeout.connect(partial(self._check_stop_in_wait, loop))
        stopper.start()
        try:
            loop.exec()
        finally:
            stopper.stop()

    def _check_stop_in_wait(self, loop: QEventLoop) -> None:
        """Slot for the periodic stop-check timer inside ``_wait``."""
        if self._stop_event.is_set():
            loop.quit()

    def _establish_baseline(self, ts: datetime) -> List[ScanResult]:
        """One-shot: capture + OCR the current page and store as baseline.

        Called from ``_do_round`` *before* any click, so the baseline
        reflects the actual user-visible state at the moment monitoring
        starts. On failure we set ``_baseline_failed`` (sticky) and
        downgrade ``use_baseline`` to False for the rest of the run.

        Baseline establishment does not save an intermediate screenshot:
        the PNG is only kept in memory for the OCR call. Whether the
        user wants the on-disk trail is governed by ``output_json`` like
        every other round, but for the baseline round itself there is
        no ``img_path`` to log — we only persist the OCR text.
        """
        cfg = self._config
        region = cfg.monitor_region
        self.log.emit(f"[基准确立] 开始扫描区域 {region.name}...")
        append_log_txt(f"[基准确立] 开始扫描区域 {region.name}...")

        try:
            png = capture_region(region.bbox)
        except CaptureError as e:
            self.log.emit(f"[基准确立失败-截图] {e}，自动关闭基准模式")
            append_log_txt(f"基准确立失败-截图: {e}，自动关闭基准模式")
            self._baseline_failed = True
            cfg.use_baseline = False
            return [ScanResult(ts, region.name, "", "", "", False, f"baseline-capture-failed: {e}")]

        try:
            text = recognize_text(png)
        except Exception as e:
            self.log.emit(f"[基准确立失败-OCR] {e}，自动关闭基准模式")
            append_log_txt(f"基准确立失败-OCR: {e}，自动关闭基准模式")
            self._baseline_failed = True
            cfg.use_baseline = False
            return [ScanResult(ts, region.name, "", "", "", False, f"baseline-ocr-failed: {e}")]

        normalized = normalize_text(text)
        ts_iso = ts.isoformat(timespec="seconds")
        rhash = region_hash(region)
        self._baseline_text = normalized
        self._baseline_established = True
        cfg.baseline_text = normalized
        cfg.baseline_region_hash = rhash
        cfg.baseline_timestamp = ts_iso

        snippet = (normalized[:80] + "...") if len(normalized) > 80 else normalized
        self.log.emit(f"[基准确立完成] 长度={len(normalized)} 预览: {snippet or '(空)'}")
        append_log_txt(f"基准确立完成: 长度={len(normalized)} 预览: {snippet or '(空)'}")
        self.baseline_updated.emit(True, normalized, rhash, ts_iso)

        # First round: text equals itself, treat as "no change yet".
        return [ScanResult(ts, region.name, text, "", "", False, "baseline-initialized")]

    def reset_baseline(self) -> None:
        """Forget the in-memory baseline so the next round rebuilds it."""
        self._baseline_text = ""
        self._baseline_established = False
        self._baseline_failed = False


class Scheduler(QObject):
    log = Signal(str)
    status_changed = Signal(bool)
    # Forwarded from ScanWorker.baseline_updated. GUI listens and persists.
    baseline_updated = Signal(bool, str, str, str)

    def __init__(self, config: ScanConfig, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._config = config
        self._last_region_hash: str = region_hash(config.monitor_region)
        self._timer: Optional[QTimer] = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[ScanWorker] = None
        self._stop_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._timer is not None and self._timer.isActive()

    def update_config(self, config: ScanConfig) -> None:
        """Apply a new config to the running scheduler.

        - Update timer interval.
        - Detect monitor region changes: clear baseline (both in-memory
          and in the config we hold) so the next round rebuilds it.
        """
        self._config = config
        if self._timer is not None:
            self._timer.setInterval(max(1, config.scan_interval) * 1000)

        new_hash = region_hash(config.monitor_region)
        if new_hash != self._last_region_hash:
            self._last_region_hash = new_hash
            config.baseline_text = ""
            config.baseline_region_hash = ""
            config.baseline_timestamp = ""
            if self._worker is not None:
                self._worker.reset_baseline()

    def clear_baseline(self) -> None:
        """Forget any saved baseline. Safe to call while running."""
        self._config.baseline_text = ""
        self._config.baseline_region_hash = ""
        self._config.baseline_timestamp = ""
        if self._worker is not None:
            self._worker.reset_baseline()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = QThread()
        self._worker = ScanWorker(self._config, self._stop_event)
        self._worker.moveToThread(self._thread)
        self._worker.log.connect(self._on_log)
        self._worker.finished_round.connect(lambda _: None)
        self._worker.baseline_updated.connect(self.baseline_updated)
        # Track region hash so update_config() can detect changes later.
        self._last_region_hash = region_hash(self._config.monitor_region)
        self._thread.start()
        self._timer = QTimer(self)
        self._timer.setInterval(max(1, self._config.scan_interval) * 1000)
        self._timer.timeout.connect(self._worker.run_once)
        self._timer.start()
        if self._config.use_baseline:
            mode_msg = "基准模式"
        else:
            mode_msg = "普通模式"
        msg = f"[启动] 扫描间隔 {self._config.scan_interval}s，等待时间 {self._config.wait_interval}s，{mode_msg}"
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
