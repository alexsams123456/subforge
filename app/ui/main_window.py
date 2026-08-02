# -*- coding: utf-8 -*-
"""Главное окно SubForge."""

from __future__ import annotations

import os
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from app import __app_name__, __version__
from app.services.app_log import format_log_hint, log_exception
from app.services.cancellation import CancellationToken, PipelineCancelledError
from app.services.engines import (
    DEFAULT_ENGINE_ID,
    ENGINES,
    all_engine_labels,
    engine_description,
    engine_label,
    label_to_id,
)
from app.services.i18n import (
    all_locale_labels,
    label_to_locale,
    locale_label,
    set_locale,
    t,
)
from app.services.languages import (
    UI_LANGUAGE_LABELS,
    code_to_ui_label,
    ui_label_to_code,
    validate_language_pair,
)
from app.services.model_status import (
    ModelStatus,
    all_engines_status,
    download_engine_model,
    format_status_text,
    get_engine_status,
)
from app.services.batch_queue import BatchJob, build_jobs
from app.services.eta import EtaEstimator
from app.services.hardware import AccelerationInfo, detect_acceleration
from app.services.ffmpeg_service import (
    has_audio_stream,
)
from app.services.pipeline import PipelineError, SubtitlePipeline
from app.services.progress import ProgressSnapshot, ProgressTracker
from app.services.settings import AppSettings, load_settings, save_settings
from app.services.subtitle_format import DEFAULT_MAX_LINES, MAX_MAX_LINES, MIN_MAX_LINES
from app.ui.log_viewer import LogViewerWindow
from app.ui.stage_progress import StageProgressPanel
from app.ui.theme import COLORS, CONTROL, SPACE, font_tuple


VIDEO_EXTENSIONS = (
    "*.mp4",
    "*.mkv",
    "*.avi",
    "*.mov",
    "*.webm",
    "*.m4v",
    "*.wmv",
)

SUPPORTED_VIDEO_SUFFIXES = frozenset(
    ext.lstrip("*").lower() for ext in VIDEO_EXTENSIONS
)


