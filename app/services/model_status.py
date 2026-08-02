# -*- coding: utf-8 -*-
"""Проверка: скачана ли модель Whisper локально."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from faster_whisper.utils import download_model

from app.services.engines import DEFAULT_ENGINE_ID, ENGINES, engine_label, resolve_engine
from app.services.i18n import t

# Примерный размер загрузки для подсказки пользователю
MODEL_DOWNLOAD_SIZE: dict[str, str] = {
    "base": "~150 МБ",
    "medium": "~1.5 ГБ",
    "large-v3": "~3 ГБ",
}


@dataclass(frozen=True)
class ModelStatus:
    model_size: str
    downloaded: bool
    local_path: Optional[str] = None

    @property
    def size_hint(self) -> str:
        return MODEL_DOWNLOAD_SIZE.get(self.model_size, "")


def get_model_status(model_size: str) -> ModelStatus:
    """Проверить наличие модели в локальном кэше Hugging Face."""
    try:
        path = download_model(model_size, local_files_only=True)
        return ModelStatus(model_size=model_size, downloaded=True, local_path=path)
    except Exception:
        return ModelStatus(model_size=model_size, downloaded=False)


def get_engine_status(engine_id: str) -> ModelStatus:
    preset = resolve_engine(engine_id)
    return get_model_status(preset.model_size)


def format_status_text(status: ModelStatus, engine_id: Optional[str] = None) -> str:
    label = engine_label(engine_id) if engine_id else ""
    if status.downloaded:
        return t("model.downloaded", label=label)
    size = status.size_hint
    if size:
        return t("model.not_downloaded_size", label=label, size=size)
    return t("model.not_downloaded", label=label)


def all_engines_status() -> dict[str, ModelStatus]:
    return {engine_id: get_model_status(preset.model_size) for engine_id, preset in ENGINES.items()}


def default_engine_status() -> ModelStatus:
    return get_engine_status(DEFAULT_ENGINE_ID)


def download_engine_model(engine_id: str) -> ModelStatus:
    """Скачать модель выбранного движка из Hugging Face."""
    preset = resolve_engine(engine_id)
    existing = get_model_status(preset.model_size)
    if existing.downloaded:
        return existing

    path = download_model(preset.model_size)
    return ModelStatus(model_size=preset.model_size, downloaded=True, local_path=path)
