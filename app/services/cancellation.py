# -*- coding: utf-8 -*-
"""Cooperative cancellation for the subtitle pipeline."""

from __future__ import annotations

from app.services.i18n import t


class PipelineCancelledError(RuntimeError):
    """Pipeline was cancelled by the user."""


class CancellationToken:
    """Thread-safe flag checked between pipeline stages and in long loops."""

    def __init__(self) -> None:
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def check(self) -> None:
        if self._cancelled:
            raise PipelineCancelledError(t("pipeline.cancelled"))
