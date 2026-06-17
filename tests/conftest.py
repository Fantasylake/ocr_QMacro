"""Shared pytest fixtures."""
import sys
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture
def app():
    a = QApplication.instance() or QApplication(sys.argv)
    yield a
