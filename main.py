#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точка входа SubForge."""

from app.services.app_log import setup_app_logging
from app.ui.main_window import MainWindow


def main() -> None:
    setup_app_logging()
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
