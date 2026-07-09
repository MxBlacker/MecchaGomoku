"""
Font utilities — provides CJK-capable fonts for Chinese text rendering.
"""

from __future__ import annotations

import pygame

# Cache of font objects: (name_key, size) → Font
_font_cache: dict[tuple[str | None, int], pygame.font.Font] = {}

# CJK font candidates in preference order (Windows)
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

    Falls back gracefully: tries best CJK fonts first, then system default,
    then pygame's built-in bitmap font.
    """
    key = ("cjk", size, bold)
    if key in _font_cache:
        return _font_cache[key]

    font = None

    # 1. Try each known CJK font
    for name in _CJK_FONTS:
        try:
            candidate = pygame.font.SysFont(name, size, bold=bold)
            # Quick test: can it render a common Chinese char?
            test_surf = candidate.render("中", True, (255, 255, 255))
            if test_surf.get_width() > 5:  # valid glyph
                font = candidate
                break
        except Exception:
            continue

    # 2. Fallback — use system default (may or may not have CJK)
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
