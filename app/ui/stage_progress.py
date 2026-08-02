# -*- coding: utf-8 -*-
"""Компактная панель прогресса по этапам (2 колонки)."""

from __future__ import annotations

import customtkinter as ctk

from app.services.eta import format_eta_duration
from app.services.i18n import t
from app.services.progress import STAGES, ProgressSnapshot, stage_title
from app.ui.theme import COLORS, SPACE, font_tuple


class StageProgressPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._rows: dict[str, dict] = {}

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 4))

        self._progress_title = ctk.CTkLabel(
            header,
            text=t("progress.title"),
            font=font_tuple("body_bold"),
            text_color=COLORS["text"],
            anchor="w",
        )
        self._progress_title.pack(side="left")

        self._overall_label = ctk.CTkLabel(
            header,
            text="0%",
            font=font_tuple("body_bold"),
            text_color=COLORS["accent"],
            anchor="e",
            width=48,
        )
        self._overall_label.pack(side="right")

        self._overall_bar = ctk.CTkProgressBar(
            self,
            height=8,
            corner_radius=6,
            progress_color=COLORS["progress_fill"],
            fg_color=COLORS["progress_track"],
        )
        self._overall_bar.pack(fill="x", pady=(0, 4))
        self._overall_bar.set(0)

        self._detail_label = ctk.CTkLabel(
            self,
            text=t("progress.waiting"),
            font=font_tuple("small"),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self._detail_label.pack(fill="x", pady=(0, 2))

        self._eta_label = ctk.CTkLabel(
            self,
            text="",
            font=font_tuple("small"),
            text_color=COLORS["text_dim"],
            anchor="w",
        )
        self._eta_label.pack(fill="x", pady=(0, 6))

        stages_wrap = ctk.CTkFrame(
            self,
            fg_color=COLORS["bg_elevated"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border_soft"],
        )
        self._stages_wrap = stages_wrap

        inner = ctk.CTkFrame(stages_wrap, fg_color="transparent")
        self._stages_inner = inner
        inner.pack(fill="x", padx=10, pady=8)
        inner.grid_columnconfigure(0, weight=1)
        inner.grid_columnconfigure(1, weight=1)

        half = (len(STAGES) + 1) // 2
        for index, stage in enumerate(STAGES):
            col = 0 if index < half else 1
            row = index if index < half else index - half

            cell = ctk.CTkFrame(inner, fg_color="transparent")
            cell.grid(row=row, column=col, sticky="ew", padx=(0, 6 if col == 0 else 0), pady=(0, 4))

            title = ctk.CTkLabel(
                cell,
                text=f"{index + 1}. {stage_title(stage.id)}",
                font=font_tuple("small"),
                text_color=COLORS["text_dim"],
                anchor="w",
            )
            title.grid(row=0, column=0, columnspan=2, sticky="w")

            bar = ctk.CTkProgressBar(
                cell,
                height=6,
                corner_radius=4,
                progress_color=COLORS["accent_dim"],
                fg_color=COLORS["progress_track"],
            )
            bar.grid(row=1, column=0, sticky="ew", pady=(2, 0))
            bar.set(0)
            cell.grid_columnconfigure(0, weight=1)

            pct = ctk.CTkLabel(
                cell,
                text="0%",
                font=font_tuple("small"),
                text_color=COLORS["text_dim"],
                anchor="e",
                width=36,
            )
            pct.grid(row=1, column=1, padx=(6, 0))

            self._rows[stage.id] = {"title": title, "bar": bar, "pct": pct, "index": index}

        self.set_compact(True)

    def apply_locale(self) -> None:
        self._progress_title.configure(text=t("progress.title"))
        self._detail_label.configure(text=t("progress.waiting"))
        for stage in STAGES:
            row = self._rows[stage.id]
            row["title"].configure(text=f"{row['index'] + 1}. {stage_title(stage.id)}")

    def set_compact(self, compact: bool) -> None:
        """В простое скрыть список этапов — окно компактнее."""
        if compact:
            self._stages_wrap.pack_forget()
        else:
            self._stages_wrap.pack(fill="x")

    def reset(self) -> None:
        self.set_compact(True)
        self._overall_bar.set(0)
        self._overall_label.configure(text="0%")
        self._detail_label.configure(text=t("progress.waiting"))
        self._eta_label.configure(text="")
        for stage in STAGES:
            row = self._rows[stage.id]
            row["bar"].set(0)
            row["pct"].configure(text="0%", text_color=COLORS["text_dim"])
            row["title"].configure(text_color=COLORS["text_dim"])

    def set_detail(self, text: str) -> None:
        self._detail_label.configure(text=text)

    def apply(
        self,
        snapshot: ProgressSnapshot,
        eta_seconds: int | None = None,
        queue_label: str | None = None,
    ) -> None:
        if snapshot.overall > 0.01:
            self.set_compact(False)

        overall = max(0.0, min(1.0, snapshot.overall))
        self._overall_bar.set(overall)
        self._overall_label.configure(text=f"{snapshot.overall_percent}%")
        self._detail_label.configure(
            text=f"{snapshot.stage_title}: {snapshot.detail} ({snapshot.stage_percent}%)"
        )

        eta_parts: list[str] = []
        if queue_label:
            eta_parts.append(queue_label)
        if eta_seconds is not None:
            eta_parts.append(
                t("progress.eta_remaining", time=format_eta_duration(eta_seconds))
            )
        self._eta_label.configure(text="  ·  ".join(eta_parts))

        for stage in STAGES:
            ratio = max(0.0, min(1.0, snapshot.stages.get(stage.id, 0.0)))
            percent = int(round(ratio * 100))
            row = self._rows[stage.id]
            row["bar"].set(ratio)
            row["pct"].configure(text=f"{percent}%")

            if ratio >= 1.0:
                color = COLORS["success"]
            elif stage.id == snapshot.stage_id and ratio > 0:
                color = COLORS["accent"]
            else:
                color = COLORS["text_dim"]
            row["pct"].configure(text_color=color)
            row["title"].configure(
                text_color=COLORS["text"] if stage.id == snapshot.stage_id else COLORS["text_dim"]
            )
