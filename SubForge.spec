# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec: SubForge onedir + CUDA (torch, ctranslate2)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files

project_root = Path(SPECPATH)

locale_datas = [
    (str(project_root / "app" / "locale" / name), "app/locale")
    for name in ("en.json", "ru.json", "de.json", "fr.json", "it.json", "ja.json")
]

datas = locale_datas + collect_data_files("customtkinter")
binaries = []
hiddenimports = [
    "faster_whisper",
    "ctranslate2",
    "speechbrain",
    "sklearn",
    "sklearn.cluster",
    "sklearn.cluster._kmeans",
    "windnd",
    "PIL",
    "PIL._tkinter_finder",
]

for package in ("ctranslate2", "torch", "torchaudio", "speechbrain", "faster_whisper"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    [str(project_root / "launch.py")],
    pathex=[str(project_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["matplotlib", "notebook", "IPython", "pytest", "test", "tests"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SubForge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SubForge",
)
