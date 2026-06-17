"""Tests for the ScanConfig data model and persistence."""
from pathlib import Path

from core.config import (
    DEFAULT_CONFIG,
    MonitorRegion,
    ScanConfig,
    ClickPoint,
    load_config,
    save_config,
)


def test_default_config_has_expected_fields():
    cfg = ScanConfig.default()
    assert cfg.scan_interval == 5
    assert cfg.wait_interval == 3
    assert cfg.keywords == []
    assert cfg.monitor_region.name == "a1"
    assert cfg.output_json is False  # disabled by default


def test_click_point_roundtrip(tmp_path: Path):
    cfg_file = tmp_path / "cfg.json"
    cfg = ScanConfig(
        scan_interval=10,
        wait_interval=2,
        keywords=["成功"],
        refresh_point=ClickPoint("刷新点", 100, 200),
        first_line_point=ClickPoint("首行点", 300, 400),
        page_click_point=ClickPoint("页内点", 500, 600),
        home_point=ClickPoint("首页点", 700, 800),
        monitor_region=MonitorRegion("a1", top=10, left=20, width=300, height=200),
        output_json=True,
    )
    save_config(cfg, cfg_file)
    loaded = load_config(cfg_file)
    assert loaded.scan_interval == 10
    assert loaded.wait_interval == 2
    assert loaded.keywords == ["成功"]
    assert loaded.refresh_point.x == 100
    assert loaded.refresh_point.y == 200
    assert loaded.first_line_point.x == 300
    assert loaded.home_point.x == 700
    assert loaded.monitor_region.top == 10
    assert loaded.monitor_region.width == 300
    assert loaded.output_json is True


def test_load_missing_file_returns_default(tmp_path: Path):
    cfg_file = tmp_path / "nope.json"
    cfg = load_config(cfg_file)
    assert cfg.scan_interval == DEFAULT_CONFIG["scan_interval"]
    assert cfg.output_json is False


def test_load_legacy_config_without_output_json(tmp_path: Path):
    """Old config files (no output_json key) should load with the default."""
    cfg_file = tmp_path / "legacy.json"
    cfg_file.write_text(
        '{"scan_interval": 7, "wait_interval": 4, "keywords": []}',
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.scan_interval == 7
    assert cfg.output_json is False


def test_load_corrupt_file_backs_up_and_returns_default(tmp_path: Path):
    cfg_file = tmp_path / "broken.json"
    cfg_file.write_text("{ this is not valid json", encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cfg.scan_interval == DEFAULT_CONFIG["scan_interval"]
    bak = tmp_path / "broken.json.bak"
    assert bak.exists()
    assert bak.read_text(encoding="utf-8") == "{ this is not valid json"
