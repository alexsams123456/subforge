# -*- coding: utf-8 -*-
"""Тесты таймингов субтитров."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services.subtitle_format import format_subtitles
from app.services.subtitle_phrases import PHRASE_PAUSE_SEC, split_segments_by_word_pauses
from app.services.subtitle_timing import MIN_CUE_GAP_SEC, normalize_subtitle_timing
from app.services.transcription import (
    END_PADDING_SEC,
    Segment,
    WordTiming,
    _segment_timing_from_whisper,
    display_end,
)


class SubtitleTimingTests(unittest.TestCase):
    def test_merge_does_not_span_long_gap(self) -> None:
        segments = [
            Segment(start=0.0, end=10.0, text="First phrase here.", speech_end=3.0),
            Segment(start=130.0, end=135.0, text="Second phrase.", speech_end=134.0),
        ]

        result = format_subtitles(segments, max_lines=2, language="en")

        self.assertEqual(len(result), 2)
        self.assertLess(result[0].end, 20.0)
        self.assertGreater(result[1].start, 120.0)

    def test_collapse_same_speaker_respects_gap(self) -> None:
        segments = [
            Segment(start=0.0, end=10.0, text="First line.", speaker="0", speech_end=3.0),
            Segment(start=130.0, end=135.0, text="Second line.", speaker="0", speech_end=134.0),
        ]

        result = format_subtitles(segments, max_lines=2, language="en")

        self.assertEqual(len(result), 2)
        self.assertLess(result[0].end, 20.0)

    def test_normalize_trims_end_before_next_start(self) -> None:
        segments = [
            Segment(start=0.0, end=62.0, text="Hello", speech_end=61.5),
            Segment(start=60.0, end=65.0, text="World", speech_end=64.0),
        ]

        result = normalize_subtitle_timing(segments)

        self.assertAlmostEqual(result[0].end, 60.0 - MIN_CUE_GAP_SEC)
        self.assertAlmostEqual(result[1].start, 60.0)
        self.assertAlmostEqual(result[1].end, display_end(64.0))

    def test_word_timing_uses_last_word_end(self) -> None:
        whisper_segment = SimpleNamespace(
            start=0.0,
            end=30.0,
            words=[
                SimpleNamespace(word="first", start=1.0, end=2.0),
                SimpleNamespace(word="second", start=2.5, end=9.5),
            ],
        )

        start, end, speech_end = _segment_timing_from_whisper(whisper_segment)

        self.assertAlmostEqual(start, 1.0)
        self.assertAlmostEqual(speech_end, 9.5)
        self.assertAlmostEqual(end, 9.5 + END_PADDING_SEC)

    def test_word_timing_fallback_without_words(self) -> None:
        whisper_segment = SimpleNamespace(start=3.0, end=8.0, words=None)

        start, end, speech_end = _segment_timing_from_whisper(whisper_segment)

        self.assertAlmostEqual(start, 3.0)
        self.assertAlmostEqual(speech_end, 8.0)
        self.assertAlmostEqual(end, 8.0 + END_PADDING_SEC)

    def test_inflated_whisper_end_capped_by_speech_end(self) -> None:
        segments = [
            Segment(start=1.0, end=30.0, text="Short phrase.", speech_end=9.5),
        ]

        result = normalize_subtitle_timing(segments)

        self.assertAlmostEqual(result[0].end, display_end(9.5))
        self.assertLess(result[0].end, 10.0)

    def test_merge_does_not_inflate_end_beyond_speech(self) -> None:
        segments = [
            Segment(start=0.0, end=10.0, text="First.", speech_end=2.0),
            Segment(start=2.5, end=15.0, text="Second.", speech_end=5.0),
        ]

        result = format_subtitles(segments, max_lines=2, language="en")

        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].speech_end, 5.0)
        self.assertAlmostEqual(result[0].end, display_end(5.0))
        self.assertLess(result[0].end, 6.0)

    def test_last_cue_trimmed_by_speech_end(self) -> None:
        segments = [
            Segment(start=100.0, end=130.0, text="Final line.", speech_end=105.0),
        ]

        result = normalize_subtitle_timing(segments)

        self.assertAlmostEqual(result[0].end, display_end(105.0))
        self.assertLess(result[0].end, 110.0)

    def test_phrase_split_on_word_pause(self) -> None:
        words = [
            WordTiming(text="Hello", start=1.0, end=1.4),
            WordTiming(text="there", start=1.5, end=1.9),
            WordTiming(text="friend", start=1.95, end=2.3),
            WordTiming(text="Good", start=3.5, end=3.8),
            WordTiming(text="bye", start=3.9, end=4.2),
        ]
        segments = [
            Segment(
                start=1.0,
                end=300.0,
                text="Hello there friend Good bye",
                speech_end=4.2,
                words=words,
            )
        ]

        result = split_segments_by_word_pauses(segments, language="en")

        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[0].start, 1.0)
        self.assertAlmostEqual(result[0].speech_end, 2.3)
        self.assertAlmostEqual(result[0].end, display_end(2.3))
        self.assertAlmostEqual(result[1].start, 3.5)
        self.assertAlmostEqual(result[1].speech_end, 4.2)
        self.assertIn("Hello", result[0].text)
        self.assertIn("bye", result[1].text)
        self.assertGreater(result[1].start - result[0].speech_end, PHRASE_PAUSE_SEC)

    def test_inflated_whisper_end_with_words(self) -> None:
        words = [
            WordTiming(text="Short", start=1.0, end=1.5),
            WordTiming(text="phrase", start=1.6, end=9.5),
        ]
        segments = [
            Segment(
                start=1.0,
                end=300.0,
                text="Short phrase",
                speech_end=9.5,
                words=words,
            )
        ]

        result = normalize_subtitle_timing(segments)

        self.assertAlmostEqual(result[0].end, display_end(9.5))
        self.assertLess(result[0].end, 10.0)

    def test_no_words_fallback_unchanged(self) -> None:
        segments = [
            Segment(start=5.0, end=8.0, text="Plain segment.", speech_end=7.5),
        ]

        result = split_segments_by_word_pauses(segments, language="en")

        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].start, 5.0)
        self.assertAlmostEqual(result[0].speech_end, 7.5)

    def test_phrase_split_preserves_speaker(self) -> None:
        words = [
            WordTiming(text="One", start=1.0, end=1.2),
            WordTiming(text="Two", start=2.0, end=2.2),
        ]
        segments = [
            Segment(
                start=1.0,
                end=10.0,
                text="One Two",
                speaker="0",
                speech_end=2.2,
                words=words,
            )
        ]

        result = split_segments_by_word_pauses(segments, language="en")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].speaker, "0")
        self.assertEqual(result[1].speaker, "0")

    def test_format_subtitles_does_not_merge_across_long_gap(self) -> None:
        segments = [
            Segment(start=0.0, end=10.0, text="First phrase here.", speech_end=3.0),
            Segment(start=130.0, end=135.0, text="Second phrase.", speech_end=134.0),
        ]

        split = split_segments_by_word_pauses(segments, language="en")
        result = format_subtitles(split, max_lines=2, language="en")
        normalized = normalize_subtitle_timing(result, language="en")

        self.assertEqual(len(normalized), 2)
        self.assertLess(normalized[0].end, 20.0)
        self.assertGreater(normalized[1].start, 120.0)

    def test_fallback_caps_inflated_segment_without_words(self) -> None:
        segments = [
            Segment(
                start=10.0,
                end=400.0,
                text="Short phrase.",
                speech_end=400.0,
            )
        ]

        result = normalize_subtitle_timing(segments, language="en")

        self.assertLess(result[0].end, 20.0)
        self.assertGreater(result[0].end, 10.0)


if __name__ == "__main__":
    unittest.main()
