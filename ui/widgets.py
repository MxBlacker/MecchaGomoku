"""
Reusable UI widgets — buttons, labels, etc.
"""

from __future__ import annotations

import pygame
from config import COLOR_BUTTON, COLOR_BUTTON_HOVER, COLOR_TEXT
from utils.fonts import get_font


class Button:
    """A clickable rectangular button."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str,
        *,
        font: pygame.font.Font | None = None,
        color: tuple[int, int, int] = COLOR_BUTTON,
        hover_color: tuple[int, int, int] = COLOR_BUTTON_HOVER,
        text_color: tuple[int, int, int] = COLOR_TEXT,
        callback=None,
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = hover_color
        self.text_color = text_color
        self.callback = callback
        self.font = font or get_font(24)
        self._hovered = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the button was clicked."""
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hovered and self.callback:
                self.callback()
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        color = self.hover_color if self._hovered else self.color
        # Glow on hover
        if self._hovered:
            glow = pygame.Surface((self.rect.width + 12, self.rect.height + 12), pygame.SRCALPHA)
            for r in range(4, 0, -1):
                a = 30 - r * 6
                pygame.draw.rect(glow, (255, 215, 0, a),
                                 (6 - r, 6 - r, self.rect.width + r*2, self.rect.height + r*2),
                                 border_radius=8 + r)
            surface.blit(glow, (self.rect.x - 6, self.rect.y - 6))
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, (255, 255, 255), self.rect, width=1, border_radius=6)
        text_surf = self.font.render(self.text, True, self.text_color)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)


