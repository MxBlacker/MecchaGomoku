"""
Player-vs-AI mode.
Human chooses black or white; the AI (Rapfi engine) plays the other color.

Non-blocking design:
  - AI思考 runs in a background thread (the engine subprocess reader).
  - The update() method polls for the AI's move each frame so the UI
    never freezes — the board, hover preview, and "AI思考中..." indicator
    all keep rendering smoothly.
"""

from __future__ import annotations

from enum import Enum, auto
import pygame

from core.game_manager import GameManager, GameState
from core.stone import StoneColor
from core.ai_engine import RapfiEngine, shutdown_engine
from modes.base_mode import BaseMode
from ui.board_view import BoardView


class _AIState(Enum):
    """Internal state machine for the non-blocking AI turn cycle."""
    INIT = auto()           # engine initializing (update_init called each frame)
    IDLE = auto()           # waiting for human input
    REQUESTING = auto()     # need to send TURN + BEGIN to engine (next update)
    THINKING = auto()       # engine is searching; poll_move() each frame


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
        self._state = _AIState.INIT
        self._engine: RapfiEngine | None = None
        self.hover_pos: tuple[int, int] | None = None
        # Human's last move — sent to engine via TURN command
        self._last_human_move: tuple[int, int] = (-1, -1)

    @property
    def is_ai_thinking(self) -> bool:
        """True when the AI is searching (used by renderer for status text)."""
        if self._engine is None:
            return False
        return self._state in (_AIState.INIT, _AIState.THINKING) or self._engine.is_thinking

    def on_enter(self) -> None:
        self.gm.new_game()

        self._engine = RapfiEngine()
        if not self._engine.start(ai_color=self.ai_color):
            self._engine = None
            return

        self._state = _AIState.INIT

    def on_exit(self) -> None:
        if self._engine:
            self._engine.stop()
            self._engine = None

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.gm.state != GameState.PLAYING:
            return

        # Don't accept input while engine is still initializing
        if self._state == _AIState.INIT:
            return

        # ── Hover preview (always track, show only on human's turn) ──
        if event.type == pygame.MOUSEMOTION:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None and self.gm.board.is_empty(*pos):
                self.hover_pos = pos
            else:
                self.hover_pos = None

        # Only the human can click to place stones
        if self.gm.current_turn != self.human_color:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                row, col = pos
                if self.gm.place_stone(row, col):
                    self.hover_pos = None
                    self._last_human_move = (row, col)
                    self._state = _AIState.REQUESTING

    def update(self) -> None:
        """Called each frame — drives the non-blocking AI lifecycle."""
        if self._engine is None:
            return

        # ── Phase 1: engine initialization (non-blocking) ──
        if self._state == _AIState.INIT:
            result = self._engine.update_init()
            if result == "ready":
                # If AI is Black, its first move was already requested in
                # update_init() and stored in _first_move.
                first = self._engine.get_first_move()
                if first is not None:
                    self.gm.place_stone(*first)
                self._state = _AIState.IDLE
            elif result == "failed":
                self._engine.stop()
                self._engine = None
            return  # don't process gameplay until init finishes

        if self.gm.state != GameState.PLAYING:
            return

        # ── Phase 2: send move request to engine ──
        if self._state == _AIState.REQUESTING and self.gm.current_turn == self.ai_color:
            self._engine.request_move(*self._last_human_move)
            self._state = _AIState.THINKING

        # ── Phase 3: poll for AI response ──
        if self._state == _AIState.THINKING:
            move = self._engine.poll_move()
            if move is not None:
                self.gm.place_stone(*move)
                self._state = _AIState.IDLE
