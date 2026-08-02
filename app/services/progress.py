# -*- coding: utf-8 -*-
"""Отслеживание прогресса пайплайна по этапам."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from app.services.i18n import t


@dataclass(frozen=True)
class StageDef:
    id: str
    weight: float


STAGES: tuple[StageDef, ...] = (
    StageDef("ffmpeg", 0.02),
    StageDef("extract", 0.10),
    StageDef("model", 0.12),
    StageDef("transcribe", 0.48),
    StageDef("diarize", 0.08),
    StageDef("srt", 0.02),
    StageDef("mux", 0.18),
)

STAGE_BY_ID = {s.id: s for s in STAGES}


def stage_title(stage_id: str) -> str:
    return t(f"stage.{stage_id}")


@dataclass
class ProgressSnapshot:
    overall: float
    stage_id: str
    stage_title: str
    stage_ratio: float
    detail: str
    stages: dict[str, float] = field(default_factory=dict)

    @property
    def overall_percent(self) -> int:
        return int(round(max(0.0, min(1.0, self.overall)) * 100))

    @property
    def stage_percent(self) -> int:
        return int(round(max(0.0, min(1.0, self.stage_ratio)) * 100))


ProgressCallback = Optional[Callable[[ProgressSnapshot], None]]


class ProgressTracker:
    """Считает общий прогресс как взвешенную сумму этапов."""

    def __init__(self, on_progress: ProgressCallback = None) -> None:
        self._on_progress = on_progress
        self._ratios: dict[str, float] = {s.id: 0.0 for s in STAGES}
        self._current_stage = STAGES[0].id

    def begin(self, stage_id: str, detail: str = "") -> None:
        self._current_stage = stage_id
        self._emit(detail or stage_title(stage_id))

    def update(self, stage_id: str, ratio: float, detail: str = "") -> None:
        self._current_stage = stage_id
        self._ratios[stage_id] = max(0.0, min(1.0, float(ratio)))
        self._emit(detail)

    def complete(self, stage_id: str, detail: str = "") -> None:
        self._current_stage = stage_id
        self._ratios[stage_id] = 1.0
        title = stage_title(stage_id)
        self._emit(detail or f"{title}{t('stage.complete_suffix')}")

    def _overall(self) -> float:
        total = 0.0
        for stage in STAGES:
            total += stage.weight * self._ratios[stage.id]
        return total

    def snapshot(self, detail: str = "") -> ProgressSnapshot:
        stage = STAGE_BY_ID[self._current_stage]
        title = stage_title(stage.id)
        return ProgressSnapshot(
            overall=self._overall(),
            stage_id=self._current_stage,
            stage_title=title,
            stage_ratio=self._ratios[self._current_stage],
            detail=detail or title,
            stages=dict(self._ratios),
        )

    def mark_all_complete(self, detail: str = "") -> ProgressSnapshot:
        for stage in STAGES:
            self._ratios[stage.id] = 1.0
        self._current_stage = STAGES[-1].id
        return self.snapshot(detail or t("stage.done"))

    def _emit(self, detail: str) -> None:
        if not self._on_progress:
            return
        self._on_progress(self.snapshot(detail))
