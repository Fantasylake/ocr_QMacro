import json
import time
from datetime import datetime
from pathlib import Path
import pytest
import core.storage as storage_mod
from core.storage import save_screenshot, append_csv_row, append_jsonl_record, sanitize_filename


def test_sanitize_filename_strips_illegal_chars():
    assert sanitize_filename("a/b\\c:d*e?f\"g<h>i|j") == "a_b_c_d_e_f_g_h_i_j"
    assert sanitize_filename("正常名称") == "正常名称"


def test_save_screenshot_creates_file(tmp_path: Path):
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    ts = datetime(2026, 6, 17, 13, 25, 10)
    path = save_screenshot(png_bytes, "状态栏", 1, ts, root=tmp_path)
    assert path.exists()
    assert path.read_bytes() == png_bytes
    assert "20260617" in str(path)
    assert "132510" in str(path)
    assert "_状态栏_1.png" in str(path)


def test_append_csv_row_is_removed():
    """CSV export is no longer produced; the function must raise loudly
    so any leftover caller is caught immediately."""
    with pytest.raises(NotImplementedError):
        append_csv_row(datetime.now(), "区域", "文本", "关键词")


def test_append_jsonl_record_creates_file(tmp_path: Path):
    ts = datetime(2026, 6, 17, 13, 25, 10)
    path = append_jsonl_record(
        ts, "状态栏", "操作成功", "成功",
        image_path="src/pic/20260617/132510_状态栏_1.png",
        root=tmp_path,
    )
    assert path.exists()
    assert path.name == "20260617.json"
    # Each line is a valid JSON object
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record == {
        "timestamp": "2026-06-17 13:25:10",
        "region": "状态栏",
        "text": "操作成功",
        "matched_keyword": "成功",
        "image_path": "src/pic/20260617/132510_状态栏_1.png",
    }


def test_append_jsonl_record_appends_one_per_line(tmp_path: Path):
    ts1 = datetime(2026, 6, 17, 13, 25, 10)
    ts2 = datetime(2026, 6, 17, 13, 25, 15)
    append_jsonl_record(ts1, "区域A", "命中一", "一", "img1.png", root=tmp_path)
    append_jsonl_record(ts2, "区域B", "命中二", "二", "img2.png", root=tmp_path)
    path = tmp_path / "20260617.json"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["region"] == "区域A"
    assert records[1]["region"] == "区域B"
    assert records[1]["matched_keyword"] == "二"


def test_append_jsonl_record_handles_unicode(tmp_path: Path):
    """Chinese text must be preserved (not escaped) in the JSON file."""
    ts = datetime(2026, 6, 17, 13, 25, 10)
    append_jsonl_record(ts, "状态栏", "操作成功！", "成功", "x.png", root=tmp_path)
    path = tmp_path / "20260617.json"
    content = path.read_text(encoding="utf-8")
    assert "操作成功" in content  # raw chars, not \uXXXX escapes


def test_save_screenshot_caps_folder_at_max_files(tmp_path: Path, monkeypatch):
    """Writing the (cap+1)th file should leave exactly PIC_FOLDER_MAX_FILES
    files in the day folder, with the newest one preserved."""
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 10)
    day = tmp_path / "20260617"
    base_ts = datetime(2026, 6, 17, 9, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    for i in range(11):
        ts = datetime(2026, 6, 17, 9, 0, i)  # 0..10s
        save_screenshot(png, "a1", 1, ts, root=tmp_path)
        # Make sure mtimes are strictly increasing so the sort is stable
        time.sleep(0.005)
    files = sorted(p for p in day.iterdir() if p.is_file())
    assert len(files) == 10
    # The newest (i=10) must be the one kept
    assert files[-1].name.endswith("_a1_1.png")
    # And the very first (i=0) must have been pruned
    assert not any(f.name.startswith("090000_") for f in files)


def test_save_screenshot_keeps_all_below_cap(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 10)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    for i in range(5):
        save_screenshot(png, "a1", 1, datetime(2026, 6, 17, 9, 0, i), root=tmp_path)
    files = list((tmp_path / "20260617").iterdir())
    assert len(files) == 5


def test_save_screenshot_cap_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 0)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    for i in range(15):
        save_screenshot(png, "a1", 1, datetime(2026, 6, 17, 9, 0, i), root=tmp_path)
    files = list((tmp_path / "20260617").iterdir())
    assert len(files) == 15  # cap disabled → nothing pruned


