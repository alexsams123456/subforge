# -*- coding: utf-8 -*-
"""Unit-тесты разбора ошибок ffmpeg и compound mux-сообщений."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.ffmpeg_service import (
    FFmpegError,
    _check_output_disk_space,
    _estimate_mux_output_bytes,
    _format_mux_errors,
    _short_ffmpeg_error,
    copy_mux_timeout,
    encode_timeout,
)


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


class CopyMuxTimeoutTests(unittest.TestCase):
    def test_uses_command_timeout_for_small_files(self) -> None:
        video = Path("small.mp4")
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "stat") as stat_mock:
                stat_mock.return_value = MagicMock(st_size=1024)
                self.assertEqual(copy_mux_timeout(60.0, video), 600.0)

    def test_scales_for_long_duration(self) -> None:
        video = Path("small.mp4")
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "stat") as stat_mock:
                stat_mock.return_value = MagicMock(st_size=1024)
                self.assertEqual(copy_mux_timeout(7200.0, video), 14400.0)

    def test_scales_for_large_source_file(self) -> None:
        video = Path("large.mp4")
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "stat") as stat_mock:
                stat_mock.return_value = MagicMock(st_size=3 * 1024 ** 3)
                self.assertEqual(copy_mux_timeout(None, video), 600.0)


class DiskSpaceTests(unittest.TestCase):
    def test_estimate_includes_faststart_headroom(self) -> None:
        video = Path("video.mp4")
        srt = Path("subs.srt")
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "stat") as stat_mock:
                stat_mock.side_effect = [
                    MagicMock(st_size=10 * 1024 ** 3),
                    MagicMock(st_size=76_000),
                ]
                required = _estimate_mux_output_bytes(video, srt)
        self.assertGreater(required, 20 * 1024 ** 3)

    def test_check_output_disk_space_raises_when_insufficient(self) -> None:
        output = Path("C:/out/video_subtitles.mp4")
        with patch("app.services.ffmpeg_service.shutil.disk_usage") as usage_mock:
            usage_mock.return_value = MagicMock(free=1024 ** 3)
            with self.assertRaises(FFmpegError) as ctx:
                _check_output_disk_space(output, 10 * 1024 ** 3)
        self.assertIn("C:", str(ctx.exception))


class FormatMuxErrorsTests(unittest.TestCase):
    def test_includes_copy_and_fallback_errors(self) -> None:
        message = _format_mux_errors("copy failed", "encode failed")
        self.assertIn("copy failed", message)
        self.assertIn("encode failed", message)

    def test_returns_fallback_only_without_copy_error(self) -> None:
        message = _format_mux_errors(None, "encode failed")
        self.assertEqual(message, "encode failed")

    def test_all_errors_message_for_three_attempts(self) -> None:
        message = _format_mux_errors(
            all_errors=["faststart failed", "copy failed", "encode failed"]
        )
        self.assertIn("faststart failed", message)
        self.assertIn("encode failed", message)

    def test_large_file_hint_for_invalid_argument(self) -> None:
        video = Path("large.mp4")
        with patch.object(Path, "is_file", return_value=True):
            with patch.object(Path, "stat") as stat_mock:
                stat_mock.return_value = MagicMock(st_size=5 * 1024 ** 3)
                message = _format_mux_errors(
                    all_errors=[
                        "Task finished with error code: -22 (Invalid argument)",
                        "Conversion failed!",
                    ],
                    video_path=video,
                )
        lowered = message.lower()
        self.assertIn("invalid argument", lowered)
        self.assertIn("mkv", lowered)


if __name__ == "__main__":
    unittest.main()
