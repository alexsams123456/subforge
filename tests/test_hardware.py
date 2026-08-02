# -*- coding: utf-8 -*-
"""Тесты определения GPU/CPU."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services.hardware import detect_acceleration


class HardwareTests(unittest.TestCase):
    @patch("ctranslate2.get_cuda_device_count", return_value=0)
    def test_cpu_only(self, _mock_cuda_count: MagicMock) -> None:
        info = detect_acceleration()
        self.assertFalse(info.cuda_available)
        self.assertIsNone(info.gpu_name)

    @patch("torch.cuda.get_device_name", return_value="NVIDIA GeForce RTX 3060")
    @patch("torch.cuda.is_available", return_value=True)
    @patch("ctranslate2.get_cuda_device_count", return_value=1)
    def test_cuda_with_gpu_name(
        self,
        _mock_cuda_count: MagicMock,
        _mock_torch_available: MagicMock,
        _mock_device_name: MagicMock,
    ) -> None:
        info = detect_acceleration()
        self.assertTrue(info.cuda_available)
        self.assertEqual(info.gpu_name, "NVIDIA GeForce RTX 3060")

    @patch("torch.cuda.is_available", return_value=False)
    @patch("ctranslate2.get_cuda_device_count", return_value=1)
    def test_cuda_without_torch_name(
        self,
        _mock_cuda_count: MagicMock,
        _mock_torch_available: MagicMock,
    ) -> None:
        info = detect_acceleration()
        self.assertTrue(info.cuda_available)
        self.assertIsNone(info.gpu_name)


if __name__ == "__main__":
    unittest.main()
