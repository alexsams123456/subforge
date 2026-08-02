# -*- coding: utf-8 -*-
"""Пути приложения: режим разработки и frozen (PyInstaller)."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Корень приложения: папка с exe (frozen) или репозиторий (dev)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def internal_dir() -> Path:
    """Распакованные ресурсы PyInstaller (_internal) или app_dir в dev."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
    return app_dir()


def locale_dir() -> Path:
    """Каталог JSON-локалей."""
    return internal_dir() / "app" / "locale"


def bin_dir() -> Path:
    """ffmpeg/ffprobe рядом с exe, не внутри _internal."""
    return app_dir() / "bin"
