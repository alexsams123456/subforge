# -*- coding: utf-8 -*-
"""Пакетная очередь обработки видео."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.output_formats import DEFAULT_OUTPUT_FORMAT, resolve_extension


@dataclass(frozen=True)
class BatchJob:
    input_video: Path
    output_video: Path
    audio_source: Path | None = None


def resolve_output_path(
    output_dir: Path,
    input_video: Path,
    reserved: set[Path] | None = None,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> Path:
    """Путь выходного файла: {stem}_subtitles.{ext} с суффиксом при коллизии."""
    output_dir = Path(output_dir)
    stem = input_video.stem
    ext = resolve_extension(output_format)
    candidate = output_dir / f"{stem}_subtitles{ext}"
    if not _path_taken(candidate, reserved):
        return candidate

    counter = 2
    while True:
        candidate = output_dir / f"{stem}_subtitles_{counter}{ext}"
        if not _path_taken(candidate, reserved):
            return candidate
        counter += 1


def _path_taken(path: Path, reserved: set[Path] | None) -> bool:
    if path.exists():
        return True
    if reserved and path in reserved:
        return True
    return False


def build_jobs(
    inputs: list[Path],
    output_dir: Path,
    output_format: str = DEFAULT_OUTPUT_FORMAT,
) -> list[BatchJob]:
    """Сформировать список job для последовательной обработки."""
    reserved: set[Path] = set()
    jobs: list[BatchJob] = []
    for input_video in inputs:
        output_video = resolve_output_path(
            output_dir,
            input_video,
            reserved,
            output_format=output_format,
        )
        reserved.add(output_video)
        jobs.append(BatchJob(input_video=input_video, output_video=output_video))
    return jobs
