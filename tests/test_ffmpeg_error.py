# -*- coding: utf-8 -*-
"""Unit-тесты разбора ошибок ffmpeg и compound mux-сообщений."""

from __future__ import annotations

import unittest

from app.services.ffmpeg_service import _format_mux_errors, _short_ffmpeg_error, encode_timeout


class ShortFfmpegErrorTests(unittest.TestCase):
    def test_prefers_error_lines_over_progress_tail(self) -> None:
        detail = (
            "ffmpeg version 8.1.2\n"
            "Input #0, mov,mp4, from 'video.mp4':\n"
            "Error opening output file out.mp4: Permission denied\n"
            "Conversion failed!\n"
            "frame=    0 fps=0.0 q=0.0 Lsize=       0KiB time=N/A bitrate=N/A speed=N/A\n"
            "[aac @ 00000202d16ac640] Qavg: 63881.199\n"
        )
        result = _short_ffmpeg_error(detail)
        self.assertIn("Permission denied", result)
        self.assertNotIn("frame=", result)
        self.assertNotIn("Qavg", result)

    def test_returns_no_audio_message_for_empty_output_stream(self) -> None:
        detail = (
            "Output #0, wav, to 'audio.wav':\n"
            "[out#0/wav @ 000001] Output file does not contain any stream\n"
        )
        result = _short_ffmpeg_error(detail)
        self.assertIn("ffmpeg", result.lower())
        self.assertIn("audio", result.lower())

    def test_falls_back_to_non_progress_lines(self) -> None:
        detail = (
            "Stream #0:0: Video: h264\n"
            "Could not write header for output file #0\n"
            "frame=    0 fps=0.0 q=0.0 Lsize=       0KiB\n"
        )
        result = _short_ffmpeg_error(detail)
        self.assertIn("Could not write header", result)


class EncodeTimeoutTests(unittest.TestCase):
    def test_minimum_for_short_or_unknown_duration(self) -> None:
        self.assertEqual(encode_timeout(None), 600.0)
        self.assertEqual(encode_timeout(0), 600.0)

    def test_scales_with_duration(self) -> None:
        self.assertEqual(encode_timeout(120), 1800.0)
        self.assertEqual(encode_timeout(3600), 14400.0)

    def test_caps_at_maximum(self) -> None:
        self.assertEqual(encode_timeout(7200), 14400.0)


class FormatMuxErrorsTests(unittest.TestCase):
    def test_includes_copy_and_fallback_errors(self) -> None:
        message = _format_mux_errors("copy failed", "encode failed")
        self.assertIn("copy failed", message)
        self.assertIn("encode failed", message)

    def test_returns_fallback_only_without_copy_error(self) -> None:
        message = _format_mux_errors(None, "encode failed")
        self.assertEqual(message, "encode failed")


if __name__ == "__main__":
    unittest.main()
