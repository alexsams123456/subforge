# -*- coding: utf-8 -*-
"""Тесты ETA."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.eta import EtaEstimator


class EtaTests(unittest.TestCase):
    @patch("app.services.eta.time.monotonic")
    def test_returns_none_before_thresholds(self, mock_mono: unittest.mock.MagicMock) -> None:
        mock_mono.side_effect = [100.0, 105.0, 109.0]
        estimator = EtaEstimator()

        self.assertIsNone(estimator.update(0.0))
        self.assertIsNone(estimator.update(0.5))
        self.assertIsNone(estimator.update(0.5))

    @patch("app.services.eta.time.monotonic")
    def test_estimates_remaining_at_half(self, mock_mono: unittest.mock.MagicMock) -> None:
        mock_mono.side_effect = [0.0, 110.0]
        estimator = EtaEstimator()

        self.assertIsNone(estimator.update(0.5))
        remaining = estimator.update(0.5)
        self.assertEqual(remaining, 110)

    @patch("app.services.eta.time.monotonic")
    def test_reset_clears_timer(self, mock_mono: unittest.mock.MagicMock) -> None:
        mock_mono.side_effect = [0.0, 100.0, 210.0]
        estimator = EtaEstimator()
        estimator.update(0.01)
        estimator.reset()
        self.assertIsNone(estimator.update(0.5))
        remaining = estimator.update(0.5)
        self.assertEqual(remaining, 110)


if __name__ == "__main__":
    unittest.main()
