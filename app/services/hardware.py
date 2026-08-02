# -*- coding: utf-8 -*-
"""Определение аппаратного ускорения (CUDA / CPU)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccelerationInfo:
    cuda_available: bool
    gpu_name: str | None = None


def detect_acceleration() -> AccelerationInfo:
    """Проверить доступность CUDA для Whisper (ctranslate2) и имя GPU (torch)."""
    cuda_available = False
    try:
        import ctranslate2

        cuda_available = ctranslate2.get_cuda_device_count() > 0
    except Exception:
        cuda_available = False

    gpu_name: str | None = None
    if cuda_available:
        try:
            import torch

            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
        except Exception:
            gpu_name = None

    return AccelerationInfo(cuda_available=cuda_available, gpu_name=gpu_name)
