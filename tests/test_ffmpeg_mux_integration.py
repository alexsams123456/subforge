# -*- coding: utf-8 -*-
"""Интеграционные тесты mux субтитров через ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.services.ffmpeg_service import find_ffmpeg, mux_subtitles
from app.runtime_paths import bin_dir


def _ffmpeg_available() -> bool:
    bundled = bin_dir() / "ffmpeg.exe"
    if bundled.is_file():
        return True
    return shutil.which("ffmpeg") is not None


def _ffprobe_subtitle_streams(path: Path) -> int:
    ffmpeg = find_ffmpeg()
    probe = Path(ffmpeg).with_name("ffprobe.exe")
    if not probe.is_file():
        found = shutil.which("ffprobe")
        if not found:
            return 0
        probe = Path(found)
    result = subprocess.run(
        [
            str(probe),
            "-v",
            "error",
            "-select_streams",
            "s",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    if result.returncode != 0:
        return 0
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return len(lines)


@unittest.skipUnless(_ffmpeg_available(), "ffmpeg not available")
class FfmpegMuxIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.mkdtemp()
        self._work = Path(self._temp_dir)
        self._ffmpeg = find_ffmpeg()
        self._source = self._work / "source.mp4"
        self._srt = self._work / "subs.srt"

        subprocess.run(
            [
                self._ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x240:d=1",
                "-f",
                "lavfi",
                "-i",
                "sine=f=440:duration=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(self._source),
            ],
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        self._srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n",
            encoding="utf-8",
        )

    def test_mux_mp4_soft_subtitle_stream(self) -> None:
        output = self._work / "out.mp4"
        mux_subtitles(self._source, self._srt, output, language="en", output_format="mp4")
        self.assertTrue(output.is_file())
        self.assertGreater(_ffprobe_subtitle_streams(output), 0)

    def test_mux_mkv_soft_subtitle_stream(self) -> None:
        output = self._work / "out.mkv"
        mux_subtitles(self._source, self._srt, output, language="en", output_format="mkv")
        self.assertTrue(output.is_file())
        self.assertGreater(_ffprobe_subtitle_streams(output), 0)

    def test_mux_webm_creates_video_without_subtitle_stream(self) -> None:
        output = self._work / "out.webm"
        mux_subtitles(self._source, self._srt, output, language="en", output_format="webm")
        self.assertTrue(output.is_file())
        self.assertEqual(_ffprobe_subtitle_streams(output), 0)


if __name__ == "__main__":
    unittest.main()
