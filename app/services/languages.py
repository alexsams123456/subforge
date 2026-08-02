# -*- coding: utf-8 -*-
"""Языки UI, коды Whisper и метаданные ffmpeg."""

from __future__ import annotations

from typing import Literal

from app.services.i18n import t

WhisperTask = Literal["transcribe", "translate"]

UI_LANGUAGE_LABELS: tuple[str, ...] = (
    "English",
    "Deutsch",
    "Français",
    "Italiano",
    "Japanese",
    "Русский",
    "Авто",
)

_UI_TO_CODE: dict[str, str] = {
    "English": "en",
    "Deutsch": "de",
    "Français": "fr",
    "Italiano": "it",
    "Japanese": "ja",
    "Русский": "ru",
    "Авто": "auto",
}

_FFMPEG_LANG: dict[str, str] = {
    "ru": "rus",
    "en": "eng",
    "de": "deu",
    "fr": "fra",
    "it": "ita",
    "ja": "jpn",
    "auto": "und",
    "rus": "rus",
    "eng": "eng",
    "deu": "deu",
    "fra": "fra",
    "ita": "ita",
    "jpn": "jpn",
    "und": "und",
}


_CODE_TO_UI: dict[str, str] = {code: label for label, code in _UI_TO_CODE.items()}


def ui_label_to_code(label: str) -> str:
    return _UI_TO_CODE.get(label, "en")


def code_to_ui_label(code: str) -> str:
    return _CODE_TO_UI.get((code or "en").lower(), "English")


def normalize_for_ffmpeg(language: str) -> str:
    return _FFMPEG_LANG.get(language.lower(), language.lower()[:3] or "und")


def whisper_task(speech_code: str, subtitle_code: str) -> WhisperTask:
    speech = (speech_code or "en").lower()
    subtitle = (subtitle_code or "en").lower()
    if subtitle == "en" and speech != "en":
        return "translate"
    return "transcribe"


def validate_language_pair(speech_code: str, subtitle_code: str) -> str | None:
    speech = (speech_code or "en").lower()
    subtitle = (subtitle_code or "en").lower()
    if speech == subtitle:
        return None
    if subtitle == "en":
        return None
    return t("language_pair.error")