def test_save_screenshot_cap_scoped_to_day_folder(tmp_path: Path, monkeypatch):
    """Pruning one day's folder must not touch other days."""
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 3)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    for d in (16, 17, 18):
        for i in range(4):
            save_screenshot(png, "a1", 1, datetime(2026, 6, d, 9, 0, i), root=tmp_path)
            time.sleep(0.002)
    assert len(list((tmp_path / "20260616").iterdir())) == 3
    assert len(list((tmp_path / "20260617").iterdir())) == 3
    assert len(list((tmp_path / "20260618").iterdir())) == 3


def test_pic_retention_removes_old_day_folders(tmp_path: Path, monkeypatch):
    """Day folders whose mtime is older than PIC_RETENTION_DAYS are removed."""
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 7)
    now = datetime(2026, 6, 17, 12, 0, 0)
    # Create day folders 1..15 days old, plus today
    for days_ago in range(0, 16):
        d = datetime(2026, 6, 17 - days_ago)
        folder = tmp_path / d.strftime("%Y%m%d")
        folder.mkdir()
        # set mtime = now - days_ago*86400
        mtime = now.timestamp() - days_ago * 86400
        import os
        os.utime(folder, (mtime, mtime))
    removed = storage_mod._enforce_pic_retention(tmp_path, now=now)
    assert removed == 8  # days 8..15 inclusive
    remaining = sorted(p.name for p in tmp_path.iterdir() if p.is_dir())
    # Today + the 7 most-recent prior days survive (0..7 days ago)
    assert remaining == [
        "20260610", "20260611", "20260612", "20260613", "20260614",
        "20260615", "20260616", "20260617",
    ]


def test_pic_retention_never_removes_today(tmp_path: Path, monkeypatch):
    """Even if mtime says otherwise, today's folder must not be deleted."""
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 7)
    now = datetime(2026, 6, 17, 12, 0, 0)
    today = tmp_path / "20260617"
    today.mkdir()
    # Pretend it is ancient
    import os
    os.utime(today, (now.timestamp() - 30 * 86400,) * 2)
    storage_mod._enforce_pic_retention(tmp_path, now=now)
    assert today.exists()


def test_pic_retention_skips_non_day_folders(tmp_path: Path, monkeypatch):
    """Subfolders whose name is not YYYYMMDD must be ignored."""
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 7)
    now = datetime(2026, 6, 17, 12, 0, 0)
    misc = tmp_path / "thumbnails"
    misc.mkdir()
    import os
    os.utime(misc, (now.timestamp() - 365 * 86400,) * 2)
    storage_mod._enforce_pic_retention(tmp_path, now=now)
    assert misc.exists()


def test_pic_retention_disabled(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 0)
    now = datetime(2026, 6, 17, 12, 0, 0)
    for days_ago in range(0, 12):
        d = datetime(2026, 6, 17 - days_ago)
        (tmp_path / d.strftime("%Y%m%d")).mkdir()
    storage_mod._enforce_pic_retention(tmp_path, now=now)
    assert sum(1 for _ in tmp_path.iterdir() if _.is_dir()) == 12


def test_save_screenshot_runs_retention(tmp_path: Path, monkeypatch):
    """save_screenshot must trigger both the per-folder cap and retention."""
    monkeypatch.setattr(storage_mod, "PIC_FOLDER_MAX_FILES", 5)
    monkeypatch.setattr(storage_mod, "PIC_RETENTION_DAYS", 7)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    now = datetime(2026, 6, 17, 12, 0, 0)
    # Seed an ancient folder
    old = tmp_path / "20260501"
    old.mkdir()
    import os
    os.utime(old, (now.timestamp() - 30 * 86400,) * 2)
    save_screenshot(png, "a1", 1, now, root=tmp_path)
    assert not old.exists()
    assert (tmp_path / "20260617").exists()
