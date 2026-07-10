"""
Font utilities — provides CJK-capable fonts for Chinese text rendering.
Uses bundled Noto Sans SC font when available, falls back to system CJK fonts.
"""

from __future__ import annotations

import os
import pygame

from config import CJK_FONT

# Cache of font objects: (name_key, size) → Font
_font_cache: dict[tuple[str | None, int], pygame.font.Font] = {}

# CJK font candidates in preference order (Windows) — fallback only
_CJK_FONTS = [
    "Microsoft YaHei",
    "Microsoft YaHei UI",
    "SimHei",
    "SimSun",
    "Microsoft JhengHei",
    "KaiTi",
    "FangSong",
]


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """
    Return a pygame Font that supports Chinese (CJK) characters.

    Priority:
      1. Bundled Noto Sans SC (via pygame.font.Font with the .ttf file)
      2. System-installed CJK fonts (via pygame.font.SysFont)
      3. System default / pygame built-in fallback
    """
    key = ("cjk", size, bold)
    if key in _font_cache:
        return _font_cache[key]

    font = None

    # 1. Try the bundled CJK font file (works even when system has no CJK fonts)
    if os.path.exists(CJK_FONT):
        try:
            font = pygame.font.Font(CJK_FONT, size)
            if bold:
                font.set_bold(True)
            # Quick test: can it render a common Chinese char?
            test_surf = font.render("中", True, (255, 255, 255))
            if test_surf.get_width() > 5:  # valid glyph
                _font_cache[key] = font
                return font
        except Exception:
            pass

    # 2. Try each known system CJK font
    for name in _CJK_FONTS:
        try:
            candidate = pygame.font.SysFont(name, size, bold=bold)
            test_surf = candidate.render("中", True, (255, 255, 255))
            if test_surf.get_width() > 5:
                font = candidate
                break
        except Exception:
            continue

    # 3. Fallback — use system default (may or may not have CJK)
    if font is None:
        try:
            font = pygame.font.SysFont(None, size, bold=bold)
        except Exception:
            font = pygame.font.Font(None, size)

    _font_cache[key] = font
    return font


def get_default_font(size: int) -> pygame.font.Font:
    """Shortcut for the standard CJK font at a given size."""
    return get_font(size, bold=False)


def get_title_font(size: int) -> pygame.font.Font:
    """Shortcut for a bold CJK title font."""
    return get_font(size, bold=True)
