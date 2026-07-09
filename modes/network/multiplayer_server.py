"""
Multiplayer game server — HTTP + WebSocket for B/S LAN play.

The Pygame host runs this server in a background thread.
A browser guest connects via WebSocket, and the server relays
moves between both players.

Communication:
  - Host (Pygame)  ← queue.Queue → server ← WebSocket → Guest (Browser)
  - Random black/white assignment
  - Move validation + forbidden-move (禁手) detection
  - Disconnection handling
"""

from __future__ import annotations

import asyncio
import json
import os
import queue
import random
import socket
import threading
from typing import Optional

import websockets
from websockets.asyncio.server import serve
from websockets.http11 import Response
from websockets.datastructures import Headers

from core.board import Board
from core.stone import StoneColor
from core.rules import check_win, check_forbidden, is_board_full

# Path to the web client HTML
_WEB_DIR = os.path.join(os.path.dirname(__file__), "web")
_HTML_PATH = os.path.join(_WEB_DIR, "index.html")

# Cached HTML content
_html_content: str | None = None


def _get_html() -> str:
    """Load the web client HTML (cached)."""
    global _html_content
    if _html_content is None:
        try:
            with open(_HTML_PATH, "r", encoding="utf-8") as f:
                _html_content = f.read()
        except FileNotFoundError:
            _html_content = "<h1>Game page not found</h1>"
    return _html_content


