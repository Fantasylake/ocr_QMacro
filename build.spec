# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for QMacro -- single-file build.

Build:
    pyinstaller build.spec

Output:
    dist/QMacro.exe  (single ~150-180 MB file)

User data still lives under %APPDATA%\\QMacro\\ at runtime (handled by
core/paths.py), so the exe itself contains only the read-only defaults
plus the bundled config.json for first-run fallback.
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None
PROJECT_ROOT = Path(SPECPATH).resolve()

# Bundle RapidOCR's onnx model files. The package declares them as
# package_data, so collect_data_files picks them up regardless of where
# the Python install lives (venv, system Python, Conda, etc.).
rapidocr_data = collect_data_files("rapidocr_onnxruntime")

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Default config.json -- first-run fallback so the user starts with
        # sane defaults even if %APPDATA%\QMacro\config.json doesn't exist yet.
        (str(PROJECT_ROOT / "config.json"), "."),
        *rapidocr_data,
    ],
    hiddenimports=[
        "rapidocr_onnxruntime",
        "rapidocr_onnxruntime.ch_ppocr_v3_det",
        "rapidocr_onnxruntime.ch_ppocr_v3_det.text_detect",
        "rapidocr_onnxruntime.ch_ppocr_v3_rec",
        "rapidocr_onnxruntime.ch_ppocr_v3_rec.text_recognize",
        "rapidocr_onnxruntime.ch_ppocr_v2_cls",
        "rapidocr_onnxruntime.ch_ppocr_v2_cls.text_cls",
        "rapidocr_onnxruntime.rapid_ocr_api",
        "mss",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / "tools" / "_pyi_runtime_hook.py")],
    excludes=[
        # Trim size: stuff we don't use.
        "tkinter",
        "matplotlib",
        "pandas",
        "PySide6.Qt3DAnimation",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTest",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtXml",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --onefile: every Analysis output goes into the single EXE.
# No COLLECT step, no exclude_binaries on EXE.
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="QMacro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                  # UPX doubles AV false-positive rate; skip it
    console=False,              # GUI app -- no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon=str(PROJECT_ROOT / "assets" / "qmacro.ico"),  # add when icon exists
    # version=str(PROJECT_ROOT / "version_info.txt"),     # add to lower AV false-positive
)