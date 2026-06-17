"""File I/O: screenshots, JSONL records, plain-text logs."""
from __future__ import annotations

import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Union

DAY_FOLDER_RE = re.compile(r"^\d{8}$")

ILLEGAL = re.compile(r'[\\/:\*\?"<>\|\x00-\x1f]')

LOG_RETENTION_DAYS = 7
LOG_DIR = Path("src/log")
OUTPUT_DIR = Path("src/output")
PIC_DIR = Path("src/pic")

# When a YYYYMMDD picture folder has more than this many PNGs, oldest
# files are removed so the folder stays bounded. Set to 0 to disable.
PIC_FOLDER_MAX_FILES = 100

# Picture subfolders older than this many days are removed entirely.
# Set to 0 to disable. The cap is applied per save, and the same value
# is used for subfolder retention below.
PIC_RETENTION_DAYS = 7


def sanitize_filename(name: str) -> str:
    return ILLEGAL.sub("_", name).strip() or "unnamed"


def clean_old_logs() -> None:
    """Remove log files older than LOG_RETENTION_DAYS days."""
    if not LOG_DIR.exists():
        return
    cutoff = time.time() - LOG_RETENTION_DAYS * 86400
    for f in LOG_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
            except OSError:
                pass


def append_log_txt(message: str, ts: Union[datetime, None] = None) -> Path:
    """Append a single line to the daily .txt log file."""
    if ts is None:
        ts = datetime.now()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{ts.strftime('%Y%m%d')}.txt"
    line = f"[{ts.strftime('%H:%M:%S')}] {message}\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(line)
    return path


def _enforce_pic_folder_cap(day_dir: Path) -> int:
    """Trim a YYYYMMDD picture folder to ``PIC_FOLDER_MAX_FILES`` entries.

    Files are removed oldest-first (by mtime). Returns the number of files
    actually deleted. No-op when the cap is disabled or the folder is at
    or below the cap.
    """
    if PIC_FOLDER_MAX_FILES <= 0 or not day_dir.is_dir():
        return 0
    try:
        files = [p for p in day_dir.iterdir() if p.is_file()]
    except OSError:
        return 0
    excess = len(files) - PIC_FOLDER_MAX_FILES
    if excess <= 0:
        return 0
    files.sort(key=lambda p: p.stat().st_mtime)
    deleted = 0
    for victim in files[:excess]:
        try:
            victim.unlink()
            deleted += 1
        except OSError:
            pass
    return deleted


def _enforce_pic_retention(root: Path, now: Union[datetime, None] = None) -> int:
    """Remove YYYYMMDD subfolders older than ``PIC_RETENTION_DAYS`` days.

    Only direct child directories whose name matches ``YYYYMMDD`` are
    considered. Returns the number of subfolders deleted. The current
    day's folder is never removed, even if the math would suggest so.
    """
    if PIC_RETENTION_DAYS <= 0 or not root.is_dir():
        return 0
    if now is None:
        now = datetime.now()
    cutoff = now.timestamp() - PIC_RETENTION_DAYS * 86400
    today_name = now.strftime("%Y%m%d")
    removed = 0
    try:
        children = list(root.iterdir())
    except OSError:
        return 0
    for child in children:
        if not child.is_dir() or not DAY_FOLDER_RE.match(child.name):
            continue
        if child.name == today_name:
            continue
        try:
            if child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
                removed += 1
        except OSError:
            pass
    return removed


def _enforce_pic_caps(day_dir: Path, root: Path) -> None:
    """Apply both per-folder cap and cross-folder retention in one call."""
    _enforce_pic_folder_cap(day_dir)
    _enforce_pic_retention(root)


def save_screenshot(
    png_bytes: bytes,
    region_name: str,
    index: int,
    ts: Union[datetime, None] = None,
    root: Union[str, Path] = PIC_DIR,
) -> Path:
    """Save screenshot PNG to date subfolder, then cap the folder size."""
    if ts is None:
        ts = datetime.now()
    root = Path(root)
    day_dir = root / ts.strftime("%Y%m%d")
    day_dir.mkdir(parents=True, exist_ok=True)
    time_part = ts.strftime("%H%M%S")
    fname = f"{time_part}_{sanitize_filename(region_name)}_{index}.png"
    path = day_dir / fname
    path.write_bytes(png_bytes)
    _enforce_pic_caps(day_dir, root)
    return path


def append_csv_row(*args, **kwargs):  # pragma: no cover
    """Removed: CSV export is no longer produced by the app.

    The function body is gone. Any caller still invoking it will get a
    ``NotImplementedError`` so the regression is loud rather than silent.
    Existing on-disk CSV files under ``src/csv/`` are no longer touched.
    """
    raise NotImplementedError(
        "append_csv_row has been removed: CSV export is no longer produced."
    )


def append_jsonl_record(
    ts: Union[datetime, None] = None,
    region: str = "",
    text: str = "",
    matched_keyword: str = "",
    image_path: str = "",
    root: Union[str, Path] = OUTPUT_DIR,
) -> Path:
    """Append a JSON record to the daily JSONL log."""
    if ts is None:
        ts = datetime.now()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{ts.strftime('%Y%m%d')}.json"
    record = {
        "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "region": region,
        "text": text,
        "matched_keyword": matched_keyword,
        "image_path": image_path,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False))
        f.write("\n")
    return path
