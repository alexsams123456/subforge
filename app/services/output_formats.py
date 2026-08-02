# -*- coding: utf-8 -*-
"""Профили форматов выходного видео."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.i18n import t

OutputFormatId = Literal["mp4", "mkv", "mov", "m4v", "avi", "webm", "wmv"]
SubtitleMode = Literal["soft", "burn_in"]

DEFAULT_OUTPUT_FORMAT: OutputFormatId = "mp4"

SOFT_SUBTITLE_FORMATS: tuple[OutputFormatId, ...] = ("mp4", "mkv", "mov", "m4v")

# Форматы в UI (без AVI/WMV — soft-дорожка в них недоступна в FFmpeg).
OUTPUT_FORMAT_ORDER: tuple[OutputFormatId, ...] = (
    "mp4",
    "mkv",
    "mov",
    "m4v",
    "webm",
)


@dataclass(frozen=True)
class OutputFormatProfile:
    format_id: OutputFormatId
    extension: str
    subtitle_mode: SubtitleMode
    subtitle_codec: str | None
    container_flags: tuple[str, ...]
    fallback_video_codec: str
    fallback_audio_codec: str
    burn_in_video_codec: str | None = None
    burn_in_audio_codec: str | None = None


_PROFILES: dict[OutputFormatId, OutputFormatProfile] = {
    "mp4": OutputFormatProfile(
        format_id="mp4",
        extension=".mp4",
        subtitle_mode="soft",
        subtitle_codec="mov_text",
        container_flags=("-movflags", "+faststart"),
        fallback_video_codec="libx264",
        fallback_audio_codec="aac",
    ),
    "m4v": OutputFormatProfile(
        format_id="m4v",
        extension=".m4v",
        subtitle_mode="soft",
        subtitle_codec="mov_text",
        container_flags=("-movflags", "+faststart"),
        fallback_video_codec="libx264",
        fallback_audio_codec="aac",
    ),
    "mov": OutputFormatProfile(
        format_id="mov",
        extension=".mov",
        subtitle_mode="soft",
        subtitle_codec="mov_text",
        container_flags=("-movflags", "+faststart"),
        fallback_video_codec="libx264",
        fallback_audio_codec="aac",
    ),
    "mkv": OutputFormatProfile(
        format_id="mkv",
        extension=".mkv",
        subtitle_mode="soft",
        subtitle_codec="srt",
        container_flags=(),
        fallback_video_codec="libx264",
        fallback_audio_codec="aac",
    ),
    "avi": OutputFormatProfile(
        format_id="avi",
        extension=".avi",
        subtitle_mode="burn_in",
        subtitle_codec=None,
        container_flags=(),
        fallback_video_codec="libx264",
        fallback_audio_codec="aac",
        burn_in_video_codec="libx264",
        burn_in_audio_codec="libmp3lame",
    ),
    "wmv": OutputFormatProfile(
        format_id="wmv",
        extension=".wmv",
        subtitle_mode="burn_in",
        subtitle_codec=None,
        container_flags=(),
        fallback_video_codec="wmv2",
        fallback_audio_codec="wmav2",
        burn_in_video_codec="wmv2",
        burn_in_audio_codec="wmav2",
    ),
    "webm": OutputFormatProfile(
        format_id="webm",
        extension=".webm",
        subtitle_mode="burn_in",
        subtitle_codec=None,
        container_flags=(),
        fallback_video_codec="libvpx-vp9",
        fallback_audio_codec="libopus",
        burn_in_video_codec="libvpx-vp9",
        burn_in_audio_codec="libopus",
    ),
}


OUTPUT_FORMAT_IDS = frozenset(_PROFILES.keys())

_LEGACY_BURN_IN_FORMATS = frozenset({"avi", "wmv"})


def normalize_output_format(value: str) -> OutputFormatId:
    """Нормализовать id формата; неизвестные и avi/wmv → mp4."""
    lowered = str(value).lower().strip()
    if lowered in _LEGACY_BURN_IN_FORMATS:
        return DEFAULT_OUTPUT_FORMAT
    if lowered in OUTPUT_FORMAT_IDS:
        return lowered  # type: ignore[return-value]
    return DEFAULT_OUTPUT_FORMAT


def supports_soft_subtitles(format_id: str) -> bool:
    """True, если формат поддерживает отключаемую soft-дорожку."""
    profile = get_profile(format_id)
    return profile.subtitle_mode == "soft"


def get_profile(format_id: str) -> OutputFormatProfile:
    """Профиль mux для формата."""
    lowered = str(format_id).lower().strip()
    if lowered in _PROFILES:
        return _PROFILES[lowered]  # type: ignore[return-value]
    return _PROFILES[DEFAULT_OUTPUT_FORMAT]


def resolve_extension(format_id: str) -> str:
    """Расширение файла для формата (с точкой)."""
    return get_profile(format_id).extension


def output_format_label(format_id: OutputFormatId) -> str:
    """Локализованная метка для UI."""
    return t(f"output_format.{format_id}")


def all_output_format_labels() -> list[str]:
    """Метки форматов в порядке OUTPUT_FORMAT_ORDER."""
    return [output_format_label(fmt) for fmt in OUTPUT_FORMAT_ORDER]


def label_to_format_id(label: str) -> OutputFormatId:
    """UI-метка → id формата."""
    for fmt in OUTPUT_FORMAT_ORDER:
        if output_format_label(fmt) == label:
            return fmt
    return DEFAULT_OUTPUT_FORMAT


def format_id_to_label(format_id: str) -> str:
    """Id формата → UI-метка."""
    return output_format_label(normalize_output_format(format_id))


def output_format_hint(format_id: str) -> str:
    """Подсказка для выбранного формата (пустая, если не нужна)."""
    fmt = normalize_output_format(format_id)
    if fmt == "webm":
        return t("output_format.hint.webm")
    return t("output_format.hint.default")
