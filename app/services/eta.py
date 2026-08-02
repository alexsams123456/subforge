# -*- coding: utf-8 -*-
"""Оценка оставшегося времени обработки."""

from __future__ import annotations

import time

from app.services.i18n import t

MIN_OVERALL = 0.03
MIN_ELAPSED_SEC = 10.0


class EtaEstimator:
    """Линейная экстраполяция ETA по общему прогрессу пайплайна."""

    def __init__(self) -> None:
        self._started_at: float | None = None

    def reset(self) -> None:
        self._started_at = None

    def update(self, overall: float) -> int | None:
        now = time.monotonic()
        if self._started_at is None:
            self._started_at = now

        overall = max(0.0, min(1.0, float(overall)))
        elapsed = now - self._started_at
        if overall < MIN_OVERALL or elapsed < MIN_ELAPSED_SEC:
            return None
        if overall >= 0.999:
            return 0

        remaining = elapsed * (1.0 - overall) / overall
        return max(0, int(round(remaining)))


def format_eta_duration(seconds: int) -> str:
    """Локализованная строка длительности для ETA."""
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return t("progress.eta_hours_minutes", h=hours, m=minutes)
        return t("progress.eta_hours_only", h=hours)
    if seconds >= 60:
        return t("progress.eta_minutes_only", m=seconds // 60)
    return t("progress.eta_seconds_only", s=seconds)
