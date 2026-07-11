"""
Skill-icon widget and skill-panel container for 技能五子棋.

Each SkillIcon is a circular button that displays a skill's state
(colour → grayscale/dim when unavailable) and shows a tooltip on hover.
"""

from __future__ import annotations

import math
from typing import Optional, Callable

import pygame

from core.skill_system import SkillID, SKILL_NAMES, SKILL_DESCS
from core.stone import StoneColor
from config import SKILL_ICON_SIZE
from utils.fonts import get_font


class SkillIcon:
    """
    A circular skill button.

    States:
      - available:   full-colour icon, clickable
      - unavailable: grayscale + dimmed, not clickable
      - hover:       tooltip drawn to one side
    """

    def __init__(
        self,
        x: int,
        y: int,
        size: int,
        skill_id: SkillID,
        icon_path: str,
        on_click: Callable[[SkillID], None],
    ):
        self.x = x          # centre x
        self.y = y          # centre y
        self.size = size    # diameter
        self.radius = size // 2
        self.skill_id = skill_id
        self.on_click = on_click

        # Load icon image (coloured original)
        self._icon_orig = self._load_icon(icon_path, size)
        # Grayscale copy (built lazily)
        self._icon_gray: Optional[pygame.Surface] = None

        self._hovered = False
        self._tooltip_font = get_font(17)

    # ── Image loading ────────────────────────────────────

    @staticmethod
    def _load_icon(path: str, size: int) -> Optional[pygame.Surface]:
        """Load and scale an icon to *size* × *size*."""
        try:
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.smoothscale(img, (size, size))
        except FileNotFoundError:
            return None

    @property
    def icon_gray(self) -> Optional[pygame.Surface]:
        """Lazily create a grayscale + dimmed version of the icon."""
        if self._icon_gray is None and self._icon_orig is not None:
            gray = self._icon_orig.copy()
            # Convert to grayscale via pixel manipulation
            arr = pygame.surfarray.pixels3d(gray)
            # luminosity formula
            lum = (arr[:, :, 0].astype(float) * 0.299 +
                   arr[:, :, 1].astype(float) * 0.587 +
                   arr[:, :, 2].astype(float) * 0.114).astype('uint8')
            arr[:, :, 0] = lum
            arr[:, :, 1] = lum
            arr[:, :, 2] = lum
            del arr
            # Dim: reduce alpha
            gray.set_alpha(100)
            self._icon_gray = gray
        return self._icon_gray

    # ── Hit test ─────────────────────────────────────────

    def contains(self, px: int, py: int) -> bool:
        """Return True if (px, py) is inside the circular icon."""
        dx = px - self.x
        dy = py - self.y
        return dx * dx + dy * dy <= self.radius * self.radius

    # ── Event handling ───────────────────────────────────

    def handle_event(self, event: pygame.event.Event, available: bool) -> bool:
        """
        Process a pygame event.  Returns True if the event was consumed.
        *available*: whether the skill is currently usable.
        """
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.contains(*event.pos)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hovered and available:
                self.on_click(self.skill_id)
                return True

        return False

    # ── Drawing ──────────────────────────────────────────

    def draw(
        self,
        surface: pygame.Surface,
        available: bool,
        cooldown_remaining: int,
        tooltip_side: str = "right",
    ) -> None:
        """
        Draw the skill icon and tooltip.

        *available*:        True → full colour; False → grayscale dim.
        *cooldown_remaining*: rounds until the skill is ready (0 = ready).
        *tooltip_side*:     "left" or "right" — which side to place the tooltip.
        """
        # Choose icon surface
        if available and self._icon_orig:
            icon = self._icon_orig
        elif not available and self.icon_gray:
            icon = self.icon_gray
        else:
            icon = self._icon_orig

        if icon is not None:
            rect = icon.get_rect(center=(self.x, self.y))
            surface.blit(icon, rect)
        else:
            # Fallback: draw a plain circle
            color = (100, 180, 100) if available else (80, 80, 80)
            pygame.draw.circle(surface, color, (self.x, self.y), self.radius)
            pygame.draw.circle(surface, (255, 255, 255), (self.x, self.y), self.radius, 2)

        # Tooltip on hover
        if self._hovered:
            self._draw_tooltip(surface, available, cooldown_remaining, tooltip_side)

    def _draw_tooltip(self, surface: pygame.Surface, available: bool,
                      cooldown: int, side: str) -> None:
        """
        Draw a black rounded-rect tooltip to the left or right of the icon.
        Contains: skill name, description (10 CJK chars/line), cooldown info.
        """
        name = SKILL_NAMES.get(self.skill_id, "???")
        desc = SKILL_DESCS.get(self.skill_id, "")

        # Wrap description to ~10 chars per line for CJK readability
        desc_lines = self._wrap_cjk(desc, chars_per_line=10)

        # Build lines
        name_font = get_font(20)
        desc_font = get_font(17)
        info_font = get_font(16)

        lines: list[tuple[pygame.Surface, int, int]] = []  # (surf, w, h)

        # Title line
        name_surf = name_font.render(name, True, (255, 255, 255))
        lines.append((name_surf, name_surf.get_width(), name_surf.get_height()))

        # Description lines
        for line in desc_lines:
            ds = desc_font.render(line, True, (200, 200, 200))
            lines.append((ds, ds.get_width(), ds.get_height()))

        # Cooldown / availability line
        if available:
            info_text = "✓ 可使用"
            info_color = (100, 255, 100)
        else:
            info_text = f"冷却剩余: {cooldown} 回合"
            info_color = (255, 180, 80)
        info_surf = info_font.render(info_text, True, info_color)
        lines.append((info_surf, info_surf.get_width(), info_surf.get_height()))

        # Measure background
        pad_x, pad_y = 12, 10
        gap_y = 4  # gap between lines
        max_w = max(w for _, w, _ in lines)
        total_h = sum(h for _, _, h in lines) + gap_y * max(0, len(lines) - 1)
        bg_w = max_w + pad_x * 2
        bg_h = total_h + pad_y * 2

        # Position the tooltip
        gap_from_icon = self.radius + 10
        if side == "right":
            bg_x = self.x + gap_from_icon
        else:
            bg_x = self.x - gap_from_icon - bg_w

        bg_y = self.y - bg_h // 2

        # Clamp to window
        bg_x = max(4, min(bg_x, surface.get_width() - bg_w - 4))
        bg_y = max(4, min(bg_y, surface.get_height() - bg_h - 4))

        # Draw background
        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 220), bg.get_rect(), border_radius=12)
        pygame.draw.rect(bg, (60, 60, 80, 200), bg.get_rect(), width=1, border_radius=12)
        surface.blit(bg, (bg_x, bg_y))

        # Draw text lines
        y = bg_y + pad_y
        for surf, _, h in lines:
            surface.blit(surf, (bg_x + pad_x, y))
            y += h + gap_y

    @staticmethod
    def _wrap_cjk(text: str, chars_per_line: int = 10) -> list[str]:
        """Wrap text at *chars_per_line* characters (CJK-friendly)."""
        lines = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue
            for i in range(0, len(paragraph), chars_per_line):
                lines.append(paragraph[i:i + chars_per_line])
        return lines


