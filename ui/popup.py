"""
Popup dialog — shown on win/draw, blocks game input until dismissed.
"""

from __future__ import annotations

import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT, POPUP_WIDTH, POPUP_HEIGHT


class Popup:
    """
    A centered modal popup with a message and an OK button.
    """

    def __init__(self, message: str, on_dismiss):
        self.message = message
        self._on_dismiss = on_dismiss
        self.visible = True

        # Position
        self.rect = pygame.Rect(
            (WINDOW_WIDTH - POPUP_WIDTH) // 2,
            (WINDOW_HEIGHT - POPUP_HEIGHT) // 2,
            POPUP_WIDTH,
            POPUP_HEIGHT,
        )

        # OK button
        btn_w, btn_h = 120, 40
        self._btn_rect = pygame.Rect(
            self.rect.centerx - btn_w // 2,
            self.rect.bottom - 60,
            btn_w,
            btn_h,
        )
        self._hovered = False

        # Fonts
        from utils.fonts import get_font, get_title_font
        self._font_msg = get_title_font(30)
        self._font_btn = get_font(22)

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.visible:
            return

        if event.type == pygame.MOUSEMOTION:
            self._hovered = self._btn_rect.collidepoint(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hovered:
                self.visible = False
                if self._on_dismiss:
                    self._on_dismiss()
            # Also dismiss on click outside? No — only OK button.

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        # Semi-transparent overlay over the entire window
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        # Popup box
        pygame.draw.rect(surface, (40, 40, 50), self.rect, border_radius=10)
        pygame.draw.rect(surface, (200, 200, 200), self.rect, width=2, border_radius=10)

        # Message
        lines = self.message.split("\n")
        for i, line in enumerate(lines):
            text = self._font_msg.render(line, True, (255, 255, 255))
            tx = self.rect.centerx - text.get_width() // 2
            ty = self.rect.top + 40 + i * 40
            surface.blit(text, (tx, ty))

        # OK button
        btn_color = (70, 130, 180) if not self._hovered else (100, 160, 210)
        pygame.draw.rect(surface, btn_color, self._btn_rect, border_radius=6)
        pygame.draw.rect(surface, (255, 255, 255), self._btn_rect, width=1, border_radius=6)
        btn_text = self._font_btn.render("确定", True, (255, 255, 255))
        bt_x = self._btn_rect.centerx - btn_text.get_width() // 2
        bt_y = self._btn_rect.centery - btn_text.get_height() // 2
        surface.blit(btn_text, (bt_x, bt_y))


class WaitingPopup:
    """
    Waiting-room popup for multiplayer — shows a URL, a copy button,
    and a cancel button. Dismissed programmatically when the opponent joins.
    """

    WAIT_W, WAIT_H = 500, 240

    def __init__(self, url: str, on_cancel):
        self.url = url
        self._on_cancel = on_cancel
        self.visible = True

        self.rect = pygame.Rect(
            (WINDOW_WIDTH - self.WAIT_W) // 2,
            (WINDOW_HEIGHT - self.WAIT_H) // 2,
            self.WAIT_W,
            self.WAIT_H,
        )

        from utils.fonts import get_font, get_title_font
        self._font_title = get_title_font(26)
        self._font_url = get_font(20)
        self._font_btn = get_font(20)

        btn_w, btn_h = 110, 38
        gap = 30
        total_w = btn_w * 2 + gap
        start_x = self.rect.centerx - total_w // 2
        btn_y = self.rect.bottom - 60

        self._copy_rect = pygame.Rect(start_x, btn_y, btn_w, btn_h)
        self._cancel_rect = pygame.Rect(start_x + btn_w + gap, btn_y, btn_w, btn_h)
        self._copy_hovered = False
        self._cancel_hovered = False
        self._copied = False

    def dismiss(self) -> None:
        """Programmatically hide this popup (called when game starts)."""
        self.visible = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.visible:
            return

        if event.type == pygame.MOUSEMOTION:
            self._copy_hovered = self._copy_rect.collidepoint(event.pos)
            self._cancel_hovered = self._cancel_rect.collidepoint(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._copy_hovered:
                self._copy_url()
            elif self._cancel_hovered:
                self.visible = False
                if self._on_cancel:
                    self._on_cancel()

    def _copy_url(self) -> None:
        """Copy URL to clipboard using best available method."""
        self._copied = True
        try:
            import pyperclip
            pyperclip.copy(self.url)
        except ImportError:
            try:
                pygame.scrap.init()
                pygame.scrap.put(pygame.SCRAP_TEXT, self.url.encode("utf-8"))
            except Exception:
                pass  # best-effort

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return

        # Overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        # Box
        pygame.draw.rect(surface, (40, 40, 50), self.rect, border_radius=10)
        pygame.draw.rect(surface, (200, 200, 200), self.rect, width=2, border_radius=10)

        # Title
        title = self._font_title.render("多人对战 — 等待对手加入", True, (255, 215, 0))
        tx = self.rect.centerx - title.get_width() // 2
        surface.blit(title, (tx, self.rect.top + 28))

        # URL (draw a dark bg behind it so it's easy to read)
        url_text = self._font_url.render(self.url, True, (200, 230, 255))
        url_rect = pygame.Rect(
            self.rect.centerx - url_text.get_width() // 2 - 12,
            self.rect.top + 72,
            url_text.get_width() + 24,
            url_text.get_height() + 14,
        )
        pygame.draw.rect(surface, (20, 30, 50), url_rect, border_radius=6)
        pygame.draw.rect(surface, (80, 80, 100), url_rect, width=1, border_radius=6)
        surface.blit(url_text, (url_rect.x + 12, url_rect.y + 7))

        # Waiting hint
        hint = self._font_url.render("请在浏览器中打开上方网址" if not self._copied else "已复制！请在浏览器中打开网址",
                                     True, (180, 180, 180))
        surface.blit(hint, (self.rect.centerx - hint.get_width() // 2, self.rect.top + 122))

        # Copy button
        copy_color = (70, 130, 180) if not self._copy_hovered else (100, 160, 210)
        pygame.draw.rect(surface, copy_color, self._copy_rect, border_radius=6)
        pygame.draw.rect(surface, (255, 255, 255), self._copy_rect, width=1, border_radius=6)
        ct = self._font_btn.render("复制" if not self._copied else "已复制", True, (255, 255, 255))
        surface.blit(ct, (self._copy_rect.centerx - ct.get_width() // 2,
                          self._copy_rect.centery - ct.get_height() // 2))

        # Cancel button
        cancel_color = (150, 60, 60) if not self._cancel_hovered else (200, 90, 90)
        pygame.draw.rect(surface, cancel_color, self._cancel_rect, border_radius=6)
        pygame.draw.rect(surface, (255, 255, 255), self._cancel_rect, width=1, border_radius=6)
        cct = self._font_btn.render("取消", True, (255, 255, 255))
        surface.blit(cct, (self._cancel_rect.centerx - cct.get_width() // 2,
                           self._cancel_rect.centery - cct.get_height() // 2))
