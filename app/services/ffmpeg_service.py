# -*- coding: utf-8 -*-
"""Работа с ffmpeg: поиск, проверка, извлечение аудио, вшивание субтитров."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from app.runtime_paths import bin_dir
from app.services.i18n import t
from app.services.languages import normalize_for_ffmpeg

if TYPE_CHECKING:
    from app.services.cancellation import CancellationToken

ProgressRatioCallback = Optional[Callable[[float], None]]

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")


class FFmpegError(RuntimeError):
    """Ошибка при работе с ffmpeg."""


class NoAudioStreamError(FFmpegError):
    """В контейнере нет аудиодорожки, которую видит ffmpeg/ffprobe."""


def no_audio_message() -> str:
    return t("ffmpeg.no_audio_message")


NO_AUDIO_MESSAGE = no_audio_message()


VERSION_TIMEOUT = 12
COMMAND_TIMEOUT = 600


def _project_ffmpeg() -> Path:
    return bin_dir() / "ffmpeg.exe"


def _winget_ffmpeg_paths() -> list[Path]:
    paths: list[Path] = []
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        packages = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if packages.is_dir():
            for pattern in ("Gyan.FFmpeg*", "*ffmpeg*", "*FFmpeg*"):
                for pkg in packages.glob(pattern):
                    paths.extend(pkg.glob("**/bin/ffmpeg.exe"))
                    paths.extend(pkg.glob("**/ffmpeg.exe"))

    for fixed in (
        Path(r"C:\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"),
        Path(r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe"),
    ):
        paths.append(fixed)
    return paths


def _iter_candidates() -> list[str]:
    ordered: list[str] = []

    bundled = _project_ffmpeg()
    if bundled.is_file():
        ordered.append(str(bundled))

    which = shutil.which("ffmpeg")
    if which:
        ordered.append(which)

    for path in _winget_ffmpeg_paths():
        if path.is_file():
            ordered.append(str(path))

    seen: set[str] = set()
    unique: list[str] = []
    for item in ordered:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _creationflags() -> int:
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        return subprocess.CREATE_NO_WINDOW
    return 0


def _verify_ffmpeg(path: str, timeout: float = VERSION_TIMEOUT) -> bool:
    exe = Path(path)
    if not exe.is_file():
        return False
    try:
        result = subprocess.run(
            [str(exe), "-version"],
            capture_output=True,
            timeout=timeout,
            creationflags=_creationflags(),
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return False

    if result.returncode != 0:
        return False

    output = (result.stdout or b"") + (result.stderr or b"")
    return b"ffmpeg version" in output.lower()


def find_ffmpeg() -> str:
    """Найти рабочий ffmpeg."""
    broken: list[str] = []
    for candidate in _iter_candidates():
        if _verify_ffmpeg(candidate):
            return candidate
        broken.append(candidate)

    if broken:
        paths = "\n".join(f"  • {p}" for p in broken[:5])
        raise FFmpegError(t("ffmpeg.broken", paths=paths))

    raise FFmpegError(t("ffmpeg.not_found"))


def _ffprobe_path(ffmpeg: str) -> Optional[str]:
    probe = Path(ffmpeg).with_name("ffprobe.exe")
    if probe.is_file():
        return str(probe)
    found = shutil.which("ffprobe")
    return found


def _run_ffprobe(args: list[str], ffmpeg: Optional[str] = None) -> Optional[str]:
    """Запустить ffprobe и вернуть stdout или None при ошибке."""
    probe = _ffprobe_path(ffmpeg or find_ffmpeg())
    if not probe:
        return None
    try:
        result = subprocess.run(
            [probe, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=VERSION_TIMEOUT,
            creationflags=_creationflags(),
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def describe_media_streams(path: Path, ffmpeg: Optional[str] = None) -> str:
    """Краткое описание потоков файла для журнала."""
    output = _run_ffprobe(
        [
            "-v",
            "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,channels,sample_rate",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        ffmpeg=ffmpeg,
    )
    if not output:
        return t("ffmpeg.streams_unreadable")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return t("ffmpeg.no_streams")
    return "; ".join(lines)


def has_audio_stream(path: Path, ffmpeg: Optional[str] = None) -> Optional[bool]:
    """Есть ли аудиодорожка. None — ffprobe недоступен, проверить позже через ffmpeg."""
    output = _run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        ffmpeg=ffmpeg,
    )
    if output is None:
        return None
    return bool(output)


def is_no_audio_error(exc: BaseException) -> bool:
    """True, если ошибка связана с отсутствием аудиопотока в файле."""
    if isinstance(exc, NoAudioStreamError):
        return True
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        return is_no_audio_error(cause)
    if isinstance(exc, FFmpegError):
        lowered = str(exc).lower()
        return "does not contain any stream" in lowered
    lowered = str(exc).lower()
    return "does not contain any stream" in lowered


def _short_ffmpeg_error(detail: str) -> str:
    """Сжать stderr ffmpeg до понятного сообщения для пользователя."""
    text = detail.strip()
    if not text:
        return t("ffmpeg.generic_error")

    lowered = text.lower()
    if "output file does not contain any stream" in lowered or "does not contain any stream" in lowered:
        return no_audio_message()

    interesting: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("ffmpeg version"):
            continue
        if stripped.startswith("built with"):
            continue
        if stripped.startswith("configuration:"):
            continue
        if stripped.startswith("lib"):
            continue
        if "Copyright (c)" in stripped:
            continue
        interesting.append(stripped)

    if interesting:
        tail = interesting[-3:]
        return "\n".join(tail)

    return text[:500]


def get_media_duration(path: Path) -> Optional[float]:
    """Длительность медиафайла в секундах."""
    ffmpeg = find_ffmpeg()
    ffprobe = _ffprobe_path(ffmpeg)
    if not ffprobe:
        return None
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=VERSION_TIMEOUT,
            creationflags=_creationflags(),
        )
        if result.returncode != 0:
            return None
        return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return None


def _parse_ffmpeg_time(line: str) -> Optional[float]:
    match = _TIME_RE.search(line)
    if not match:
        return None
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    return hours * 3600 + minutes * 60 + seconds


def _run_with_progress(
    cmd: list[str],
    duration: Optional[float],
    on_progress: ProgressRatioCallback = None,
    timeout: float = COMMAND_TIMEOUT,
    cancel: Optional["CancellationToken"] = None,
) -> None:
    from app.services.cancellation import PipelineCancelledError

    started = time.monotonic()
    stderr_chunks: list[str] = []

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creationflags(),
    )

    assert proc.stderr is not None
    while True:
        if cancel and cancel.is_cancelled:
            proc.kill()
            raise PipelineCancelledError(t("pipeline.cancelled"))

        if time.monotonic() - started > timeout:
            proc.kill()
            raise FFmpegError(
                t("ffmpeg.timeout", seconds=int(timeout))
            )

        line = proc.stderr.readline()
        if line:
            stderr_chunks.append(line)
            if on_progress and duration and duration > 0:
                pos = _parse_ffmpeg_time(line)
                if pos is not None:
                    on_progress(min(pos / duration, 0.99))
            continue

        if proc.poll() is not None:
            break

    if proc.returncode != 0:
        detail = "".join(stderr_chunks).strip()
        raise FFmpegError(
            _short_ffmpeg_error(detail)
            if detail
            else t("ffmpeg.command_failed", code=proc.returncode)
        )

    if on_progress:
        on_progress(1.0)


def _run(cmd: list[str], timeout: float = COMMAND_TIMEOUT) -> None:
    _run_with_progress(cmd, duration=None, on_progress=None, timeout=timeout)


def check_ffmpeg() -> str:
    """Проверить доступность ffmpeg, вернуть путь."""
    return find_ffmpeg()


def extract_audio(
    video_path: Path,
    audio_path: Path,
    on_progress: ProgressRatioCallback = None,
    cancel: Optional["CancellationToken"] = None,
) -> None:
    """Извлечь аудио в WAV 16 kHz mono для Whisper."""
    ffmpeg = find_ffmpeg()
    audio_path.parent.mkdir(parents=True, exist_ok=True)

    has_audio = has_audio_stream(video_path, ffmpeg=ffmpeg)
    if has_audio is False:
        summary = describe_media_streams(video_path, ffmpeg=ffmpeg)
        raise NoAudioStreamError(
            t(
                "ffmpeg.no_audio_detail",
                message=no_audio_message(),
                summary=summary,
            )
        )

    duration = get_media_duration(video_path)
    _run_with_progress(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(audio_path),
        ],
        duration=duration,
        on_progress=on_progress,
        cancel=cancel,
    )


def _subtitle_mux_args(lang: str) -> list[str]:
    """Аргументы ffmpeg для soft-субтитров, видимых при открытии видео."""
    return [
        "-c:s",
        "mov_text",
        "-metadata:s:s:0",
        f"language={lang}",
        "-metadata:s:s:0",
        "title=SubForge",
        "-disposition:s:0",
        "default+forced",
    ]


def mux_soft_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    language: str = "rus",
    on_progress: ProgressRatioCallback = None,
    cancel: Optional["CancellationToken"] = None,
) -> None:
    """Вшить soft-субтитры (mov_text) в MP4."""
    ffmpeg = find_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = get_media_duration(video_path)
    lang = normalize_for_ffmpeg(language)

    copy_cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(srt_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map",
        "1:0",
        "-c:v",
        "copy",
        "-c:a",
        "copy",
        *_subtitle_mux_args(lang),
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    try:
        _run_with_progress(copy_cmd, duration=duration, on_progress=on_progress, cancel=cancel)
        return
    except FFmpegError:
        pass

    encode_cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(srt_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map",
        "1:0",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        *_subtitle_mux_args(lang),
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run_with_progress(encode_cmd, duration=duration, on_progress=on_progress, cancel=cancel)
