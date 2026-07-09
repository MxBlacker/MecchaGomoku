"""
Board rendering — draws the grid, stones, and last-move highlight.
"""

from __future__ import annotations

import pygame
from config import (
    BOARD_SIZE, CELL_SIZE, MARGIN,
    COLOR_BOARD, COLOR_GRID_LINE, COLOR_HIGHLIGHT,
    BLACK_STONE_IMG, WHITE_STONE_IMG,
    BOARD_IMG, BOARD_IMG_SCALE,
)
from core.board import Board
from core.stone import StoneColor


class BoardView:
    """Handles drawing the board and stones onto a pygame Surface."""

    def __init__(self, offset_x: int = 0, offset_y: int = 0):
        self.size = BOARD_SIZE
        self.cell_size = CELL_SIZE
        self.margin = MARGIN
        self.offset_x = offset_x
        self.offset_y = offset_y

        # Board texture image (replaces hand-drawn background + grid)
        # CELL_SIZE and MARGIN are derived from BOARD_IMG_SCALE, so the
        # scaled image's internal grid aligns with grid_to_pixel() at (offset_x, offset_y).
        self._board_img = self._load_board_image()

        # Load stone images (fallback to drawn circles if images missing)
        self._black_img = self._load_stone_image(BLACK_STONE_IMG)
        self._white_img = self._load_stone_image(WHITE_STONE_IMG)

    # ── helpers ─────────────────────────────────────────

    def set_board_skin(self, path: str) -> None:
        """Switch the board texture to the image at *path*."""
        img = self._load_image_at(path)
        if img is not None:
            self._board_img = img

    @staticmethod
    def _load_board_image() -> pygame.Surface | None:
        """Load the board texture image, scaled by BOARD_IMG_SCALE."""
        return BoardView._load_image_at(BOARD_IMG)

    @staticmethod
    def _load_image_at(img_path: str) -> pygame.Surface | None:
        """Load an image from *img_path* and scale it by BOARD_IMG_SCALE."""
        try:
            img = pygame.image.load(img_path).convert_alpha()
            w = int(img.get_width() * BOARD_IMG_SCALE)
            h = int(img.get_height() * BOARD_IMG_SCALE)
            return pygame.transform.smoothscale(img, (w, h))
        except FileNotFoundError:
            return None

    @staticmethod
    def _load_stone_image(path: str) -> pygame.Surface | None:
        try:
            img = pygame.image.load(path)
            size = int(CELL_SIZE * 0.85)
            return pygame.transform.smoothscale(img, (size, size))
        except FileNotFoundError:
            return None

    def grid_to_pixel(self, row: int, col: int) -> tuple[int, int]:
        """Convert board (row, col) → pixel center (including offset)."""
        x = self.offset_x + self.margin + col * self.cell_size
        y = self.offset_y + self.margin + row * self.cell_size
        return x, y

    def pixel_to_grid(self, px: int, py: int) -> tuple[int, int] | None:
        """Convert pixel → nearest (row, col), or None if outside the playable area."""
        col = round((px - self.offset_x - self.margin) / self.cell_size)
        row = round((py - self.offset_y - self.margin) / self.cell_size)
        if 0 <= row < self.size and 0 <= col < self.size:
            # Check proximity to the intersection
            cx, cy = self.grid_to_pixel(row, col)
            if abs(px - cx) <= self.cell_size // 2 and abs(py - cy) <= self.cell_size // 2:
                return row, col
        return None

    # ── drawing ─────────────────────────────────────────

    def draw(self, surface: pygame.Surface, board: Board, last_move_highlight: bool = True) -> None:
        """Render the full board + stones."""
        if self._board_img:
            surface.blit(self._board_img, (self.offset_x, self.offset_y))
        else:
            self._draw_background(surface)
            self._draw_grid(surface)
        self._draw_stones(surface, board)

        if last_move_highlight:
            last = board.last_move()
            if last:
                self._draw_highlight(surface, last.row, last.col)

    def _draw_background(self, surface: pygame.Surface) -> None:
        # Grid span: (size-1) gaps between first and last line
        span = (self.size - 1) * self.cell_size
        padding = self.margin  # space around the grid lines
        rect = pygame.Rect(
            self.offset_x + self.margin - padding // 2,
            self.offset_y + self.margin - padding // 2,
            span + padding, span + padding,
        )
        pygame.draw.rect(surface, COLOR_BOARD, rect, border_radius=4)

    def _draw_grid(self, surface: pygame.Surface) -> None:
        """Draw grid lines and star points."""
        ox, oy = self.offset_x, self.offset_y
        for i in range(self.size):
            # Horizontal line
            start_x = ox + self.margin
            start_y = oy + self.margin + i * self.cell_size
            end_x = ox + self.margin + (self.size - 1) * self.cell_size
            pygame.draw.line(surface, COLOR_GRID_LINE, (start_x, start_y), (end_x, start_y), 1)

            # Vertical line
            start_x_v = ox + self.margin + i * self.cell_size
            start_y_v = oy + self.margin
            end_y_v = oy + self.margin + (self.size - 1) * self.cell_size
            pygame.draw.line(surface, COLOR_GRID_LINE, (start_x_v, start_y_v), (start_x_v, end_y_v), 1)

        # Star points (standard positions on a 15×15 board)
        star_points = [(3, 3), (3, 7), (3, 11),
                       (7, 3), (7, 7), (7, 11),
                       (11, 3), (11, 7), (11, 11)]
        for r, c in star_points:
            cx, cy = self.grid_to_pixel(r, c)
            pygame.draw.circle(surface, COLOR_GRID_LINE, (cx, cy), 3)

    def _draw_stones(self, surface: pygame.Surface, board: Board) -> None:
        grid = board.get_grid()
        for r in range(self.size):
            for c in range(self.size):
                color = grid[r][c]
                if color is None:
                    continue
                cx, cy = self.grid_to_pixel(r, c)
                img = self._black_img if color == StoneColor.BLACK else self._white_img
                if img:
                    rect = img.get_rect(center=(cx, cy))
                    surface.blit(img, rect)
                else:
                    # Fallback — draw a solid circle
                    pygame_color = (0, 0, 0) if color == StoneColor.BLACK else (255, 255, 255)
                    pygame.draw.circle(surface, pygame_color, (cx, cy), self.cell_size // 2 - 2)
                    pygame.draw.circle(surface, (80, 80, 80), (cx, cy), self.cell_size // 2 - 2, 1)

    def _draw_highlight(self, surface: pygame.Surface, row: int, col: int) -> None:
        """Pulsing red ring + diamond marker on the last-placed stone."""
        import math
        cx, cy = self.grid_to_pixel(row, col)
        t = pygame.time.get_ticks() / 1000.0
        pulse = 1.0 + 0.25 * math.sin(t * 3.5)

        # Red ring around the stone
        ring_r = self.cell_size // 2
        pygame.draw.circle(surface, COLOR_HIGHLIGHT, (cx, cy), ring_r, width=2)

        # Pulsing rotated diamond
        size = 6.0 * pulse
        pts = [
            (cx, cy - size),
            (cx + size, cy),
            (cx, cy + size),
            (cx - size, cy),
        ]
        pygame.draw.polygon(surface, COLOR_HIGHLIGHT, pts)
        # White center dot
        pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 2)

    # ── Hover preview ────────────────────────────────────

    def draw_hover_preview(
        self, surface: pygame.Surface, row: int, col: int, color
    ) -> None:
        """
        Draw a semi-transparent (50% opacity) stone at (row, col)
        to indicate where the current player would place.
        """
        img = self._black_img if color.name == "BLACK" else self._white_img
        if img is None:
            return

        cx, cy = self.grid_to_pixel(row, col)
        ghost = img.copy()
        ghost.set_alpha(128)  # 50% opacity
        rect = ghost.get_rect(center=(cx, cy))
        surface.blit(ghost, rect)
