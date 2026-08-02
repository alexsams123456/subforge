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
from app.services.output_formats import OutputFormatProfile, get_profile

if TYPE_CHECKING:
    from app.services.cancellation import CancellationToken

ProgressRatioCallback = Optional[Callable[[float], None]]

_TIME_RE = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
_PROGRESS_LINE_RE = re.compile(r"^\s*frame=\s*\d")
_ERROR_KEYWORDS = (
    "error",
    "invalid",
    "no such file",
    "permission denied",
    "could not",
    "failed",
    "not found",
    "conversion failed",
    "unable to",
)
_LIBASS_ERROR_MARKERS = (
    "error opening subtitle",
    "unable to open subtitle",
    "could not open file",
    "no such file or directory",
    "invalid data found when processing input",
)
_BURN_IN_FORCE_STYLE = (
    "FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,"
    "Outline=2,BorderStyle=1"
)
MIN_SRT_BYTES = 10


class FFmpegError(RuntimeError):
    """Ошибка при работе с ffmpeg."""


class NoAudioStreamError(FFmpegError):
    """В контейнере нет аудиодорожки, которую видит ffmpeg/ffprobe."""


def no_audio_message() -> str:
    return t("ffmpeg.no_audio_message")


NO_AUDIO_MESSAGE = no_audio_message()


VERSION_TIMEOUT = 12
COMMAND_TIMEOUT = 600
# Burn-in / re-encode: до ~10× длительности ролика, но не меньше COMMAND_TIMEOUT.
ENCODE_TIMEOUT_FACTOR = 10
MAX_ENCODE_TIMEOUT = 14_400  # 4 ч


def encode_timeout(duration: Optional[float]) -> float:
    """Таймаут ffmpeg для перекодирования (burn-in и fallback encode)."""
    if duration is None or duration <= 0:
        return float(COMMAND_TIMEOUT)
    scaled = duration * ENCODE_TIMEOUT_FACTOR + COMMAND_TIMEOUT
    return min(float(MAX_ENCODE_TIMEOUT), max(float(COMMAND_TIMEOUT), scaled))


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


def _is_ffmpeg_noise_line(line: str) -> bool:
    if line.startswith("ffmpeg version"):
        return True
    if line.startswith("built with"):
        return True
    if line.startswith("configuration:"):
        return True
    if line.startswith("lib"):
        return True
    return "Copyright (c)" in line


def _is_ffmpeg_progress_line(line: str) -> bool:
    if _PROGRESS_LINE_RE.match(line):
        return True
    if line.startswith("size=") and "time=" in line:
        return True
    if line.startswith("Stream mapping:"):
        return True
    if line.startswith("Press [q]"):
        return True
    return False


def _short_ffmpeg_error(detail: str) -> str:
    """Сжать stderr ffmpeg до понятного сообщения для пользователя."""
    text = detail.strip()
    if not text:
        return t("ffmpeg.generic_error")

    lowered = text.lower()
    if "output file does not contain any stream" in lowered or "does not contain any stream" in lowered:
        return no_audio_message()

    error_lines: list[str] = []
    other_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or _is_ffmpeg_noise_line(stripped) or _is_ffmpeg_progress_line(stripped):
            continue
        line_lower = stripped.lower()
        if any(keyword in line_lower for keyword in _ERROR_KEYWORDS):
            error_lines.append(stripped)
        else:
            other_lines.append(stripped)

    if error_lines:
        return "\n".join(error_lines[-3:])

    if other_lines:
        return "\n".join(other_lines[-3:])

    return text[:500]


