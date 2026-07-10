"""
Replay mode — loads a saved GameRecord and lets the user step through moves.
Includes AI-powered analysis via DeepSeek API.
"""

from __future__ import annotations

import pygame

from core.board import Board, pos_to_label
from core.game_manager import GameManager, GameState
from core.recorder import GameRecorder, GameRecord
from core.stone import StoneColor
from core.ai_analyzer import AIAnalyzer
from modes.base_mode import BaseMode
from ui.board_view import BoardView
from config import COLOR_TEXT, DEEPSEEK_API_TOKEN


class ReplayMode(BaseMode):
    """
    Steps through a previously recorded game.
    Controls:
        → (RIGHT) or wheel-down : next move
        ← (LEFT)  or wheel-up   : previous move
        SPACE                    : auto-play (toggle)
        ESC                      : back to history
        A                        : toggle AI analysis panel
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

        # AI analysis
        self._ai = AIAnalyzer(token=DEEPSEEK_API_TOKEN)
        self._ai_text: str = ""          # current analysis text to display
        self._ai_move: int = -1          # which move the current text is for
        self._ai_pending: bool = False   # waiting for API response
        self._ai_panel_visible: bool = True  # toggle with 'A' key
        self._ai.set_on_result(self._on_ai_result)

    def load_record(self, record_id: str) -> bool:
        """Load a record and prepare for replay."""
        self.record = self.recorder.load(record_id)
        if self.record is None:
            return False
        self._replay_board = Board(size=self.record.board_size)
        self._move_index = 0
        self._auto_play = False
        self._auto_timer = 0.0
        self._ai_text = ""
        self._ai_move = -1
        self._ai_pending = False
        self._ai.clear_cache()
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
            elif event.key == pygame.K_a:
                self._ai_panel_visible = not self._ai_panel_visible

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

        # Trigger AI analysis for the new position
        self._request_ai_analysis()

    def _request_ai_analysis(self) -> None:
        """Request AI analysis for the current board position."""
        if not self._ai_panel_visible:
            return
        if not self.record or self._move_index == 0:
            self._ai_text = ""
            self._ai_move = 0
            self._ai_pending = False
            return

        # Check cache first
        cached = self._ai.get_cached(self._move_index)
        if cached is not None:
            self._ai_text = cached
            self._ai_move = self._move_index
            self._ai_pending = False
            return

        # Build last move info
        last_move_info = "无"
        if 1 <= self._move_index <= len(self.record.moves):
            move = self.record.moves[self._move_index - 1]
            if move.get("action") == "undo":
                color_name = "黑方" if move["color"] == "BLACK" else "白方"
                last_move_info = f"{color_name} 悔棋"
            else:
                color_name = "黑方" if move["color"] == "BLACK" else "白方"
                label = pos_to_label(move["row"], move["col"], self._replay_board.size)
                last_move_info = f"{color_name} 落子 {label}"

        # Determine game result
        game_result = None
        if self._move_index == self.total_moves and self.total_moves > 0:
            winner = self.record.winner
            if winner:
                game_result = "黑方胜" if winner == "BLACK" else "白方胜"
                wr = self.record.win_reason
                if wr and wr != "五连":
                    reason_label = {
                        "三三禁手": "黑方三三禁手",
                        "四四禁手": "黑方四四禁手",
                        "长连禁手": "黑方长连禁手",
                    }.get(wr, wr)
                    game_result += f"（{reason_label}）"
                elif wr == "五连":
                    game_result += "（五连）"
            else:
                game_result = "平局"

        # Show pending state
        self._ai_text = "🤔 AI 正在分析中..."
        self._ai_move = self._move_index
        self._ai_pending = True

        # Fire API request (async)
        self._ai.request_analysis(
            self._replay_board, self._move_index, self.total_moves,
            last_move_info, game_result,
        )

    def _on_ai_result(self, move_index: int, text: str) -> None:
        """Called (from background thread) when AI analysis completes."""
        if move_index == self._move_index:
            self._ai_text = text
            self._ai_pending = False

    # ── AI analysis panel getters ────────────────────────

    @property
    def ai_text(self) -> str:
        return self._ai_text

    @property
    def ai_pending(self) -> bool:
        return self._ai_pending

    @property
    def ai_panel_visible(self) -> bool:
        return self._ai_panel_visible

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
