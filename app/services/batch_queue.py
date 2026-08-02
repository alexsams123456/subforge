# -*- coding: utf-8 -*-
"""Пакетная очередь обработки видео."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BatchJob:
    input_video: Path
    output_video: Path
    audio_source: Path | None = None


def resolve_output_path(
    output_dir: Path,
    input_video: Path,
    reserved: set[Path] | None = None,
) -> Path:
    """Путь выходного MP4: {stem}_subtitles.mp4 с суффиксом при коллизии."""
    output_dir = Path(output_dir)
    stem = input_video.stem
    candidate = output_dir / f"{stem}_subtitles.mp4"
    if not _path_taken(candidate, reserved):
        return candidate

    counter = 2
    while True:
        candidate = output_dir / f"{stem}_subtitles_{counter}.mp4"
        if not _path_taken(candidate, reserved):
            return candidate
        counter += 1


def _path_taken(path: Path, reserved: set[Path] | None) -> bool:
    if path.exists():
        return True
    if reserved and path in reserved:
        return True
    return False


def build_jobs(inputs: list[Path], output_dir: Path) -> list[BatchJob]:
    """Сформировать список job для последовательной обработки."""
    reserved: set[Path] = set()
    jobs: list[BatchJob] = []
    for input_video in inputs:
        output_video = resolve_output_path(output_dir, input_video, reserved)
        reserved.add(output_video)
        jobs.append(BatchJob(input_video=input_video, output_video=output_video))
    return jobs
