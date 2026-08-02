# -*- coding: utf-8 -*-
"""Тесты настроек пользователя."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.settings import AppSettings, _normalize_settings, load_settings, save_settings


class SettingsTests(unittest.TestCase):
    def test_normalize_defaults_for_empty_dict(self) -> None:
        settings = _normalize_settings({})
        self.assertEqual(settings.ui_locale, "en")
        self.assertEqual(settings.engine_id, "powerful")
        self.assertEqual(settings.speech_language, "en")
        self.assertEqual(settings.subtitle_language, "en")
        self.assertEqual(settings.max_subtitle_lines, 2)
        self.assertTrue(settings.separate_speakers)
        self.assertFalse(settings.hide_non_speech)

    def test_normalize_legacy_ui_locale_only(self) -> None:
        settings = _normalize_settings({"ui_locale": "ru"})
        self.assertEqual(settings.ui_locale, "ru")
        self.assertEqual(settings.engine_id, "powerful")
        self.assertEqual(settings.speech_language, "en")

    def test_normalize_invalid_values(self) -> None:
        settings = _normalize_settings(
            {
                "engine_id": "unknown",
                "speech_language": "xx",
                "subtitle_language": "yy",
                "max_subtitle_lines": 99,
                "ui_locale": "zz",
            }
        )
        self.assertEqual(settings.engine_id, "powerful")
        self.assertEqual(settings.speech_language, "en")
        self.assertEqual(settings.subtitle_language, "en")
        self.assertEqual(settings.max_subtitle_lines, 4)
        self.assertEqual(settings.ui_locale, "en")

    def test_roundtrip_balanced_engine(self) -> None:
        original = AppSettings(engine_id="balanced")
        with patch("app.services.settings._settings_path") as mock_path:
            path = Path(self._temp_dir) / "settings.json"
            mock_path.return_value = path

            save_settings(original)
            loaded = load_settings()

        self.assertEqual(loaded.engine_id, "balanced")

    def test_roundtrip_save_load(self) -> None:
        original = AppSettings(
            ui_locale="ja",
            engine_id="simple",
            speech_language="ja",
            subtitle_language="en",
            max_subtitle_lines=3,
            separate_speakers=False,
            hide_non_speech=True,
        )
        with patch("app.services.settings._settings_path") as mock_path:
            path = Path(self._temp_dir) / "settings.json"
            mock_path.return_value = path

            save_settings(original)
            loaded = load_settings()

        self.assertEqual(loaded, original)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["engine_id"], "simple")
        self.assertEqual(data["hide_non_speech"], True)

    def setUp(self) -> None:
        import tempfile

        self._temp_dir = tempfile.mkdtemp()


if __name__ == "__main__":
    unittest.main()
