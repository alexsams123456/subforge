# -*- coding: utf-8 -*-
"""Окно просмотра журнала ошибок SubForge."""

from __future__ import annotations

import subprocess
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from app import __app_name__
from app.services.app_log import get_log_file_path, read_log_text
from app.services.i18n import t
from app.ui.theme import COLORS, CONTROL, SPACE, font_tuple


class LogViewerWindow(ctk.CTkToplevel):
    """Модальное окно с текстом журнала и кнопками обновления/копирования."""

    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master)
        self.title(t("log.window_title"))
        self.geometry("720x420")
        self.minsize(560, 320)
        self.configure(fg_color=COLORS["bg_deep"])
        self.transient(master)
        self.grab_set()

        self._header = ctk.CTkLabel(
            self,
            text=t("log.header"),
            font=font_tuple("body_bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self._header.pack(fill="x", padx=SPACE["page_x"], pady=(SPACE["page_y"], SPACE["field"]))

        self._hint = ctk.CTkLabel(
            self,
            text=t("log.hint"),
            font=font_tuple("small"),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self._hint.pack(fill="x", padx=SPACE["page_x"], pady=(0, SPACE["inner"]))

        self._text = ctk.CTkTextbox(
            self,
            font=("Consolas", 11),
            fg_color=COLORS["bg_panel"],
            text_color=COLORS["text"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=CONTROL["corner"],
            wrap="word",
        )
        self._text.pack(fill="both", expand=True, padx=SPACE["page_x"], pady=(0, SPACE["inner"]))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=SPACE["page_x"], pady=(0, SPACE["page_y"]))

        self._btn_refresh = ctk.CTkButton(
            actions,
            text=t("btn.refresh"),
            font=font_tuple("body"),
            height=CONTROL["btn_height"],
            width=120,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self._refresh,
        )
        self._btn_refresh.pack(side="left")

        self._btn_copy = ctk.CTkButton(
            actions,
            text=t("btn.copy"),
            font=font_tuple("body"),
            height=CONTROL["btn_height"],
            width=120,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text"],
            command=self._copy,
        )
        self._btn_copy.pack(side="left", padx=(SPACE["row"], 0))

        self._btn_folder = ctk.CTkButton(
            actions,
            text=t("btn.log_folder"),
            font=font_tuple("body"),
            height=CONTROL["btn_height"],
            width=120,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["bg_elevated"],
            hover_color=COLORS["border"],
            text_color=COLORS["text_muted"],
            command=self._open_log_folder,
        )
        self._btn_folder.pack(side="left", padx=(SPACE["row"], 0))

        self._btn_close = ctk.CTkButton(
            actions,
            text=t("btn.close"),
            font=font_tuple("body"),
            height=CONTROL["btn_height"],
            width=120,
            corner_radius=CONTROL["corner"],
            fg_color=COLORS["accent_dim"],
            hover_color=COLORS["accent"],
            text_color=COLORS["text"],
            command=self.destroy,
        )
        self._btn_close.pack(side="right")

        self._refresh()
        self.after(50, self._center_over_master)

    def apply_locale(self) -> None:
        self.title(t("log.window_title"))
        self._header.configure(text=t("log.header"))
        self._hint.configure(text=t("log.hint"))
        self._btn_refresh.configure(text=t("btn.refresh"))
        self._btn_copy.configure(text=t("btn.copy"))
        self._btn_folder.configure(text=t("btn.log_folder"))
        self._btn_close.configure(text=t("btn.close"))

    def _center_over_master(self) -> None:
        self.update_idletasks()
        master = self.master
        if not isinstance(master, tk.Misc):
            return
        mx = master.winfo_rootx()
        my = master.winfo_rooty()
        mw = master.winfo_width()
        mh = master.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = mx + max(0, (mw - w) // 2)
        y = my + max(0, (mh - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def refresh(self) -> None:
        """Перечитать журнал и показать в текстовом поле."""
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", read_log_text())
        self._text.configure(state="disabled")
        self._text.see("end")

    def _refresh(self) -> None:
        self.refresh()

    def _copy(self) -> None:
        content = read_log_text()
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo(__app_name__, t("log.copied"), parent=self)

    def _open_log_folder(self) -> None:
        folder = str(get_log_file_path().parent.resolve())
        try:
            import os

            os.startfile(folder)  # type: ignore[attr-defined]
        except Exception:
            subprocess.run(["explorer", folder], check=False)
