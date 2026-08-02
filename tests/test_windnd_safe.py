# -*- coding: utf-8 -*-
"""Тесты безопасного drag-and-drop hook."""

from __future__ import annotations

import queue
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class WindndSafeTests(unittest.TestCase):
    def test_import_hook_dropfiles(self) -> None:
        from app.ui.windnd_safe import hook_dropfiles

        self.assertTrue(callable(hook_dropfiles))

    def test_log_info_writes_without_error(self) -> None:
        from app.services.app_log import get_log_file_path, log_info, setup_app_logging

        setup_app_logging()
        log_info("drag_drop_test", "unit test message")
        self.assertTrue(get_log_file_path().is_file())

    def test_on_files_dropped_only_queues_paths(self) -> None:
        from app.ui.main_window import MainWindow

        window = MagicMock()
        window._drop_queue = queue.Queue()
        paths = [r"C:\videos\sample.mp4"]

        with patch("app.ui.main_window.log_info") as log_info:
            MainWindow._on_files_dropped(window, paths)

        self.assertEqual(window._drop_queue.get_nowait(), paths)
        with self.assertRaises(queue.Empty):
            window._drop_queue.get_nowait()
        window.after.assert_not_called()
        log_info.assert_called_once_with("drag_drop_files", "queued 1 path(s)")

    def test_on_files_dropped_ignores_empty_list(self) -> None:
        from app.ui.main_window import MainWindow

        window = MagicMock()
        window._drop_queue = queue.Queue()

        MainWindow._on_files_dropped(window, [])

        with self.assertRaises(queue.Empty):
            window._drop_queue.get_nowait()

    def test_handle_dropped_files_adds_supported_video(self) -> None:
        from app.ui.main_window import MainWindow

        window = MagicMock()
        window._busy = False
        window._queue = []
        window._is_supported_video = MainWindow._is_supported_video
        window._add_to_queue = MainWindow._add_to_queue.__get__(window, MainWindow)
        window._normalize_queue_path = MainWindow._normalize_queue_path.__get__(
            window, MainWindow
        )

        with patch("app.ui.main_window.log_info"), patch("app.ui.main_window.messagebox"):
            MainWindow._handle_dropped_files(
                window,
                [str(Path("C:/videos/sample.mp4"))],
            )

        self.assertEqual(len(window._queue), 1)
        self.assertEqual(window._queue[0].name, "sample.mp4")


if __name__ == "__main__":
    unittest.main()
