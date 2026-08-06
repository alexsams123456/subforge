# -*- coding: utf-8 -*-
"""Нормализация таймингов субтитров: обрезка end до следующей реплики."""

from __future__ import annotations

from app.services.transcription import END_PADDING_SEC, Segment, display_end

MIN_CUE_GAP_SEC = 0.05
MIN_CUE_DURATION_SEC = 0.05
MAX_SPEECH_SPAN_SEC = 18.0
SHORT_TEXT_MAX_CHARS = 80
LATIN_CHARS_PER_SEC = 14.0
CJK_CHARS_PER_SEC = 4.5

_CJK_LANGS = frozenset({"ja", "zh", "ko", "zh-cn", "zh-tw"})


def _is_cjk_language(language: str) -> bool:
    lang = (language or "en").lower()
    return lang in _CJK_LANGS or lang.startswith("zh")


def _estimate_speech_end(start: float, text: str, language: str) -> float:
    clean = text.replace("\n", "").strip()
    char_count = len(clean)
    if char_count <= 0:
        return start + MIN_CUE_DURATION_SEC

    rate = CJK_CHARS_PER_SEC if _is_cjk_language(language) else LATIN_CHARS_PER_SEC
    duration = max(char_count / rate, MIN_CUE_DURATION_SEC)
    return start + duration


def _cap_inflated_speech_end(seg: Segment, language: str) -> float | None:
    if seg.words or seg.speech_end is None:
        return seg.speech_end

    span = seg.speech_end - seg.start
    if span <= MAX_SPEECH_SPAN_SEC:
        return seg.speech_end

    # Только если end не был скорректирован относительно speech_end (сырой Whisper).
    if abs(seg.end - display_end(seg.speech_end)) > END_PADDING_SEC * 2:
        return seg.speech_end

    clean = seg.text.replace("\n", "").strip()
    if len(clean) > SHORT_TEXT_MAX_CHARS:
        return seg.speech_end

    estimated = _estimate_speech_end(seg.start, seg.text, language)
    if estimated < seg.speech_end:
        return estimated
    return seg.speech_end


def normalize_subtitle_timing(
    segments: list[Segment],
    language: str = "en",
) -> list[Segment]:
    """Обрезает end каждого cue, чтобы субтитры не висели в тишине."""
    if not segments:
        return []

    normalized: list[Segment] = []
    for index, seg in enumerate(segments):
        start = seg.start
        end = seg.end
        speech_end = _cap_inflated_speech_end(seg, language)
        if speech_end is not None:
            end = min(end, display_end(speech_end))
        if index + 1 < len(segments):
            next_start = segments[index + 1].start
            capped = next_start - MIN_CUE_GAP_SEC
            end = min(end, max(capped, start + MIN_CUE_DURATION_SEC))
        if end <= start:
            end = start + MIN_CUE_DURATION_SEC
        normalized.append(
            Segment(
                start=start,
                end=end,
                text=seg.text,
                speaker=seg.speaker,
                speech_end=speech_end,
                words=seg.words,
            )
        )
    return normalized
