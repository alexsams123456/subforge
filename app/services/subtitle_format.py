# -*- coding: utf-8 -*-
"""Форматирование субтитров: объединение фрагментов Whisper и ограничение строк."""

from __future__ import annotations

import re

from app.services.transcription import Segment

DEFAULT_MAX_LINES = 2
MIN_MAX_LINES = 1
MAX_MAX_LINES = 4
MAX_MERGE_GAP_SEC = 1.2

_CJK_LANGS = frozenset({"ja", "zh", "ko", "zh-cn", "zh-tw"})
_CJK_PUNCT = set("、。！？，．…：；")

_WHITESPACE = re.compile(r"\s+")


def chars_per_line(language: str) -> int:
    lang = (language or "en").lower()
    if lang == "auto":
        return 42
    if lang in _CJK_LANGS or lang.startswith("zh"):
        return 18
    return 42


def _join_parts(parts: list[str], language: str) -> str:
    cleaned = [p.strip() for p in parts if p and p.strip()]
    if not cleaned:
        return ""
    lang = (language or "en").lower()
    if lang in _CJK_LANGS or lang.startswith("zh"):
        return "".join(cleaned)
    return " ".join(cleaned)


def _normalize(text: str, language: str) -> str:
    text = text.strip()
    lang = (language or "en").lower()
    if lang in _CJK_LANGS or lang.startswith("zh"):
        return text.replace("\n", "")
    return _WHITESPACE.sub(" ", text.replace("\n", " ")).strip()


