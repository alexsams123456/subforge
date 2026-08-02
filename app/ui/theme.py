# -*- coding: utf-8 -*-
"""Визуальные токены SubForge."""

from __future__ import annotations

# Глубокий графит / холодно-синий — без фиолетовых «ИИ»-градиентов
COLORS = {
    "bg_deep": "#0B1220",
    "bg_panel": "#121A2B",
    "bg_elevated": "#1A2438",
    "bg_drop": "#152033",
    "border": "#2A3A55",
    "border_soft": "#1E2C44",
    "text": "#E8EEF8",
    "text_muted": "#8FA3C1",
    "text_dim": "#5E7190",
    "accent": "#3DDC97",
    "accent_hover": "#56E6A8",
    "accent_dim": "#1F8F63",
    "accent_text": "#04140C",
    "warn": "#F0B429",
    "error": "#F07178",
    "success": "#3DDC97",
    "progress_track": "#1E2C44",
    "progress_fill": "#3DDC97",
}

FONTS = {
    "brand": ("Segoe UI Variable Display", 32, "bold"),
    "brand_fallback": ("Segoe UI", 32, "bold"),
    "headline": ("Segoe UI Variable Text", 13, "normal"),
    "body": ("Segoe UI Variable Text", 13, "normal"),
    "body_bold": ("Segoe UI Variable Text", 13, "bold"),
    "small": ("Segoe UI Variable Text", 10, "normal"),
    "button": ("Segoe UI Variable Text", 13, "bold"),
}

SPACE = {
    "page_x": 24,
    "page_y": 14,
    "section": 10,
    "block": 14,
    "inner": 12,
    "field": 5,
    "row": 8,
}

CONTROL = {
    "menu_width": 200,
    "menu_height": 34,
    "btn_height": 36,
    "btn_primary_height": 42,
    "corner": 10,
    "corner_lg": 12,
}


def font_tuple(key: str) -> tuple:
    """Вернуть кортеж шрифта; CustomTkinter сам подхватит доступный face."""
    return FONTS.get(key, FONTS["body"])
