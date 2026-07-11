"""
Visual effects for 技能五子棋 skills.

Handles:
  - Defence glow:  blue pulsing ring around player avatar, fade-out on break
  - Reverse:       yin-yang symbol rotation animation (360°, then disappear)
  - Dead zone:     3×3 red overlay with diagonal slash lines at cell centres
  - Gacha hover:   flickering black/white ghost stone preview
  - Nullify flash: brief "技能被抵消!" text
"""

from __future__ import annotations

import math
from typing import Optional

import pygame

from core.stone import StoneColor
from config import (
    SKILL_YINYANG_IMG, SKILL_DEFENSE_GLOW_IMG,
    CELL_SIZE, AVATAR_SIZE, WINDOW_WIDTH,
)
from utils.fonts import get_font


class SkillEffects:
    """
    Owns and drives all active skill visual effects.
    Call update() each frame, then draw().
    """

    def __init__(self, board_view):
        self._board_view = board_view

        # ── Defence glow ──────────────────────────────────
        self._defense_glow_img = self._load_defense_glow()
        self._glow_black: bool = False   # black has glow?
        self._glow_white: bool = False   # white has glow?
        self._glow_fade_black: float = 0.0  # 1.0 → 0.0 fade-out
        self._glow_fade_white: float = 0.0

        # ── Reverse animation ─────────────────────────────
        self._yinyang_img = self._load_yinyang()
        self._reverse_active: bool = False
        self._reverse_angle: float = 0.0       # current rotation degrees
        self._reverse_duration: float = 1.5    # seconds for full rotation + fade
        self._reverse_elapsed: float = 0.0
        self._reverse_scale: float = 0.0       # scale grows 0→1 during anim
        self._reverse_alpha: int = 255         # fade-out towards the end

        # ── Dead zones ────────────────────────────────────
        # list of (row, col) tuples for currently visible dead-zone centres
        self._dead_zone_centres: list[tuple[int, int]] = []
        self._dead_zone_alphas: list[float] = []   # pulse alpha per zone

        # ── Gacha hover ───────────────────────────────────
        self._gacha_hover_pos: Optional[tuple[int, int]] = None
        self._gacha_blink_timer: float = 0.0

        # ── Nullify flash ─────────────────────────────────
        self._nullify_text: Optional[str] = None
        self._nullify_timer: float = 0.0
        self._nullify_duration: float = 1.5  # seconds

    # ── Image loading ────────────────────────────────────

    @staticmethod
    def _load_defense_glow() -> Optional[pygame.Surface]:
        """Load and scale the defence-glow image to wrap around an avatar."""
        try:
            img = pygame.image.load(SKILL_DEFENSE_GLOW_IMG).convert_alpha()
            target = AVATAR_SIZE + 40  # glow ring extends beyond avatar
            return pygame.transform.smoothscale(img, (target, target))
        except FileNotFoundError:
            return None

    @staticmethod
    def _load_yinyang() -> Optional[pygame.Surface]:
        """Load and scale the yin-yang symbol for the board-centre animation."""
        try:
            img = pygame.image.load(SKILL_YINYANG_IMG).convert_alpha()
            target = int(CELL_SIZE * 5)  # ~210 px — large and visible
            return pygame.transform.smoothscale(img, (target, target))
        except FileNotFoundError:
            return None

    # ── Public API ───────────────────────────────────────

    def set_defense_glow(self, color: StoneColor, active: bool) -> None:
        """Enable / disable the defence glow for *color*."""
        if color == StoneColor.BLACK:
            self._glow_black = active
            if not active:
                self._glow_fade_black = 1.0  # start fade-out
            else:
                self._glow_fade_black = 0.0
        else:
            self._glow_white = active
            if not active:
                self._glow_fade_white = 1.0
            else:
                self._glow_fade_white = 0.0

    def start_reverse_animation(self) -> None:
        """Begin the yin-yang rotation sequence."""
        self._reverse_active = True
        self._reverse_angle = 0.0
        self._reverse_elapsed = 0.0
        self._reverse_scale = 0.3  # starts small, grows in
        self._reverse_alpha = 255  # full opacity, fades out at end

    def set_dead_zones(self, positions: list[tuple[int, int]]) -> None:
        """Set the list of dead-zone centre positions to render."""
        self._dead_zone_centres = positions
        self._dead_zone_alphas = [0.0] * len(positions)

    def set_gacha_hover(self, pos: Optional[tuple[int, int]]) -> None:
        """Set the position for gacha flickering hover preview."""
        self._gacha_hover_pos = pos

    def show_nullified(self, text: str = "技能被防御抵消!") -> None:
        """Flash a 'skill nullified' message."""
        self._nullify_text = text
        self._nullify_timer = self._nullify_duration

    # ── Per-frame update ─────────────────────────────────

    def update(self, dt_ms: float) -> None:
        """
        Advance all animations by *dt_ms* milliseconds.
        Call once per frame before draw().
        """
        dt = dt_ms / 1000.0  # seconds

        # ── Glow fade-out ──────────────────────────────
        fade_speed = 2.5  # per second
        if self._glow_fade_black > 0:
            self._glow_fade_black = max(0, self._glow_fade_black - fade_speed * dt)
        if self._glow_fade_white > 0:
            self._glow_fade_white = max(0, self._glow_fade_white - fade_speed * dt)

        # ── Reverse animation ───────────────────────────
        if self._reverse_active:
            self._reverse_elapsed += dt
            progress = min(self._reverse_elapsed / self._reverse_duration, 1.0)
            # Full 360° rotation over the duration
            self._reverse_angle = progress * 360.0

            # Scale: grows 0.3 → 1.0 in first 25% of time, then holds
            scale_progress = min(progress / 0.25, 1.0)
            self._reverse_scale = 0.3 + 0.7 * scale_progress

            # Alpha: full opacity for first 60%, then fade to 0
            if progress < 0.6:
                self._reverse_alpha = 255
            else:
                fade_progress = (progress - 0.6) / 0.4  # 0→1
                self._reverse_alpha = int(255 * (1.0 - fade_progress))

            if progress >= 1.0:
                self._reverse_active = False

        # ── Dead zone pulse ────────────────────────────
        for i in range(len(self._dead_zone_alphas)):
            target = 1.0
            self._dead_zone_alphas[i] += (target - self._dead_zone_alphas[i]) * 4.0 * dt

        # ── Gacha blink ────────────────────────────────
        if self._gacha_hover_pos is not None:
            self._gacha_blink_timer += dt
            if self._gacha_blink_timer > 0.5:
                self._gacha_blink_timer = 0.0

        # ── Nullify flash ──────────────────────────────
        if self._nullify_timer > 0:
            self._nullify_timer -= dt
            if self._nullify_timer <= 0:
                self._nullify_text = None

    # ── Drawing ───────────────────────────────────────────

    def draw_all(
        self,
        surface: pygame.Surface,
        board_center: tuple[int, int],
        black_avatar_rect: Optional[pygame.Rect],
        white_avatar_rect: Optional[pygame.Rect],
    ) -> None:
        """
        Draw all active effects onto *surface*.

        Order (back → front):
          1. Dead-zone overlays
          2. Reverse (yin-yang) animation
          3. Defence glows
          4. Gacha hover preview
          5. Nullify flash text
        """
        self._draw_dead_zones(surface)
        self._draw_reverse(surface, board_center)
        self._draw_defense_glows(surface, black_avatar_rect, white_avatar_rect)
        self._draw_gacha_hover(surface)
        self._draw_nullify_flash(surface)

    # ── Individual effect drawers ────────────────────────

    def _draw_dead_zones(self, surface: pygame.Surface) -> None:
        """Draw a 3×3 red-diagonal overlay for each dead-zone centre."""
        bv = self._board_view
        cell = CELL_SIZE

        for idx, (row, col) in enumerate(self._dead_zone_centres):
            cx, cy = bv.grid_to_pixel(row, col)
            # The overlay rectangle: corners at cell centres, not intersections
            # Size = 3 cells × 3 cells centred on the stone
            half = int(cell * 1.5)
            left = cx - half
            top = cy - half
            size_px = half * 2  # = 3 * cell

            alpha = self._dead_zone_alphas[idx] if idx < len(self._dead_zone_alphas) else 1.0
            overlay = pygame.Surface((size_px, size_px), pygame.SRCALPHA)

            # Semi-transparent red fill
            fill_alpha = int(40 * alpha)
            overlay.fill((255, 30, 30, fill_alpha))

            # Red diagonal slash lines
            line_alpha = int(130 * alpha)
            spacing = 8
            for i in range(-size_px, size_px, spacing):
                pygame.draw.line(
                    overlay, (255, 40, 40, line_alpha),
                    (i, 0), (i + size_px, size_px), 2,
                )

            # Border rectangle
            border_alpha = int(180 * alpha)
            pygame.draw.rect(
                overlay, (255, 30, 30, border_alpha),
                overlay.get_rect(), width=2,
            )

            surface.blit(overlay, (left, top))

    def _draw_reverse(self, surface: pygame.Surface,
                      board_center: tuple[int, int]) -> None:
        """Draw the yin-yang rotation animation at the board centre."""
        if not self._reverse_active or self._yinyang_img is None:
            return

        bcx, bcy = board_center

        # Scale the image
        w = int(self._yinyang_img.get_width() * self._reverse_scale)
        h = int(self._yinyang_img.get_height() * self._reverse_scale)
        if w < 4 or h < 4:
            return
        scaled = pygame.transform.smoothscale(self._yinyang_img, (w, h))

        # Rotate
        rotated = pygame.transform.rotate(scaled, self._reverse_angle)

        # Apply fade-out alpha
        if self._reverse_alpha < 255:
            rotated.set_alpha(self._reverse_alpha)

        rect = rotated.get_rect(center=(bcx, bcy))
        surface.blit(rotated, rect)

    def _draw_defense_glows(
        self,
        surface: pygame.Surface,
        black_rect: Optional[pygame.Rect],
        white_rect: Optional[pygame.Rect],
    ) -> None:
        """Draw blue pulsing glow around avatar(s) with defence active."""
        t = pygame.time.get_ticks() / 1000.0
        pulse = 1.0 + 0.12 * math.sin(t * 3.5)

        for color, rect, fading in [
            (StoneColor.BLACK, black_rect, self._glow_fade_black),
            (StoneColor.WHITE, white_rect, self._glow_fade_white),
        ]:
            active = (color == StoneColor.BLACK and self._glow_black) or \
                     (color == StoneColor.WHITE and self._glow_white)
            if not active and fading <= 0:
                continue

            if rect is None:
                continue

            alpha_mult = 1.0 - fading if not active else 1.0

            if self._defense_glow_img is not None:
                # Use the glow image, scaled by pulse
                gw = int(self._defense_glow_img.get_width() * pulse)
                gh = int(self._defense_glow_img.get_height() * pulse)
                if gw > 4 and gh > 4:
                    glow = pygame.transform.smoothscale(self._defense_glow_img, (gw, gh))
                    glow.set_alpha(int(200 * alpha_mult))
                    gr = glow.get_rect(center=rect.center)
                    surface.blit(glow, gr)
            else:
                # Fallback: draw concentric blue circles
                cx, cy = rect.center
                for i in range(3):
                    r = (AVATAR_SIZE // 2 + 8 + i * 6) * pulse
                    alpha = int((60 - i * 15) * alpha_mult)
                    pygame.draw.circle(
                        surface, (30, 100, 255, alpha), (cx, cy), int(r), width=3,
                    )

    def _draw_gacha_hover(self, surface: pygame.Surface) -> None:
        """Draw a flickering ghost stone (alternates black ↔ white) for gacha."""
        if self._gacha_hover_pos is None:
            return

        row, col = self._gacha_hover_pos
        bv = self._board_view

        # Alternate every 0.25 s: 0.0–0.25 → black, 0.25–0.5 → white
        is_black = (self._gacha_blink_timer < 0.25)

        img = bv._black_img if is_black else bv._white_img
        if img is None:
            return

        cx, cy = bv.grid_to_pixel(row, col)
        ghost = img.copy()
        ghost.set_alpha(150)
        rect = ghost.get_rect(center=(cx, cy))
        surface.blit(ghost, rect)

    def _draw_nullify_flash(self, surface: pygame.Surface) -> None:
        """Draw a brief 'skill nullified' message near the board centre."""
        if self._nullify_text is None or self._nullify_timer <= 0:
            return

        font = get_font(28)
        text_surf = font.render(self._nullify_text, True, (255, 100, 100))

        # Fade out in the last 0.4 s
        alpha = 255
        if self._nullify_timer < 0.4:
            alpha = int(255 * (self._nullify_timer / 0.4))
        text_surf.set_alpha(max(0, alpha))

        tw, th = text_surf.get_size()
        x = WINDOW_WIDTH // 2 - tw // 2
        y = 120  # fixed height near top of board area
        surface.blit(text_surf, (x, y))

    # ── Helpers for external positioning ──────────────────

    @property
    def reverse_active(self) -> bool:
        return self._reverse_active
