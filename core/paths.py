"""Resolve the user-data directory at runtime.

- In a frozen PyInstaller build (``QMacro.exe``): ``%APPDATA%\\QMacro\\``
  is created on first call and reused thereafter.
- In dev mode (``python main.py``): the repo root, found by walking up
  from this file until a ``config.json`` is located.

The split exists because:

1. ``QMacro.exe`` cannot write to its install folder on modern Windows
   (``%APPDATA%`` is the standard user-writable location).
2. ``python main.py`` runs from the repo root, where keeping the data
   alongside the code makes development and tests natural.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def _repo_root() -> Path:
    """Locate the dev repo root by searching upwards for ``config.json``."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "config.json").exists():
            return p
        p = p.parent
    # Fallback: project root is the parent of ``core/``.
    return Path(__file__).resolve().parent.parent


def app_data_dir() -> Path:
    """Return the absolute base directory for user-mutable data.

    - Frozen: ``%APPDATA%\\QMacro\\`` (auto-created).
    - Dev: repo root (no auto-creation; it already exists).
    """
    if is_frozen():
        base = Path(os.environ["APPDATA"]) / "QMacro"
        base.mkdir(parents=True, exist_ok=True)
        return base
    return _repo_root()


def config_path() -> Path:
    """Path to the user-editable ``config.json``."""
    return app_data_dir() / "config.json"


def log_dir() -> Path:
    """Directory holding daily ``.txt`` run logs."""
    d = app_data_dir() / "log"
    d.mkdir(parents=True, exist_ok=True)
    return d


def output_dir() -> Path:
    """Directory holding daily ``.json`` OCR-hit records."""
    d = app_data_dir() / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def pic_dir() -> Path:
    """Directory holding date-bucketed screenshot PNGs."""
    d = app_data_dir() / "pic"
    d.mkdir(parents=True, exist_ok=True)
    return d