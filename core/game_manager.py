"""
Central game state machine — turn management, win detection, mode delegation.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional

from core.board import Board
from core.stone import StoneColor
from core.rules import check_win, check_forbidden, is_board_full
from core.recorder import GameRecorder


class GameState(Enum):
    """High-level game lifecycle states."""
    MENU      = auto()
    PLAYING   = auto()
    PAUSED    = auto()
    GAME_OVER = auto()


class GameManager:
    """
    Owns the board and turn logic.
    Game modes (PvP, AI, network) drive this manager by calling its methods.
    """

    def __init__(self, board: Optional[Board] = None, recorder: Optional[GameRecorder] = None):
        self.board: Board = board or Board()
        self.state: GameState = GameState.MENU
        self.current_turn: StoneColor = StoneColor.BLACK  # black goes first 黑棋先行
        self.winner: Optional[StoneColor] = None
        self.win_reason: Optional[str] = None  # e.g. "五连", "三三禁手", "四四禁手", "长连禁手"
        self._observers: list = []  # callback(stones added/removed)

        # Recording
        self.recorder: Optional[GameRecorder] = recorder
        self.game_mode: str = "pvp"  # "pvp" | "ai" | "network" | "skill"

    # ── Observer pattern ────────────────────────────────

    def subscribe(self, callback) -> None:
        """Register a listener called after each state change."""
        self._observers.append(callback)

    def _notify(self, event: str) -> None:
        for cb in self._observers:
            cb(event)

    # ── Game control ────────────────────────────────────

    def new_game(self) -> None:
        """Reset the board and start a fresh game."""
        self.board.reset()
        self.current_turn = StoneColor.BLACK
        self.winner = None
        self.win_reason = None
        self.state = GameState.PLAYING

        # Start recording
        if self.recorder:
            self.recorder.start_record(mode=self.game_mode)

        self._notify("new_game")

    def place_stone(self, row: int, col: int) -> bool:
        """
        Attempt to place a stone for the current player.
        Returns True if the move was legal and executed.

        Forbidden-move (禁手) logic for BLACK:
          1. 五连優先 — a five-in-a-row always wins, ignoring any forbidden pattern.
          2. If no five, check for 长连 (≥6), 三三 (≥2 open-threes), 四四 (≥2 fours).
             Any such pattern makes black lose (white wins).
        """
        if self.state != GameState.PLAYING:
            return False

        if not self.board.place_stone(row, col, self.current_turn):
            return False  # occupied or out of bounds

        # Record the move
        if self.recorder:
            self.recorder.add_move(row, col, self.current_turn)

        # ── 1. Check five-in-a-row (always wins, 五连優先) ──
        if check_win(self.board, row, col):
            self.winner = self.current_turn
            self.win_reason = "五连"
            self.state = GameState.GAME_OVER
            if self.recorder:
                self.recorder.finish(winner=self.winner, win_reason=self.win_reason)
            self._notify("win")
            return True

        # ── 2. Forbidden-move check (BLACK only) ──
        if self.current_turn == StoneColor.BLACK:
            is_forbidden, reason = check_forbidden(self.board, row, col)
            if is_forbidden:
                # Black played a forbidden move → White wins
                self.winner = StoneColor.WHITE
                self.win_reason = reason
                self.state = GameState.GAME_OVER
                if self.recorder:
                    self.recorder.finish(winner=self.winner, win_reason=self.win_reason)
                self._notify("win")
                return True

        # ── 3. Check draw ──
        if is_board_full(self.board):
            self.winner = None  # draw
            self.win_reason = "平局"
            self.state = GameState.GAME_OVER
            if self.recorder:
                self.recorder.finish(winner=None, win_reason=self.win_reason)
            self._notify("draw")
            return True

        # ── 4. Switch turn ──
        self.current_turn = self.current_turn.opponent()
        self._notify("turn_switch")
        return True

    def undo_move(self) -> bool:
        """
        Undo the last move.  Records the undo action for replay.

        Disabled during network multiplayer (the remote opponent must agree).
        """
        if self.state not in (GameState.PLAYING, GameState.GAME_OVER):
            return False
        if self.game_mode == "network":
            return False  # undo not supported in network mode

        stone = self.board.undo()
        if stone is None:
            return False

        # Record the undo
        if self.recorder:
            self.recorder.add_undo(stone.color)

        self.current_turn = stone.color  # revert to the player who just undid
        self.winner = None
        self.win_reason = None
        self.state = GameState.PLAYING
        self._notify("undo")
        return True

    def pause(self) -> None:
        if self.state == GameState.PLAYING:
            self.state = GameState.PAUSED
            self._notify("pause")

    def resume(self) -> None:
        if self.state == GameState.PAUSED:
            self.state = GameState.PLAYING
            self._notify("resume")

    def go_to_menu(self) -> None:
        self.state = GameState.MENU
        self._notify("menu")
