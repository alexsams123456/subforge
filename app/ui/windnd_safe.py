# -*- coding: utf-8 -*-
"""Обёртка над windnd: один hook, совместимость с CTk на Windows x64."""

from __future__ import annotations

from typing import Callable

import windnd


def hook_dropfiles(
    tkwindow_or_winfoid,
    func: Callable[[list[str]], None],
    *,
    force_unicode: bool = True,
) -> None:
    """Подключить WM_DROPFILES через проверенный windnd."""
    windnd.hook_dropfiles(
        tkwindow_or_winfoid,
        func=func,
        force_unicode=force_unicode,
    )
