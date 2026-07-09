"""
Replay mode — loads a saved GameRecord and lets the user step through moves.
"""

from __future__ import annotations

import pygame

from core.board import Board
from core.game_manager import GameManager, GameState
from core.recorder import GameRecorder, GameRecord
from core.stone import StoneColor
from modes.base_mode import BaseMode
from ui.board_view import BoardView
from config import COLOR_TEXT


class ReplayMode(BaseMode):
    """
    Steps through a previously recorded game.
    Controls:
        → (RIGHT) or wheel-down : next move
        ← (LEFT)  or wheel-up   : previous move
        SPACE                    : auto-play (toggle)
        ESC                      : back to history
    """

    def __init__(
        self,
        game_manager: GameManager,
        board_view: BoardView,
        recorder: GameRecorder,
    ):
        super().__init__(game_manager)
        self.board_view = board_view
        self.recorder = recorder
        self.record: GameRecord | None = None
        self._replay_board = Board()
        self._move_index = 0
        self._auto_play = False
        self._auto_timer = 0.0
        self._auto_delay = 0.5  # seconds between moves in auto-play
        self._on_done = None     # callback to return to history

    def load_record(self, record_id: str) -> bool:
        """Load a record and prepare for replay."""
        self.record = self.recorder.load(record_id)
        if self.record is None:
            return False
        self._replay_board = Board(size=self.record.board_size)
        self._move_index = 0
        self._auto_play = False
        self._auto_timer = 0.0
        self._apply_moves_up_to(0)
        self.gm.state = GameState.PLAYING  # keep renderer happy
        return True

    def on_enter(self) -> None:
        pass

    def on_exit(self) -> None:
        self._auto_play = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RIGHT:
                self._step_forward()
            elif event.key == pygame.K_LEFT:
                self._step_backward()
            elif event.key == pygame.K_SPACE:
                self._auto_play = not self._auto_play
                self._auto_timer = 0.0
            elif event.key == pygame.K_ESCAPE:
                if self._on_done:
                    self._on_done()

        elif event.type == pygame.MOUSEWHEEL:
            if event.y > 0:
                self._step_forward()
            elif event.y < 0:
                self._step_backward()

    def update(self) -> None:
        """Handle auto-play timing."""
        if self._auto_play and self.record:
            self._auto_timer += 1 / 60.0  # approximate — assumes ~60 FPS
            while self._auto_timer >= self._auto_delay and self._auto_play:
                self._auto_timer -= self._auto_delay
                if self._move_index < len(self.record.moves):
                    self._step_forward()
                else:
                    self._auto_play = False
                    break

    # ── Replay logic ─────────────────────────────────────

    def _step_forward(self) -> None:
        if self.record and self._move_index < len(self.record.moves):
            self._move_index += 1
            self._apply_moves_up_to(self._move_index)

    def _step_backward(self) -> None:
        if self._move_index > 0:
            self._move_index -= 1
            self._apply_moves_up_to(self._move_index)

    def _apply_moves_up_to(self, n: int) -> None:
        """Rebuild the board state from the first `n` moves, handling undo actions."""
        self._replay_board.reset()
        for move in self.record.moves[:n]:
            if move.get("action") == "undo":
                self._replay_board.undo()
            else:
                color = StoneColor[move["color"]]
                self._replay_board.place_stone(move["row"], move["col"], color)
        # Sync with game_manager so BoardView draws the right board
        self.gm.board = self._replay_board

    # ── Status info ──────────────────────────────────────

    @property
    def move_index(self) -> int:
        return self._move_index

    @property
    def total_moves(self) -> int:
        return len(self.record.moves) if self.record else 0

    @property
    def is_playing(self) -> bool:
        return self._auto_play
