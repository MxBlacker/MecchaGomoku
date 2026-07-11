"""
Main renderer — owns the pygame window and delegates drawing to sub-views.
Manages screen transitions: menu ↔ game modes ↔ history ↔ settings ↔ replay.
Integrates hover-preview, placement sound, and win/draw popup.
"""

from __future__ import annotations

import sys
from typing import Optional

import pygame

from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS, TITLE, COLOR_BG, COLOR_TEXT,
    BOARD_OFFSET_X, BOARD_OFFSET_Y, BOARD_SIZE, CELL_SIZE, MARGIN,
    MENU_BAR_HEIGHT, MENU_BAR_BTN_SCALE,
    EXIT_BUTTON_IMG, MINIMIZE_BUTTON_IMG,
    DEEPSEEK_GIRL_IMG,
    BLACK_AVATAR_IMG, WHITE_AVATAR_IMG, AVATAR_SIZE,
    SKILL_ICON_SIZE, SKILL_USE_SOUND,
    SKILL_GACHA_IMG, SKILL_REVERSE_IMG, SKILL_DEADZONE_IMG, SKILL_DEFENSE_IMG,
)
from core.game_manager import GameManager, GameState
from core.stone import StoneColor
from core.board import pos_to_label
from core.recorder import GameRecorder
from ui.board_view import BoardView
from ui.menu import MainMenu
from ui.settings_screen import SettingsScreen
from ui.history_screen import HistoryScreen
from ui.popup import Popup, WaitingPopup, ColorChoicePopup
from ui.widgets import ImageButton
from modes.local_pvp import LocalPvPMode
from modes.ai_mode import AIVsMode
from modes.replay_mode import ReplayMode
from modes.skill_mode import SkillMode
from modes.network.multiplayer_mode import MultiplayerMode
from core.skill_system import SkillManager, SkillID, SkillResult
from ui.skill_widget import SkillPanel
from ui.skill_effects import SkillEffects
from utils.asset_loader import (
    get_place_sound, get_victory_sound, load_background,
    play_sfx, set_sfx_volume,
    get_available_backgrounds, get_available_boards,
    get_background_path, get_board_path,
)
from utils.fonts import get_font
from utils.bgm_player import BGMPlayer, BGM_TRACK_END
from utils.settings_manager import SettingsManager
from utils.window_effects import enable_transparency, start_window_drag, KEY_COLOR
from utils.particles import EffectsManager


