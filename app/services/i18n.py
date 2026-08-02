# -*- coding: utf-8 -*-
"""Локализация интерфейса SubForge."""

from __future__ import annotations

import json
from pathlib import Path

from app.runtime_paths import locale_dir

DEFAULT_LOCALE = "en"

SUPPORTED_LOCALES: tuple[str, ...] = ("en", "ru", "de", "fr", "it", "ja")

LOCALE_LABELS: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "ja": "日本語",
}

def _locale_dir() -> Path:
    return locale_dir()
_catalog: dict[str, str] = {}
_fallback: dict[str, str] = {}
_current = DEFAULT_LOCALE


def _load_catalog(locale: str) -> dict[str, str]:
    path = _locale_dir() / f"{locale}.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def set_locale(locale: str) -> None:
    """Установить язык интерфейса и загрузить каталог переводов."""
    global _current, _catalog, _fallback
    code = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    _current = code
    _catalog = _load_catalog(code)
    _fallback = _load_catalog(DEFAULT_LOCALE) if code != DEFAULT_LOCALE else _catalog


def current_locale() -> str:
    return _current


def locale_label(locale: str) -> str:
    return LOCALE_LABELS.get(locale, locale)


def all_locale_labels() -> list[str]:
    return [LOCALE_LABELS[code] for code in SUPPORTED_LOCALES]


def label_to_locale(label: str) -> str:
    for code, native in LOCALE_LABELS.items():
        if native == label:
            return code
    return DEFAULT_LOCALE


def t(key: str, **kwargs: object) -> str:
    """Перевод по ключу с fallback на English."""
    text = _catalog.get(key) or _fallback.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


# Инициализация каталога по умолчанию
set_locale(DEFAULT_LOCALE)
