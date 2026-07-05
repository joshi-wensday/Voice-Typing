# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Vype V2 (onedir, windowed).
# Build from the CPU-only build venv:  .venv-build\Scripts\pyinstaller vype.spec
# The Parakeet model itself is downloaded to the HF cache on first run.

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ["run_vype.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("logo-1280.ico", "."),
        *collect_data_files("onnx_asr"),  # bundled preprocessor .onnx files
    ],
    hiddenimports=[
        *collect_submodules("onnx_asr"),
        "sounddevice",
        "keyboard",
        "pyperclip",
        "huggingface_hub",
    ],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtPdf",
        "PySide6.QtCharts",
        "PySide6.QtMultimedia",
        "PySide6.QtDataVisualization",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="vype",
    icon="logo-1280.ico",
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="vype",
)
