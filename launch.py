# -*- coding: utf-8 -*-
"""Запуск SubForge через ярлык (без консоли, с понятной ошибкой)."""

from __future__ import annotations

import sys
import traceback


def _show_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror("SubForge", message)
        root.destroy()
    except Exception:
        pass


def main() -> int:
    try:
        from app.services.app_log import (
            format_log_hint,
            install_uncaught_handlers,
            log_exception,
            setup_app_logging,
        )
        from app.services.i18n import set_locale, t
        from app.services.settings import load_settings
        from app.ui.main_window import MainWindow

        settings = load_settings()
        set_locale(settings.ui_locale)
        setup_app_logging()
        install_uncaught_handlers()
        app = MainWindow()
        app.mainloop()
        return 0
    except Exception as exc:  # noqa: BLE001
        try:
            from app.services.app_log import format_log_hint, log_exception
            from app.services.i18n import set_locale, t
            from app.services.settings import load_settings

            settings = load_settings()
            set_locale(settings.ui_locale)
            log_exception("Startup failed", exc)
            details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            _show_error(
                t(
                    "startup.failed",
                    details=details,
                    log_hint=format_log_hint(),
                )
            )
        except Exception:
            details = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            _show_error(
                "Failed to start SubForge.\n\n"
                f"{details}\n\n"
                "Check that dependencies are installed:\n"
                "pip install -r requirements.txt"
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