class SkillPanel:
    """
    A vertical stack of 4 SkillIcons for one player, placed beside the board.

    Draws and handles events for all icons; delegates clicks to a callback.
    """

    def __init__(
        self,
        center_x: int,
        center_y: int,
        icon_size: int,
        icon_spacing: int,
        owner_color: StoneColor,
        icon_paths: dict[SkillID, str],
        on_use_skill: Callable[[StoneColor, SkillID], None],
    ):
        self.owner_color = owner_color
        self.icon_size = icon_size
        self.icon_spacing = icon_spacing

        # Vertical layout: 4 icons centred on center_y
        total_h = 4 * icon_size + 3 * icon_spacing
        start_y = center_y - total_h // 2 + icon_size // 2

        self.icons: dict[SkillID, SkillIcon] = {}
        skill_order = [SkillID.GACHA, SkillID.REVERSE, SkillID.DEADZONE, SkillID.DEFENSE]
        for i, sid in enumerate(skill_order):
            ix = center_x
            iy = start_y + i * (icon_size + icon_spacing)
            self.icons[sid] = SkillIcon(
                x=ix, y=iy, size=icon_size, skill_id=sid,
                icon_path=icon_paths.get(sid, ""),
                on_click=lambda sid, c=owner_color: on_use_skill(c, sid),
            )

    # ── Event handling ───────────────────────────────────

    def handle_event(self, event: pygame.event.Event,
                     available_map: dict[SkillID, bool]) -> bool:
        """
        Forward *event* to each icon.  Returns True if any icon consumed it.
        """
        for sid, icon in self.icons.items():
            if icon.handle_event(event, available_map.get(sid, False)):
                return True
        return False

    # ── Drawing ──────────────────────────────────────────

    def draw(
        self,
        surface: pygame.Surface,
        available_map: dict[SkillID, bool],
        cooldown_map: dict[SkillID, int],
        tooltip_side: str = "right",
    ) -> None:
        """Draw all four skill icons."""
        for sid, icon in self.icons.items():
            icon.draw(
                surface,
                available=available_map.get(sid, False),
                cooldown_remaining=cooldown_map.get(sid, 0),
                tooltip_side=tooltip_side,
            )
