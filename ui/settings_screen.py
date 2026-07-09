"""
Settings screen — volume control, song switching, board skin, background.
"""

from __future__ import annotations

import os
import pygame

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, COLOR_TEXT,
    SETTINGS_BG_IMG, SLIDER_TRACK_IMG, SLIDER_THUMB_IMG,
    BTN_PREV_IMG, BTN_NEXT_IMG, BTN_PLAYPAUSE_IMG,
    CHECKBOX_ON_IMG, CHECKBOX_OFF_IMG,
)
from ui.widgets import Button, Slider
from utils.fonts import get_font, get_title_font
from utils.asset_loader import (
    get_available_backgrounds, get_available_boards,
    get_background_path, get_board_path,
)


# Layout constants relative to the settings panel
PANEL_W, PANEL_H = 900, 620
PANEL_X = (WINDOW_WIDTH - PANEL_W) // 2
PANEL_Y = (WINDOW_HEIGHT - PANEL_H) // 2

# Internal layout helpers
def _px(x: int) -> int: return PANEL_X + x
def _py(y: int) -> int: return PANEL_Y + y


class SettingsScreen:
    """Settings overlay with volume sliders, prev/next toggles for skins/songs."""

    def __init__(self, on_back, *, settings_mgr, bgm_player, board_view, reload_background):
        self._on_back = on_back
        self._settings = settings_mgr
        self._bgm = bgm_player
        self._board_view = board_view
        self._reload_background = reload_background

        # ── Load UI images ───────────────────────────────
        self._panel_img = self._load_img(SETTINGS_BG_IMG)
        self._track_img = self._load_img(SLIDER_TRACK_IMG)
        self._thumb_img = self._load_img(SLIDER_THUMB_IMG)
        self._btn_prev_img = self._load_img(BTN_PREV_IMG)
        self._btn_next_img = self._load_img(BTN_NEXT_IMG)
        self._btn_playpause_img = self._load_img(BTN_PLAYPAUSE_IMG)
        self._chk_on_img  = self._load_img(CHECKBOX_ON_IMG)
        self._chk_off_img = self._load_img(CHECKBOX_OFF_IMG)

        # ── Available asset lists ────────────────────────
        self._boards = get_available_boards()
        self._backgrounds = get_available_backgrounds()
        self._board_index = self._find_index(self._boards, self._settings.current_board_skin)
        self._bg_index = self._find_index(self._backgrounds, self._settings.current_background)

        # ── Build widgets ────────────────────────────────
        self.widgets: list = []
        self._build()

    # ── Build ────────────────────────────────────────────

    def _build(self) -> None:
        """Layout with generous spacing between sections.
        Panel is 900×620; content area y=70 .. y=580.
        """
        c_gold = (255, 215, 0)
        font_label   = get_font(24)
        font_value   = get_font(22)
        font_section = get_title_font(28)

        # Absolute Y anchors inside the panel (relative to panel top-left)
        SEC1_TITLE = 80    # 音量控制
        SEC1_BGM   = 125   # BGM slider row
        SEC1_SFX   = 178   # SFX slider row

        SEC2_TITLE = 238   # 背景音乐
        SEC2_CTRL  = 282   # prev / song / next / playpause

        SEC3_TITLE = 348   # 棋盘皮肤
        SEC3_CTRL  = 392   # prev / name / next

        SEC4_TITLE = 458   # 背景切换
        SEC4_CTRL  = 502   # prev / name / next

        BACK_BTN_Y = 565
        btn_w, btn_h = 220, 50

        # ── Section 1: Volume ────────────────────────────
        self.widgets.append(
            Label(_px(60), _py(SEC1_TITLE), "音量控制", font=font_section, color=c_gold)
        )

        # BGM
        self.widgets.append(Label(_px(80), _py(SEC1_BGM), "BGM", font=font_label))
        self._bgm_pct = Label(_px(570), _py(SEC1_BGM), "50%", font=font_value)
        self.widgets.append(self._bgm_pct)
        bgm_slider = Slider(
            _px(160), _py(SEC1_BGM + 4), 300,
            value=self._settings.bgm_volume,
            track_img=self._track_img, thumb_img=self._thumb_img,
            on_change=self._on_bgm_volume,
        )
        self.widgets.append(bgm_slider)
        self._bgm_slider = bgm_slider

        # SFX
        self.widgets.append(Label(_px(80), _py(SEC1_SFX), "SFX", font=font_label))
        self._sfx_pct = Label(_px(570), _py(SEC1_SFX), f"{int(self._settings.sfx_volume * 100)}%", font=font_value)
        self.widgets.append(self._sfx_pct)
        sfx_slider = Slider(
            _px(160), _py(SEC1_SFX + 4), 300,
            value=self._settings.sfx_volume,
            track_img=self._track_img, thumb_img=self._thumb_img,
            on_change=self._on_sfx_volume,
        )
        self.widgets.append(sfx_slider)
        self._sfx_slider = sfx_slider

        # ── Section 2: Song ──────────────────────────────
        self.widgets.append(
            Label(_px(60), _py(SEC2_TITLE), "背景音乐", font=font_section, color=c_gold)
        )

        self._song_label = Label(_px(240), _py(SEC2_CTRL), self._song_display_text(), font=font_value)
        self.widgets.append(self._song_label)

        self.widgets.append(
            ImageButtonWidget(_px(140), _py(SEC2_CTRL - 5), self._btn_prev_img,
                              callback=self._on_prev_song)
        )
        self.widgets.append(
            ImageButtonWidget(_px(555), _py(SEC2_CTRL - 5), self._btn_next_img,
                              callback=self._on_next_song)
        )
        self.widgets.append(
            ImageButtonWidget(_px(625), _py(SEC2_CTRL - 5), self._btn_playpause_img,
                              callback=self._on_toggle_pause)
        )

        # ── Section 3: Board skin ────────────────────────
        self.widgets.append(
            Label(_px(60), _py(SEC3_TITLE), "棋盘皮肤", font=font_section, color=c_gold)
        )

        self._board_label = Label(_px(240), _py(SEC3_CTRL), self._board_display_text(), font=font_value)
        self.widgets.append(self._board_label)

        self.widgets.append(
            ImageButtonWidget(_px(140), _py(SEC3_CTRL - 5), self._btn_prev_img,
                              callback=self._on_prev_board)
        )
        self.widgets.append(
            ImageButtonWidget(_px(555), _py(SEC3_CTRL - 5), self._btn_next_img,
                              callback=self._on_next_board)
        )

        # ── Section 4: Background ────────────────────────
        self.widgets.append(
            Label(_px(60), _py(SEC4_TITLE), "背景切换", font=font_section, color=c_gold)
        )

        self._bg_label = Label(_px(240), _py(SEC4_CTRL), self._bg_display_text(), font=font_value)
        self.widgets.append(self._bg_label)

        self.widgets.append(
            ImageButtonWidget(_px(140), _py(SEC4_CTRL - 5), self._btn_prev_img,
                              callback=self._on_prev_bg)
        )
        self.widgets.append(
            ImageButtonWidget(_px(555), _py(SEC4_CTRL - 5), self._btn_next_img,
                              callback=self._on_next_bg)
        )

        # ── Starfield toggle (compact row) ────────────────
        TOGGLE_Y = 540
        self._starfield_check = Checkbox(
            _px(80), _py(TOGGLE_Y),
            self._chk_on_img, self._chk_off_img,
            checked=self._settings.show_starfield,
            callback=self._on_toggle_starfield,
        )
        self.widgets.append(self._starfield_check)
        self.widgets.append(
            Label(_px(130), _py(TOGGLE_Y + 6), "星空背景效果", font=font_value)
        )

        # ── Back button ──────────────────────────────────
        self.widgets.append(
            Button(_px(PANEL_W // 2 - btn_w // 2), _py(BACK_BTN_Y), btn_w, btn_h,
                   "返回 (Back)", callback=self._on_back)
        )

    # ── Display text helpers ─────────────────────────────

    def _song_display_text(self) -> str:
        cur = self._bgm.current_track or "(无)"
        total = self._bgm.playlist_size
        idx = self._bgm.current_index + 1 if total > 0 else 0
        return f"{cur}  ({idx}/{total})"

    def _board_display_text(self) -> str:
        cur = self._boards[self._board_index] if self._boards else "board_default.png"
        total = len(self._boards)
        idx = self._board_index + 1
        # Strip extension for display
        name = os.path.splitext(cur)[0]
        return f"{name}  ({idx}/{total})"

    def _bg_display_text(self) -> str:
        cur = self._backgrounds[self._bg_index] if self._backgrounds else "bg_default.png"
        total = len(self._backgrounds)
        idx = self._bg_index + 1
        name = os.path.splitext(cur)[0]
        return f"{name}  ({idx}/{total})"

    def _refresh_labels(self) -> None:
        self._song_label.text = self._song_display_text()
        self._board_label.text = self._board_display_text()
        self._bg_label.text = self._bg_display_text()

    # ── Volume callbacks ─────────────────────────────────

    def _on_bgm_volume(self, value: float) -> None:
        self._settings.bgm_volume = value
        self._bgm.set_volume(value)
        self._bgm_pct.text = f"{int(value * 100)}%"

    def _on_sfx_volume(self, value: float) -> None:
        self._settings.sfx_volume = value
        from utils.asset_loader import set_sfx_volume
        set_sfx_volume(value)
        self._sfx_pct.text = f"{int(value * 100)}%"

    # ── Song callbacks ───────────────────────────────────

    def _on_prev_song(self) -> None:
        if self._bgm.playlist_size > 0:
            self._bgm.prev_track()
            self._refresh_labels()

    def _on_next_song(self) -> None:
        if self._bgm.playlist_size > 0:
            self._bgm.next_track()
            self._refresh_labels()

    def _on_toggle_pause(self) -> None:
        self._bgm.toggle_pause()
        self._refresh_labels()

    # ── Board skin callbacks ─────────────────────────────

    def _on_prev_board(self) -> None:
        if not self._boards:
            return
        self._board_index = (self._board_index - 1) % len(self._boards)
        filename = self._boards[self._board_index]
        self._settings.current_board_skin = filename
        path = get_board_path(filename)
        self._board_view.set_board_skin(path)
        self._refresh_labels()

    def _on_next_board(self) -> None:
        if not self._boards:
            return
        self._board_index = (self._board_index + 1) % len(self._boards)
        filename = self._boards[self._board_index]
        self._settings.current_board_skin = filename
        path = get_board_path(filename)
        self._board_view.set_board_skin(path)
        self._refresh_labels()

    # ── Background callbacks ─────────────────────────────

    def _on_prev_bg(self) -> None:
        if not self._backgrounds:
            return
        self._bg_index = (self._bg_index - 1) % len(self._backgrounds)
        filename = self._backgrounds[self._bg_index]
        self._settings.current_background = filename
        path = get_background_path(filename)
        self._reload_background(path)
        self._refresh_labels()

    def _on_next_bg(self) -> None:
        if not self._backgrounds:
            return
        self._bg_index = (self._bg_index + 1) % len(self._backgrounds)
        filename = self._backgrounds[self._bg_index]
        self._settings.current_background = filename
        path = get_background_path(filename)
        self._reload_background(path)
        self._refresh_labels()

    # ── Display toggle ──────────────────────────────────

    def _on_toggle_starfield(self, checked: bool) -> None:
        self._settings.show_starfield = checked

    # ── Helpers ──────────────────────────────────────────

    @staticmethod
    def _find_index(items: list[str], target: str) -> int:
        try:
            return items.index(target)
        except ValueError:
            return 0

    @staticmethod
    def _load_img(path: str) -> pygame.Surface | None:
        try:
            return pygame.image.load(path).convert_alpha()
        except FileNotFoundError:
            return None

    # ── Event / Draw ─────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        for w in self.widgets:
            if hasattr(w, "handle_event"):
                w.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        # Semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        surface.blit(overlay, (0, 0))

        # Panel background image
        if self._panel_img:
            surface.blit(self._panel_img, (PANEL_X, PANEL_Y))
        else:
            panel_rect = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H)
            pygame.draw.rect(surface, (30, 30, 45), panel_rect, border_radius=14)
            pygame.draw.rect(surface, (180, 180, 200), panel_rect, width=2, border_radius=14)

        # Thin separator lines between sections
        sep_color = (100, 100, 120)
        for sep_y in (228, 338, 448):
            pygame.draw.line(surface, sep_color,
                             (_px(60), _py(sep_y)),
                             (_px(PANEL_W - 60), _py(sep_y)), 1)

        # Widgets
        for w in self.widgets:
            w.draw(surface)


