"""
Player-vs-AI mode.
Human chooses black or white; the AI (Rapfi engine) plays the other color.
"""

from __future__ import annotations

import pygame

from core.game_manager import GameManager, GameState
from core.stone import StoneColor
from core.ai_engine import RapfiEngine, shutdown_engine
from modes.base_mode import BaseMode
from ui.board_view import BoardView


class AIVsMode(BaseMode):
    """
    Human vs AI (Rapfi engine via Piskvork protocol).
    """

    def __init__(self, game_manager: GameManager, board_view: BoardView,
                 human_color: StoneColor = StoneColor.BLACK):
        super().__init__(game_manager)
        self.board_view = board_view
        self.human_color = human_color
        self.ai_color = human_color.opponent()
        self._ai_thinking = False
        self._engine: RapfiEngine | None = None
        self.hover_pos: tuple[int, int] | None = None

    def on_enter(self) -> None:
        self.gm.new_game()

        # Start the Rapfi engine (first move obtained inside start() if AI is Black)
        self._engine = RapfiEngine()
        if not self._engine.start(ai_color=self.ai_color):
            self._engine = None
            return

        # If AI plays black, its first move is ready — trigger immediately
        if self.ai_color == StoneColor.BLACK:
            self._ai_thinking = True

    def on_exit(self) -> None:
        if self._engine:
            self._engine.stop()
            self._engine = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.gm.state != GameState.PLAYING:
            return

        # Hover preview (always track, but only show on human's turn)
        if event.type == pygame.MOUSEMOTION:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None and self.gm.board.is_empty(*pos):
                self.hover_pos = pos
            else:
                self.hover_pos = None

        if self.gm.current_turn != self.human_color:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                row, col = pos
                if self.gm.place_stone(row, col):
                    self.hover_pos = None
                    self._ai_thinking = True  # trigger AI in update()

    def update(self) -> None:
        """Called each frame — if it's the AI's turn, request a move."""
        if (
            self._ai_thinking
            and self._engine is not None
            and self.gm.state == GameState.PLAYING
            and self.gm.current_turn == self.ai_color
        ):
            self._ai_thinking = False
            move = self._request_ai_move()
            if move is not None:
                self.gm.place_stone(*move)

    # ── AI integration ──────────────────────────────────

    def _request_ai_move(self) -> tuple[int, int] | None:
        """Get the AI's next move from the Rapfi engine."""
        if self._engine is None:
            return None

        last_stone = self.gm.board.last_move()
        if last_stone and last_stone.color == self.human_color:
            opp_row, opp_col = last_stone.row, last_stone.col
        else:
            opp_row, opp_col = -1, -1

        return self._engine.get_move(opp_row, opp_col)
