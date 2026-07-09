"""
Network multiplayer mode — host runs a server, guest joins via browser.
"""

from __future__ import annotations

import pygame

from core.game_manager import GameManager, GameState
from core.stone import StoneColor
from modes.base_mode import BaseMode
from modes.network.multiplayer_server import MultiplayerServer
from ui.board_view import BoardView


class MultiplayerMode(BaseMode):
    """
    B/S multiplayer: Pygame host (this process) vs Browser guest.

    Flow:
      1. on_enter() → start server, show waiting popup.
      2. Guest connects → colors assigned → game starts → popup dismissed.
      3. Host moves → gm.place_stone() + server.host_place_stone().
      4. Guest moves → received via poll_events() → gm.place_stone().
      5. Game over → popup with reason.
    """

    def __init__(self, game_manager: GameManager, board_view: BoardView):
        super().__init__(game_manager)
        self.board_view = board_view
        self._server: MultiplayerServer | None = None
        self._my_color: StoneColor | None = None
        self._url: str = ""
        self._waiting = True
        self._error: str | None = None
        self._popup_dismissed = False
        self.hover_pos: tuple[int, int] | None = None

        # Callbacks set by renderer
        self._show_waiting_popup = None   # fn(url, on_cancel)
        self._dismiss_waiting = None      # fn()
        self._show_result_popup = None    # fn(message, on_dismiss)

    # ── Lifecycle ────────────────────────────────────────

    def on_enter(self) -> None:
        self._my_color = None
        self._waiting = True
        self._error = None
        self._popup_dismissed = False

        # Start server
        self._server = MultiplayerServer()
        try:
            self._url = self._server.start()
        except OSError as e:
            self._error = f"服务器启动失败: {e}"
            return

        # Show waiting popup
        if self._show_waiting_popup:
            self._show_waiting_popup(self._url, self._on_cancel_waiting)

    def on_exit(self) -> None:
        if self._server:
            self._server.stop()
            self._server = None
        if self._dismiss_waiting:
            self._dismiss_waiting()

    # ── Events ───────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._waiting or self._error:
            return
        if self.gm.state != GameState.PLAYING:
            return

        # Only allow input on our turn
        if self._my_color is None or self.gm.current_turn != self._my_color:
            return

        if event.type == pygame.MOUSEMOTION:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                r, c = pos
                if self.gm.board.is_empty(r, c):
                    self.hover_pos = pos
                    return
            self.hover_pos = None

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = self.board_view.pixel_to_grid(*event.pos)
            if pos is not None:
                row, col = pos
                if self.gm.place_stone(row, col):
                    self.hover_pos = None
                    # Send to the browser guest
                    if self._server:
                        self._server.host_place_stone(row, col)

    def update(self) -> None:
        """Poll server events each frame."""
        if self._server is None:
            return

        # If server failed to start, show error and bail out
        if self._error:
            if self._show_result_popup:
                self._show_result_popup(f"服务器启动失败\n{self._error}")
            self._error = None  # only show once
            return

        for evt in self._server.poll_events():
            self._handle_server_event(evt)

    # ── Server event handling ────────────────────────────

    def _handle_server_event(self, evt: dict) -> None:
        etype = evt.get("type")

        if etype == "color_assign":
            color_name = evt["color"]
            self._my_color = StoneColor[color_name]

        elif etype == "game_start":
            self._waiting = False
            self.gm.new_game()
            # Dismiss the waiting popup
            if self._dismiss_waiting:
                self._dismiss_waiting()

        elif etype == "opponent_move":
            row, col = evt["row"], evt["col"]
            self.gm.place_stone(row, col)

        elif etype == "game_over":
            winner_name = evt.get("winner")
            reason = evt.get("reason", "")
            self._show_game_over(winner_name, reason)

        elif etype == "opponent_disconnected":
            self._show_game_over(None, "对手断开连接")

        elif etype == "error":
            self._error = evt.get("message", "未知错误")

    def _show_game_over(self, winner_name: str | None, reason: str) -> None:
        """Build and show the game-over popup via renderer callback."""
        if winner_name:
            color_name = "● 黑方" if winner_name == "BLACK" else "○ 白方"
            message = f"{color_name} 获胜！"
            if reason and reason != "五连":
                reason_label = {
                    "三三禁手": "黑方三三禁手",
                    "四四禁手": "黑方四四禁手",
                    "长连禁手": "黑方长连禁手",
                }.get(reason, reason)
                message += f"\n{reason_label}"
            elif reason == "五连":
                message += "\n"
            else:
                message += f"\n{reason}"
        else:
            message = "对手断开连接，你赢了！" if reason == "对手断开连接" else f"游戏结束\n{reason}"

        if self._show_result_popup:
            self._show_result_popup(message)

    # ── Callbacks ────────────────────────────────────────

    def _on_cancel_waiting(self) -> None:
        """User clicked cancel on the waiting popup."""
        if self._server:
            self._server.stop()
            self._server = None
        self._waiting = False
        self._error = "已取消"