class MainWindow(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._settings = load_settings()
        set_locale(self._settings.ui_locale)

        self.title(t("window.title"))
        self.geometry("840x620")
        self.minsize(800, 580)
        self.configure(fg_color=COLORS["bg_deep"])

        self._queue: list[Path] = []
        self._queue_row_widgets: list[ctk.CTkFrame] = []
        self._output_path: Optional[Path] = None
        self._batch_jobs: list[BatchJob] | None = None
        self._batch_index = 0
        self._batch_active = False
        self._batch_output_dir: Optional[Path] = None
        self._progress_queue_label: str | None = None
        self._eta = EtaEstimator()
        self._busy = False
        self._pipeline = SubtitlePipeline()
        self._progress_value = 0.0
        self._pulse_phase = 0
        self._ffmpeg_ok = False
        self._model_download_busy = False
        self._anim_after_id: Optional[str] = None
        self._last_bg_size: Optional[tuple[int, int]] = None
        self._bg_rect_id: Optional[int] = None
        self._bg_oval1_id: Optional[int] = None
        self._bg_oval2_id: Optional[int] = None
        self._bg_accent_id: Optional[int] = None
        self._log_viewer: Optional[LogViewerWindow] = None
        self._cancel_token: Optional[CancellationToken] = None
        self._accel_info: Optional[AccelerationInfo] = None
        self._build_ui()
        self._setup_drag_drop()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._animate_accent()
        self.after(0, self._maximize_window)
        self.after(200, self._check_ffmpeg_async)
        self.after(250, self._refresh_engine_status_async)
        self.after(300, self._check_acceleration_async)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        shell = ctk.CTkFrame(self, fg_color=COLORS["bg_deep"], corner_radius=0)
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            shell,
            highlightthickness=0,
            bd=0,
            bg=COLORS["bg_deep"],
        )
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._bg_canvas = canvas
        canvas.bind("<Configure>", self._on_bg_canvas_configure)

        self._scroll = ctk.CTkScrollableFrame(
            shell,
            fg_color="transparent",
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_dim"],
        )
        self._scroll.pack(fill="both", expand=True, padx=SPACE["page_x"], pady=SPACE["page_y"])

        content = ctk.CTkFrame(self._scroll, fg_color="transparent")
        content.pack(fill="x")
        content.grid_columnconfigure(0, weight=1)

        brand_wrap = ctk.CTkFrame(content, fg_color="transparent")
        brand_wrap.grid(row=0, column=0, sticky="ew", pady=(0, SPACE["section"]))

        self._brand = ctk.CTkLabel(
            brand_wrap,
            text=__app_name__,
            font=font_tuple("brand"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self._brand.pack(anchor="w")

        self._tagline = ctk.CTkLabel(
            brand_wrap,
            text=t("tagline"),
            font=font_tuple("headline"),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self._tagline.pack(anchor="w", pady=(2, 0))

        self._drop = ctk.CTkFrame(
            content,
            fg_color=COLORS["bg_drop"],
            border_width=1,
            border_color=COLORS["border"],
            corner_radius=CONTROL["corner_lg"],
        )
        self._drop.grid(row=1, column=0, sticky="ew", pady=(0, SPACE["section"]))

        inner = ctk.CTkFrame(self._drop, fg_color="transparent")
        inner.pack(fill="x", padx=SPACE["block"], pady=SPACE["block"])

        self._file_title = ctk.CTkLabel(
            inner,
            text=t("file.no_video"),
            font=font_tuple("body_bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self._file_title.pack(fill="x", anchor="w")

        self._file_hint = ctk.CTkLabel(
            inner,
            text=t("file.formats_hint"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
            wraplength=720,
            justify="left",
        )
        self._file_hint.pack(fill="x", anchor="w", pady=(SPACE["field"], SPACE["field"]))

        btn_row = ctk.CTkFrame(inner, fg_color="transparent")
        btn_row.pack(fill="x")

        self._btn_pick = ctk.CTkButton(
            btn_row,
            text=t("btn.pick_video"),
            font=font_tuple("button"),
            height=CONTROL["btn_height"],
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["accent_text"],
            command=self._pick_video,
        )
        self._btn_pick.pack(side="left")

        self._btn_clear = ctk.CTkButton(
            btn_row,
            text=t("btn.clear"),
            font=font_tuple("body"),
            height=CONTROL["btn_height"],
            width=120,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            command=self._clear_video,
            state="disabled",
        )
        self._btn_clear.pack(side="left", padx=(SPACE["row"], 0))

        self._queue_scroll = ctk.CTkScrollableFrame(
            inner,
            fg_color=COLORS["bg_elevated"],
            height=110,
            corner_radius=CONTROL["corner"],
            scrollbar_button_color=COLORS["border"],
            scrollbar_button_hover_color=COLORS["accent_dim"],
        )
        self._queue_inner = ctk.CTkFrame(self._queue_scroll, fg_color="transparent")
        self._queue_inner.pack(fill="x")

        settings = ctk.CTkFrame(content, fg_color="transparent")
        settings.grid(row=2, column=0, sticky="ew", pady=(0, SPACE["section"]))
        settings.grid_columnconfigure(0, weight=1, uniform="settings")
        settings.grid_columnconfigure(1, weight=1, uniform="settings")

        engine_box = ctk.CTkFrame(settings, fg_color="transparent")
        engine_box.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE["row"]))

        lang_box = ctk.CTkFrame(settings, fg_color="transparent")
        lang_box.grid(row=0, column=1, sticky="nsew", padx=(SPACE["row"], 0))

        engine_header = ctk.CTkFrame(engine_box, fg_color="transparent")
        engine_header.pack(fill="x")

        self._lbl_engine = ctk.CTkLabel(
            engine_header,
            text=t("settings.engine"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._lbl_engine.pack(side="left", anchor="w")

        self._engine_status_badge = ctk.CTkLabel(
            engine_header,
            text=t("status.checking_model"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="e",
        )
        self._engine_status_badge.pack(side="right", anchor="e")

        engine_controls = ctk.CTkFrame(engine_box, fg_color="transparent")
        engine_controls.pack(fill="x", pady=(SPACE["field"], 0))

        self._engine_var = ctk.StringVar(value=engine_label(self._settings.engine_id))
        self._engine_menu = ctk.CTkOptionMenu(
            engine_controls,
            values=all_engine_labels(),
            variable=self._engine_var,
            width=CONTROL["menu_width"],
            height=CONTROL["menu_height"],
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            dropdown_fg_color=COLORS["bg_panel"],
            font=font_tuple("body"),
            command=self._on_engine_change,
        )
        self._engine_menu.pack(side="left", fill="x", expand=True)

        self._btn_download_model = ctk.CTkButton(
            engine_controls,
            text=t("btn.download"),
            font=font_tuple("small"),
            height=CONTROL["menu_height"],
            width=88,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            command=self._download_model_async,
        )
        self._btn_download_model.pack(side="left", padx=(SPACE["row"], 0))

        self._lbl_speech = ctk.CTkLabel(
            lang_box,
            text=t("settings.speech_language"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._lbl_speech.pack(fill="x", anchor="w")

        self._lang_var = ctk.StringVar(value=code_to_ui_label(self._settings.speech_language))
        self._lang_menu = ctk.CTkOptionMenu(
            lang_box,
            values=list(UI_LANGUAGE_LABELS),
            variable=self._lang_var,
            width=CONTROL["menu_width"],
            height=CONTROL["menu_height"],
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            dropdown_fg_color=COLORS["bg_panel"],
            font=font_tuple("body"),
            command=self._on_processing_setting_change,
        )
        self._lang_menu.pack(fill="x", anchor="w", pady=(SPACE["field"], 0))

        self._lbl_subtitle = ctk.CTkLabel(
            lang_box,
            text=t("settings.subtitle_language"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._lbl_subtitle.pack(fill="x", anchor="w", pady=(SPACE["field"], 0))

        self._subtitle_lang_var = ctk.StringVar(
            value=code_to_ui_label(self._settings.subtitle_language)
        )
        self._subtitle_lang_menu = ctk.CTkOptionMenu(
            lang_box,
            values=list(UI_LANGUAGE_LABELS),
            variable=self._subtitle_lang_var,
            width=CONTROL["menu_width"],
            height=CONTROL["menu_height"],
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            dropdown_fg_color=COLORS["bg_panel"],
            font=font_tuple("body"),
            command=self._on_processing_setting_change,
        )
        self._subtitle_lang_menu.pack(fill="x", anchor="w", pady=(SPACE["field"], 0))

        subs_row = ctk.CTkFrame(settings, fg_color="transparent")
        subs_row.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(SPACE["field"], 0),
        )
        subs_row.grid_columnconfigure(1, weight=1)

        self._lbl_max_lines = ctk.CTkLabel(
            subs_row,
            text=t("settings.max_lines"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._lbl_max_lines.grid(row=0, column=0, sticky="w")

        self._lines_var = ctk.StringVar(value=str(self._settings.max_subtitle_lines))
        self._lines_menu = ctk.CTkOptionMenu(
            subs_row,
            values=[str(n) for n in range(MIN_MAX_LINES, MAX_MAX_LINES + 1)],
            variable=self._lines_var,
            width=72,
            height=CONTROL["menu_height"],
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            dropdown_fg_color=COLORS["bg_panel"],
            font=font_tuple("body"),
            command=self._on_processing_setting_change,
        )
        self._lines_menu.grid(row=0, column=1, sticky="w", padx=(SPACE["row"], 0))

        self._speakers_var = ctk.BooleanVar(value=self._settings.separate_speakers)
        self._speakers_switch = ctk.CTkSwitch(
            subs_row,
            text=t("settings.separate_speakers"),
            variable=self._speakers_var,
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            progress_color=COLORS["accent"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            command=self._on_processing_setting_change,
        )
        self._speakers_switch.grid(row=1, column=0, columnspan=2, sticky="w", pady=(SPACE["field"], 0))

        self._non_speech_var = ctk.BooleanVar(value=self._settings.hide_non_speech)
        self._non_speech_switch = ctk.CTkSwitch(
            subs_row,
            text=t("settings.hide_non_speech"),
            variable=self._non_speech_var,
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            progress_color=COLORS["accent"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            command=self._on_processing_setting_change,
        )
        self._non_speech_switch.grid(row=2, column=0, columnspan=2, sticky="w", pady=(SPACE["field"], 0))

        status_block = ctk.CTkFrame(content, fg_color="transparent")
        status_block.grid(row=3, column=0, sticky="ew", pady=(0, SPACE["section"]))

        self._engine_hint = ctk.CTkLabel(
            status_block,
            text=engine_description(self._settings.engine_id),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._engine_hint.pack(fill="x", anchor="w")

        self._engines_overview = ctk.CTkLabel(
            status_block,
            text="",
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._engines_overview.pack(fill="x", anchor="w", pady=(2, 0))

        self._accel_status = ctk.CTkLabel(
            status_block,
            text=t("status.checking_accel"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._accel_status.pack(fill="x", anchor="w", pady=(2, 0))

        self._ffmpeg_status = ctk.CTkLabel(
            status_block,
            text=t("status.checking_ffmpeg"),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._ffmpeg_status.pack(fill="x", anchor="w", pady=(2, 0))

        progress_wrap = ctk.CTkFrame(
            content,
            fg_color=COLORS["bg_panel"],
            border_width=1,
            border_color=COLORS["border_soft"],
            corner_radius=CONTROL["corner_lg"],
        )
        progress_wrap.grid(row=4, column=0, sticky="ew", pady=(0, SPACE["section"]))

        prog_inner = ctk.CTkFrame(progress_wrap, fg_color="transparent")
        prog_inner.pack(fill="x", padx=SPACE["inner"], pady=SPACE["inner"])

        self._stage_panel = StageProgressPanel(prog_inner)
        self._stage_panel.pack(fill="x")

        actions = ctk.CTkFrame(content, fg_color="transparent")
        actions.grid(row=5, column=0, sticky="ew", pady=(0, SPACE["field"]))

        self._btn_run = ctk.CTkButton(
            actions,
            text=t("btn.create_subtitles"),
            font=font_tuple("button"),
            height=CONTROL["btn_primary_height"],
            corner_radius=CONTROL["corner_lg"],
            fg_color=COLORS["accent_dim"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self._start_process,
            state="disabled",
        )
        self._btn_run.pack(side="left")

        self._btn_cancel = ctk.CTkButton(
            actions,
            text=t("btn.cancel"),
            font=font_tuple("body"),
            height=CONTROL["btn_primary_height"],
            width=120,
            corner_radius=CONTROL["corner_lg"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            command=self._on_cancel,
            state="disabled",
        )
        self._btn_cancel.pack(side="left", padx=(SPACE["row"], 0))

        self._btn_open = ctk.CTkButton(
            actions,
            text=t("btn.open_folder"),
            font=font_tuple("body"),
            height=CONTROL["btn_primary_height"],
            width=160,
            corner_radius=CONTROL["corner_lg"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            command=self._open_output_folder,
            state="disabled",
        )
        self._btn_open.pack(side="left", padx=(SPACE["row"], 0))

        footer_row = ctk.CTkFrame(content, fg_color="transparent")
        footer_row.grid(row=6, column=0, sticky="ew")
        footer_row.grid_columnconfigure(0, weight=1)

        self._footer = ctk.CTkLabel(
            footer_row,
            text=t("footer.version", version=__version__),
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._footer.grid(row=0, column=0, sticky="w")

        footer_actions = ctk.CTkFrame(footer_row, fg_color="transparent")
        footer_actions.grid(row=0, column=1, sticky="e")

        self._locale_var = ctk.StringVar(value=locale_label(self._settings.ui_locale))
        self._locale_menu = ctk.CTkOptionMenu(
            footer_actions,
            values=all_locale_labels(),
            variable=self._locale_var,
            width=120,
            height=28,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            button_color=COLORS["border"],
            button_hover_color=COLORS["accent_dim"],
            dropdown_fg_color=COLORS["bg_panel"],
            font=font_tuple("small"),
            command=self._on_ui_locale_change,
        )
        self._locale_menu.pack(side="left", padx=(0, SPACE["row"]))

        self._btn_log = ctk.CTkButton(
            footer_actions,
            text=t("btn.log"),
            font=font_tuple("small"),
            height=28,
            width=88,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            command=self._show_log_viewer,
        )
        self._btn_log.pack(side="left")

    def _apply_locale(self) -> None:
        self.title(t("window.title"))
        self._tagline.configure(text=t("tagline"))
        self._btn_pick.configure(text=t("btn.pick_video"))
        self._btn_clear.configure(text=t("btn.clear"))
        self._lbl_engine.configure(text=t("settings.engine"))
        self._lbl_speech.configure(text=t("settings.speech_language"))
        self._lbl_subtitle.configure(text=t("settings.subtitle_language"))
        self._lbl_max_lines.configure(text=t("settings.max_lines"))
        self._speakers_switch.configure(text=t("settings.separate_speakers"))
        self._non_speech_switch.configure(text=t("settings.hide_non_speech"))
        self._btn_download_model.configure(text=t("btn.download"))
        self._btn_run.configure(text=t("btn.create_subtitles"))
        self._btn_cancel.configure(text=t("btn.cancel"))
        self._btn_open.configure(text=t("btn.open_folder"))
        self._footer.configure(text=t("footer.version", version=__version__))
        self._btn_log.configure(text=t("btn.log"))

        engine_id = self._engine_id()
        self._engine_menu.configure(values=all_engine_labels())
        self._engine_var.set(engine_label(engine_id))
        self._engine_hint.configure(text=engine_description(engine_id))

        if not self._queue:
            self._file_title.configure(text=t("file.no_video"))
            self._file_hint.configure(text=t("file.formats_hint"), wraplength=720)
        else:
            self._update_queue_header()

        if not self._ffmpeg_ok and self._ffmpeg_status.cget("text") == t("status.checking_ffmpeg"):
            self._ffmpeg_status.configure(text=t("status.checking_ffmpeg"))

        self._stage_panel.apply_locale()
        self._apply_engine_status()
        self._apply_accel_status()

        if self._log_viewer is not None and self._log_viewer.winfo_exists():
            self._log_viewer.apply_locale()

    def _on_ui_locale_change(self, choice: str) -> None:
        code = label_to_locale(choice)
        if code == self._settings.ui_locale:
            return
        set_locale(code)
        self._settings.ui_locale = code
        save_settings(self._settings)
        self._apply_locale()

    def _persist_settings(self) -> None:
        self._settings.engine_id = self._engine_id()
        self._settings.speech_language = self._lang_code()
        self._settings.subtitle_language = self._subtitle_lang_code()
        self._settings.max_subtitle_lines = self._max_subtitle_lines()
        self._settings.separate_speakers = bool(self._speakers_var.get())
        self._settings.hide_non_speech = bool(self._non_speech_var.get())
        save_settings(self._settings)

    def _on_processing_setting_change(self, *_args) -> None:
        if self._busy:
            return
        self._persist_settings()

    def _maximize_window(self) -> None:
        self.update_idletasks()
        self.state("zoomed")

    def _on_bg_canvas_configure(self, event=None) -> None:
        if event is not None:
            size = (event.width, event.height)
            if size == self._last_bg_size:
                return
            self._last_bg_size = size
        canvas = self._bg_canvas
        try:
            if not canvas.winfo_exists():
                return
        except tk.TclError:
            return
        w = max(canvas.winfo_width(), 1)
        h = max(canvas.winfo_height(), 1)
        self._ensure_atmosphere_items(w, h)
        self._update_accent_pulse()

    def _ensure_atmosphere_items(self, w: int, h: int) -> None:
        canvas = self._bg_canvas
        if self._bg_rect_id is None:
            self._bg_rect_id = canvas.create_rectangle(
                0, 0, w, h, fill=COLORS["bg_deep"], outline=""
            )
            self._bg_oval1_id = canvas.create_oval(
                -w * 0.15,
                -h * 0.25,
                w * 0.55,
                h * 0.55,
                fill="#102038",
                outline="",
            )
            self._bg_oval2_id = canvas.create_oval(
                w * 0.45,
                h * 0.35,
                w * 1.25,
                h * 1.25,
                fill="#0E1C30",
                outline="",
            )
            pulse = 0.35 + 0.15 * abs((self._pulse_phase % 60) - 30) / 30
            accent = self._mix_hex(COLORS["accent"], COLORS["bg_deep"], 1.0 - pulse)
            self._bg_accent_id = canvas.create_rectangle(
                0, 0, w, 3, fill=accent, outline=""
            )
        else:
            canvas.coords(self._bg_rect_id, 0, 0, w, h)
            canvas.coords(self._bg_oval1_id, -w * 0.15, -h * 0.25, w * 0.55, h * 0.55)
            canvas.coords(self._bg_oval2_id, w * 0.45, h * 0.35, w * 1.25, h * 1.25)
            canvas.coords(self._bg_accent_id, 0, 0, w, 3)

    def _update_accent_pulse(self) -> None:
        canvas = self._bg_canvas
        try:
            if not canvas.winfo_exists():
                return
            if self._bg_accent_id is None:
                w = max(canvas.winfo_width(), 1)
                h = max(canvas.winfo_height(), 1)
                self._ensure_atmosphere_items(w, h)
        except tk.TclError:
            return
        pulse = 0.35 + 0.15 * abs((self._pulse_phase % 60) - 30) / 30
        accent = self._mix_hex(COLORS["accent"], COLORS["bg_deep"], 1.0 - pulse)
        try:
            canvas.itemconfig(self._bg_accent_id, fill=accent)
        except tk.TclError:
            return

    def _mix_hex(self, a: str, b: str, t_val: float) -> str:
        def parse(c: str) -> tuple[int, int, int]:
            c = c.lstrip("#")
            return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

        ar, ag, ab = parse(a)
        br, bg, bb = parse(b)
        r = int(ar + (br - ar) * t_val)
        g = int(ag + (bg - ag) * t_val)
        bl = int(ab + (bb - ab) * t_val)
        return f"#{r:02x}{g:02x}{bl:02x}"

    def _animate_accent(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self._pulse_phase = (self._pulse_phase + 1) % 120
        try:
            self._update_accent_pulse()
        except tk.TclError:
            return
        self._anim_after_id = self.after(50, self._animate_accent)

    def _on_close(self) -> None:
        if self._anim_after_id is not None:
            try:
                self.after_cancel(self._anim_after_id)
            except Exception:
                pass
            self._anim_after_id = None
        self.destroy()

    # -------------------------------------------------------------- actions
    def _lang_code(self) -> str:
        return ui_label_to_code(self._lang_var.get())

    def _subtitle_lang_code(self) -> str:
        return ui_label_to_code(self._subtitle_lang_var.get())

    def _engine_id(self) -> str:
        return label_to_id(self._engine_var.get())

    def _max_subtitle_lines(self) -> int:
        try:
            value = int(self._lines_var.get())
        except ValueError:
            value = DEFAULT_MAX_LINES
        return max(MIN_MAX_LINES, min(value, MAX_MAX_LINES))

    def _set_ffmpeg_status(self, ok: bool, message: str) -> None:
        self._ffmpeg_ok = ok
        self._ffmpeg_status.configure(
            text=message,
            text_color=COLORS["success"] if ok else COLORS["warn"],
        )

    def _apply_accel_status(self, info: AccelerationInfo | None = None) -> None:
        if info is not None:
            self._accel_info = info
        info = self._accel_info
        if info is None:
            self._accel_status.configure(
                text=t("status.checking_accel"),
                text_color=COLORS["text_dim"],
            )
            return
        if info.cuda_available:
            name = info.gpu_name or "CUDA"
            self._accel_status.configure(
                text=t("status.accel_cuda", name=name),
                text_color=COLORS["accent"],
            )
        else:
            self._accel_status.configure(
                text=t("status.accel_cpu"),
                text_color=COLORS["text_dim"],
            )

    def _check_acceleration_async(self) -> None:
        def worker() -> None:
            try:
                info = detect_acceleration()
            except Exception:  # noqa: BLE001
                info = AccelerationInfo(cuda_available=False)
            self.after(0, lambda i=info: self._apply_accel_status(i))

        threading.Thread(target=worker, daemon=True).start()

    def _setup_drag_drop(self) -> None:
        try:
            import windnd

            windnd.hook_dropfiles(self, func=self._on_files_dropped)
        except Exception:
            pass

    def _on_files_dropped(self, files) -> None:
        if self._busy or not files:
            return
        paths: list[Path] = []
        had_invalid = False
        for raw in files:
            path_str = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
            path = Path(path_str)
            if self._is_supported_video(path):
                paths.append(path)
            else:
                had_invalid = True
        if not paths:
            if had_invalid:
                messagebox.showwarning(__app_name__, t("file.drop_unsupported"))
            return
        if had_invalid:
            messagebox.showwarning(__app_name__, t("file.drop_partial"))
        self._add_to_queue(paths)

    @staticmethod
    def _is_supported_video(path: Path) -> bool:
        return path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES

    def _normalize_queue_path(self, path: Path) -> Path:
        try:
            return path.resolve()
        except OSError:
            return path

    def _add_to_queue(self, paths: list[Path]) -> None:
        existing = {self._normalize_queue_path(item) for item in self._queue}
        added = False
        for path in paths:
            if not self._is_supported_video(path):
                continue
            key = self._normalize_queue_path(path)
            if key in existing:
                continue
            existing.add(key)
            self._queue.append(path)
            added = True
        if added:
            self._refresh_queue_ui()
            self._reset_progress(t("main.status.file_selected"))

    def _remove_from_queue(self, index: int) -> None:
        if self._busy or index < 0 or index >= len(self._queue):
            return
        self._queue.pop(index)
        self._refresh_queue_ui()
        if not self._queue:
            self._reset_progress(t("main.status.select_video"))

    def _update_queue_header(self) -> None:
        count = len(self._queue)
        self._file_title.configure(text=t("file.queue_count", count=count))
        if count == 1:
            self._file_hint.configure(text=str(self._queue[0]), wraplength=720)
        else:
            self._file_hint.configure(
                text=t("file.queue_multi_hint", count=count),
                wraplength=720,
            )

    def _refresh_queue_ui(self) -> None:
        for widget in self._queue_row_widgets:
            widget.destroy()
        self._queue_row_widgets.clear()

        if not self._queue:
            self._queue_scroll.pack_forget()
            self._file_title.configure(text=t("file.no_video"))
            self._file_hint.configure(text=t("file.formats_hint"), wraplength=720)
            self._btn_clear.configure(state="disabled")
            self._btn_run.configure(
                state="disabled",
                fg_color=COLORS["accent_dim"],
                text_color=COLORS["text"],
            )
            return

        if not self._queue_scroll.winfo_ismapped():
            self._queue_scroll.pack(fill="x", pady=(SPACE["field"], 0))
        self._update_queue_header()
        self._btn_clear.configure(state="normal")
        self._btn_run.configure(
            state="normal",
            fg_color=COLORS["accent"],
            text_color=COLORS["accent_text"],
        )
        self._btn_open.configure(state="disabled")

        for index, path in enumerate(self._queue):
            row = ctk.CTkFrame(self._queue_inner, fg_color="transparent")
            row.pack(fill="x", pady=1)

            label = ctk.CTkLabel(
                row,
                text=path.name,
                font=font_tuple("small"),
                text_color=COLORS["text_muted"],
                anchor="w",
            )
            label.pack(side="left", fill="x", expand=True)

            remove_btn = ctk.CTkButton(
                row,
                text="×",
                width=28,
                height=24,
                corner_radius=CONTROL["corner"],
                fg_color=COLORS["bg_panel"],
                hover_color=COLORS["border"],
                text_color=COLORS["text_muted"],
                command=lambda idx=index: self._remove_from_queue(idx),
            )
            remove_btn.pack(side="right")
            self._queue_row_widgets.append(row)

    def _download_model_async(self) -> None:
        if self._busy or self._model_download_busy:
            return

        engine_id = self._engine_id()
        label = engine_label(engine_id)
        status = get_engine_status(engine_id)
        if status.downloaded:
            messagebox.showinfo(__app_name__, t("main.model_already_downloaded", label=label))
            return

        self._model_download_busy = True
        self._btn_download_model.configure(state="disabled")
        size = status.size_hint or "~150 MB"
        self._reset_progress(t("main.model_download_progress", label=label, size=size))

        def worker() -> None:
            tracker = ProgressTracker(
                on_progress=lambda snap: self.after(0, lambda s=snap: self._apply_progress(s))
            )
            try:
                tracker.begin("model", t("main.model_downloading", label=label))
                tracker.update("model", 0.2, t("main.model_download_connect"))
                download_engine_model(engine_id)
                tracker.complete("model", t("main.model_downloaded_msg", label=label))
                self.after(0, lambda: self._on_model_download_success(label))
            except Exception as exc:  # noqa: BLE001
                log_exception("Model download failed", exc)
                msg = str(exc)
                self.after(0, lambda m=msg: self._on_model_download_error(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_model_download_success(self, label: str) -> None:
        self._model_download_busy = False
        self._btn_download_model.configure(state="normal")
        self._apply_engine_status()
        snapshot = ProgressTracker().mark_all_complete(t("main.model_downloaded_msg", label=label))
        self._apply_progress(snapshot)
        messagebox.showinfo(__app_name__, t("main.model_downloaded_success", label=label))

    def _on_model_download_error(self, message: str) -> None:
        self._model_download_busy = False
        self._btn_download_model.configure(state="normal")
        self._reset_progress(t("main.status.model_download_error"))
        if messagebox.askyesno(
            __app_name__,
            t("main.model_download_failed", message=message, log_hint=format_log_hint()),
            icon="error",
        ):
            self._show_log_viewer()

    def _on_engine_change(self, choice: str) -> None:
        engine_id = label_to_id(choice)
        self._engine_hint.configure(text=engine_description(engine_id))
        self._apply_engine_status()
        if not self._busy:
            self._persist_settings()

    def _apply_engine_status(self, statuses: dict[str, ModelStatus] | None = None) -> None:
        if statuses is None:
            statuses = all_engines_status()

        engine_id = self._engine_id()
        current = statuses.get(engine_id) or get_engine_status(engine_id)

        if current.downloaded:
            self._engine_status_badge.configure(
                text=t("badge.downloaded"),
                text_color=COLORS["success"],
            )
        else:
            size = f" ({current.size_hint})" if current.size_hint else ""
            self._engine_status_badge.configure(
                text=t("badge.not_downloaded", size=size),
                text_color=COLORS["warn"],
            )

        overview_parts = [
            format_status_text(statuses.get(eid) or get_engine_status(eid), eid)
            for eid in ENGINES
        ]
        self._engines_overview.configure(text="  ·  ".join(overview_parts))

    def _refresh_engine_status_async(self) -> None:
        def worker() -> None:
            try:
                statuses = all_engines_status()
            except Exception:  # noqa: BLE001
                statuses = {}
            self.after(0, lambda: self._apply_engine_status(statuses))

        threading.Thread(target=worker, daemon=True).start()

    def _pick_video(self) -> None:
        if self._busy:
            return
        paths = filedialog.askopenfilenames(
            title=t("main.dialog.pick_video"),
            filetypes=[
                (t("main.dialog.filetypes.video"), " ".join(VIDEO_EXTENSIONS)),
                (t("main.dialog.filetypes.all"), "*.*"),
            ],
        )
        if not paths:
            return
        self._add_to_queue([Path(path) for path in paths])

    def _clear_video(self) -> None:
        if self._busy:
            return
        self._queue.clear()
        self._output_path = None
        self._batch_output_dir = None
        self._refresh_queue_ui()
        self._reset_progress(t("main.status.select_video"))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        pick_state = "disabled" if busy else "normal"
        self._btn_pick.configure(state=pick_state)
        self._btn_clear.configure(state="disabled" if busy or not self._queue else "normal")
        self._btn_run.configure(
            state="disabled" if busy or not self._queue else "normal",
        )
        self._engine_menu.configure(state=state)
        self._lang_menu.configure(state=state)
        self._subtitle_lang_menu.configure(state=state)
        self._lines_menu.configure(state=state)
        self._speakers_switch.configure(state=state)
        self._non_speech_switch.configure(state=state)
        self._locale_menu.configure(state=state)
        self._btn_cancel.configure(state="normal" if busy else "disabled")
        if not self._model_download_busy:
            self._btn_download_model.configure(state=state)
        if hasattr(self, "_queue_row_widgets"):
            for row in self._queue_row_widgets:
                for child in row.winfo_children():
                    if isinstance(child, ctk.CTkButton):
                        child.configure(state="disabled" if busy else "normal")

    def _reset_progress(self, detail: str | None = None) -> None:
        self._progress_value = 0.0
        self._stage_panel.reset()
        if detail is not None:
            self._stage_panel.set_detail(detail)

    def _apply_progress(self, snapshot: ProgressSnapshot) -> None:
        self._progress_value = snapshot.overall
        eta_seconds = self._eta.update(snapshot.overall) if self._busy else None
        self._stage_panel.apply(
            snapshot,
            eta_seconds=eta_seconds,
            queue_label=self._progress_queue_label,
        )

    def _preflight_batch(self, queue: list[Path]) -> bool:
        missing = [str(path) for path in queue if not path.is_file()]
        if missing:
            messagebox.showerror(
                __app_name__,
                t("main.batch_preflight_missing", files="\n".join(missing)),
            )
            return False

        no_audio = [path.name for path in queue if has_audio_stream(path) is False]
        if no_audio:
            messagebox.showerror(
                __app_name__,
                t("main.batch_preflight_no_audio", files="\n".join(no_audio)),
            )
            return False
        return True

    def _start_process(self) -> None:
        if self._busy or not self._queue:
            return

        if not self._ffmpeg_ok:
            messagebox.showerror(__app_name__, t("main.ffmpeg_not_installed"))
            return

        speech_language = self._lang_code()
        subtitle_language = self._subtitle_lang_code()
        pair_error = validate_language_pair(speech_language, subtitle_language)
        if pair_error:
            messagebox.showerror(__app_name__, pair_error)
            return

        output_dir = filedialog.askdirectory(title=t("main.dialog.output_folder"))
        if not output_dir:
            return

        output_dir_path = Path(output_dir)
        if not self._preflight_batch(self._queue):
            return

        self._batch_jobs = build_jobs(self._queue, output_dir_path)
        self._batch_index = 0
        self._batch_active = True
        self._batch_output_dir = output_dir_path
        self._process_next_batch_job()

    def _process_next_batch_job(self) -> None:
        if not self._batch_jobs or self._batch_index >= len(self._batch_jobs):
            return
        job = self._batch_jobs[self._batch_index]
        self._launch_pipeline(job.input_video, job.output_video, batch_mode=True)

    def _finish_batch_stopped(self, status_key: str) -> None:
        stopped_at = self._batch_index + 1 if self._batch_jobs else 0
        total = len(self._batch_jobs) if self._batch_jobs else 0
        self._batch_jobs = None
        self._batch_active = False
        self._batch_index = 0
        self._progress_queue_label = None
        self._cancel_token = None
        self._set_busy(False)
        if total > 1:
            detail = t(status_key, current=stopped_at, total=total)
        elif status_key == "main.batch_stopped":
            detail = t("main.status.cancelled")
        else:
            detail = t("main.status.error_retry")
        self._reset_progress(detail)

    def _on_batch_complete(self) -> None:
        count = len(self._batch_jobs) if self._batch_jobs else 0
        output_dir = self._batch_output_dir
        self._output_path = output_dir
        self._batch_jobs = None
        self._batch_active = False
        self._batch_index = 0
        self._progress_queue_label = None
        self._cancel_token = None
        self._set_busy(False)
        self._btn_open.configure(state="normal")
        snapshot = ProgressTracker().mark_all_complete(
            t("main.batch_done_detail", count=count)
        )
        self._apply_progress(snapshot)
        self._refresh_engine_status_async()
        messagebox.showinfo(
            __app_name__,
            t("main.batch_done", count=count, folder=str(output_dir)),
        )

    def _launch_pipeline(
        self,
        input_video: Path,
        output: Path,
        audio_source: Optional[Path] = None,
        batch_mode: bool = False,
    ) -> None:
        self._set_busy(True)
        self._btn_open.configure(state="disabled")
        self._reset_progress(t("main.status.processing_start"))
        self._cancel_token = CancellationToken()
        self._eta.reset()

        if batch_mode and self._batch_jobs:
            self._progress_queue_label = t(
                "progress.queue_position",
                current=self._batch_index + 1,
                total=len(self._batch_jobs),
            )
        else:
            self._progress_queue_label = None

        engine = self._engine_id()
        speech_language = self._lang_code()
        subtitle_language = self._subtitle_lang_code()
        max_lines = self._max_subtitle_lines()
        separate_speakers = bool(self._speakers_var.get())
        hide_non_speech = bool(self._non_speech_var.get())
        source = input_video
        cancel = self._cancel_token

        def worker() -> None:
            try:
                def on_progress(snapshot: ProgressSnapshot) -> None:
                    self.after(0, lambda s=snapshot: self._apply_progress(s))

                result = self._pipeline.process(
                    source,
                    output,
                    engine=engine,
                    speech_language=speech_language,
                    subtitle_language=subtitle_language,
                    max_subtitle_lines=max_lines,
                    separate_speakers=separate_speakers,
                    hide_non_speech=hide_non_speech,
                    audio_source=audio_source,
                    on_progress=on_progress,
                    cancel=cancel,
                )
                self.after(0, lambda r=result: self._on_success(r.output_path, r.segment_count))
            except PipelineCancelledError:
                self.after(0, self._on_cancelled)
            except PipelineError as exc:
                log_exception("Pipeline failed", exc)
                msg = str(exc)
                self.after(0, lambda m=msg: self._on_error(m))
            except Exception as exc:  # noqa: BLE001
                log_exception("Unexpected pipeline error", exc)
                msg = t("main.unexpected_error", error=exc)
                self.after(0, lambda m=msg: self._on_error(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_cancel(self) -> None:
        if self._cancel_token is not None:
            self._cancel_token.request_cancel()
        self._stage_panel.set_detail(t("main.status.cancelling"))

    def _on_cancelled(self) -> None:
        if self._batch_active:
            self._finish_batch_stopped("main.batch_stopped")
            return
        self._cancel_token = None
        self._set_busy(False)
        self._reset_progress(t("main.status.cancelled"))

    def _on_success(self, output_path: Path, segment_count: int) -> None:
        self._cancel_token = None
        self._output_path = output_path

        if self._batch_active and self._batch_jobs:
            self._batch_index += 1
            if self._batch_index < len(self._batch_jobs):
                self._process_next_batch_job()
                return
            self._on_batch_complete()
            return

        self._set_busy(False)
        self._btn_open.configure(state="normal")
        snapshot = ProgressTracker().mark_all_complete(
            t("main.success_detail", name=output_path.name, count=segment_count)
        )
        self._apply_progress(snapshot)
        self._refresh_engine_status_async()
        messagebox.showinfo(__app_name__, t("main.success"))

    def _show_log_viewer(self) -> None:
        if self._log_viewer is not None and self._log_viewer.winfo_exists():
            self._log_viewer.lift()
            self._log_viewer.focus_force()
            self._log_viewer.refresh()
            return
        self._log_viewer = LogViewerWindow(self)

    def _on_error(self, message: str) -> None:
        if self._batch_active:
            self._finish_batch_stopped("main.batch_stopped")
        else:
            self._cancel_token = None
            self._set_busy(False)
            self._reset_progress(t("main.status.error_retry"))
        if messagebox.askyesno(
            __app_name__,
            t("main.error_open_log", message=message, log_hint=format_log_hint()),
            icon="error",
        ):
            self._show_log_viewer()

    def _open_output_folder(self) -> None:
        target = self._batch_output_dir or self._output_path
        if not target:
            return
        folder = str(target if target.is_dir() else target.parent.resolve())
        try:
            os.startfile(folder)  # type: ignore[attr-defined]
        except Exception:
            subprocess.run(["explorer", folder], check=False)

    def _check_ffmpeg_async(self) -> None:
        def worker() -> None:
            try:
                from app.services import ffmpeg_service

                path = ffmpeg_service.check_ffmpeg()
                msg = t("main.ffmpeg_ready", path=path)
                self.after(0, lambda m=msg: self._set_ffmpeg_status(True, m))
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).replace("\n", " ")
                self.after(0, lambda m=msg: self._set_ffmpeg_status(False, f"ffmpeg: {m}"))

        threading.Thread(target=worker, daemon=True).start()
