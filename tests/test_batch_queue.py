# -*- coding: utf-8 -*-
"""Тесты пакетной очереди."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.batch_queue import build_jobs, resolve_output_path


class BatchQueueTests(unittest.TestCase):
    def test_resolve_output_path_default_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            result = resolve_output_path(output_dir, Path("C:/videos/film.mp4"))
            self.assertEqual(result, output_dir / "film_subtitles.mp4")

    def test_resolve_output_path_collision_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            existing = output_dir / "film_subtitles.mp4"
            existing.write_bytes(b"x")
            result = resolve_output_path(output_dir, Path("film.mp4"))
            self.assertEqual(result, output_dir / "film_subtitles_2.mp4")

    def test_resolve_output_path_collision_in_reserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            reserved = {output_dir / "film_subtitles.mp4"}
            result = resolve_output_path(output_dir, Path("film.mp4"), reserved)
            self.assertEqual(result, output_dir / "film_subtitles_2.mp4")

    def test_build_jobs_preserves_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            inputs = [
                Path("a.mp4"),
                Path("b.mp4"),
                Path("c.mp4"),
            ]
            jobs = build_jobs(inputs, output_dir)
            self.assertEqual(len(jobs), 3)
            self.assertEqual(jobs[0].input_video, inputs[0])
            self.assertEqual(jobs[1].input_video, inputs[1])
            self.assertEqual(jobs[2].input_video, inputs[2])
            self.assertEqual(jobs[0].output_video.name, "a_subtitles.mp4")
            self.assertEqual(jobs[1].output_video.name, "b_subtitles.mp4")


if __name__ == "__main__":
    unittest.main()
