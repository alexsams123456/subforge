# -*- coding: utf-8 -*-
"""Настройки пользователя SubForge."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from app.services.engines import DEFAULT_ENGINE_ID, ENGINES
from app.services.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES
from app.services.subtitle_format import DEFAULT_MAX_LINES, MAX_MAX_LINES, MIN_MAX_LINES

_VALID_LANGUAGE_CODES = frozenset({"en", "de", "fr", "it", "ja", "ru", "auto"})


@dataclass
class AppSettings:
    ui_locale: str = DEFAULT_LOCALE
    engine_id: str = DEFAULT_ENGINE_ID
    speech_language: str = "en"
    subtitle_language: str = "en"
    max_subtitle_lines: int = DEFAULT_MAX_LINES
    separate_speakers: bool = True
    hide_non_speech: bool = False


def _settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA", "")
    if base:
        return Path(base) / "SubForge" / "settings.json"
    return Path.home() / ".subforge" / "settings.json"


def _normalize_settings(data: dict) -> AppSettings:
    defaults = AppSettings()

    locale = str(data.get("ui_locale", defaults.ui_locale))
    if locale not in SUPPORTED_LOCALES:
        locale = defaults.ui_locale

    engine_id = str(data.get("engine_id", defaults.engine_id))
    if engine_id not in ENGINES:
        engine_id = defaults.engine_id

    speech_language = str(data.get("speech_language", defaults.speech_language)).lower()
    if speech_language not in _VALID_LANGUAGE_CODES:
        speech_language = defaults.speech_language

    subtitle_language = str(data.get("subtitle_language", defaults.subtitle_language)).lower()
    if subtitle_language not in _VALID_LANGUAGE_CODES:
        subtitle_language = defaults.subtitle_language

    try:
        max_subtitle_lines = int(data.get("max_subtitle_lines", defaults.max_subtitle_lines))
    except (TypeError, ValueError):
        max_subtitle_lines = defaults.max_subtitle_lines
    max_subtitle_lines = max(MIN_MAX_LINES, min(MAX_MAX_LINES, max_subtitle_lines))

    return AppSettings(
        ui_locale=locale,
        engine_id=engine_id,
        speech_language=speech_language,
        subtitle_language=subtitle_language,
        max_subtitle_lines=max_subtitle_lines,
        separate_speakers=bool(data.get("separate_speakers", defaults.separate_speakers)),
        hide_non_speech=bool(data.get("hide_non_speech", defaults.hide_non_speech)),
    )


def load_settings() -> AppSettings:
    path = _settings_path()
    if not path.is_file():
        return AppSettings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()

    if not isinstance(data, dict):
        return AppSettings()

    return _normalize_settings(data)


def save_settings(settings: AppSettings) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
