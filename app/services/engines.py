# -*- coding: utf-8 -*-
"""Пресеты движков распознавания речи (Whisper)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.i18n import t


@dataclass(frozen=True)
class EnginePreset:
    id: str
    model_size: str
    beam_size: int
    best_of: int


# Простой — быстрый Whisper base
# Мощный — large-v3, максимальное качество (медленнее, больше памяти)
ENGINES: dict[str, EnginePreset] = {
    "simple": EnginePreset(
        id="simple",
        model_size="base",
        beam_size=5,
        best_of=5,
    ),
    "balanced": EnginePreset(
        id="balanced",
        model_size="medium",
        beam_size=6,
        best_of=6,
    ),
    "powerful": EnginePreset(
        id="powerful",
        model_size="large-v3",
        beam_size=8,
        best_of=8,
    ),
}

DEFAULT_ENGINE_ID = "powerful"
ENGINE_ORDER: tuple[str, ...] = ("powerful", "balanced", "simple")


def engine_label(engine_id: str) -> str:
    return t(f"engine.{engine_id}.label")


def engine_description(engine_id: str) -> str:
    return t(f"engine.{engine_id}.description")


def all_engine_labels() -> list[str]:
    return [engine_label(eid) for eid in ENGINE_ORDER]


def label_to_id(label: str) -> str:
    for engine_id in ENGINE_ORDER:
        if engine_label(engine_id) == label:
            return engine_id
    return DEFAULT_ENGINE_ID


def resolve_engine(engine_id_or_label: str) -> EnginePreset:
    key = (engine_id_or_label or "").strip()
    if key in ENGINES:
        return ENGINES[key]
    engine_id = label_to_id(key)
    return ENGINES[engine_id]