class Renderer:
    """
    Top-level render loop.
    Owns the window Surface and orchestrates scene rendering.
    """

    def __init__(self, game_manager: GameManager):
        pygame.init()
        pygame.mixer.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.NOFRAME)
        pygame.display.set_caption(TITLE)
        self._transparent = enable_transparency()  # make KEY_COLOR pixels see-through
        self.clock = pygame.time.Clock()
        self.running = True

        self.gm = game_manager
        self.recorder = GameRecorder()
        self.gm.recorder = self.recorder  # wire up recording

        self.board_view = BoardView(offset_x=BOARD_OFFSET_X, offset_y=BOARD_OFFSET_Y)
        self._place_sound = get_place_sound()
        self._victory_sound = get_victory_sound()

        # Board pixel dimensions (for positioning side panels)
        self._board_px_w = MARGIN * 2 + (BOARD_SIZE - 1) * CELL_SIZE
        self._board_px_h = self._board_px_w  # square

        # Player avatars
        self._black_avatar = self._load_avatar(BLACK_AVATAR_IMG)
        self._white_avatar = self._load_avatar(WHITE_AVATAR_IMG)

        # DeepSeek AI girl character (for replay AI panel)
        self._deepseek_girl = self._load_deepseek_girl()

        # Last move position per player
        self._last_black_move: tuple[int, int] | None = None
        self._last_white_move: tuple[int, int] | None = None

        # Background image (shared by menu, game, replay, etc.)
        self._background = load_background()

        # BGM playlist player
        self._bgm = BGMPlayer()
        self._bgm.set_volume(0.5)
        self._bgm.start()

        # Persistent settings (volume, skins, etc.)
        self._settings_mgr = SettingsManager()

        # Apply saved settings
        self._bgm.set_volume(self._settings_mgr.bgm_volume)
        set_sfx_volume(self._settings_mgr.sfx_volume)

        # Apply saved board skin
        saved_board = self._settings_mgr.current_board_skin
        self.board_view.set_board_skin(get_board_path(saved_board))

        # Apply saved background
        saved_bg = self._settings_mgr.current_background
        loaded_bg = load_background(get_background_path(saved_bg))
        if loaded_bg:
            self._background = loaded_bg

        # Top bar buttons (visible on all screens)
        self._bar_buttons: list[ImageButton] = []
        self._build_top_bar()

        # Active game mode
        self._active_mode: Optional[LocalPvPMode | AIVsMode | ReplayMode | MultiplayerMode] = None

        # Multiplayer waiting / result popups
        self._waiting_popup: Optional[WaitingPopup] = None

        # AI color-choice popup
        self._color_choice_popup: Optional[ColorChoicePopup] = None

        # Replay mode (reused)
        self._replay_mode = ReplayMode(self.gm, self.board_view, self.recorder)
        self._replay_mode._on_done = self._on_replay_done

        # Popup (created when game ends)
        self._popup: Optional[Popup] = None

        # Skill Gomoku objects (created in _on_start_skill)
        self._skill_mgr: Optional[SkillManager] = None
        self._skill_panel_left: Optional[SkillPanel] = None
        self._skill_panel_right: Optional[SkillPanel] = None
        self._skill_effects: Optional[SkillEffects] = None
        self._skill_use_sound: Optional[pygame.mixer.Sound] = None

        # Screen state
        self._screen = "menu"  # "menu" | "game" | "history" | "settings" | "replay"
        self._current_screen: Optional[MainMenu | SettingsScreen | HistoryScreen] = None

        # Track previous board state for sound trigger
        self._prev_move_count = 0

        # Visual effects
        self._fx = EffectsManager()

        self._build_menu()

    # ── Main loop ───────────────────────────────────────

    def run(self) -> None:
        """Blocking main loop. Returns when the user quits."""
        while self.running:
            dt = self.clock.tick(FPS)
            self._fx.update()

            for event in pygame.event.get():
                self._handle_event(event)

            # Per-frame updates
            if self._active_mode:
                self._active_mode.update()
            if self._skill_effects:
                self._skill_effects.update(dt)

            self._draw()
            pygame.display.flip()

        self._bgm.stop()
        pygame.quit()
        sys.exit()

    # ── Events ──────────────────────────────────────────

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
            return

        # BGM track-end → auto-advance playlist
        self._bgm.handle_event(event)

        # Color-choice popup (AI mode) — swallows events
        if self._color_choice_popup and self._color_choice_popup.visible:
            self._color_choice_popup.handle_event(event)
            return

        # Waiting popup (multiplayer) — swallows events but doesn't block BGM
        if self._waiting_popup and self._waiting_popup.visible:
            self._waiting_popup.handle_event(event)
            return

        # Popup swallows all events
        if self._popup and self._popup.visible:
            self._popup.handle_event(event)
            return

        # Top bar buttons (all screens except when popup is up)
        for btn in self._bar_buttons:
            btn.handle_event(event)

        # Drag window by the menu bar (click on empty bar space → native drag)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._is_on_menu_bar_empty(event.pos):
                start_window_drag()

        # Global keyboard shortcuts
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if self._screen == "menu":
                    self.running = False  # quit from main menu
                else:
                    self._go_to_menu()
                return

            # Ctrl+U — undo last move
            if event.key == pygame.K_u and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                if self._screen == "game" and self._active_mode:
                    if self.gm.undo_move():
                        self._prev_move_count = self.gm.board.move_count
                        self._last_black_move = None
                        self._last_white_move = None
                        # Re-scan last moves from history
                        for stone in self.gm.board._history:
                            if stone.color.name == "BLACK":
                                self._last_black_move = (stone.row, stone.col)
                            else:
                                self._last_white_move = (stone.row, stone.col)
                return

        # Delegate to current screen / mode
        if self._screen == "menu" and self._current_screen:
            self._current_screen.handle_event(event)

        elif self._screen in ("settings", "history") and self._current_screen:
            self._current_screen.handle_event(event)

        elif self._screen == "replay":
            self._replay_mode.handle_event(event)

        elif self._screen == "game" and self._active_mode:
            self._active_mode.handle_event(event)
            # Play sound if a stone was placed
            new_count = self.gm.board.move_count
            if new_count > self._prev_move_count:
                self._prev_move_count = new_count
                self._update_last_move()
                # Spawn particle burst at stone position
                stone = self.gm.board.last_move()
                if stone:
                    px, py = self.board_view.grid_to_pixel(stone.row, stone.col)
                    self._fx.spawn_burst(px, py)
                play_sfx(self._place_sound)
            # Check if game just ended → show popup
            if self.gm.state == GameState.GAME_OVER and not self._popup:
                self._show_game_over_popup()

    # ── Drawing ─────────────────────────────────────────

    def _draw(self) -> None:
        # Shared background + top bar on every screen
        self._draw_bg_or_fill()
        self._draw_top_bar()

        if self._screen in ("menu", "settings", "history") and self._current_screen:
            self._current_screen.draw(self.screen)

        elif self._screen == "replay":
            self._draw_replay_content()

        elif self._screen == "game":
            self._draw_game_content()

        # Color-choice popup (AI mode)
        if self._color_choice_popup and self._color_choice_popup.visible:
            self._color_choice_popup.draw(self.screen)

        # Waiting popup (multiplayer)
        if self._waiting_popup and self._waiting_popup.visible:
            self._waiting_popup.draw(self.screen)

        # Popup on top of everything
        if self._popup and self._popup.visible:
            self._popup.draw(self.screen)

    def _draw_game_content(self) -> None:
        # Board glow — subtle radial light behind the board
        glow_cx = BOARD_OFFSET_X + self._board_px_w // 2
        glow_cy = BOARD_OFFSET_Y + self._board_px_h // 2
        glow_r = self._board_px_w // 2 + 30
        for i in range(3):
            alpha = 30 - i * 8
            s = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (80, 120, 200, alpha), (glow_r, glow_r), glow_r - i * 15)
            self.screen.blit(s, (glow_cx - glow_r, glow_cy - glow_r))

        self.board_view.draw(self.screen, self.gm.board)

        # Stone placement particle bursts
        self._fx.draw_bursts(self.screen)

        # ── Skill effects (dead zones, yin-yang, defence glow) ──
        if self._skill_effects and self._screen == "game":
            board_center_x = BOARD_OFFSET_X + self._board_px_w // 2
            board_center_y = BOARD_OFFSET_Y + self._board_px_h // 2

            # Compute avatar rects for defence-glow positioning
            board_left = BOARD_OFFSET_X
            board_top = BOARD_OFFSET_Y
            board_bottom = BOARD_OFFSET_Y + self._board_px_h
            gap = 15

            black_rect = None
            if self._black_avatar:
                ax = board_left - AVATAR_SIZE - gap
                ay = board_top + 25
                black_rect = pygame.Rect(ax, ay, AVATAR_SIZE, AVATAR_SIZE)

            white_rect = None
            if self._white_avatar:
                ax = board_left + self._board_px_w + gap
                ay = board_bottom - 25 - AVATAR_SIZE
                white_rect = pygame.Rect(ax, ay, AVATAR_SIZE, AVATAR_SIZE)

            self._skill_effects.draw_all(
                self.screen,
                board_center=(board_center_x, board_center_y),
                black_avatar_rect=black_rect,
                white_avatar_rect=white_rect,
            )

        # Player info panels (avatars + move history)
        self._draw_player_panels()

        # ── Skill panels (icon grids on both sides) ─────
        if self._skill_mgr and self._skill_panel_left and self._skill_panel_right \
                and self._screen == "game":
            # Build availability / cooldown maps for each player
            if isinstance(self._active_mode, SkillMode):
                black_avail = self._active_mode._build_available_map(StoneColor.BLACK)
                white_avail = self._active_mode._build_available_map(StoneColor.WHITE)
                black_cd = self._active_mode.get_cooldown_map(StoneColor.BLACK)
                white_cd = self._active_mode.get_cooldown_map(StoneColor.WHITE)
            else:
                black_avail = {sid: False for sid in SkillID}
                white_avail = {sid: False for sid in SkillID}
                black_cd = {sid: 0 for sid in SkillID}
                white_cd = {sid: 0 for sid in SkillID}

            self._skill_panel_left.draw(
                self.screen, black_avail, black_cd, tooltip_side="right")
            self._skill_panel_right.draw(
                self.screen, white_avail, white_cd, tooltip_side="left")

        # Hover ghost stone preview (PvP and multiplayer)
        # Skip normal preview during gacha first-stone (flickering preview is drawn by effects)
        is_gacha_hover = (isinstance(self._active_mode, SkillMode)
                          and self._active_mode._is_gacha_first())
        if (self._active_mode
                and hasattr(self._active_mode, "hover_pos")
                and self._active_mode.hover_pos is not None
                and self.gm.state == GameState.PLAYING
                and not is_gacha_hover):
            r, c = self._active_mode.hover_pos
            self.board_view.draw_hover_preview(self.screen, r, c, self.gm.current_turn)

        # Hover coordinate tooltip (follows mouse cursor)
        self._draw_hover_coord_tooltip()

        self._draw_status_bar()

        # Stone count badge (bottom-right)
        self._draw_stone_count(self.gm.board)

    def _draw_replay_content(self) -> None:
        self.board_view.draw(self.screen, self.gm.board)

        # Hover coordinate tooltip (follows mouse cursor)
        self._draw_hover_coord_tooltip()

        rm = self._replay_mode
        font = get_font(22)

        # ── AI analysis panel ─────────────────────────────
        if rm.ai_panel_visible:
            self._draw_ai_panel(rm)

        # ── Bottom control bar (with black backdrop) ────────
        font = get_font(22)
        font_sm = get_font(18)

        # Gather all bottom text lines to measure the backdrop
        bottom_lines: list[tuple[str, pygame.font.Font, tuple[int, int, int]]] = []

        info = f"复盘  {rm.move_index}/{rm.total_moves}  "
        if rm.is_playing:
            info += "▶ 自动播放中"
        else:
            info += "← → 步进  |  SPACE 自动  |  A 切换AI面板  |  ESC 返回"
        bottom_lines.append((info, font, COLOR_TEXT))

        if rm.total_moves > 0 and 1 <= rm.move_index <= rm.total_moves:
            move = rm.record.moves[rm.move_index - 1]
            if move.get("action") == "undo":
                color_name = "● 黑方" if move["color"] == "BLACK" else "○ 白方"
                detail = f"{color_name} 悔棋一步"
            else:
                color_name = "● 黑方" if move["color"] == "BLACK" else "○ 白方"
                label = pos_to_label(move["row"], move["col"])
                detail = f"{color_name} → {label}"
            bottom_lines.append((detail, font_sm, (200, 200, 220)))

        if rm.move_index == rm.total_moves and rm.total_moves > 0:
            winner = rm.record.winner
            if winner:
                badge = f"胜者: {'● 黑方' if winner == 'BLACK' else '○ 白方'}"
                wr = rm.record.win_reason
                if wr and wr != "五连":
                    reason_label = {
                        "三三禁手": "黑方三三禁手",
                        "四四禁手": "黑方四四禁手",
                        "长连禁手": "黑方长连禁手",
                    }.get(wr, wr)
                    badge += f"（{reason_label}）"
                elif wr == "五连":
                    badge += "（五连）"
            else:
                badge = "平局"
            bottom_lines.append((badge, font, (255, 215, 0)))

        if bottom_lines:
            # Measure all lines
            max_w = 0
            total_h = 0
            for text, f, _ in bottom_lines:
                tw, th = f.size(text)
                if tw > max_w:
                    max_w = tw
                total_h += th
            total_h += max(0, len(bottom_lines) - 1) * 4  # gaps between lines

            pad = 14
            bg_w = max_w + pad * 2
            bg_h = total_h + pad * 2
            bg_x = WINDOW_WIDTH // 2 - bg_w // 2
            bg_y = WINDOW_HEIGHT - 80 - pad
            bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            pygame.draw.rect(bg, (50, 50, 70, 180), bg.get_rect(), width=1, border_radius=10)
            self.screen.blit(bg, (bg_x, bg_y))

            # Draw text centered
            y = bg_y + pad
            for text, f, color in bottom_lines:
                surf = f.render(text, True, color)
                x = WINDOW_WIDTH // 2 - surf.get_width() // 2
                self.screen.blit(surf, (x, y))
                y += f.get_height() + 4

        # Stone count badge (bottom-right)
        self._draw_stone_count(self.gm.board)

    # ── AI Analysis panel drawing ────────────────────────

    def _draw_ai_panel(self, rm) -> None:
        """
        Draw the AI analysis panel during replay:
        - Left side: analysis text with black rounded-rect background
        - Right side: deepseek_girl character image
        Both panels are vertically aligned with the board.
        """
        board_top = BOARD_OFFSET_Y
        board_bottom = BOARD_OFFSET_Y + self._board_px_h
        board_left = BOARD_OFFSET_X
        board_right = board_left + self._board_px_w

        # ── Right panel: DeepSeek girl ────────────────────
        girl_x = 0  # will be set below
        if self._deepseek_girl:
            girl_w = self._deepseek_girl.get_width()
            girl_h = self._deepseek_girl.get_height()
            # Right-align: put girl to the right of the board, centered vertically
            girl_gap = 15
            girl_x = board_right + girl_gap
            girl_y = board_top + (self._board_px_h - girl_h) // 2

            # Don't overflow window
            if girl_x + girl_w > WINDOW_WIDTH - 10:
                girl_x = WINDOW_WIDTH - girl_w - 10

            self.screen.blit(self._deepseek_girl, (girl_x, girl_y))

            # Label below girl
            label_font = get_font(18)
            label = label_font.render("DeepSeek AI 分析", True, (100, 180, 255))
            label_x = girl_x + (girl_w - label.get_width()) // 2
            label_y = girl_y + girl_h + 6
            self.screen.blit(label, (label_x, label_y))

            # Pending indicator (thinking dots)
            if rm.ai_pending:
                dots = "." * (1 + int(pygame.time.get_ticks() / 600) % 3)
                pending = label_font.render(f"分析中{dots}", True, (255, 200, 100))
                self.screen.blit(pending, (label_x + 20, label_y + 22))

        # ── Left panel: AI analysis text ──────────────────
        ai_text = rm.ai_text
        if not ai_text:
            return

        # Panel: sits to the left of the board, same height as board
        panel_x = 10
        panel_y = board_top
        # Width: from left edge to just before the board (leave 10px gap)
        panel_w = board_left - 20 - panel_x
        panel_h = self._board_px_h

        # Draw background with round corners
        bg_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(bg_surf, (0, 0, 0, 195), bg_surf.get_rect(), border_radius=12)
        # Subtle border
        pygame.draw.rect(bg_surf, (60, 60, 90, 180), bg_surf.get_rect(), width=1, border_radius=12)
        self.screen.blit(bg_surf, (panel_x, panel_y))

        # Title
        title_font = get_font(18)
        title = title_font.render("💬 AI 分析", True, (100, 200, 255))
        self.screen.blit(title, (panel_x + 12, panel_y + 10))

        # Draw wrapped text
        text_font = get_font(17)
        line_h = text_font.get_linesize()
        text_area_w = panel_w - 24
        text_start_y = panel_y + 36
        text_area_h = panel_h - 48  # leave margin for title + bottom padding

        wrapped_lines = self._wrap_text(ai_text, text_font, text_area_w)
        visible_lines = text_area_h // line_h

        for i, line in enumerate(wrapped_lines):
            if i >= visible_lines:
                break
            # If last visible line and there's more, show ellipsis
            if i == visible_lines - 1 and len(wrapped_lines) > visible_lines:
                line = line[:max(0, len(line) - 3)] + "..."
            line_surf = text_font.render(line, True, (230, 230, 240))
            self.screen.blit(line_surf, (panel_x + 12, text_start_y + i * line_h))

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        """Wrap text into lines that fit within max_width pixels.
        Handles both CJK characters (break anywhere) and Latin words (break on spaces)."""
        lines: list[str] = []
        for paragraph in text.split("\n"):
            if not paragraph:
                lines.append("")
                continue

            current_line = ""
            for ch in paragraph:
                # Try adding this character
                test_line = current_line + ch
                if font.size(test_line)[0] <= max_width:
                    current_line = test_line
                else:
                    # Line is full — try to break at a space for Latin text
                    if current_line:
                        # Look back for a space to break at
                        break_at = current_line.rfind(" ")
                        if break_at > len(current_line) // 2:
                            # Break at the space
                            lines.append(current_line[:break_at])
                            current_line = current_line[break_at + 1:] + ch
                        else:
                            # No good space break — just break here
                            lines.append(current_line)
                            current_line = ch
                    else:
                        # Single character wider than max_width, force it
                        current_line = ch
            if current_line:
                lines.append(current_line)
        return lines

    def _draw_bg_or_fill(self) -> None:
        """Fill with deep space color, draw background, then starfield on top."""
        if self._transparent:
            self.screen.fill(KEY_COLOR)
        else:
            self.screen.fill((5, 5, 18))
        if self._background:
            self.screen.blit(self._background, (0, 0))
        # Starfield drawn on top of background so it's visible
        if self._settings_mgr.show_starfield:
            self._fx.draw_starfield(self.screen)

    # ── Top bar ──────────────────────────────────────────

    def _is_on_menu_bar_empty(self, pos: tuple[int, int]) -> bool:
        """True if *pos* is inside the menu bar but NOT on any bar button."""
        x, y = pos
        if y < 0 or y >= MENU_BAR_HEIGHT:
            return False
        # Check the click isn't on an existing bar button
        return not any(btn.rect.collidepoint(pos) for btn in self._bar_buttons)

    def _build_top_bar(self) -> None:
        """Create exit and minimize buttons, right-aligned in the menu bar area."""
        btn_size = int(200 * MENU_BAR_BTN_SCALE)  # 30
        y = (MENU_BAR_HEIGHT - btn_size) // 2
        gap = 20
        exit_x = WINDOW_WIDTH - 20 - btn_size
        min_x = exit_x - gap - btn_size
        self._bar_buttons = [
            ImageButton(exit_x, y, EXIT_BUTTON_IMG,
                        callback=self._on_quit_game, scale=MENU_BAR_BTN_SCALE),
            ImageButton(min_x, y, MINIMIZE_BUTTON_IMG,
                        callback=self._on_minimize, scale=MENU_BAR_BTN_SCALE),
        ]

    @staticmethod
    def _on_minimize() -> None:
        pygame.display.iconify()

    def _draw_top_bar(self) -> None:
        """Draw the menu bar buttons (drawn on top of background)."""
        for btn in self._bar_buttons:
            btn.draw(self.screen)

    # ── Status bar ───────────────────────────────────────

    def _draw_status_bar(self) -> None:
        """Show current turn / game-over info below the board."""
        font = get_font(22)
        if self.gm.state == GameState.GAME_OVER:
            if self.gm.winner:
                color_name = "● 黑方" if self.gm.winner.name == "BLACK" else "○ 白方"
                msg = f"游戏结束 — {color_name} 获胜！"
                if self.gm.win_reason and self.gm.win_reason != "五连":
                    reason_label = {
                        "三三禁手": "黑方三三禁手",
                        "四四禁手": "黑方四四禁手",
                        "长连禁手": "黑方长连禁手",
                    }.get(self.gm.win_reason, self.gm.win_reason)
                    msg += f"（{reason_label}）"
                elif self.gm.win_reason == "五连":
                    msg += "（五连）"
            else:
                msg = "平局！"
        else:
            turn_name = "● 黑方" if self.gm.current_turn.name == "BLACK" else "○ 白方"
            msg = f"当前回合: {turn_name}  |  Ctrl+U 悔棋  |  ESC 返回菜单"

        text = font.render(msg, True, COLOR_TEXT)
        tw, th = text.get_size()
        x = WINDOW_WIDTH // 2 - tw // 2
        y = WINDOW_HEIGHT - 50

        padding = 12
        bg_rect = pygame.Rect(x - padding, y - padding, tw + padding * 2, th + padding * 2)
        bg_overlay = pygame.Surface(bg_rect.size, pygame.SRCALPHA)
        bg_overlay.fill((0, 0, 0, 140))
        self.screen.blit(bg_overlay, bg_rect)

        self.screen.blit(text, (x, y))

    # ── Stone count badge ─────────────────────────────────

    def _draw_stone_count(self, board) -> None:
        """Draw a small badge showing black/white stone counts (bottom-right)."""
        black_cnt = 0
        white_cnt = 0
        for r in range(board.size):
            for c in range(board.size):
                stone = board.get_color(r, c)
                if stone is None:
                    continue
                if stone.name == "BLACK":
                    black_cnt += 1
                else:
                    white_cnt += 1

        font = get_font(18)
        line1 = f"● 黑方 {black_cnt}"
        line2 = f"○ 白方 {white_cnt}"

        s1 = font.render(line1, True, (220, 220, 220))
        s2 = font.render(line2, True, (220, 220, 220))

        pad = 10
        gap = 4
        bg_w = max(s1.get_width(), s2.get_width()) + pad * 2
        bg_h = s1.get_height() + s2.get_height() + pad * 2 + gap

        # Position: top-right, below the menu bar, above the white avatar
        board_right = BOARD_OFFSET_X + self._board_px_w
        bg_x = board_right + 15
        bg_y = MENU_BAR_HEIGHT + 20

        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        pygame.draw.rect(bg, (60, 60, 90, 180), bg.get_rect(), width=1, border_radius=8)
        self.screen.blit(bg, (bg_x, bg_y))

        self.screen.blit(s1, (bg_x + pad, bg_y + pad))
        self.screen.blit(s2, (bg_x + pad, bg_y + pad + s1.get_height() + gap))

    # ── Hover coordinate tooltip ──────────────────────────

    def _draw_hover_coord_tooltip(self) -> None:
        """
        Draw a coordinate label (e.g. 'H8') to the right of the mouse cursor
        whenever the cursor hovers over a valid board intersection.

        The label is rendered on a rounded, semi-transparent black backdrop
        that follows the mouse.
        """
        mx, my = pygame.mouse.get_pos()
        pos = self.board_view.pixel_to_grid(mx, my)
        if pos is None:
            return

        row, col = pos
        label = pos_to_label(row, col)  # e.g. "H8"

        font = get_font(28)
        text_surf = font.render(label, True, (255, 255, 255))
        tw, th = text_surf.get_size()

        # Rounded semi-transparent black backdrop
        pad_x = 16
        pad_y = 8
        bg_w = tw + pad_x * 2
        bg_h = th + pad_y * 2

        # Place the tooltip to the right of the cursor, slightly above
        gap = 18  # pixels between cursor and tooltip
        bg_x = mx + gap
        bg_y = my - bg_h // 2

        # Keep the tooltip on screen
        if bg_x + bg_w > WINDOW_WIDTH - 4:
            bg_x = mx - bg_w - gap   # flip to left side if it would overflow right
        if bg_y < MENU_BAR_HEIGHT + 4:
            bg_y = MENU_BAR_HEIGHT + 4
        if bg_y + bg_h > WINDOW_HEIGHT - 4:
            bg_y = WINDOW_HEIGHT - bg_h - 4

        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (0, 0, 0, 185), bg.get_rect(), border_radius=10)
        self.screen.blit(bg, (bg_x, bg_y))

        # Draw label text centered in the backdrop
        text_x = bg_x + pad_x
        text_y = bg_y + pad_y
        self.screen.blit(text_surf, (text_x, text_y))

    # ── Popup ───────────────────────────────────────────

    def _show_game_over_popup(self) -> None:
        """Create and show the win/draw popup, and play victory sound."""
        # Play victory SFX
        play_sfx(self._victory_sound)

        if self.gm.winner:
            color_name = "● 黑方" if self.gm.winner.name == "BLACK" else "○ 白方"
            message = f"{color_name} 获胜！"
            # Annotate win reason if it's a forbidden-move win
            if self.gm.win_reason and self.gm.win_reason != "五连":
                reason_label = {
                    "三三禁手": "黑方三三禁手",
                    "四四禁手": "黑方四四禁手",
                    "长连禁手": "黑方长连禁手",
                }.get(self.gm.win_reason, self.gm.win_reason)
                message = f"{color_name} 获胜！\n{reason_label}"
            elif self.gm.win_reason == "五连":
                message = f"{color_name} 获胜！"
        else:
            message = "平局！"
        self._popup = Popup(message, on_dismiss=self._on_popup_dismiss)

    def _on_popup_dismiss(self) -> None:
        """Called when the user clicks OK on the popup."""
        self._popup = None
        self._go_to_menu()

    # ── Screen navigation ───────────────────────────────

    def _build_menu(self) -> None:
        self._current_screen = MainMenu(
            on_pvp=self._on_start_pvp,
            on_ai=self._on_start_ai,
            on_multiplayer=self._on_start_multiplayer,
            on_skill=self._on_start_skill,
            on_history=self._on_open_history,
            on_settings=self._on_open_settings,
        )
        self._screen = "menu"
        self._active_mode = None
        self._popup = None
        self._waiting_popup = None

    def _go_to_menu(self) -> None:
        self.gm.state = GameState.MENU
        if self.gm.recorder:
            self.gm.recorder.cancel()
        if self._active_mode:
            self._active_mode.on_exit()
            self._active_mode = None
        self._waiting_popup = None
        self._build_menu()

    # ── Menu callbacks ──────────────────────────────────

    def _on_start_pvp(self) -> None:
        self.gm.game_mode = "pvp"
        self._active_mode = LocalPvPMode(self.gm, self.board_view)
        self._active_mode.on_enter()
        self._prev_move_count = 0
        self._last_black_move = None
        self._last_white_move = None
        self._screen = "game"

    # ── Skill callbacks ─────────────────────────────────

    def _on_skill_activate(self, color: StoneColor, skill_id: SkillID) -> None:
        """Forwarded from SkillPanel → SkillMode."""
        if isinstance(self._active_mode, SkillMode):
            self._active_mode._on_use_skill(color, skill_id)

    def _play_skill_sfx(self) -> None:
        """Play the skill-activation sound effect."""
        if self._skill_use_sound:
            self._skill_use_sound.play()

    def _on_start_ai(self) -> None:
        """Show color-choice popup, then start AI game with chosen color."""
        def on_choose(color_name: str):
            human_color = StoneColor[color_name]
            self.gm.game_mode = "ai"
            self._active_mode = AIVsMode(self.gm, self.board_view,
                                         human_color=human_color)
            self._active_mode.on_enter()
            self._prev_move_count = 0
            self._last_black_move = None
            self._last_white_move = None
            self._screen = "game"
            self._color_choice_popup = None

        self._color_choice_popup = ColorChoicePopup(on_choose)

    def _on_start_multiplayer(self) -> None:
        self.gm.game_mode = "network"
        mode = MultiplayerMode(self.gm, self.board_view)
        # Wire callbacks
        mode._show_waiting_popup = self._show_multiplayer_waiting
        mode._dismiss_waiting = self._dismiss_multiplayer_waiting
        mode._show_result_popup = self._show_multiplayer_result
        self._active_mode = mode
        self._prev_move_count = 0
        self._last_black_move = None
        self._last_white_move = None
        self._screen = "game"
        mode.on_enter()

    # ── Multiplayer popup callbacks ─────────────────────

    def _show_multiplayer_waiting(self, url: str, on_cancel) -> None:
        """Show the waiting-room popup (called from MultiplayerMode)."""
        def handle_cancel():
            if on_cancel:
                on_cancel()
            self._waiting_popup = None
            self._go_to_menu()

        self._waiting_popup = WaitingPopup(url, handle_cancel)

    def _dismiss_multiplayer_waiting(self) -> None:
        """Dismiss the waiting-room popup (opponent joined)."""
        if self._waiting_popup:
            self._waiting_popup.dismiss()
            self._waiting_popup = None

    def _show_multiplayer_result(self, message: str) -> None:
        """Show a game-over popup for multiplayer (called from MultiplayerMode)."""
        if self._victory_sound:
            self._victory_sound.play()
        self._popup = Popup(message, on_dismiss=self._on_popup_dismiss)

    def _on_start_skill(self) -> None:
        """Start a Skill Gomoku game with the full skill system."""
        self.gm.game_mode = "skill"

        # Create skill manager (fresh state per game)
        self._skill_mgr = SkillManager()

        # Skill icon paths
        icon_paths = {
            SkillID.GACHA:   SKILL_GACHA_IMG,
            SkillID.REVERSE: SKILL_REVERSE_IMG,
            SkillID.DEADZONE: SKILL_DEADZONE_IMG,
            SkillID.DEFENSE: SKILL_DEFENSE_IMG,
        }

        # Board area reference points
        board_center_x = BOARD_OFFSET_X + self._board_px_w // 2
        board_center_y = BOARD_OFFSET_Y + self._board_px_h // 2

        # Left skill panel (Black) — between window left edge and black avatar
        left_x = 80
        self._skill_panel_left = SkillPanel(
            center_x=left_x,
            center_y=board_center_y,
            icon_size=SKILL_ICON_SIZE,
            icon_spacing=16,
            owner_color=StoneColor.BLACK,
            icon_paths=icon_paths,
            on_use_skill=self._on_skill_activate,
        )

        # Right skill panel (White) — between white avatar and window right edge
        right_x = WINDOW_WIDTH - 80
        self._skill_panel_right = SkillPanel(
            center_x=right_x,
            center_y=board_center_y,
            icon_size=SKILL_ICON_SIZE,
            icon_spacing=16,
            owner_color=StoneColor.WHITE,
            icon_paths=icon_paths,
            on_use_skill=self._on_skill_activate,
        )

        # Visual effects
        self._skill_effects = SkillEffects(self.board_view)

        # Skill SFX
        self._skill_use_sound = None
        try:
            self._skill_use_sound = pygame.mixer.Sound(SKILL_USE_SOUND)
        except FileNotFoundError:
            pass

        # Create and activate skill mode
        self._active_mode = SkillMode(
            game_manager=self.gm,
            board_view=self.board_view,
            skill_manager=self._skill_mgr,
            panel_left=self._skill_panel_left,
            panel_right=self._skill_panel_right,
            effects=self._skill_effects,
            on_play_sfx=self._play_skill_sfx,
        )
        self._active_mode.on_enter()
        self._prev_move_count = 0
        self._last_black_move = None
        self._last_white_move = None
        self._screen = "game"

    def _on_open_history(self) -> None:
        self._screen = "history"
        self._current_screen = HistoryScreen(
            self.recorder,
            on_back=self._go_to_menu,
            on_replay=self._on_start_replay,
        )
        self._current_screen.on_enter()

    def _on_open_settings(self) -> None:
        self._screen = "settings"
        self._current_screen = SettingsScreen(
            on_back=self._go_to_menu,
            settings_mgr=self._settings_mgr,
            bgm_player=self._bgm,
            board_view=self.board_view,
            reload_background=self._reload_background,
        )

    def _on_start_replay(self, record_id: str) -> None:
        if self._replay_mode.load_record(record_id):
            self._screen = "replay"
            self._active_mode = None
            self._popup = None

    def _on_replay_done(self) -> None:
        self._on_open_history()

    def _on_quit_game(self) -> None:
        """Quit the entire application."""
        self.running = False

    def _reload_background(self, path: str) -> None:
        """Switch the background image to *path* (called from settings)."""
        bg = load_background(path)
        if bg:
            self._background = bg

    # ── Player info panels ──────────────────────────────

    @staticmethod
    def _load_avatar(path: str) -> pygame.Surface | None:
        """Load an avatar image and scale to AVATAR_SIZE."""
        try:
            img = pygame.image.load(path).convert_alpha()
            return pygame.transform.smoothscale(img, (AVATAR_SIZE, AVATAR_SIZE))
        except FileNotFoundError:
            return None

    @staticmethod
    def _load_deepseek_girl() -> pygame.Surface | None:
        """Load the DeepSeek girl character image, scale to fit the right panel."""
        try:
            img = pygame.image.load(DEEPSEEK_GIRL_IMG).convert_alpha()
            # Scale to fill the right side space, keeping aspect ratio
            board_right = BOARD_OFFSET_X + MARGIN * 2 + (BOARD_SIZE - 1) * CELL_SIZE
            max_w = WINDOW_WIDTH - board_right - 30   # available right-side width
            board_px_h = MARGIN * 2 + (BOARD_SIZE - 1) * CELL_SIZE
            max_h = board_px_h                         # match board height
            # Scale so both dimensions fit
            ratio = min(max_w / img.get_width(), max_h / img.get_height())
            target_w = int(img.get_width() * ratio)
            target_h = int(img.get_height() * ratio)
            return pygame.transform.smoothscale(img, (target_w, target_h))
        except FileNotFoundError:
            return None

    def _update_last_move(self) -> None:
        """Read the last stone from the board and record which color moved."""
        stone = self.gm.board.last_move()
        if stone is None:
            return
        if stone.color == StoneColor.BLACK:
            self._last_black_move = (stone.row, stone.col)
        else:
            self._last_white_move = (stone.row, stone.col)

    def _draw_player_panels(self) -> None:
        """Draw black (left) and white (right) player info panels beside the board."""
        font_name = get_font(28)
        font_pos  = get_font(24)
        font_turn = get_font(26)

        board_left   = BOARD_OFFSET_X
        board_top    = BOARD_OFFSET_Y
        board_right  = BOARD_OFFSET_X + self._board_px_w
        board_bottom = BOARD_OFFSET_Y + self._board_px_h

        c_white = (255, 255, 255)
        c_gold  = (255, 215, 0)
        c_gray  = (200, 200, 200)
        gap     = 15   # gap between avatar and board edge

        # ── Black panel (left side) ──────────────────────
        if self._black_avatar:
            ax = board_left - AVATAR_SIZE - gap
            ay = board_top + 25
            self.screen.blit(self._black_avatar, (ax, ay))

        # Determine player names for AI mode
        is_ai_mode = isinstance(self._active_mode, AIVsMode)
        if is_ai_mode:
            ai_mode = self._active_mode
            black_name = "智能AI" if ai_mode.ai_color == StoneColor.BLACK else "玩家"
            white_name = "智能AI" if ai_mode.ai_color == StoneColor.WHITE else "玩家"
        else:
            black_name = "玩家1"
            white_name = "玩家2"

        # Text left-aligned, grows downward from below the avatar
        black_lines = []
        black_lines.append((black_name, font_name, c_white))
        if self._last_black_move:
            label = pos_to_label(self._last_black_move[0], self._last_black_move[1])
            black_lines.append((f"落子: {label}", font_pos, c_gray))
        else:
            black_lines.append(("落子: -", font_pos, c_gray))
        if self.gm.state == GameState.PLAYING and self.gm.current_turn == StoneColor.BLACK:
            turn_text = "轮到你了" if (not is_ai_mode or ai_mode.human_color == StoneColor.BLACK) else "AI思考中..."
            turn_color = c_gold if (not is_ai_mode or ai_mode.human_color == StoneColor.BLACK) else (100, 200, 255)
            black_lines.append((turn_text, font_turn, turn_color))

        tx = board_left - AVATAR_SIZE - gap  # left edge, aligned with avatar
        ty = board_top + 25 + AVATAR_SIZE + 18  # just below avatar
        self._draw_text_block(black_lines, tx, ty, grow="down")

        # ── White panel (right side) ─────────────────────
        if self._white_avatar:
            ax = board_right + gap
            ay = board_bottom - 25 - AVATAR_SIZE
            self.screen.blit(self._white_avatar, (ax, ay))

        # Text left-aligned, grows upward from above the avatar
        white_lines = []
        if self.gm.state == GameState.PLAYING and self.gm.current_turn == StoneColor.WHITE:
            turn_text = "轮到你了" if (not is_ai_mode or ai_mode.human_color == StoneColor.WHITE) else "AI思考中..."
            turn_color = c_gold if (not is_ai_mode or ai_mode.human_color == StoneColor.WHITE) else (100, 200, 255)
            white_lines.append((turn_text, font_turn, turn_color))
        if self._last_white_move:
            label = pos_to_label(self._last_white_move[0], self._last_white_move[1])
            white_lines.append((f"落子: {label}", font_pos, c_gray))
        else:
            white_lines.append(("落子: -", font_pos, c_gray))
        white_lines.append((white_name, font_name, c_white))

        tx = board_right + gap  # left edge, aligned with avatar
        ty = board_bottom - 25 - AVATAR_SIZE - 18  # just above avatar — bottom of text block
        self._draw_text_block(white_lines, tx, ty, grow="up")

    def _draw_text_block(
        self, lines: list[tuple[str, pygame.font.Font, tuple]],
        anchor_x: int, anchor_y: int, *, grow: str
    ) -> None:
        """
        Draw a left-aligned block of text lines with a semi-transparent
        black backdrop.

        *lines*:   list of (text, font, color)
        *anchor_x*: left edge of the text block
        *anchor_y*: top edge (grow="down") or bottom edge (grow="up")
        *grow*:    "down" → text grows downward from anchor_y
                   "up"   → text grows upward (ends at anchor_y)
        """
        if not lines:
            return

        # Measure all lines
        surfs = []
        max_w = 0
        total_h = 0
        for text, font, color in lines:
            s = font.render(text, True, color)
            surfs.append(s)
            if s.get_width() > max_w:
                max_w = s.get_width()
            total_h += s.get_height()
        gaps_h = max(0, len(surfs) - 1) * 6
        total_h += gaps_h
        pad = 10

        bg_w = max_w + pad * 2
        bg_h = total_h + pad * 2

        if grow == "up":
            bg_y = anchor_y - bg_h
            text_start_y = anchor_y - total_h - pad
        else:
            bg_y = anchor_y - pad
            text_start_y = anchor_y

        bg_x = anchor_x - pad
        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        self.screen.blit(bg, (bg_x, bg_y))

        # Draw text lines
        y = text_start_y
        for s in surfs:
            self.screen.blit(s, (anchor_x, y))
            y += s.get_height() + 6