def get_lan_ip() -> str:
    """Return the LAN IP address of this machine."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class MultiplayerServer:
    """
    B/S multiplayer server.

    Usage from the Pygame host:
        server = MultiplayerServer()
        url = server.start()  # → "http://192.168.1.5:8765"

        # In game loop:
        for event in server.poll_events():
            if event["type"] == "opponent_move":
                gm.place_stone(event["row"], event["col"])
            elif event["type"] == "game_over":
                ...

        # When host places a stone:
        server.host_place_stone(row, col)
    """

    def __init__(self, port: int = 8765):
        self.port = port
        self._board = Board()
        self._host_color: Optional[StoneColor] = None
        self._guest_color: Optional[StoneColor] = None
        self._current_turn: StoneColor = StoneColor.BLACK
        self._host_queue: queue.Queue = queue.Queue()
        self._guest_ws = None
        self._game_started = False
        self._game_over = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._host_last_move: tuple[int, int] | None = None
        self._guest_last_move: tuple[int, int] | None = None

    # ── Public API (called from Pygame main thread) ─────

    def start(self) -> str:
        """Start the server in a daemon thread. Returns the LAN URL."""
        self._running = True
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()
        ip = get_lan_ip()
        return f"http://{ip}:{self.port}"

    def stop(self) -> None:
        """Shut down the server."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._shutdown_loop)

    def _shutdown_loop(self) -> None:
        """Cancel all pending tasks and stop the loop (must run in loop thread)."""
        for task in asyncio.all_tasks(self._loop):
            task.cancel()

    def host_place_stone(self, row: int, col: int) -> bool:
        """
        Called by the Pygame host when they place a stone.
        Returns True if the move is accepted.
        """
        if not self._game_started or self._game_over:
            return False
        if self._host_color is None or self._current_turn != self._host_color:
            return False
        if not self._board.place_stone(row, col, self._host_color):
            return False

        self._host_last_move = (row, col)

        # Always send the move to the guest first (so they see the stone)
        self._send_to_guest({"type": "move", "row": row, "col": col,
                             "color": self._host_color.name})

        # Check five-in-a-row first
        if check_win(self._board, row, col):
            self._end_game(self._host_color, "五连")
            return True

        # Forbidden-move check for black
        if self._host_color == StoneColor.BLACK:
            is_forbidden, reason = check_forbidden(self._board, row, col)
            if is_forbidden:
                self._end_game(StoneColor.WHITE, reason)
                return True

        # Draw check
        if is_board_full(self._board):
            self._end_game(None, "平局")
            return True

        # Switch turn
        self._current_turn = self._current_turn.opponent()
        return True

    def poll_events(self) -> list[dict]:
        """
        Drain and return all pending events for the Pygame host.
        Called once per frame.
        """
        events = []
        while not self._host_queue.empty():
            try:
                events.append(self._host_queue.get_nowait())
            except queue.Empty:
                break
        return events

    @property
    def host_color(self) -> Optional[StoneColor]:
        return self._host_color

    @property
    def game_started(self) -> bool:
        return self._game_started

    # ── Game logic ───────────────────────────────────────

    def _end_game(self, winner: Optional[StoneColor], reason: str) -> None:
        """Declare game over and notify both sides."""
        self._game_over = True
        self._game_started = False
        winner_name = winner.name if winner else None
        payload = {"type": "game_over", "winner": winner_name, "reason": reason}

        # Notify guest via WebSocket
        self._send_to_guest(payload)

        # Notify host via queue
        self._host_queue.put(payload)

    # ── WebSocket / HTTP server (runs in asyncio thread) ─

    def _run_async_loop(self) -> None:
        """Entry point for the background thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            loop.run_until_complete(self._serve())
        except (OSError, asyncio.CancelledError, RuntimeError):
            pass
        finally:
            loop.close()

    async def _serve(self) -> None:
        """Start the HTTP + WS server."""
        try:
            async with serve(
                self._ws_handler,
                "0.0.0.0",
                self.port,
                process_request=self._http_handler,
            ):
                await asyncio.get_event_loop().create_future()  # run forever
        except (asyncio.CancelledError, GeneratorExit):
            pass  # expected on shutdown

    def _http_handler(self, connection, request):
        """
        Serve the web client HTML for `/`, and let `/ws` pass through
        for WebSocket upgrade. Returns None for WebSocket paths.
        """
        if request.path == "/" or request.path == "/index.html":
            html = _get_html()
            html_bytes = html.encode("utf-8")
            headers = Headers()
            headers["Content-Type"] = "text/html; charset=utf-8"
            headers["Content-Length"] = str(len(html_bytes))
            return Response(200, "OK", headers, html_bytes)
        # Return None for WebSocket paths — lets the upgrade proceed
        if request.path == "/ws":
            return None
        return Response(404, "Not Found", Headers(), b"")

    async def _ws_handler(self, websocket) -> None:
        """Handle a WebSocket connection (the browser guest)."""
        if self._guest_ws is not None:
            # Only one guest allowed
            await websocket.send(json.dumps({
                "type": "error", "message": "房间已满"
            }))
            await websocket.close()
            return

        self._guest_ws = websocket

        # Randomly assign colors
        if random.random() < 0.5:
            self._host_color = StoneColor.BLACK
            self._guest_color = StoneColor.WHITE
        else:
            self._host_color = StoneColor.WHITE
            self._guest_color = StoneColor.BLACK

        # Notify both sides
        await websocket.send(json.dumps({
            "type": "color_assign", "color": self._guest_color.name,
        }))
        self._host_queue.put({
            "type": "color_assign", "color": self._host_color.name,
        })

        # Wait for guest's "ready" message
        try:
            raw = await asyncio.wait_for(websocket.recv(), timeout=60)
            msg = json.loads(raw)
            if msg.get("type") != "ready":
                await websocket.close()
                self._guest_ws = None
                return
        except (asyncio.TimeoutError, json.JSONDecodeError):
            self._guest_ws = None
            self._host_queue.put({"type": "error", "message": "对手连接超时"})
            return

        # Start the game
        self._game_started = True
        start_msg = json.dumps({
            "type": "game_start", "current_turn": "BLACK",
        })
        await websocket.send(start_msg)
        self._host_queue.put({"type": "game_start", "current_turn": "BLACK"})

        # Listen for guest moves
        try:
            async for raw in websocket:
                if self._game_over:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "move":
                    await self._process_guest_move(msg, websocket)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            if self._guest_ws is websocket:
                self._guest_ws = None
            if not self._game_over:
                self._host_queue.put({"type": "opponent_disconnected"})

    async def _process_guest_move(self, msg: dict, websocket) -> None:
        """Validate and apply a move from the browser guest."""
        if not self._game_started or self._game_over:
            return
        if self._guest_color is None or self._current_turn != self._guest_color:
            await websocket.send(json.dumps({
                "type": "error", "message": "还没轮到你"
            }))
            return

        row = msg.get("row")
        col = msg.get("col")
        if row is None or col is None:
            return

        if not self._board.place_stone(row, col, self._guest_color):
            await websocket.send(json.dumps({
                "type": "error", "message": "此处不能落子"
            }))
            return

        self._guest_last_move = (row, col)

        # Always notify the host of the move first (so they see the stone)
        self._host_queue.put({
            "type": "opponent_move", "row": row, "col": col,
            "color": self._guest_color.name,
        })

        # Check five-in-a-row first
        if check_win(self._board, row, col):
            self._end_game(self._guest_color, "五连")
            return

        # Forbidden-move check for black
        if self._guest_color == StoneColor.BLACK:
            is_forbidden, reason = check_forbidden(self._board, row, col)
            if is_forbidden:
                self._end_game(StoneColor.WHITE, reason)
                return

        # Draw check
        if is_board_full(self._board):
            self._end_game(None, "平局")
            return

        # Switch turn
        self._current_turn = self._current_turn.opponent()

    def _send_to_guest(self, payload: dict) -> None:
        """Enqueue a message to be sent to the browser guest."""
        if self._guest_ws and self._loop and self._loop.is_running():
            data = json.dumps(payload)
            self._loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._safe_send(data))
            )

    async def _safe_send(self, data: str) -> None:
        """Send to guest, ignoring connection errors."""
        if self._guest_ws:
            try:
                await self._guest_ws.send(data)
            except websockets.exceptions.ConnectionClosed:
                self._guest_ws = None
