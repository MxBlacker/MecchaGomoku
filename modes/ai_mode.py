"""
Player-vs-AI mode.
Currently a placeholder — the AI will be connected via an external API later.
"""

from __future__ import annotations

import pygame

from core.game_manager import GameManager, GameState
from core.stone import StoneColor
from modes.base_mode import BaseMode
from ui.board_view import BoardView


class AIVsMode(BaseMode):
    """
    Human (Black) vs AI (White).
    The AI integration point is the `_request_ai_move()` method.
    """

    def __init__(self, game_manager: GameManager, board_view: BoardView):
        super().__init__(game_manager)
        self.board_view = board_view
        self._human_color = StoneColor.BLACK
        self._ai_color = StoneColor.WHITE
        self._ai_thinking = False

    def on_enter(self) -> None:
        self.gm.new_game()

    def on_exit(self) -> None:
        pass

    def handle_event(self, event: pygame.event.Event) -> None:
        # Only allow input when it's the human's turn
        if self.gm.current_turn != self._human_color:
            return
        if self.gm.state != GameState.PLAYING:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                row, col = pos
                if self.gm.place_stone(row, col):
                    self._ai_thinking = True  # trigger AI in update()

    def update(self) -> None:
        """Called each frame — if it's the AI's turn, request a move."""
        if (
            self._ai_thinking
            and self.gm.state == GameState.PLAYING
            and self.gm.current_turn == self._ai_color
        ):
            self._ai_thinking = False
            move = self._request_ai_move()
            if move is not None:
                self.gm.place_stone(*move)

    # ── AI integration point ────────────────────────────

    def _request_ai_move(self) -> tuple[int, int] | None:
        """
        TODO: Call an external AI API (e.g. DeepSeek, a local model, etc.)
        to get the next move. For now, returns None (AI passes).

        Expected return: (row, col) or None.
        """
        # Placeholder — replace with actual API call later
        # Example:
        #   board_state = self.gm.board.get_grid()
        #   response = api.post("/move", json={"board": board_state})
        #   return response["row"], response["col"]
        return None
