"""
Game server — hosts a LAN room and relays moves between clients.
Uses HTTP for setup and WebSocket for real-time game messages.
"""

from __future__ import annotations

import socket
import threading
from typing import Optional

from config import DEFAULT_HOST, DEFAULT_PORT, BUFFER_SIZE
from modes.network.protocol import Message, MessageType
from core.board import Board
from core.stone import StoneColor
from core.rules import check_win, is_board_full
from utils.logger import setup_logger

logger = setup_logger("gomoku.server")


class GameServer:
    """
    A lightweight TCP server for LAN Gomoku.

    Architecture:
    - One server, one room (for simplicity — can be extended to multi-room).
    - Exactly 2 players per room: Black (host / first to join) and White (second).
    - The server is authoritative for game rules.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._socket: Optional[socket.socket] = None
        self._clients: dict[socket.socket, StoneColor] = {}  # socket → assigned color
        self._board = Board()
        self._current_turn = StoneColor.BLACK
        self._running = False

    # ── Lifecycle ───────────────────────────────────────

    def start(self) -> None:
        """Start listening for connections (blocking — run in a thread)."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.listen(2)
        self._running = True
        logger.info(f"Server listening on {self.host}:{self.port}")

        try:
            while self._running and len(self._clients) < 2:
                conn, addr = self._socket.accept()
                logger.info(f"Connection from {addr}")

                # Assign color
                if len(self._clients) == 0:
                    color = StoneColor.BLACK
                else:
                    color = StoneColor.WHITE
                self._clients[conn] = color

                # Send join confirmation
                msg = Message(MessageType.JOINED.value, {"color": color.name})
                self._send(conn, msg)

                # Start listener thread
                t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                t.start()

                # If two players connected, start the game
                if len(self._clients) == 2:
                    self._broadcast(Message(MessageType.GAME_START.value, {
                        "board_size": self._board.size,
                        "current_turn": "BLACK",
                    }))

        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            self.stop()

    def stop(self) -> None:
        """Shut down the server."""
        self._running = False
        for conn in list(self._clients):
            conn.close()
        if self._socket:
            self._socket.close()
        logger.info("Server stopped.")

    # ── Client handling ─────────────────────────────────

    def _handle_client(self, conn: socket.socket) -> None:
        """Read messages from a single client."""
        color = self._clients.get(conn)
        try:
            while self._running:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break
                msg = Message.decode(data)
                self._process_message(conn, msg, color)
        except (ConnectionError, OSError) as e:
            logger.info(f"Client {color} disconnected: {e}")
        finally:
            if conn in self._clients:
                del self._clients[conn]
                self._broadcast(Message(MessageType.PLAYER_LEFT.value, {
                    "color": color.name if color else "UNKNOWN",
                }))

    def _process_message(self, conn: socket.socket, msg: Message, color: StoneColor) -> None:
        """Handle an incoming game message."""
        if msg.type == MessageType.MOVE.value:
            # Only the current-turn player can move
            if color != self._current_turn:
                self._send(conn, Message(MessageType.ERROR.value, {"reason": "Not your turn"}))
                return

            row = msg.payload["row"]
            col = msg.payload["col"]

            if not self._board.place_stone(row, col, color):
                self._send(conn, Message(MessageType.ERROR.value, {"reason": "Invalid move"}))
                return

            # Broadcast the move
            self._broadcast(Message(MessageType.MOVE.value, {
                "row": row, "col": col, "color": color.name,
            }))

            # Check win / draw
            if check_win(self._board, row, col):
                self._broadcast(Message(MessageType.GAME_OVER.value, {
                    "winner": color.name,
                }))
                self._board.reset()
                self._current_turn = StoneColor.BLACK
            elif is_board_full(self._board):
                self._broadcast(Message(MessageType.GAME_OVER.value, {"winner": None}))
                self._board.reset()
                self._current_turn = StoneColor.BLACK
            else:
                self._current_turn = self._current_turn.opponent()

        elif msg.type == MessageType.CHAT.value:
            self._broadcast(msg, exclude=conn)

        elif msg.type == MessageType.LEAVE.value:
            if conn in self._clients:
                del self._clients[conn]
            conn.close()

    # ── Messaging ───────────────────────────────────────

    def _send(self, conn: socket.socket, msg: Message) -> None:
        """Send a message to one client."""
        try:
            conn.sendall(msg.encode())
        except (ConnectionError, OSError):
            pass

    def _broadcast(self, msg: Message, exclude: socket.socket | None = None) -> None:
        """Send a message to all connected clients (optionally excluding one)."""
        for conn in list(self._clients):
            if conn != exclude:
                self._send(conn, msg)
