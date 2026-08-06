# -*- coding: utf-8 -*-
"""Разбиение Whisper-сегментов на короткие cue по паузам между словами."""

from __future__ import annotations

from app.services.subtitle_format import join_text_parts
from app.services.transcription import Segment, WordTiming, display_end

PHRASE_PAUSE_SEC = 0.45


def _group_words_by_pause(words: list[WordTiming]) -> list[list[WordTiming]]:
    if not words:
        return []

    groups: list[list[WordTiming]] = [[words[0]]]
    for word in words[1:]:
        pause = word.start - groups[-1][-1].end
        if pause > PHRASE_PAUSE_SEC:
            groups.append([word])
        else:
            groups[-1].append(word)
    return groups


def _segment_from_word_group(
    group: list[WordTiming],
    language: str,
    speaker: str | None,
) -> Segment | None:
    parts = [word.text for word in group if word.text.strip()]
    text = join_text_parts(parts, language)
    if not text:
        return None

    speech_end = group[-1].end
    return Segment(
        start=group[0].start,
        end=display_end(speech_end),
        text=text,
        speaker=speaker,
        speech_end=speech_end,
    )


def split_segments_by_word_pauses(
    segments: list[Segment],
    language: str = "en",
) -> list[Segment]:
    """Делит сегменты на отдельные cue по паузам между словами."""
    if not segments:
        return []

    result: list[Segment] = []
    for seg in segments:
        words = seg.words
        if not words or len(words) < 2:
            result.append(seg)
            continue

        for group in _group_words_by_pause(words):
            phrase = _segment_from_word_group(group, language, seg.speaker)
            if phrase is not None:
                result.append(phrase)

    return result
