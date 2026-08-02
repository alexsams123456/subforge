# -*- coding: utf-8 -*-
"""Тесты таймингов субтитров."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.subtitle_format import format_subtitles
from app.services.subtitle_timing import MIN_CUE_GAP_SEC, normalize_subtitle_timing
from app.services.transcription import END_PADDING_SEC, Segment, _segment_timing_from_whisper


class SubtitleTimingTests(unittest.TestCase):
    def test_merge_does_not_span_long_gap(self) -> None:
        segments = [
            Segment(start=0.0, end=10.0, text="First phrase here."),
            Segment(start=130.0, end=135.0, text="Second phrase."),
        ]

        result = format_subtitles(segments, max_lines=2, language="en")

        self.assertEqual(len(result), 2)
        self.assertLess(result[0].end, 20.0)
        self.assertGreater(result[1].start, 120.0)

    def test_collapse_same_speaker_respects_gap(self) -> None:
        segments = [
            Segment(start=0.0, end=10.0, text="First line.", speaker="0"),
            Segment(start=130.0, end=135.0, text="Second line.", speaker="0"),
        ]

        result = format_subtitles(segments, max_lines=2, language="en")

        self.assertEqual(len(result), 2)
        self.assertLess(result[0].end, 20.0)

    def test_normalize_trims_end_before_next_start(self) -> None:
        segments = [
            Segment(start=0.0, end=62.0, text="Hello"),
            Segment(start=60.0, end=65.0, text="World"),
        ]

        result = normalize_subtitle_timing(segments)

        self.assertAlmostEqual(result[0].end, 60.0 - MIN_CUE_GAP_SEC)
        self.assertAlmostEqual(result[1].start, 60.0)
        self.assertAlmostEqual(result[1].end, 65.0)

    def test_word_timing_uses_last_word_end(self) -> None:
        whisper_segment = SimpleNamespace(
            start=0.0,
            end=30.0,
            words=[
                SimpleNamespace(start=1.0, end=2.0),
                SimpleNamespace(start=2.5, end=9.5),
            ],
        )

        start, end = _segment_timing_from_whisper(whisper_segment)

        self.assertAlmostEqual(start, 1.0)
        self.assertAlmostEqual(end, 9.5 + END_PADDING_SEC)

    def test_word_timing_fallback_without_words(self) -> None:
        whisper_segment = SimpleNamespace(start=3.0, end=8.0, words=None)

        start, end = _segment_timing_from_whisper(whisper_segment)

        self.assertAlmostEqual(start, 3.0)
        self.assertAlmostEqual(end, 8.0)


if __name__ == "__main__":
    unittest.main()
