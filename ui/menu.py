"""
Menu screens — main menu with title logo and image buttons.
(Background and top bar are drawn by the renderer.)
"""

from __future__ import annotations

import pygame
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, MENU_BTN_SCALE, MENU_BAR_HEIGHT,
    BACKGROUND_IMG, TITLE_IMG,
    BTN_SINGLE_PLAYER, BTN_PLAYER_VS_AI, BTN_INTERNET_VS,
    BTN_SKILL_GOMOKU, BTN_HISTORY_REVIEW, BTN_SETTING,
)
from ui.widgets import ImageButton


TITLE_SCALE = 0.70


class MainMenu:
    """The title screen — title logo + 6 mode buttons."""

    def __init__(
        self,
        on_pvp, on_ai, on_multiplayer, on_skill, on_history, on_settings,
    ):
        self._on_pvp = on_pvp
        self._on_ai = on_ai
        self._on_multiplayer = on_multiplayer
        self._on_skill = on_skill
        self._on_history = on_history
        self._on_settings = on_settings

        self._title_img = self._load_title()
        self._buttons: list[ImageButton] = []
        self._build_buttons()

    # ── Title ────────────────────────────────────────────

    @staticmethod
    def _load_title() -> pygame.Surface | None:
        try:
            img = pygame.image.load(TITLE_IMG).convert_alpha()
            w = int(img.get_width() * TITLE_SCALE)
            h = int(img.get_height() * TITLE_SCALE)
            return pygame.transform.smoothscale(img, (w, h))
        except FileNotFoundError:
            return None

    @property
    def _title_height(self) -> int:
        return self._title_img.get_height() if self._title_img else 0

    # ── Buttons ──────────────────────────────────────────

    def _build_buttons(self) -> None:
        pairs = [
            (BTN_SINGLE_PLAYER,  self._on_pvp),
            (BTN_SKILL_GOMOKU,   self._on_skill),
            (BTN_PLAYER_VS_AI,   self._on_ai),
            (BTN_HISTORY_REVIEW, self._on_history),
            (BTN_INTERNET_VS,    self._on_multiplayer),
            (BTN_SETTING,        self._on_settings),
        ]

        bw = int(425 * MENU_BTN_SCALE)
        bh = int(135 * MENU_BTN_SCALE)
        gap_x, gap_y = 30, 20
        total_w = bw * 2 + gap_x
        total_h = bh * 3 + gap_y * 2
        start_x = (WINDOW_WIDTH - total_w) // 2

        title_top = MENU_BAR_HEIGHT + 10
        title_bottom = title_top + self._title_height + 0
        remaining = WINDOW_HEIGHT - title_bottom
        start_y = title_bottom + (remaining - total_h) // 2

        for i, (path, cb) in enumerate(pairs):
            col, row = i % 2, i // 2
            x = start_x + col * (bw + gap_x)
            y = start_y + row * (bh + gap_y)
            self._buttons.append(ImageButton(x, y, path, callback=cb, scale=MENU_BTN_SCALE))

    # ── Event / Draw ─────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        for btn in self._buttons:
            btn.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        # Title logo
        if self._title_img:
            tx = (WINDOW_WIDTH - self._title_img.get_width()) // 2
            surface.blit(self._title_img, (tx, MENU_BAR_HEIGHT + 10))
        # Buttons
        for btn in self._buttons:
            btn.draw(surface)
