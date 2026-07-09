"""
Game client — connects to a remote GameServer for LAN play.
"""

from __future__ import annotations

import socket
import threading
from typing import Optional

from config import DEFAULT_PORT, BUFFER_SIZE
from core.stone import StoneColor
from modes.network.protocol import Message, MessageType
from utils.logger import setup_logger

logger = setup_logger("gomoku.client")


class GameClient:
    """
    Connects to a GameServer, sends local moves, and receives opponent moves.

    Usage:
        client = GameClient()
        client.connect("192.168.1.100")
        client.send_move(row, col)
        # Poll client.incoming_moves or register a callback
    """

    def __init__(self):
        self._socket: Optional[socket.socket] = None
        self._running = False
        self.assigned_color: Optional[StoneColor] = None

        # Incoming message queue (thread-safe via GIL for simple lists)
        self.incoming_moves: list[tuple[int, int, StoneColor]] = []
        self.game_events: list[Message] = []

    # ── Connection ──────────────────────────────────────

    def connect(self, host: str, port: int = DEFAULT_PORT) -> bool:
        """Connect to the server. Returns True on success."""
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.connect((host, port))
            self._running = True

            # Start listener
            t = threading.Thread(target=self._listen, daemon=True)
            t.start()

            logger.info(f"Connected to {host}:{port}")
            return True
        except (ConnectionError, OSError) as e:
            logger.error(f"Connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Gracefully disconnect."""
        self._running = False
        if self._socket:
            try:
                self._send(Message(MessageType.LEAVE.value))
                self._socket.close()
            except (ConnectionError, OSError):
                pass

    # ── Game actions ────────────────────────────────────

    def send_move(self, row: int, col: int) -> None:
        """Send a move to the server."""
        msg = Message(MessageType.MOVE.value, {"row": row, "col": col})
        self._send(msg)

    def send_chat(self, text: str) -> None:
        """Send a chat message."""
        msg = Message(MessageType.CHAT.value, {"text": text})
        self._send(msg)

    # ── Internal ────────────────────────────────────────

    def _listen(self) -> None:
        """Background thread: read messages from the server."""
        try:
            while self._running and self._socket:
                data = self._socket.recv(BUFFER_SIZE)
                if not data:
                    break
                msg = Message.decode(data)
                self._handle_message(msg)
        except (ConnectionError, OSError) as e:
            logger.info(f"Disconnected: {e}")
        finally:
            self._running = False

    def _handle_message(self, msg: Message) -> None:
        """Process an incoming message."""
        if msg.type == MessageType.JOINED.value:
            color_name = msg.payload["color"]
            self.assigned_color = StoneColor[color_name]
            logger.info(f"Assigned color: {self.assigned_color}")

        elif msg.type == MessageType.MOVE.value:
            row, col = msg.payload["row"], msg.payload["col"]
            color = StoneColor[msg.payload["color"]]
            self.incoming_moves.append((row, col, color))

        elif msg.type in (MessageType.GAME_OVER.value, MessageType.GAME_START.value,
                          MessageType.PLAYER_LEFT.value, MessageType.ERROR.value):
            self.game_events.append(msg)

    def _send(self, msg: Message) -> None:
        """Send a message to the server."""
        if self._socket:
            try:
                self._socket.sendall(msg.encode())
            except (ConnectionError, OSError):
                pass
