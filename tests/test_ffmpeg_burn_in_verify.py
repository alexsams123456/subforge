# -*- coding: utf-8 -*-
"""Unit-тесты burn-in фильтра и верификации субтитров."""

from __future__ import annotations

import unittest
from pathlib import Path

from app.services.ffmpeg_service import (
    _burn_in_subtitle_filter,
    _libass_errors_in_stderr,
    _subtitle_filter_path,
    validate_srt_file,
)
from app.services.output_formats import get_profile


class SubtitleFilterPathTests(unittest.TestCase):
    def test_escapes_drive_colon_on_windows(self) -> None:
        path = Path("C:/Temp/subs.srt")
        escaped = _subtitle_filter_path(path)
        self.assertIn("\\:", escaped)
        self.assertNotIn("\\\\", escaped.replace("\\:", ""))

    def test_burn_in_filter_includes_force_style(self) -> None:
        path = Path("C:/Temp/subs.srt")
        filt = _burn_in_subtitle_filter(path)
        self.assertIn("subtitles=", filt)
        self.assertIn("force_style=", filt)
        self.assertIn("FontSize=24", filt)


class LibassStderrTests(unittest.TestCase):
    def test_detects_open_failure(self) -> None:
        stderr = (
            "[Parsed_subtitles_0 @ 000] Error opening subtitle file "
            "C:/missing/subs.srt: No such file or directory\n"
        )
        hits = _libass_errors_in_stderr(stderr)
        self.assertTrue(hits)

    def test_ignores_clean_stderr(self) -> None:
        stderr = "frame=  120 fps= 30 q=28.0 size=    1024kB time=00:00:04.00\n"
        self.assertEqual(_libass_errors_in_stderr(stderr), [])


class ValidateSrtTests(unittest.TestCase):
    def test_rejects_missing_file(self) -> None:
        with self.assertRaises(Exception):
            validate_srt_file(Path("C:/no/such/subs.srt"))

    def test_rejects_zero_cues(self) -> None:
        with self.assertRaises(Exception):
            validate_srt_file(Path(__file__), cue_count=0)


class VerifyProfileTests(unittest.TestCase):
    def test_avi_is_burn_in(self) -> None:
        self.assertEqual(get_profile("avi").subtitle_mode, "burn_in")

    def test_mp4_is_soft(self) -> None:
        self.assertEqual(get_profile("mp4").subtitle_mode, "soft")


if __name__ == "__main__":
    unittest.main()
