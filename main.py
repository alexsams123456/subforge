#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точка входа SubForge."""

from app.services.app_log import install_uncaught_handlers, setup_app_logging
from app.ui.main_window import MainWindow


def main() -> None:
    setup_app_logging()
    install_uncaught_handlers()
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
