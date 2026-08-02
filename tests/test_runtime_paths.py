# -*- coding: utf-8 -*-
"""Тесты путей frozen/dev."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from app import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_dev_mode_paths(self) -> None:
        with patch.object(runtime_paths, "is_frozen", return_value=False):
            root = runtime_paths.app_dir()
            self.assertTrue((root / "app" / "locale" / "en.json").is_file())
            self.assertEqual(runtime_paths.bin_dir(), root / "bin")
            self.assertEqual(runtime_paths.locale_dir(), root / "app" / "locale")

    def test_frozen_mode_paths(self) -> None:
        fake_exe = Path("C:/Apps/SubForge/SubForge.exe")
        fake_meipass = Path("C:/Apps/SubForge/_internal")
        with patch.object(runtime_paths, "is_frozen", return_value=True):
            with patch.object(sys, "executable", str(fake_exe)):
                with patch.object(sys, "_MEIPASS", str(fake_meipass), create=True):
                    self.assertEqual(runtime_paths.app_dir(), fake_exe.parent)
                    self.assertEqual(runtime_paths.internal_dir(), fake_meipass)
                    self.assertEqual(
                        runtime_paths.locale_dir(),
                        fake_meipass / "app" / "locale",
                    )
                    self.assertEqual(
                        runtime_paths.bin_dir(),
                        fake_exe.parent / "bin",
                    )


if __name__ == "__main__":
    unittest.main()
