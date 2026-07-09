"""
Local player-vs-player mode — two humans alternating on the same machine.
Tracks mouse hover for the ghost-stone preview.
"""

from __future__ import annotations

import pygame

from core.game_manager import GameManager, GameState
from modes.base_mode import BaseMode
from ui.board_view import BoardView


class LocalPvPMode(BaseMode):
    """Handles mouse clicks → stone placement, alternating between Black/White."""

    def __init__(self, game_manager: GameManager, board_view: BoardView):
        super().__init__(game_manager)
        self.board_view = board_view
        self.hover_pos: tuple[int, int] | None = None  # (row, col) under mouse

    def on_enter(self) -> None:
        self.gm.new_game()
        self.hover_pos = None

    def on_exit(self) -> None:
        self.hover_pos = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.gm.state != GameState.PLAYING:
            return

        if event.type == pygame.MOUSEMOTION:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                r, c = pos
                if self.gm.board.is_empty(r, c):
                    self.hover_pos = pos
                    return
            self.hover_pos = None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                row, col = pos
                if self.gm.place_stone(row, col):
                    self.hover_pos = None  # hide ghost after placement
                    return True
        return False

    def update(self) -> None:
        pass  # PvP doesn't need per-frame logic
