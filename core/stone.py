"""
Stone representation — the fundamental piece on the board.
"""

from enum import Enum, auto


class StoneColor(Enum):
    """The two players in Gomoku."""
    BLACK = auto()
    WHITE = auto()

    def opponent(self) -> "StoneColor":
        """Return the opposing color."""
        return StoneColor.WHITE if self == StoneColor.BLACK else StoneColor.BLACK

    def __str__(self) -> str:
        return "●" if self == StoneColor.BLACK else "○"


class Stone:
    """A single stone placed on the board."""

    __slots__ = ("row", "col", "color")

    def __init__(self, row: int, col: int, color: StoneColor):
        self.row = row
        self.col = col
        self.color = color

    def __repr__(self) -> str:
        return f"Stone({self.row}, {self.col}, {self.color})"
