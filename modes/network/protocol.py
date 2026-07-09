"""
Communication protocol — message types and serialization for network play.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


class MessageType(Enum):
    """All message types exchanged between server and client."""
    # Connection
    JOIN       = "join"        # client → server: join a room
    JOINED     = "joined"      # server → client: join confirmed (assigns color)
    LEAVE      = "leave"
    ERROR      = "error"

    # Game
    MOVE       = "move"        # client → server, server → opponent
    BOARD_SYNC = "board_sync"  # server → clients: full board state
    GAME_START = "game_start"  # server → clients: game begins
    GAME_OVER  = "game_over"   # server → clients: winner declared
    CHAT       = "chat"        # optional chat messages

    # Room
    ROOM_LIST  = "room_list"
    PLAYER_LEFT = "player_left"


@dataclass
class Message:
    """A structured network message."""
    type: str          # MessageType value
    payload: dict[str, Any] = None

    def __post_init__(self):
        if self.payload is None:
            self.payload = {}

    def encode(self) -> bytes:
        """Serialize to JSON bytes, prefixed with length."""
        body = json.dumps({"type": self.type, "payload": self.payload})
        header = f"{len(body):08d}"
        return (header + body).encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> "Message":
        """Deserialize from bytes. Expects length-prefixed JSON."""
        text = data.decode("utf-8")
        header = text[:8]
        body = text[8 : 8 + int(header)]
        obj = json.loads(body)
        return Message(type=obj["type"], payload=obj.get("payload", {}))
