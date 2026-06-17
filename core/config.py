"""Configuration data models and persistence."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

DEFAULT_CONFIG = {
    "scan_interval": 5,
    "wait_interval": 3,
    "keywords": [],
    "refresh_point": {"name": "刷新点", "x": 0, "y": 0},
    "first_line_point": {"name": "首行点", "x": 0, "y": 0},
    "page_click_point": {"name": "页内点", "x": 0, "y": 0},
    "home_point": {"name": "首页点", "x": 0, "y": 0},
    "monitor_region": {"name": "a1", "top": 0, "left": 0, "width": 0, "height": 0},
    "output_json": False,
}


@dataclass
class ClickPoint:
    name: str
    x: int
    y: int

    @classmethod
    def from_dict(cls, d: dict) -> "ClickPoint":
        return cls(
            name=str(d.get("name", "")),
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
        )

    def to_dict(self) -> dict:
        return {"name": self.name, "x": self.x, "y": self.y}


@dataclass
class MonitorRegion:
    name: str
    top: int
    left: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, d: dict) -> "MonitorRegion":
        b = d.get("bbox", d)
        return cls(
            name=str(d.get("name", "")),
            top=int(b.get("top", 0)),
            left=int(b.get("left", 0)),
            width=int(b.get("width", 0)),
            height=int(b.get("height", 0)),
        )

    def to_dict(self) -> dict:
        return {"name": self.name, "bbox": {"top": self.top, "left": self.left, "width": self.width, "height": self.height}}

    @property
    def bbox(self) -> dict:
        return {"top": self.top, "left": self.left, "width": self.width, "height": self.height}


@dataclass
class ScanConfig:
    scan_interval: int = 5
    wait_interval: int = 3
    keywords: List[str] = field(default_factory=list)
    refresh_point: ClickPoint = field(default_factory=lambda: ClickPoint("刷新点", 0, 0))
    first_line_point: ClickPoint = field(default_factory=lambda: ClickPoint("首行点", 0, 0))
    page_click_point: ClickPoint = field(default_factory=lambda: ClickPoint("页内点", 0, 0))
    home_point: ClickPoint = field(default_factory=lambda: ClickPoint("首页点", 0, 0))
    monitor_region: MonitorRegion = field(default_factory=lambda: MonitorRegion("a1", 0, 0, 0, 0))
    output_json: bool = False

    @classmethod
    def default(cls) -> "ScanConfig":
        return cls(
            scan_interval=DEFAULT_CONFIG["scan_interval"],
            wait_interval=DEFAULT_CONFIG["wait_interval"],
            keywords=list(DEFAULT_CONFIG["keywords"]),
            refresh_point=ClickPoint.from_dict(DEFAULT_CONFIG["refresh_point"]),
            first_line_point=ClickPoint.from_dict(DEFAULT_CONFIG["first_line_point"]),
            page_click_point=ClickPoint.from_dict(DEFAULT_CONFIG["page_click_point"]),
            home_point=ClickPoint.from_dict(DEFAULT_CONFIG["home_point"]),
            monitor_region=MonitorRegion.from_dict(DEFAULT_CONFIG["monitor_region"]),
            output_json=bool(DEFAULT_CONFIG["output_json"]),
        )


def load_config(path: Path) -> ScanConfig:
    if not path.exists():
        return ScanConfig.default()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        bak = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(path, bak)
        except OSError:
            pass
        return ScanConfig.default()
    if not isinstance(raw, dict):
        return ScanConfig.default()

    return ScanConfig(
        scan_interval=int(raw.get("scan_interval", DEFAULT_CONFIG["scan_interval"])),
        wait_interval=int(raw.get("wait_interval", DEFAULT_CONFIG["wait_interval"])),
        keywords=[str(k) for k in raw.get("keywords", [])],
        refresh_point=ClickPoint.from_dict(raw.get("refresh_point", DEFAULT_CONFIG["refresh_point"])),
        first_line_point=ClickPoint.from_dict(raw.get("first_line_point", DEFAULT_CONFIG["first_line_point"])),
        page_click_point=ClickPoint.from_dict(raw.get("page_click_point", DEFAULT_CONFIG["page_click_point"])),
        home_point=ClickPoint.from_dict(raw.get("home_point", DEFAULT_CONFIG["home_point"])),
        monitor_region=MonitorRegion.from_dict(raw.get("monitor_region", DEFAULT_CONFIG["monitor_region"])),
        output_json=bool(raw.get("output_json", DEFAULT_CONFIG["output_json"])),
    )


def save_config(cfg: ScanConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "scan_interval": cfg.scan_interval,
        "wait_interval": cfg.wait_interval,
        "keywords": cfg.keywords,
        "refresh_point": cfg.refresh_point.to_dict(),
        "first_line_point": cfg.first_line_point.to_dict(),
        "page_click_point": cfg.page_click_point.to_dict(),
        "home_point": cfg.home_point.to_dict(),
        "monitor_region": cfg.monitor_region.to_dict(),
        "output_json": cfg.output_json,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