def _format_mux_errors(copy_error: str | None, fallback_error: str) -> str:
    """Сообщение при падении copy и fallback mux."""
    combined = f"{copy_error or ''}\n{fallback_error}"
    if "Not yet implemented" in combined and "srt" in combined.lower():
        hint = t("ffmpeg.mux_soft_unsupported")
        if copy_error:
            return t("ffmpeg.mux_both_failed", copy=copy_error, fallback=f"{fallback_error}\n\n{hint}")
        return f"{fallback_error}\n\n{hint}"
    if copy_error:
        return t("ffmpeg.mux_both_failed", copy=copy_error, fallback=fallback_error)
    return fallback_error


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
) -> str:
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

    if proc.stdout:
        proc.stdout.close()
    if proc.stderr:
        proc.stderr.close()

    if proc.returncode != 0:
        detail = "".join(stderr_chunks).strip()
        raise FFmpegError(
            _short_ffmpeg_error(detail)
            if detail
            else t("ffmpeg.command_failed", code=proc.returncode)
        )

    if on_progress:
        on_progress(1.0)

    return "".join(stderr_chunks)


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


def _subtitle_filter_path(srt_path: Path) -> str:
    """Путь SRT для фильтра subtitles= на Windows."""
    resolved = srt_path.resolve()
    text = str(resolved).replace("\\", "/")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\\'")
    return text


def _burn_in_subtitle_filter(srt_path: Path) -> str:
    """Фильтр burn-in с читаемым стилем субтитров."""
    sub_path = _subtitle_filter_path(srt_path)
    return f"subtitles='{sub_path}':force_style='{_BURN_IN_FORCE_STYLE}'"


def _prepare_burn_in_srt(srt_path: Path, output_path: Path) -> Path:
    """Копия SRT рядом с выходным файлом — надёжнее libass на Windows."""
    local_srt = output_path.with_name(f"{output_path.stem}.srt")
    local_srt.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(srt_path, local_srt)
    return local_srt


def _libass_errors_in_stderr(stderr: str) -> list[str]:
    lowered = stderr.lower()
    hits: list[str] = []
    for line in stderr.splitlines():
        line_lower = line.strip().lower()
        if not line_lower:
            continue
        if any(marker in line_lower for marker in _LIBASS_ERROR_MARKERS):
            hits.append(line.strip())
    if hits:
        return hits
    if "libass" in lowered and "error" in lowered:
        for line in stderr.splitlines():
            stripped = line.strip()
            if stripped and "error" in stripped.lower():
                hits.append(stripped)
    return hits


def validate_srt_file(srt_path: Path, *, cue_count: int | None = None) -> None:
    """Проверить, что SRT не пуст перед mux."""
    if cue_count is not None and cue_count <= 0:
        raise FFmpegError(t("pipeline.empty_srt"))
    if not srt_path.is_file():
        raise FFmpegError(t("pipeline.empty_srt"))
    if srt_path.stat().st_size < MIN_SRT_BYTES:
        raise FFmpegError(t("pipeline.empty_srt"))


def count_subtitle_streams(path: Path, ffmpeg: Optional[str] = None) -> int:
    """Число subtitle-потоков в контейнере."""
    output = _run_ffprobe(
        [
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
        ffmpeg=ffmpeg,
    )
    if not output:
        return 0
    return len([line for line in output.splitlines() if line.strip()])


def _has_video_stream(path: Path, ffmpeg: Optional[str] = None) -> bool:
    output = _run_ffprobe(
        [
            "-v",
            "error",
            "-select_streams",
            "v",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(path),
        ],
        ffmpeg=ffmpeg,
    )
    return bool(output)


def extract_video_frame(
    video_path: Path,
    timestamp_sec: float,
    output_png: Path,
    ffmpeg: Optional[str] = None,
) -> None:
    """Извлечь один кадр в PNG (для тестов burn-in)."""
    exe = ffmpeg or find_ffmpeg()
    output_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            exe,
            "-y",
            "-ss",
            f"{timestamp_sec:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-update",
            "1",
            str(output_png),
        ],
        check=True,
        capture_output=True,
        creationflags=_creationflags(),
    )


