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
    BLACK_AVATAR_IMG, WHITE_AVATAR_IMG, AVATAR_SIZE,
)
from core.game_manager import GameManager, GameState
from core.stone import StoneColor
from core.recorder import GameRecorder
from ui.board_view import BoardView
from ui.menu import MainMenu
from ui.settings_screen import SettingsScreen
from ui.history_screen import HistoryScreen
from ui.popup import Popup, WaitingPopup
from ui.widgets import ImageButton
from modes.local_pvp import LocalPvPMode
from modes.ai_mode import AIVsMode
from modes.replay_mode import ReplayMode
from modes.network.multiplayer_mode import MultiplayerMode
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

        # Replay mode (reused)
        self._replay_mode = ReplayMode(self.gm, self.board_view, self.recorder)
        self._replay_mode._on_done = self._on_replay_done

        # Popup (created when game ends)
        self._popup: Optional[Popup] = None

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

        # Player info panels (avatars + move history)
        self._draw_player_panels()

        # Hover ghost stone preview (PvP and multiplayer)
        if (self._active_mode
                and hasattr(self._active_mode, "hover_pos")
                and self._active_mode.hover_pos is not None
                and self.gm.state == GameState.PLAYING):
            r, c = self._active_mode.hover_pos
            self.board_view.draw_hover_preview(self.screen, r, c, self.gm.current_turn)

        self._draw_status_bar()

    def _draw_replay_content(self) -> None:
        self.board_view.draw(self.screen, self.gm.board)

        rm = self._replay_mode
        font = get_font(22)
        info = f"复盘  {rm.move_index}/{rm.total_moves}  "
        if rm.is_playing:
            info += "▶ 自动播放中"
        else:
            info += "← → 步进  |  SPACE 自动  |  ESC 返回"
        text = font.render(info, True, COLOR_TEXT)
        self.screen.blit(text, (WINDOW_WIDTH // 2 - text.get_width() // 2, WINDOW_HEIGHT - 76))

        # Show current move detail
        if rm.total_moves > 0 and 1 <= rm.move_index <= rm.total_moves:
            move = rm.record.moves[rm.move_index - 1]
            if move.get("action") == "undo":
                color_name = "● 黑方" if move["color"] == "BLACK" else "○ 白方"
                detail = f"{color_name} 悔棋一步"
            else:
                color_name = "● 黑方" if move["color"] == "BLACK" else "○ 白方"
                detail = f"{color_name} → ({move['row']}, {move['col']})"
            dtext = get_font(18).render(detail, True, (200, 200, 220))
            self.screen.blit(dtext, (WINDOW_WIDTH // 2 - dtext.get_width() // 2, WINDOW_HEIGHT - 50))

        if rm.move_index == rm.total_moves and rm.total_moves > 0:
            winner = rm.record.winner
            if winner:
                badge = f"胜者: {'● 黑方' if winner == 'BLACK' else '○ 白方'}"
                # Annotate win reason if present in the record
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
            btext = font.render(badge, True, (255, 215, 0))
            self.screen.blit(btext, (20, WINDOW_HEIGHT - 50))

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

    def _on_start_ai(self) -> None:
        self.gm.game_mode = "ai"
        self._active_mode = AIVsMode(self.gm, self.board_view)
        self._active_mode.on_enter()
        self._prev_move_count = 0
        self._last_black_move = None
        self._last_white_move = None
        self._screen = "game"

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
        self.gm.game_mode = "skill"
        self._active_mode = LocalPvPMode(self.gm, self.board_view)
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

        # Text left-aligned, grows downward from below the avatar
        black_lines = []
        black_lines.append(("玩家1", font_name, c_white))
        if self._last_black_move:
            black_lines.append(
                (f"落子: ({self._last_black_move[0]}, {self._last_black_move[1]})", font_pos, c_gray)
            )
        else:
            black_lines.append(("落子: -", font_pos, c_gray))
        if self.gm.state == GameState.PLAYING and self.gm.current_turn == StoneColor.BLACK:
            black_lines.append(("轮到你了", font_turn, c_gold))

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
            white_lines.append(("轮到你了", font_turn, c_gold))
        if self._last_white_move:
            white_lines.append(
                (f"落子: ({self._last_white_move[0]}, {self._last_white_move[1]})", font_pos, c_gray)
            )
        else:
            white_lines.append(("落子: -", font_pos, c_gray))
        white_lines.append(("玩家2", font_name, c_white))

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
