# -*- coding: utf-8 -*-
"""Фильтрация сегментов Whisper без слов — только звуковые/эмоциональные метки."""

from __future__ import annotations

import re

from app.services.transcription import Segment

_ANNOTATION = re.compile(
    r"\[[^\]]*\]"
    r"|\([^)]*\)"
    r"|<[^>]+>"
    r"|［[^］]*］"
    r"|（[^）]*）"
    r"|♪+",
    re.IGNORECASE,
)
_PUNCT_ONLY = re.compile(r"[\s…\.\-—–,，、]+")


def is_non_speech_text(text: str) -> bool:
    """True, если текст — только звуковые метки без слов (например [laughter], ♪)."""
    cleaned = _ANNOTATION.sub("", text or "").strip()
    cleaned = _PUNCT_ONLY.sub("", cleaned)
    return not cleaned


def filter_non_speech_segments(segments: list[Segment]) -> list[Segment]:
    """Удаляет сегменты, состоящие только из звуковых меток."""
    return [seg for seg in segments if not is_non_speech_text(seg.text)]
