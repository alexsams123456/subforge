# -*- coding: utf-8 -*-
"""Нормализация таймингов субтитров: обрезка end до следующей реплики."""

from __future__ import annotations

from app.services.transcription import Segment

MIN_CUE_GAP_SEC = 0.05
MIN_CUE_DURATION_SEC = 0.05


def normalize_subtitle_timing(segments: list[Segment]) -> list[Segment]:
    """Обрезает end каждого cue, чтобы субтитры не висели в тишине."""
    if not segments:
        return []

    normalized: list[Segment] = []
    for index, seg in enumerate(segments):
        start = seg.start
        end = seg.end
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
            )
        )
    return normalized