# ── Adapter classes (thin wrappers so the settings screen code reads cleanly) ──

class Label:
    """Thin wrapper matching the widget Label api used in this module."""
    def __init__(self, x, y, text, *, font=None, color=COLOR_TEXT):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.font = font or get_font(22)

    def handle_event(self, event):
        pass

    def draw(self, surface):
        s = self.font.render(self.text, True, self.color)
        surface.blit(s, (self.x, self.y))


class ImageButtonWidget:
    """Thin wrapper around an image-only clickable button."""
    def __init__(self, x, y, img, *, callback=None):
        self.rect = img.get_rect(topleft=(x, y)) if img else pygame.Rect(x, y, 40, 40)
        self._img = img
        self._hover_img = self._make_hover(img) if img else None
        self.callback = callback
        self._hovered = False
        self._active_img = img

    @staticmethod
    def _make_hover(img: pygame.Surface) -> pygame.Surface:
        h = img.copy()
        bright = pygame.Surface(h.get_size(), pygame.SRCALPHA)
        bright.fill((60, 60, 60, 0))
        h.blit(bright, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return h

    def handle_event(self, event):
        if not self._img:
            return
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
            self._active_img = self._hover_img if self._hovered else self._img
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._hovered and self.callback:
                self.callback()

    def draw(self, surface):
        if self._img:
            surface.blit(self._active_img, self.rect)


class Checkbox:
    """A clickable checkbox that toggles between on/off images."""

    def __init__(self, x, y, img_on, img_off, *, checked=False, callback=None):
        self.rect = img_on.get_rect(topleft=(x, y)) if img_on else pygame.Rect(x, y, 40, 40)
        self._img_on = img_on
        self._img_off = img_off
        self.checked = checked
        self.callback = callback

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.checked = not self.checked
                if self.callback:
                    self.callback(self.checked)

    def draw(self, surface):
        img = self._img_on if self.checked else self._img_off
        if img:
            surface.blit(img, self.rect)
