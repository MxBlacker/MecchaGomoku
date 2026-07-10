"""
Game board state — the 15×15 grid of stones.
"""

from __future__ import annotations

from typing import Optional

from core.stone import Stone, StoneColor
from config import BOARD_SIZE


class Board:
    """Represents the Go/Gomoku board state."""

    def __init__(self, size: int = BOARD_SIZE):
        self.size = size
        # grid[row][col] → StoneColor or None
        self._grid: list[list[Optional[StoneColor]]] = [
            [None for _ in range(size)] for _ in range(size)
        ]
        self._history: list[Stone] = []  # move history for undo / replay

    # ── Read ────────────────────────────────────────────

    def get_color(self, row: int, col: int) -> Optional[StoneColor]:
        """Return the stone color at (row, col), or None."""
        if 0 <= row < self.size and 0 <= col < self.size:
            return self._grid[row][col]
        return None

    def is_empty(self, row: int, col: int) -> bool:
        """Return True if the cell is unoccupied."""
        return self.get_color(row, col) is None

    def last_move(self) -> Optional[Stone]:
        """Return the last placed stone, or None."""
        return self._history[-1] if self._history else None

    @property
    def move_count(self) -> int:
        """Total number of stones placed."""
        return len(self._history)

    # ── Write ───────────────────────────────────────────

    def place_stone(self, row: int, col: int, color: StoneColor) -> bool:
        """
        Attempt to place a stone at (row, col).
        Returns True on success, False if the cell is occupied or out of bounds.
        """
        if not (0 <= row < self.size and 0 <= col < self.size):
            return False
        if self._grid[row][col] is not None:
            return False

        self._grid[row][col] = color
        self._history.append(Stone(row, col, color))
        return True

    def undo(self) -> Optional[Stone]:
        """Remove and return the last stone placed, or None."""
        if not self._history:
            return None
        stone = self._history.pop()
        self._grid[stone.row][stone.col] = None
        return stone

    def reset(self) -> None:
        """Clear the board entirely."""
        for r in range(self.size):
            for c in range(self.size):
                self._grid[r][c] = None
        self._history.clear()

    # ── Utility ─────────────────────────────────────────

    def get_grid(self) -> list[list[Optional[StoneColor]]]:
        """Return a shallow snapshot of the grid (for rendering)."""
        return [row[:] for row in self._grid]


# ── Coordinate display helpers ─────────────────────────
# Internal: _grid[row][col], row 0=top, col 0=left
# Display:  A1=bottom-left (row=14, col=0), O15=top-right (row=0, col=14)

def row_to_label(row: int, board_size: int = 15) -> str:
    """Convert internal row index to display number (bottom=1, top=15)."""
    return str(board_size - row)


def col_to_label(col: int) -> str:
    """Convert internal col index to display letter (left=A, right=O)."""
    return chr(ord('A') + col)


def pos_to_label(row: int, col: int, board_size: int = 15) -> str:
    """Convert internal (row, col) to display label like 'A1' (bottom-left)."""
    return f"{col_to_label(col)}{row_to_label(row, board_size)}"
