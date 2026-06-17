"""Verify MainWindow config sync and validation for the new single-region flow."""
import sys
import pytest
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    import ui.main_window as mw
    monkeypatch.setattr(mw, "CONFIG_PATH", tmp_path / "config.json")
    w = MainWindow()
    yield w
    w.close()


def test_default_config_has_no_region(window):
    r = window._config.monitor_region
    assert r.width == 0
    assert r.height == 0


def test_picking_point_updates_config(window):
    """Filling a point and triggering save should sync to config."""
    window._pt_x[0].setValue(100)
    window._pt_y[0].setValue(200)
    window._mark_dirty()
    window._save_timer.stop()
    window._save_config()

    assert window._config.refresh_point.x == 100
    assert window._config.refresh_point.y == 200


def test_picking_region_updates_config(window):
    window.region_panel.fill_from_pick(top=10, left=20, width=300, height=200)
    window.region_panel.name_edit.setText("状态栏")
    window._mark_dirty()
    window._save_timer.stop()
    window._save_config()

    assert window._config.monitor_region.top == 10
    assert window._config.monitor_region.left == 20
    assert window._config.monitor_region.width == 300
    assert window._config.monitor_region.height == 200
    assert window._config.monitor_region.name == "状态栏"


def test_validation_rejects_empty_keywords(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: warned.append(a[2]) or QMessageBox.Ok)

    window.kw_edit.setText("")
    window._pt_x[0].setValue(100)
    window._pt_y[0].setValue(200)
    window.region_panel.fill_from_pick(10, 20, 300, 200)

    window._on_start()
    assert "关键词" in warned[0]


def test_validation_rejects_zero_region(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning",
                       lambda parent, title, text, *a, **kw: (warned.append(text) or 0))

    window.kw_edit.setText("成功")
    for i in range(4):
        window._pt_x[i].setValue(100 + i)
        window._pt_y[i].setValue(200 + i)
    window.region_panel.fill_from_pick(0, 0, 0, 0)

    window._on_start()
    assert any("区域" in w for w in warned), f"No region warning found in {warned}"


def test_validation_accepts_valid_setup(window, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **kw: warned.append(a[2]) or QMessageBox.Ok)
    window.scheduler.start = lambda: None
    window.scheduler.update_config = lambda cfg: None

    window.kw_edit.setText("成功")
    for i in range(4):
        window._pt_x[i].setValue(100 + i * 10)
        window._pt_y[i].setValue(200 + i * 10)
    window.region_panel.fill_from_pick(10, 20, 300, 200)

    window._on_start()
    assert warned == [], f"Unexpected warnings: {warned}"
