"""
Win-detection and rule-checking logic for Gomoku.
Includes Renju-style forbidden-move (禁手) detection for black:
  - 三三禁手 (double-three)
  - 四四禁手 (double-four)
  - 长连禁手 (over-line, 6+)
  五连优先 — a five-in-a-row always wins, ignoring any simultaneous forbidden patterns.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.board import Board
    from core.stone import StoneColor


# Four analysis directions as (dr, dc) pairs
_DIRECTIONS = [
    (1, 0),   # vertical
    (0, 1),   # horizontal
    (1, 1),   # diagonal ↘
    (1, -1),  # diagonal ↙
]


# ── Five-in-a-row win check ────────────────────────────────────

def check_win(board: "Board", row: int, col: int) -> "StoneColor | None":
    """
    Check if the stone placed at (row, col) creates a line of 5 (or more).

    Returns the winning StoneColor, or None if no win.
    """
    color = board.get_color(row, col)
    if color is None:
        return None

    for dr, dc in _DIRECTIONS:
        count = 1  # the stone itself

        # Count in positive direction
        count += _count_in_direction(board, row, col, dr, dc, color)
        # Count in negative direction
        count += _count_in_direction(board, row, col, -dr, -dc, color)

        if count >= 5:
            return color

    return None


def _count_in_direction(
    board: "Board", row: int, col: int, dr: int, dc: int, color: "StoneColor"
) -> int:
    """Count consecutive same-color stones starting one step away from (row, col)."""
    count = 0
    r, c = row + dr, col + dc
    size = board.size

    while 0 <= r < size and 0 <= c < size and board.get_color(r, c) == color:
        count += 1
        r += dr
        c += dc

    return count


# ── Line analysis for forbidden-move detection ──────────────────

def _analyze_line(
    board: "Board", row: int, col: int, dr: int, dc: int, color: "StoneColor"
) -> tuple[int, bool, bool]:
    """
    Analyze the consecutive line of *color* stones through (row, col)
    along direction (dr, dc).

    Returns (count, end1_open, end2_open):
      - count:        number of consecutive same-color stones including (row, col)
      - end1_open:    True if the cell just beyond the line in the +direction is empty
      - end2_open:    True if the cell just beyond the line in the -direction is empty
    """
    size = board.size

    # Count in positive direction
    count_pos = 0
    r, c = row + dr, col + dc
    while 0 <= r < size and 0 <= c < size and board.get_color(r, c) == color:
        count_pos += 1
        r += dr
        c += dc
    # Is the cell just beyond the positive end open?
    end1_open = (
        0 <= r < size and 0 <= c < size and board.get_color(r, c) is None
    )

    # Count in negative direction
    count_neg = 0
    r, c = row - dr, col - dc
    while 0 <= r < size and 0 <= c < size and board.get_color(r, c) == color:
        count_neg += 1
        r -= dr
        c -= dc
    # Is the cell just beyond the negative end open?
    end2_open = (
        0 <= r < size and 0 <= c < size and board.get_color(r, c) is None
    )

    return 1 + count_pos + count_neg, end1_open, end2_open


def check_forbidden(board: "Board", row: int, col: int) -> tuple[bool, Optional[str]]:
    """
    Check whether the BLACK stone just placed at (row, col) constitutes a
    forbidden move (禁手).  Only meaningful for BLACK; returns (False, None)
    for WHITE stones.

    Detection order (五连优先):
      1. If the move creates a five-in-a-row → NOT forbidden (black wins).
      2. Otherwise check 长连 (≥6), 三三 (≥2 open-threes), 四四 (≥2 fours).

    Returns (is_forbidden, reason_string_or_None).
    """
    from core.stone import StoneColor

    color = board.get_color(row, col)
    if color is None or color != StoneColor.BLACK:
        return False, None

    open_threes = 0
    fours = 0
    has_over_line = False
    has_five = False

    for dr, dc in _DIRECTIONS:
        count, end1_open, end2_open = _analyze_line(board, row, col, dr, dc, color)

        if count >= 6:
            has_over_line = True
        elif count == 5:
            has_five = True
        elif count == 4:
            # A "four" that can still become five requires at least one open end
            if end1_open or end2_open:
                fours += 1
        elif count == 3:
            # An "open three" (活三) requires BOTH ends to be open
            if end1_open and end2_open:
                open_threes += 1

    # 五连优先 — five-in-a-row always wins, ignore all forbidden patterns
    if has_five:
        return False, None

    if has_over_line:
        return True, "长连禁手"
    if open_threes >= 2:
        return True, "三三禁手"
    if fours >= 2:
        return True, "四四禁手"

    return False, None


def is_board_full(board: "Board") -> bool:
    """Return True if every cell on the board is occupied."""
    return all(board.get_color(r, c) is not None
               for r in range(board.size)
               for c in range(board.size))
