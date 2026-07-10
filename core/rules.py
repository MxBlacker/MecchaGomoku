"""
Win-detection and rule-checking logic for Gomoku.
Includes Renju-style forbidden-move (禁手) detection for black:
  - 三三禁手 (double-three)
  - 四四禁手 (double-four)
  - 长连禁手 (over-line, 6+)
  五连优先 — a five-in-a-row always wins, ignoring any simultaneous forbidden patterns.

Key improvements over the previous version:
  - check_win() uses == 5 (not >= 5) so 长连 is not mis-classified as a win.
  - Four / three detection uses 5-cell sliding windows, which correctly
    handles jump-fours (跳四) and jump-threes (跳三), not just consecutive lines.
  - Each direction reports only the strongest pattern (five > overline > four > three).
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

# Number of cells to examine on each side of the placed stone.
# 5 cells each way + center = 11 cells total.
# This is enough to detect any five-in-a-row, overline, four, or three
# pattern that includes the placed stone.
_WINDOW_RADIUS = 5


# ── Five-in-a-row win check ────────────────────────────────────

def check_win(board: "Board", row: int, col: int) -> "StoneColor | None":
    """
    Check if the stone placed at (row, col) creates a line of EXACTLY 5.

    Uses == 5 (not >= 5) so that overline (长连, 6+) is NOT treated as a win.
    Returns the winning StoneColor, or None if no win.
    """
    color = board.get_color(row, col)
    if color is None:
        return None

    for dr, dc in _DIRECTIONS:
        count = 1  # the stone itself
        count += _count_consecutive(board, row, col, dr, dc, color)
        count += _count_consecutive(board, row, col, -dr, -dc, color)

        if count == 5:
            return color

    return None


def _count_consecutive(
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


# ── Line extraction ────────────────────────────────────────────

def _extract_line(
    board: "Board", row: int, col: int, dr: int, dc: int
) -> tuple[list[StoneColor | None | str], int]:
    """
    Extract a line segment centered on (row, col) along direction (dr, dc).

    Returns (cells, center_idx) where:
      - cells is a list of length up to 2*_WINDOW_RADIUS + 1
      - Each element is StoneColor, None (empty), or 'edge' (out-of-bounds)
      - center_idx is the index of (row, col) within the list
    """
    size = board.size
    cells: list[StoneColor | None | str] = []

    for i in range(-_WINDOW_RADIUS, _WINDOW_RADIUS + 1):
        r, c = row + i * dr, col + i * dc
        if 0 <= r < size and 0 <= c < size:
            cells.append(board.get_color(r, c))
        else:
            cells.append('edge')

    return cells, _WINDOW_RADIUS


# ── Direction analysis (the core of forbidden-move detection) ──

def _analyze_direction(
    board: "Board", row: int, col: int, dr: int, dc: int, color: "StoneColor"
) -> dict:
    """
    Analyze one direction through (row, col) for Gomoku patterns.

    Returns a dict with boolean keys:
      'five'     — exactly 5 consecutive stones (五连)
      'overline' — 6+ consecutive stones (长连)
      'four'     — the placed stone participates in a four pattern
                   (4 same-color in a 5-cell window that includes the placed stone,
                    i.e. one move away from completing a five)
      'three'    — the placed stone participates in a three pattern
                   (3 stones that can become an open-four in one move)

    Priority: five > overline > four > three
    Only the strongest pattern in this direction is reported.
    """
    cells, center = _extract_line(board, row, col, dr, dc)
    result = {'five': False, 'overline': False, 'four': False, 'three': False}

    # ── 1. Consecutive count through the placed stone ──
    consecutive = 1
    # positive direction
    for i in range(center + 1, len(cells)):
        if cells[i] == color:
            consecutive += 1
        else:
            break
    # negative direction
    for i in range(center - 1, -1, -1):
        if cells[i] == color:
            consecutive += 1
        else:
            break

    if consecutive >= 6:
        result['overline'] = True
        return result
    if consecutive == 5:
        result['five'] = True
        return result

    # ── 2. Four detection: 5-cell sliding windows ──
    # A "four" = 4 same-color + 1 empty in any 5-cell window
    # that includes the placed stone (center).
    for start in range(len(cells) - 4):
        if not (start <= center < start + 5):
            continue  # window must contain the placed stone
        window = cells[start:start + 5]
        same = sum(1 for c in window if c == color)
        empty = sum(1 for c in window if c is None)
        opponent = sum(1 for c in window if c not in (color, None))
        if same == 4 and empty == 1 and opponent == 0:
            result['four'] = True
            break

    # ── 3. Three detection: can it become an open four? ──
    # An "open four" (活四) = exactly 4 consecutive same-color stones
    # with BOTH adjacent cells empty (not 'edge', not opponent).
    # A "three" is a pattern where adding ONE stone at some empty cell
    # would create an open four that INCLUDES the placed stone.
    if not result['four']:
        for empty_idx in range(len(cells)):
            if cells[empty_idx] is not None:
                continue  # only try placing at empty cells

            # Check every possible 4-core window that includes center
            # and the hypothetical placement
            for core_start in range(len(cells) - 3):
                core_end = core_start + 3
                if not (core_start <= center <= core_end):
                    continue
                if not (core_start <= empty_idx <= core_end):
                    continue

                # Would the core be all same-color after placing at empty_idx?
                core_all_same = True
                for j in range(core_start, core_end + 1):
                    cell_val = color if j == empty_idx else cells[j]
                    if cell_val != color:
                        core_all_same = False
                        break

                if not core_all_same:
                    continue

                # Check that both ends are OPEN (empty and not 'edge')
                left_end = cells[core_start - 1] if core_start > 0 else 'edge'
                right_end = cells[core_end + 1] if core_end + 1 < len(cells) else 'edge'

                # Adjust ends if the hypothetical stone is at an end position
                if empty_idx == core_start - 1:
                    left_end = color  # would be occupied, not open
                if empty_idx == core_end + 1:
                    right_end = color  # would be occupied, not open

                if left_end is None and right_end is None:
                    result['three'] = True
                    break

            if result['three']:
                break

    return result


# ── Forbidden-move check ───────────────────────────────────────

def check_forbidden(board: "Board", row: int, col: int) -> tuple[bool, Optional[str]]:
    """
    Check whether the BLACK stone just placed at (row, col) constitutes a
    forbidden move (禁手).  Only meaningful for BLACK; returns (False, None)
    for WHITE stones.

    Detection order (五连优先):
      1. If the move creates a five-in-a-row → NOT forbidden (black wins).
      2. Otherwise check 长连 (≥6), 三三 (≥2 threes), 四四 (≥2 fours).

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
        info = _analyze_direction(board, row, col, dr, dc, color)

        if info['five']:
            has_five = True
        elif info['overline']:
            has_over_line = True
        elif info['four']:
            fours += 1
        elif info['three']:
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
