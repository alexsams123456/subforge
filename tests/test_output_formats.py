# -*- coding: utf-8 -*-
"""Тесты профилей форматов выхода."""

from __future__ import annotations

import unittest

from app.services.output_formats import (
    DEFAULT_OUTPUT_FORMAT,
    OUTPUT_FORMAT_ORDER,
    get_profile,
    normalize_output_format,
    resolve_extension,
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

    def test_wmv_fallback_codecs(self) -> None:
        profile = get_profile("wmv")
        self.assertEqual(profile.fallback_video_codec, "wmv2")
        self.assertEqual(profile.fallback_audio_codec, "wmav2")


if __name__ == "__main__":
    unittest.main()