def burn_in_frame_differs(
    source_video: Path,
    output_video: Path,
    timestamp_sec: float = 0.5,
    ffmpeg: Optional[str] = None,
) -> bool:
    """True, если кадр после burn-in отличается от исходника."""
    exe = ffmpeg or find_ffmpeg()
    work = output_video.parent
    source_png = work / "_subforge_src_frame.png"
    output_png = work / "_subforge_out_frame.png"
    try:
        extract_video_frame(source_video, timestamp_sec, source_png, ffmpeg=exe)
        extract_video_frame(output_video, timestamp_sec, output_png, ffmpeg=exe)
        return source_png.read_bytes() != output_png.read_bytes()
    finally:
        source_png.unlink(missing_ok=True)
        output_png.unlink(missing_ok=True)


def verify_output_subtitles(
    output_path: Path,
    profile: OutputFormatProfile,
    *,
    source_video: Path | None = None,
    mux_stderr: str = "",
    check_frame_diff: bool = False,
) -> None:
    """Проверить, что субтитры попали в выходной файл."""
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise FFmpegError(t("ffmpeg.verify_output_missing"))

    ffmpeg = find_ffmpeg()
    if profile.subtitle_mode == "soft":
        if count_subtitle_streams(output_path, ffmpeg) <= 0:
            raise FFmpegError(t("ffmpeg.verify_no_subtitle_stream"))
        return

    libass_errors = _libass_errors_in_stderr(mux_stderr)
    if libass_errors:
        raise FFmpegError(t("ffmpeg.verify_libass_failed", detail=libass_errors[0]))

    if not _has_video_stream(output_path, ffmpeg):
        raise FFmpegError(t("ffmpeg.verify_no_video_stream"))

    if check_frame_diff and source_video is not None:
        if not burn_in_frame_differs(source_video, output_path, ffmpeg=ffmpeg):
            raise FFmpegError(t("ffmpeg.verify_burn_in_invisible"))


def _subtitle_mux_args(profile: OutputFormatProfile, lang: str) -> list[str]:
    """Аргументы ffmpeg для soft-субтитров, видимых при открытии видео."""
    if profile.subtitle_codec is None:
        return []
    return [
        "-c:s",
        profile.subtitle_codec,
        "-metadata:s:s:0",
        f"language={lang}",
        "-metadata:s:s:0",
        "title=SubForge",
        "-disposition:s:0",
        "default",
    ]


def _append_container_flags(cmd: list[str], profile: OutputFormatProfile) -> None:
    cmd.extend(profile.container_flags)


def _include_audio_in_mux(video_path: Path, ffmpeg: str) -> bool:
    """True — добавить аудиодорожку в mux; False — только видео и субтитры."""
    has_audio = has_audio_stream(video_path, ffmpeg=ffmpeg)
    if has_audio is None:
        return True
    return has_audio


def _build_soft_mux_cmd(
    ffmpeg: str,
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    profile: OutputFormatProfile,
    lang: str,
    *,
    video_codec: str,
    include_audio: bool,
    audio_codec: str | None = None,
    video_encode_preset: tuple[str, ...] = (),
) -> list[str]:
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(srt_path),
        "-map",
        "0:v:0",
    ]
    if include_audio:
        cmd.extend(["-map", "0:a?"])
    cmd.extend(["-map", "1:0", "-c:v", video_codec])
    cmd.extend(video_encode_preset)
    if include_audio and audio_codec:
        cmd.extend(["-c:a", audio_codec])
        if audio_codec == "aac":
            cmd.extend(["-b:a", "192k"])
    cmd.extend(_subtitle_mux_args(profile, lang))
    _append_container_flags(cmd, profile)
    cmd.append(str(output_path))
    return cmd