class ImageButton:
    """A button rendered from a PNG image."""

    def __init__(
        self,
        x: int,
        y: int,
        image_path: str,
        *,
        callback=None,
        scale: float = 1.0,
    ):
        self._base_img = pygame.image.load(image_path).convert_alpha()
        if scale != 1.0:
            w = int(self._base_img.get_width() * scale)
            h = int(self._base_img.get_height() * scale)
            self._base_img = pygame.transform.smoothscale(self._base_img, (w, h))

        self.rect = self._base_img.get_rect(topleft=(x, y))
        self._hovered = False
        self.callback = callback

        # Pre-create a brighter version for hover feedback
        self._hover_img = self._base_img.copy()
        bright = pygame.Surface(self._hover_img.get_size(), pygame.SRCALPHA)
        bright.fill((60, 60, 60, 0))
        self._hover_img.blit(bright, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if clicked."""
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hovered and self.callback:
                self.callback()
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if self._hovered and self._base_img.get_width() > 30:
            # Glow behind hovered button
            glow = pygame.Surface((self.rect.width + 14, self.rect.height + 14), pygame.SRCALPHA)
            cx, cy = glow.get_width() // 2, glow.get_height() // 2
            for r in range(5, 0, -1):
                a = 35 - r * 5
                pygame.draw.rect(glow, (255, 215, 0, a),
                                 (cx - self.rect.width//2 - r, cy - self.rect.height//2 - r,
                                  self.rect.width + r*2, self.rect.height + r*2),
                                 border_radius=10 + r)
            surface.blit(glow, (self.rect.x - 7, self.rect.y - 7))
        img = self._hover_img if self._hovered else self._base_img
        surface.blit(img, self.rect)


class Slider:
    """A horizontal slider with optional track/thumb images."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        value: float = 0.5,
        *,
        track_img: pygame.Surface | None = None,
        thumb_img: pygame.Surface | None = None,
        on_change=None,
    ):
        self.rect = pygame.Rect(x, y, width, 0)
        self.value = value  # 0.0 – 1.0
        self._track_img = track_img
        self._thumb_img = thumb_img
        self._on_change = on_change
        self._dragging = False

        # Determine thumb half-width for clamping
        self._thumb_hw = (self._thumb_img.get_width() // 2) if self._thumb_img else 12

    # ── helpers ──────────────────────────────────────────

    def _get_thumb_rect(self) -> pygame.Rect:
        """Pixel rect of the thumb at the current value."""
        track_left = self.rect.x + self._thumb_hw
        track_right = self.rect.x + self.rect.width - self._thumb_hw
        cx = int(track_left + self.value * (track_right - track_left))
        if self._thumb_img:
            r = self._thumb_img.get_rect(center=(cx, self.rect.centery))
        else:
            r = pygame.Rect(cx - 12, self.rect.centery - 12, 24, 24)
        return r

    def _set_from_mouse(self, mouse_x: int) -> None:
        track_left = self.rect.x + self._thumb_hw
        track_right = self.rect.x + self.rect.width - self._thumb_hw
        rel = max(track_left, min(track_right, mouse_x))
        new_val = (rel - track_left) / max(1, track_right - track_left)
        if abs(new_val - self.value) > 0.001:
            self.value = new_val
            if self._on_change:
                self._on_change(self.value)

    # ── event / draw ─────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            thumb = self._get_thumb_rect()
            if thumb.collidepoint(event.pos):
                self._dragging = True
            elif self.rect.inflate(0, 20).collidepoint(event.pos):
                self._set_from_mouse(event.pos[0])
                self._dragging = True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._dragging = False

        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._set_from_mouse(event.pos[0])

    def draw(self, surface: pygame.Surface) -> None:
        # Track
        if self._track_img:
            tr = self._track_img.get_rect(center=self.rect.center)
            surface.blit(self._track_img, tr)
        else:
            tr = pygame.Rect(self.rect.x, self.rect.centery - 4, self.rect.width, 8)
            pygame.draw.rect(surface, (80, 80, 80), tr, border_radius=4)
            # Filled portion
            fill_w = int(self.rect.width * self.value)
            if fill_w > 0:
                pygame.draw.rect(surface, (70, 130, 180),
                                 pygame.Rect(self.rect.x, self.rect.centery - 4, fill_w, 8),
                                 border_radius=4)

        # Thumb
        thumb = self._get_thumb_rect()
        if self._thumb_img:
            surface.blit(self._thumb_img, thumb)
        else:
            pygame.draw.circle(surface, (200, 200, 200), thumb.center, 12)
            pygame.draw.circle(surface, (255, 255, 255), thumb.center, 12, 1)


class TextInput:
    """A single-line text input field with cursor and visual feedback."""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text: str = "",
        *,
        font: pygame.font.Font | None = None,
        placeholder: str = "",
        password: bool = False,
    ):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font or get_font(22)
        self.placeholder = placeholder
        self.password = password
        self._active = False
        self._cursor_pos = len(text)
        self._cursor_timer = 0.0
        self._cursor_visible = True

    @property
    def active(self) -> bool:
        return self._active

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if the event was consumed."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._active = self.rect.collidepoint(event.pos)
            if self._active:
                self._cursor_pos = len(self.text)
            return self._active

        if not self._active:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                if self._cursor_pos > 0:
                    self.text = self.text[:self._cursor_pos - 1] + self.text[self._cursor_pos:]
                    self._cursor_pos -= 1
                return True
            elif event.key == pygame.K_DELETE:
                if self._cursor_pos < len(self.text):
                    self.text = self.text[:self._cursor_pos] + self.text[self._cursor_pos + 1:]
                return True
            elif event.key == pygame.K_LEFT:
                self._cursor_pos = max(0, self._cursor_pos - 1)
                return True
            elif event.key == pygame.K_RIGHT:
                self._cursor_pos = min(len(self.text), self._cursor_pos + 1)
                return True
            elif event.key == pygame.K_HOME:
                self._cursor_pos = 0
                return True
            elif event.key == pygame.K_END:
                self._cursor_pos = len(self.text)
                return True
            elif event.key == pygame.K_v and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                # Paste from clipboard
                try:
                    clip = pygame.scrap.get(pygame.SCRAP_TEXT)
                    if clip:
                        pasted = clip.decode("utf-8").replace("\r", "").replace("\n", "")
                        self.text = self.text[:self._cursor_pos] + pasted + self.text[self._cursor_pos:]
                        self._cursor_pos += len(pasted)
                except Exception:
                    pass
                return True
            elif event.unicode and event.unicode.isprintable():
                self.text = self.text[:self._cursor_pos] + event.unicode + self.text[self._cursor_pos:]
                self._cursor_pos += 1
                return True

        return False

    def update(self) -> None:
        """Update cursor blink timer (call once per frame)."""
        self._cursor_timer += 1 / 60.0
        if self._cursor_timer >= 0.5:
            self._cursor_timer = 0.0
            self._cursor_visible = not self._cursor_visible

    def draw(self, surface: pygame.Surface) -> None:
        # Background
        bg_color = (40, 40, 55) if self._active else (30, 30, 42)
        border_color = (100, 150, 220) if self._active else (80, 80, 100)
        pygame.draw.rect(surface, bg_color, self.rect, border_radius=6)
        pygame.draw.rect(surface, border_color, self.rect, width=2, border_radius=6)

        # Text (or placeholder)
        display = self.text
        if self.password and display:
            display = "•" * len(display)
        if not display and self.placeholder and not self._active:
            text_surf = self.font.render(self.placeholder, True, (120, 120, 140))
        else:
            text_surf = self.font.render(display, True, COLOR_TEXT)

        text_rect = text_surf.get_rect(midleft=(self.rect.x + 10, self.rect.centery))
        # Clip text if too wide
        clip_rect = pygame.Rect(self.rect.x + 8, self.rect.y + 4,
                                self.rect.width - 16, self.rect.height - 8)
        surface.blit(text_surf, text_rect, clip_rect)

        # Cursor
        if self._active and self._cursor_visible:
            cursor_x = self.rect.x + 10
            if self._cursor_pos > 0:
                prefix = display[:self._cursor_pos]
                cursor_x += self.font.size(prefix)[0]
            cursor_h = self.font.get_height()
            cursor_y = self.rect.centery - cursor_h // 2
            pygame.draw.line(surface, (200, 200, 220),
                             (cursor_x, cursor_y),
                             (cursor_x, cursor_y + cursor_h), 2)


class Label:
    """A static text label."""

    def __init__(
        self,
        x: int,
        y: int,
        text: str,
        *,
        font: pygame.font.Font | None = None,
        color: tuple[int, int, int] = COLOR_TEXT,
    ):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.font = font or get_font(22)

    def draw(self, surface: pygame.Surface) -> None:
        text_surf = self.font.render(self.text, True, self.color)
        surface.blit(text_surf, (self.x, self.y))
