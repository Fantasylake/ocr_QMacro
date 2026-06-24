"""Configuration data models and persistence."""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from core.paths import is_frozen

DEFAULT_CONFIG = {
    "scan_interval": 5,
    "wait_interval": 3,
    "keywords": [
        "通风天窗", "通风气楼", "薄型天窗", "电动消防联动排烟天窗",
        "流线型通风器", "三角型排烟天窗", "通风天窗厂家",
        "通风气楼厂家", "电动排烟天窗厂家",
    ],
    "exclude_keywords": ["自己的厂房"],
    "refresh_point": {"name": "刷新页面点", "x": 0, "y": 0},
    "first_line_point": {"name": "首行业务点", "x": 0, "y": 0},
    "page_click_point": {"name": "立即接单点", "x": 0, "y": 0},
    "page_click_point_2": {"name": "确认接单点", "x": 0, "y": 0},
    "home_point": {"name": "返回首页点", "x": 0, "y": 0},
    "monitor_region": {"name": "a1", "top": 0, "left": 0, "width": 0, "height": 0},
    "output_json": False,
    "use_baseline": False,
    "baseline_text": "",
    "baseline_region_hash": "",
    "baseline_timestamp": "",
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
    exclude_keywords: List[str] = field(default_factory=list)
    refresh_point: ClickPoint = field(default_factory=lambda: ClickPoint("刷新页面点", 0, 0))
    first_line_point: ClickPoint = field(default_factory=lambda: ClickPoint("首行业务点", 0, 0))
    page_click_point: ClickPoint = field(default_factory=lambda: ClickPoint("立即接单点", 0, 0))
    page_click_point_2: ClickPoint = field(default_factory=lambda: ClickPoint("确认接单点", 0, 0))
    home_point: ClickPoint = field(default_factory=lambda: ClickPoint("返回首页点", 0, 0))
    monitor_region: MonitorRegion = field(default_factory=lambda: MonitorRegion("a1", 0, 0, 0, 0))
    output_json: bool = False
    use_baseline: bool = False
    baseline_text: str = ""
    baseline_region_hash: str = ""
    baseline_timestamp: str = ""

    @classmethod
    def default(cls) -> "ScanConfig":
        return cls(
            scan_interval=DEFAULT_CONFIG["scan_interval"],
            wait_interval=DEFAULT_CONFIG["wait_interval"],
            keywords=list(DEFAULT_CONFIG["keywords"]),
            exclude_keywords=list(DEFAULT_CONFIG["exclude_keywords"]),
            refresh_point=ClickPoint.from_dict(DEFAULT_CONFIG["refresh_point"]),
            first_line_point=ClickPoint.from_dict(DEFAULT_CONFIG["first_line_point"]),
            page_click_point=ClickPoint.from_dict(DEFAULT_CONFIG["page_click_point"]),
            page_click_point_2=ClickPoint.from_dict(DEFAULT_CONFIG["page_click_point_2"]),
            home_point=ClickPoint.from_dict(DEFAULT_CONFIG["home_point"]),
            monitor_region=MonitorRegion.from_dict(DEFAULT_CONFIG["monitor_region"]),
            output_json=bool(DEFAULT_CONFIG["output_json"]),
            use_baseline=bool(DEFAULT_CONFIG["use_baseline"]),
            baseline_text=str(DEFAULT_CONFIG["baseline_text"]),
            baseline_region_hash=str(DEFAULT_CONFIG["baseline_region_hash"]),
            baseline_timestamp=str(DEFAULT_CONFIG["baseline_timestamp"]),
        )


def _bundled_template_path() -> Optional[Path]:
    """Path to the read-only template shipped inside a frozen build."""
    if not is_frozen():
        return None
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is None:
        return None
    template = Path(meipass) / "config.template.json"
    return template if template.exists() else None


def _seed_config_from_template(path: Path) -> bool:
    """Copy the bundled template to ``path`` on first run. Returns success."""
    template = _bundled_template_path()
    if template is None:
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template, path)
        return True
    except OSError:
        return False


def load_config(path: Path) -> ScanConfig:
    if not path.exists():
        if not _seed_config_from_template(path):
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
        exclude_keywords=[str(k) for k in raw.get("exclude_keywords", [])],
        refresh_point=ClickPoint.from_dict(raw.get("refresh_point", DEFAULT_CONFIG["refresh_point"])),
        first_line_point=ClickPoint.from_dict(raw.get("first_line_point", DEFAULT_CONFIG["first_line_point"])),
        page_click_point=ClickPoint.from_dict(raw.get("page_click_point", DEFAULT_CONFIG["page_click_point"])),
        page_click_point_2=ClickPoint.from_dict(raw.get("page_click_point_2", DEFAULT_CONFIG["page_click_point_2"])),
        home_point=ClickPoint.from_dict(raw.get("home_point", DEFAULT_CONFIG["home_point"])),
        monitor_region=MonitorRegion.from_dict(raw.get("monitor_region", DEFAULT_CONFIG["monitor_region"])),
        output_json=bool(raw.get("output_json", DEFAULT_CONFIG["output_json"])),
        use_baseline=bool(raw.get("use_baseline", DEFAULT_CONFIG["use_baseline"])),
        baseline_text=str(raw.get("baseline_text", DEFAULT_CONFIG["baseline_text"])),
        baseline_region_hash=str(raw.get("baseline_region_hash", DEFAULT_CONFIG["baseline_region_hash"])),
        baseline_timestamp=str(raw.get("baseline_timestamp", DEFAULT_CONFIG["baseline_timestamp"])),
    )


def save_config(cfg: ScanConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "scan_interval": cfg.scan_interval,
        "wait_interval": cfg.wait_interval,
        "keywords": cfg.keywords,
        "exclude_keywords": cfg.exclude_keywords,
        "refresh_point": cfg.refresh_point.to_dict(),
        "first_line_point": cfg.first_line_point.to_dict(),
        "page_click_point": cfg.page_click_point.to_dict(),
        "page_click_point_2": cfg.page_click_point_2.to_dict(),
        "home_point": cfg.home_point.to_dict(),
        "monitor_region": cfg.monitor_region.to_dict(),
        "output_json": cfg.output_json,
        "use_baseline": cfg.use_baseline,
        "baseline_text": cfg.baseline_text,
        "baseline_region_hash": cfg.baseline_region_hash,
        "baseline_timestamp": cfg.baseline_timestamp,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def region_hash(region: MonitorRegion) -> str:
    """Stable hash of a monitor region for detecting coordinate changes."""
    import hashlib
    raw = f"{region.top},{region.left},{region.width},{region.height}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()
