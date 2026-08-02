# -*- coding: utf-8 -*-
"""Тесты профилей форматов выхода."""

from __future__ import annotations

import unittest

from app.services.output_formats import (
    DEFAULT_OUTPUT_FORMAT,
    OUTPUT_FORMAT_ORDER,
    SOFT_SUBTITLE_FORMATS,
    get_profile,
    normalize_output_format,
    resolve_extension,
    supports_soft_subtitles,
)


class OutputFormatsTests(unittest.TestCase):
    def test_default_format(self) -> None:
        self.assertEqual(DEFAULT_OUTPUT_FORMAT, "mp4")
        self.assertEqual(normalize_output_format("unknown"), "mp4")

    def test_all_formats_have_profiles(self) -> None:
        for fmt in OUTPUT_FORMAT_ORDER:
            profile = get_profile(fmt)
            self.assertEqual(profile.format_id, fmt)
            self.assertTrue(profile.extension.startswith("."))

    def test_resolve_extension(self) -> None:
        self.assertEqual(resolve_extension("mp4"), ".mp4")
        self.assertEqual(resolve_extension("mkv"), ".mkv")
        self.assertEqual(resolve_extension("webm"), ".webm")

    def test_mp4_family_uses_mov_text(self) -> None:
        for fmt in ("mp4", "m4v", "mov"):
            profile = get_profile(fmt)
            self.assertEqual(profile.subtitle_mode, "soft")
            self.assertEqual(profile.subtitle_codec, "mov_text")
            self.assertIn("+faststart", profile.container_flags)

    def test_mkv_uses_srt_soft(self) -> None:
        profile = get_profile("mkv")
        self.assertEqual(profile.subtitle_codec, "srt")
        self.assertEqual(profile.subtitle_mode, "soft")
        self.assertEqual(profile.container_flags, ())

    def test_webm_burn_in(self) -> None:
        profile = get_profile("webm")
        self.assertEqual(profile.subtitle_mode, "burn_in")
        self.assertIsNone(profile.subtitle_codec)
        self.assertEqual(profile.burn_in_video_codec, "libvpx-vp9")
        self.assertEqual(profile.burn_in_audio_codec, "libopus")

    def test_normalize_migrates_avi_wmv_to_mp4(self) -> None:
        self.assertEqual(normalize_output_format("avi"), "mp4")
        self.assertEqual(normalize_output_format("wmv"), "mp4")

    def test_ui_formats_exclude_avi_wmv(self) -> None:
        self.assertNotIn("avi", OUTPUT_FORMAT_ORDER)
        self.assertNotIn("wmv", OUTPUT_FORMAT_ORDER)
        self.assertIn("webm", OUTPUT_FORMAT_ORDER)

    def test_supports_soft_subtitles(self) -> None:
        for fmt in SOFT_SUBTITLE_FORMATS:
            self.assertTrue(supports_soft_subtitles(fmt))
        self.assertFalse(supports_soft_subtitles("webm"))
        self.assertFalse(supports_soft_subtitles("avi"))
        profile = get_profile("wmv")
        self.assertEqual(profile.fallback_video_codec, "wmv2")
        self.assertEqual(profile.fallback_audio_codec, "wmav2")


if __name__ == "__main__":
    unittest.main()