def _mux_soft_subtitles(
    ffmpeg: str,
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    profile: OutputFormatProfile,
    lang: str,
    duration: Optional[float],
    on_progress: ProgressRatioCallback,
    cancel: Optional["CancellationToken"],
) -> None:
    include_audio = _include_audio_in_mux(video_path, ffmpeg)

    copy_cmd = _build_soft_mux_cmd(
        ffmpeg,
        video_path,
        srt_path,
        output_path,
        profile,
        lang,
        video_codec="copy",
        include_audio=include_audio,
        audio_codec="copy" if include_audio else None,
    )

    copy_error: str | None = None
    try:
        _run_with_progress(copy_cmd, duration=duration, on_progress=on_progress, cancel=cancel)
        return
    except FFmpegError as exc:
        copy_error = str(exc)

    encode_cmd = _build_soft_mux_cmd(
        ffmpeg,
        video_path,
        srt_path,
        output_path,
        profile,
        lang,
        video_codec=profile.fallback_video_codec,
        include_audio=include_audio,
        audio_codec=profile.fallback_audio_codec if include_audio else None,
        video_encode_preset=("-preset", "fast", "-crf", "20"),
    )

    try:
        _run_with_progress(
            encode_cmd,
            duration=duration,
            on_progress=on_progress,
            timeout=encode_timeout(duration),
            cancel=cancel,
        )
    except FFmpegError as exc:
        raise FFmpegError(_format_mux_errors(copy_error, str(exc))) from exc


def _burn_in_encode_args(video_codec: str, audio_codec: str) -> list[str]:
    args = ["-c:v", video_codec]
    if video_codec == "libx264":
        args.extend(["-preset", "fast", "-crf", "23"])
    else:
        args.extend(["-crf", "30", "-b:v", "0"])
    args.extend(["-c:a", audio_codec])
    if audio_codec == "aac":
        args.extend(["-b:a", "192k"])
    elif audio_codec == "libmp3lame":
        args.extend(["-b:a", "192k"])
    return args


def _mux_burn_in_subtitles(
    ffmpeg: str,
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    profile: OutputFormatProfile,
    duration: Optional[float],
    on_progress: ProgressRatioCallback,
    cancel: Optional["CancellationToken"],
) -> str:
    video_codec = profile.burn_in_video_codec or profile.fallback_video_codec
    audio_codec = profile.burn_in_audio_codec or profile.fallback_audio_codec
    local_srt = _prepare_burn_in_srt(srt_path, output_path)

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vf",
        _burn_in_subtitle_filter(local_srt),
        *_burn_in_encode_args(video_codec, audio_codec),
    ]
    _append_container_flags(cmd, profile)
    cmd.append(str(output_path))
    try:
        stderr = _run_with_progress(
            cmd,
            duration=duration,
            on_progress=on_progress,
            timeout=encode_timeout(duration),
            cancel=cancel,
        )
    finally:
        local_srt.unlink(missing_ok=True)

    libass_errors = _libass_errors_in_stderr(stderr)
    if libass_errors:
        raise FFmpegError(t("ffmpeg.verify_libass_failed", detail=libass_errors[0]))
    return stderr


def mux_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    language: str = "rus",
    output_format: str = "mp4",
    on_progress: ProgressRatioCallback = None,
    cancel: Optional["CancellationToken"] = None,
) -> None:
    """Вшить субтитры в видео согласно профилю формата."""
    profile = get_profile(output_format)
    ffmpeg = find_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = get_media_duration(video_path)
    lang = normalize_for_ffmpeg(language)

    validate_srt_file(srt_path)

    mux_stderr = ""
    if profile.subtitle_mode == "burn_in":
        mux_stderr = _mux_burn_in_subtitles(
            ffmpeg,
            video_path,
            srt_path,
            output_path,
            profile,
            duration,
            on_progress,
            cancel,
        )
    else:
        _mux_soft_subtitles(
            ffmpeg,
            video_path,
            srt_path,
            output_path,
            profile,
            lang,
            duration,
            on_progress,
            cancel,
        )

    verify_output_subtitles(
        output_path,
        profile,
        source_video=video_path if profile.subtitle_mode == "burn_in" else None,
        mux_stderr=mux_stderr,
    )


def mux_soft_subtitles(
    video_path: Path,
    srt_path: Path,
    output_path: Path,
    language: str = "rus",
    on_progress: ProgressRatioCallback = None,
    cancel: Optional["CancellationToken"] = None,
) -> None:
    """Вшить soft-субтитры (mov_text) в MP4 — совместимость."""
    mux_subtitles(
        video_path,
        srt_path,
        output_path,
        language=language,
        output_format="mp4",
        on_progress=on_progress,
        cancel=cancel,
    )
