# -*- coding: utf-8 -*-
"""Запись ошибок SubForge в файл и внутренний журнал приложения."""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from collections import deque
from pathlib import Path
from threading import Lock

from app.services.i18n import t

_LOGGER_NAME = "subforge"
_LOG_FILE_NAME = "subforge.log"
_MAX_MEMORY_LINES = 2000
_initialized = False
_memory_lock = Lock()
_memory_lines: deque[str] = deque(maxlen=_MAX_MEMORY_LINES)


class _MemoryLogHandler(logging.Handler):
    """Дублирует записи лога во внутренний буфер приложения."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001
            self.handleError(record)
            return
        with _memory_lock:
            _memory_lines.append(line)
            if record.exc_info:
                for tb_line in traceback.format_exception(*record.exc_info):
                    for part in tb_line.rstrip("\n").splitlines():
                        _memory_lines.append(part)


def get_log_file_path() -> Path:
    """Путь к файлу логов (%LOCALAPPDATA%\\SubForge\\logs\\subforge.log)."""
    base = os.environ.get("LOCALAPPDATA", "")
    if base:
        return Path(base) / "SubForge" / "logs" / _LOG_FILE_NAME
    return Path.home() / ".subforge" / "logs" / _LOG_FILE_NAME


def _log_formatter() -> logging.Formatter:
    return logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _get_logger() -> logging.Logger:
    setup_app_logging()
    return logging.getLogger(_LOGGER_NAME)


def setup_app_logging() -> Path:
    """Настроить запись логов в файл и в память. Безопасно вызывать повторно."""
    global _initialized
    log_path = get_log_file_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(_LOGGER_NAME)
    if _initialized:
        return log_path

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = _log_formatter()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    memory_handler = _MemoryLogHandler()
    memory_handler.setLevel(logging.ERROR)
    memory_handler.setFormatter(formatter)
    logger.addHandler(memory_handler)

    _initialized = True
    return log_path


def log_info(context: str, message: str) -> None:
    """Записать информационное сообщение (drag-and-drop, этапы UI)."""
    _get_logger().info("%s: %s", context, message)


def log_exception(context: str, exc: BaseException) -> Path:
    """Записать контекст и полный traceback исключения в лог."""
    _get_logger().exception("%s: %s", context, exc)
    return get_log_file_path()


def _format_uncaught(exc_type, exc_value, exc_tb) -> str:
    return "".join(traceback.format_exception(exc_type, exc_value, exc_tb))


def _sys_excepthook(exc_type, exc_value, exc_tb) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    try:
        log_exception("uncaught", exc_value)
    except Exception:  # noqa: BLE001
        pass
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _threading_excepthook(args: threading.ExceptHookArgs) -> None:
    try:
        log_exception("uncaught_thread", args.exc_value)
    except Exception:  # noqa: BLE001
        pass
    if hasattr(threading, "__excepthook__") and threading.__excepthook__ is not None:
        threading.__excepthook__(args)


def install_uncaught_handlers() -> None:
    """Перехват необработанных исключений главного потока и worker-потоков."""
    sys.excepthook = _sys_excepthook
    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_excepthook


def read_log_text(max_lines: int = 500) -> str:
    """Текст журнала: сначала из памяти, иначе последние строки файла."""
    setup_app_logging()

    with _memory_lock:
        if _memory_lines:
            lines = list(_memory_lines)[-max_lines:]
            return "\n".join(lines)

    log_path = get_log_file_path()
    if not log_path.is_file():
        return t("app_log.empty")

    try:
        content = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return t("app_log.read_failed", error=exc)

    lines = content.splitlines()
    if len(lines) <= max_lines:
        return content.strip() or t("app_log.empty")
    return "\n".join(lines[-max_lines:])


def format_log_hint() -> str:
    """Строка для messagebox — открыть журнал в приложении."""
    return t("app_log.hint")
