# -*- coding: utf-8 -*-
"""Интеграционные тесты mux субтитров через ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.services.output_formats import get_profile
from app.services.ffmpeg_service import (
    _build_soft_mux_cmd,
    burn_in_frame_differs,
    count_subtitle_streams,
    find_ffmpeg,
    mux_subtitles,
    verify_output_subtitles,
)
from app.runtime_paths import bin_dir


def _ffmpeg_available() -> bool:
    bundled = bin_dir() / "ffmpeg.exe"
    if bundled.is_file():
        return True
    return shutil.which("ffmpeg") is not None


def _ffprobe_subtitle_streams(path: Path) -> int:
    return count_subtitle_streams(path)


@unittest.skipUnless(_ffmpeg_available(), "ffmpeg not available")
class FfmpegMuxIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.mkdtemp()
        self._work = Path(self._temp_dir)
        self._ffmpeg = find_ffmpeg()
        self._source = self._work / "source.mp4"
        self._video_only = self._work / "video_only.mp4"
        self._srt = self._work / "subs.srt"
        creationflags = (
            subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )

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
            creationflags=creationflags,
        )
        subprocess.run(
            [
                self._ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=320x240:d=1",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-t",
                "1",
                str(self._video_only),
            ],
            check=True,
            capture_output=True,
            creationflags=creationflags,
        )
        self._srt.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nTest subtitle\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._temp_dir, ignore_errors=True)

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

    def test_mux_webm_burn_in_frame_diff(self) -> None:
        output = self._work / "out_burn.webm"
        mux_subtitles(self._source, self._srt, output, language="en", output_format="webm")
        self.assertTrue(output.is_file())
        self.assertTrue(
            burn_in_frame_differs(self._source, output, timestamp_sec=0.5, ffmpeg=self._ffmpeg)
        )

    def test_mux_video_only_mp4(self) -> None:
        output = self._work / "video_only_out.mp4"
        mux_subtitles(
            self._video_only,
            self._srt,
            output,
            language="en",
            output_format="mp4",
        )
        self.assertTrue(output.is_file())
        self.assertGreater(_ffprobe_subtitle_streams(output), 0)

    def test_mux_video_only_mkv(self) -> None:
        output = self._work / "video_only_out.mkv"
        mux_subtitles(
            self._video_only,
            self._srt,
            output,
            language="en",
            output_format="mkv",
        )
        self.assertTrue(output.is_file())
        self.assertGreater(_ffprobe_subtitle_streams(output), 0)

    def test_build_soft_mux_cmd_without_faststart(self) -> None:
        profile = get_profile("mp4")
        cmd = _build_soft_mux_cmd(
            self._ffmpeg,
            self._source,
            self._srt,
            self._work / "out.mp4",
            profile,
            "en",
            video_codec="copy",
            include_audio=True,
            audio_codec="copy",
            use_faststart=False,
        )
        self.assertNotIn("-movflags", cmd)
        self.assertNotIn("+faststart", cmd)


if __name__ == "__main__":
    unittest.main()
