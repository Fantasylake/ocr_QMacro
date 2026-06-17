"""Tests for the simplified single-region RegionPanel."""
import sys
from PySide6.QtWidgets import QApplication

from ui.region_panel import RegionPanel


def test_collect_returns_correct_dict():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = RegionPanel()

    panel.name_edit.setText("状态栏")
    panel.top_spin.setValue(10)
    panel.left_spin.setValue(20)
    panel.width_spin.setValue(300)
    panel.height_spin.setValue(400)

    data = panel.collect()
    assert data["name"] == "状态栏"
    assert data["top"] == 10
    assert data["left"] == 20
    assert data["width"] == 300
    assert data["height"] == 400
    print("[OK] collect returns correct dict")


def test_apply_sets_fields():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = RegionPanel()

    panel.apply({
        "name": "a1",
        "top": 100,
        "left": 200,
        "width": 800,
        "height": 600,
    })

    assert panel.name_edit.text() == "a1"
    assert panel.top_spin.value() == 100
    assert panel.left_spin.value() == 200
    assert panel.width_spin.value() == 800
    assert panel.height_spin.value() == 600
    print("[OK] apply sets all fields correctly")


def test_fill_from_pick_sets_spins_and_name():
    app = QApplication.instance() or QApplication(sys.argv)
    panel = RegionPanel()

    panel.fill_from_pick(top=43, left=500, width=728, height=822)

    assert panel.top_spin.value() == 43
    assert panel.left_spin.value() == 500
    assert panel.width_spin.value() == 728
    assert panel.height_spin.value() == 822
    assert panel.name_edit.text() == "a1"
    print("[OK] fill_from_pick sets spins and auto-fills name")


if __name__ == "__main__":
    test_collect_returns_correct_dict()
    test_apply_sets_fields()
    test_fill_from_pick_sets_spins_and_name()
    print("\n*** All region panel tests PASS ***")
