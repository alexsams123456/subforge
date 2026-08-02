# -*- coding: utf-8 -*-
"""Тесты cooperative cancellation."""

from __future__ import annotations

import unittest

from app.services.cancellation import CancellationToken, PipelineCancelledError
from app.services.i18n import set_locale


class CancellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        set_locale("en")

    def test_check_raises_after_request_cancel(self) -> None:
        token = CancellationToken()
        token.request_cancel()
        with self.assertRaises(PipelineCancelledError):
            token.check()

    def test_not_cancelled_by_default(self) -> None:
        token = CancellationToken()
        self.assertFalse(token.is_cancelled)
        token.check()


if __name__ == "__main__":
    unittest.main()
