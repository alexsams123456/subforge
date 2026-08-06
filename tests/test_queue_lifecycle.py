# -*- coding: utf-8 -*-
"""Тесты жизненного цикла очереди видео в MainWindow."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.batch_queue import BatchJob


class QueueLifecycleTests(unittest.TestCase):
    def _make_window(self) -> MagicMock:
        from app.ui.main_window import MainWindow

        window = MagicMock()
        window._queue = []
        window._queue_row_widgets = []
        window._busy = False
        window._batch_active = False
        window._batch_jobs = None
        window._batch_index = 0
        window._cancel_token = None
        window._output_path = None
        window._normalize_queue_path = MainWindow._normalize_queue_path.__get__(
            window, MainWindow
        )
        window._remove_from_queue_by_path = MainWindow._remove_from_queue_by_path.__get__(
            window, MainWindow
        )
        window._on_success = MainWindow._on_success.__get__(window, MainWindow)
        window._on_batch_complete = MainWindow._on_batch_complete.__get__(
            window, MainWindow
        )
        window._finish_batch_stopped = MainWindow._finish_batch_stopped.__get__(
            window, MainWindow
        )
        window._process_next_batch_job = MagicMock()
        return window

    def test_remove_from_queue_by_path_removes_matching_file(self) -> None:
        window = self._make_window()
        video_a = Path("C:/videos/a.mp4")
        video_b = Path("C:/videos/b.mp4")
        window._queue = [video_a, video_b]
        window._refresh_queue_ui = MagicMock()

        window._remove_from_queue_by_path(video_a)

        self.assertEqual(window._queue, [video_b])
        window._refresh_queue_ui.assert_called_once()

    def test_remove_from_queue_by_path_noop_when_missing(self) -> None:
        window = self._make_window()
        window._queue = [Path("C:/videos/b.mp4")]
        window._refresh_queue_ui = MagicMock()

        window._remove_from_queue_by_path(Path("C:/videos/a.mp4"))

        self.assertEqual(len(window._queue), 1)
        window._refresh_queue_ui.assert_not_called()

    def test_on_success_removes_completed_batch_job_from_queue(self) -> None:
        window = self._make_window()
        video_a = Path("C:/videos/a.mp4")
        video_b = Path("C:/videos/b.mp4")
        window._queue = [video_a, video_b]
        window._batch_active = True
        window._batch_jobs = [
            BatchJob(input_video=video_a, output_video=Path("C:/out/a_subtitles.mp4")),
            BatchJob(input_video=video_b, output_video=Path("C:/out/b_subtitles.mp4")),
        ]
        window._batch_index = 0

        with patch.object(window, "_remove_from_queue_by_path") as remove_mock:
            window._on_success(Path("C:/out/a_subtitles.mp4"), 10, "mp4")

        remove_mock.assert_called_once_with(video_a)
        self.assertEqual(window._batch_index, 1)
        window._process_next_batch_job.assert_called_once()

    def test_on_batch_complete_clears_queue(self) -> None:
        window = self._make_window()
        window._queue = [Path("C:/videos/a.mp4")]
        window._batch_jobs = [
            BatchJob(
                input_video=Path("C:/videos/a.mp4"),
                output_video=Path("C:/out/a_subtitles.mp4"),
            ),
        ]
        window._batch_active = True
        window._batch_output_dir = Path("C:/out")
        window._refresh_queue_ui = MagicMock()

        with patch("app.ui.main_window.messagebox"), patch(
            "app.ui.main_window.ProgressTracker"
        ):
            window._on_batch_complete()

        self.assertEqual(window._queue, [])
        window._refresh_queue_ui.assert_called_once()

    def test_finish_batch_stopped_preserves_queue(self) -> None:
        window = self._make_window()
        video_a = Path("C:/videos/a.mp4")
        video_b = Path("C:/videos/b.mp4")
        window._queue = [video_a, video_b]
        window._batch_active = True
        window._batch_jobs = [
            BatchJob(input_video=video_a, output_video=Path("C:/out/a_subtitles.mp4")),
            BatchJob(input_video=video_b, output_video=Path("C:/out/b_subtitles.mp4")),
        ]
        window._batch_index = 1

        window._finish_batch_stopped("main.batch_stopped")

        self.assertEqual(window._queue, [video_a, video_b])


if __name__ == "__main__":
    unittest.main()