def _break_line(text: str, max_len: int, language: str) -> int:
    if len(text) <= max_len:
        return len(text)

    lang = (language or "en").lower()
    if lang in _CJK_LANGS or lang.startswith("zh"):
        window = text[:max_len]
        for i in range(len(window) - 1, max(0, max_len // 2) - 1, -1):
            if window[i] in _CJK_PUNCT:
                return i + 1
        return max_len

    window = text[: max_len + 1]
    space = window.rfind(" ")
    if space > max_len // 3:
        return space
    return max_len


def _take_block(text: str, max_lines: int, chars_per_line: int, language: str) -> tuple[str, str]:
    text = _normalize(text, language)
    if not text:
        return "", ""

    lines: list[str] = []
    pos = 0
    while pos < len(text) and len(lines) < max_lines:
        chunk_end = _break_line(text[pos:], chars_per_line, language)
        lines.append(text[pos : pos + chunk_end].rstrip())
        pos += chunk_end
        while pos < len(text) and text[pos].isspace():
            pos += 1

    display = "\n".join(line for line in lines if line)
    remainder = text[pos:].strip()
    return display, remainder


def _fits_in_lines(text: str, max_lines: int, chars_per_line: int, language: str) -> bool:
    _, remainder = _take_block(text, max_lines, chars_per_line, language)
    return not remainder


def _has_speakers(segments: list[Segment]) -> bool:
    return any(seg.speaker is not None for seg in segments)


def _gap_too_large(prev_end: float, next_start: float) -> bool:
    return next_start - prev_end > MAX_MERGE_GAP_SEC


def _merge_same_speaker_segments(segments: list[Segment], language: str) -> list[Segment]:
    """Объединяет реплики одного говорящего, не захватывая длинные паузы."""
    if not segments:
        return []

    ordered = sorted(segments, key=lambda item: item.start)
    merged: list[Segment] = []
    parts = [ordered[0].text]
    start = ordered[0].start
    end = ordered[0].end
    speaker = ordered[0].speaker

    for seg in ordered[1:]:
        if not _gap_too_large(end, seg.start):
            parts.append(seg.text)
            end = max(end, seg.end)
            continue

        merged.append(
            Segment(
                start=start,
                end=end,
                text=_join_parts(parts, language),
                speaker=speaker,
            )
        )
        parts = [seg.text]
        start = seg.start
        end = seg.end

    merged.append(
        Segment(
            start=start,
            end=end,
            text=_join_parts(parts, language),
            speaker=speaker,
        )
    )
    return merged


def _collapse_same_speaker(segments: list[Segment], language: str) -> list[Segment]:
    if not segments:
        return []

    collapsed: list[Segment] = []
    parts = [segments[0].text]
    start = segments[0].start
    end = segments[0].end
    speaker = segments[0].speaker

    for seg in segments[1:]:
        if seg.speaker == speaker and not _gap_too_large(end, seg.start):
            parts.append(seg.text)
            end = seg.end
            continue

        collapsed.append(
            Segment(
                start=start,
                end=end,
                text=_join_parts(parts, language),
                speaker=speaker,
            )
        )
        parts = [seg.text]
        start = seg.start
        end = seg.end
        speaker = seg.speaker

    collapsed.append(
        Segment(
            start=start,
            end=end,
            text=_join_parts(parts, language),
            speaker=speaker,
        )
    )
    return collapsed


def _merge_consecutive(
    segments: list[Segment],
    max_lines: int,
    cpl: int,
    language: str,
) -> list[Segment]:
    if not segments:
        return []

    merged: list[Segment] = []
    parts = [segments[0].text]
    start = segments[0].start
    end = segments[0].end
    speaker = segments[0].speaker

    for seg in segments[1:]:
        if seg.speaker != speaker:
            merged.append(
                Segment(
                    start=start,
                    end=end,
                    text=_join_parts(parts, language),
                    speaker=speaker,
                )
            )
            parts = [seg.text]
            start = seg.start
            end = seg.end
            speaker = seg.speaker
            continue

        trial = _join_parts(parts + [seg.text], language)
        if (
            not _gap_too_large(end, seg.start)
            and _fits_in_lines(trial, max_lines, cpl, language)
        ):
            parts.append(seg.text)
            end = seg.end
        else:
            merged.append(
                Segment(
                    start=start,
                    end=end,
                    text=_join_parts(parts, language),
                    speaker=speaker,
                )
            )
            parts = [seg.text]
            start = seg.start
            end = seg.end

    merged.append(
        Segment(
            start=start,
            end=end,
            text=_join_parts(parts, language),
            speaker=speaker,
        )
    )
    return merged


def _segments_overlap(a: Segment, b: Segment) -> bool:
    return a.start < b.end and b.start < a.end


def _cluster_overlapping(utterances: list[Segment]) -> list[list[Segment]]:
    """Группирует реплики с пересечением по времени (транзитивно)."""
    count = len(utterances)
    if count == 0:
        return []

    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_left] = root_right

    for left in range(count):
        for right in range(left + 1, count):
            if _segments_overlap(utterances[left], utterances[right]):
                union(left, right)

    buckets: dict[int, list[Segment]] = {}
    for index, segment in enumerate(utterances):
        buckets.setdefault(find(index), []).append(segment)

    clusters = list(buckets.values())
    clusters.sort(key=lambda cluster: min(item.start for item in cluster))
    return clusters


def _line_for_speaker(segments: list[Segment], language: str, cpl: int) -> str:
    text = _normalize(_join_parts([seg.text for seg in segments], language), language)
    if not text:
        return ""
    if len(text) > cpl:
        return text[:cpl].rstrip()
    return text


def _group_by_speaker_lines(
    utterances: list[Segment],
    max_lines: int,
    cpl: int,
    language: str,
) -> list[Segment]:
    """Перекрывающиеся реплики разных говорящих — один блок, по строке на говорящего."""
    if not utterances:
        return []

    grouped: list[Segment] = []
    for cluster in _cluster_overlapping(utterances):
        by_speaker: dict[str, list[Segment]] = {}
        for segment in cluster:
            speaker = segment.speaker or "0"
            by_speaker.setdefault(speaker, []).append(segment)

        if len(by_speaker) == 1:
            speaker = next(iter(by_speaker))
            segments = by_speaker[speaker]
            for merged in _merge_same_speaker_segments(segments, language):
                grouped.extend(_split_long_segment(merged, max_lines, cpl, language))
            continue

        ranked: list[tuple[float, str, str]] = []
        for speaker, segments in by_speaker.items():
            duration = sum(max(item.end - item.start, 0.0) for item in segments)
            line = _line_for_speaker(segments, language, cpl)
            if line:
                ranked.append((duration, speaker, line))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        lines = [line for _, _, line in ranked[:max_lines]]
        if not lines:
            continue

        grouped.append(
            Segment(
                start=min(item.start for item in cluster),
                end=max(item.end for item in cluster),
                text="\n".join(lines),
                speaker=None,
            )
        )

    return grouped


def _split_long_segment(
    segment: Segment,
    max_lines: int,
    cpl: int,
    language: str,
) -> list[Segment]:
    text = _normalize(segment.text, language)
    if not text:
        return []

    blocks: list[str] = []
    remaining = text
    while remaining:
        block, remaining = _take_block(remaining, max_lines, cpl, language)
        if block:
            blocks.append(block)

    if len(blocks) <= 1:
        display = blocks[0] if blocks else text
        return [
            Segment(
                start=segment.start,
                end=segment.end,
                text=display,
                speaker=segment.speaker,
            )
        ]

    total_chars = sum(len(b.replace("\n", "")) for b in blocks)
    duration = max(segment.end - segment.start, 0.05)
    t_start = segment.start
    result: list[Segment] = []

    for idx, block in enumerate(blocks):
        block_chars = len(block.replace("\n", ""))
        if idx == len(blocks) - 1:
            t_end = segment.end
        elif total_chars > 0:
            share = block_chars / total_chars
            t_end = min(t_start + duration * share, segment.end)
        else:
            t_end = segment.end

        if t_end <= t_start:
            t_end = min(t_start + 0.05, segment.end)
        result.append(
            Segment(
                start=t_start,
                end=t_end,
                text=block,
                speaker=segment.speaker,
            )
        )
        t_start = t_end

    if result:
        result[-1] = Segment(
            start=result[-1].start,
            end=segment.end,
            text=result[-1].text,
            speaker=segment.speaker,
        )
    return result


def format_subtitles(
    segments: list[Segment],
    max_lines: int = DEFAULT_MAX_LINES,
    language: str = "en",
) -> list[Segment]:
    """Объединяет фрагменты Whisper и ограничивает строк на экране."""
    if not segments:
        return []

    max_lines = max(MIN_MAX_LINES, min(int(max_lines), MAX_MAX_LINES))
    cpl = chars_per_line(language)

    if _has_speakers(segments):
        utterances = _collapse_same_speaker(segments, language)
        return _group_by_speaker_lines(utterances, max_lines, cpl, language)

    merged = _merge_consecutive(segments, max_lines, cpl, language)
    formatted: list[Segment] = []
    for seg in merged:
        formatted.extend(_split_long_segment(seg, max_lines, cpl, language))
    return formatted
