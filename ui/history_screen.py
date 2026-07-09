"""
History screen — lists saved game records and allows entering replay mode.
"""

from __future__ import annotations

import pygame
from config import WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_BG, COLOR_TEXT, COLOR_BUTTON
from core.recorder import GameRecorder, GameRecord
from ui.widgets import Button, Label
from utils.fonts import get_font, get_title_font


_MODE_LABELS = {
    "pvp": "人人对战",
    "ai": "人机对战",
    "network": "多人联机",
    "skill": "技能五子棋",
}


class HistoryScreen:
    """Shows a scrollable list of recorded games."""

    def __init__(self, recorder: GameRecorder, on_back, on_replay):
        self.recorder = recorder
        self._on_back = on_back
        self._on_replay = on_replay  # callback(record_id)

        self._records: list[GameRecord] = []
        self._scroll_offset = 0
        self._hovered_index = -1

        # Layout
        self._list_top = 120
        self._item_height = 36
        self._visible_items = 12
        self._font = get_font(22)
        self._font_small = get_font(18)

        cx = WINDOW_WIDTH // 2
        btn_w, btn_h = 220, 50
        self._back_btn = Button(
            cx - btn_w // 2, WINDOW_HEIGHT - 70, btn_w, btn_h,
            "返回 (Back)", callback=on_back,
        )

    # ── Lifecycle ────────────────────────────────────────

    def on_enter(self) -> None:
        """Refresh the record list when entering this screen."""
        self._records = self.recorder.list_records()
        self._scroll_offset = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        self._back_btn.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self._hovered_index >= 0:
                idx = self._hovered_index + self._scroll_offset
                if 0 <= idx < len(self._records):
                    self._on_replay(self._records[idx].id)

        elif event.type == pygame.MOUSEMOTION:
            mx, my = event.pos
            rel_y = my - self._list_top
            self._hovered_index = (
                rel_y // self._item_height
                if 0 <= rel_y < self._visible_items * self._item_height
                else -1
            )

        elif event.type == pygame.MOUSEWHEEL:
            self._scroll_offset = max(
                0,
                min(
                    self._scroll_offset - event.y,
                    max(0, len(self._records) - self._visible_items),
                ),
            )
            self._hovered_index = -1

    def draw(self, surface: pygame.Surface) -> None:
        # Dim the background so the white/grey text is readable
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surface.blit(overlay, (0, 0))

        # Title
        title = self._font.render("历史记录 / Game History", True, (255, 215, 0))
        surface.blit(title, (WINDOW_WIDTH // 2 - title.get_width() // 2, 40))

        # Column headers
        header_x = 40
        for label, x_off in [("#", 0), ("模式", 40), ("日期", 200), ("黑方", 340),
                              ("白方", 440), ("结果", 540), ("手数", 620)]:
            hdr = self._font_small.render(label, True, (180, 180, 180))
            surface.blit(hdr, (header_x + x_off, 90))

        pygame.draw.line(surface, (100, 100, 100), (40, 115), (WINDOW_WIDTH - 40, 115), 1)

        # Record rows
        start = self._scroll_offset
        end = min(start + self._visible_items, len(self._records))
        for i in range(start, end):
            rec = self._records[i]
            row_y = self._list_top + (i - start) * self._item_height

            # Highlight hovered row
            if i - start == self._hovered_index:
                rect = pygame.Rect(35, row_y, WINDOW_WIDTH - 70, self._item_height)
                pygame.draw.rect(surface, (60, 60, 90), rect, border_radius=4)

            winner_str = {"BLACK": "黑胜", "WHITE": "白胜", None: "平局"}.get(rec.winner, "—")
            items = [
                str(i + 1),
                _MODE_LABELS.get(rec.mode, rec.mode),
                rec.created_at[:16].replace("T", " "),
                rec.players.get("black", "—"),
                rec.players.get("white", "—"),
                winner_str,
                str(rec.move_count),
            ]
            for j, text in enumerate(items):
                color = COLOR_TEXT if i - start == self._hovered_index else (200, 200, 200)
                surf = self._font_small.render(text, True, color)
                surface.blit(surf, (header_x + [0, 40, 200, 340, 440, 540, 620][j], row_y + 8))

        # Empty state
        if not self._records:
            empty = self._font.render("暂无记录 — 开始一局游戏吧！", True, (140, 140, 140))
            surface.blit(empty, (WINDOW_WIDTH // 2 - empty.get_width() // 2, 250))

        # Scroll indicator
        if len(self._records) > self._visible_items:
            pct = self._scroll_offset / max(1, len(self._records) - self._visible_items)
            bar_h = self._visible_items * self._item_height
            thumb_h = max(20, bar_h * self._visible_items / len(self._records))
            thumb_y = self._list_top + pct * (bar_h - thumb_h)
            pygame.draw.rect(surface, (80, 80, 80),
                             (WINDOW_WIDTH - 20, self._list_top, 6, bar_h), border_radius=3)
            pygame.draw.rect(surface, (160, 160, 160),
                             (WINDOW_WIDTH - 20, int(thumb_y), 6, int(thumb_h)), border_radius=3)

        self._back_btn.draw(surface)
