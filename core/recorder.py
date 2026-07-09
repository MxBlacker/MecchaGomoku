"""
GameRecorder — saves and loads game records as JSON files for replay.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from core.stone import StoneColor
from config import RECORDS_DIR


@dataclass
class GameRecord:
    """All data needed to replay a single game."""

    id: str                                    # e.g. "20260708_143000"
    mode: str                                  # "pvp" | "ai" | "network" | "skill"
    board_size: int = 15
    created_at: str = ""                       # ISO timestamp
    players: dict[str, str] = field(default_factory=dict)   # {"black": "…", "white": "…"}
    winner: Optional[str] = None               # "BLACK" | "WHITE" | None (draw)
    win_reason: Optional[str] = None           # "五连" | "三三禁手" | "四四禁手" | "长连禁手" | "平局"
    moves: list[dict] = field(default_factory=list)  # [{"row":7,"col":7,"color":"BLACK"}, …]

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat(timespec="seconds")
        if not self.id:
            self.id = datetime.now().strftime("%Y%m%d_%H%M%S")

    @property
    def move_count(self) -> int:
        return len(self.moves)

    def total_stones(self) -> int:
        return len(self.moves)


class GameRecorder:
    """
    Manages JSON-based game records on disk.

    Usage:
        rec = GameRecorder()
        rec.start_record(mode="pvp", black_name="Alice", white_name="Bob")
        rec.add_move(7, 7, StoneColor.BLACK)
        rec.add_move(7, 8, StoneColor.WHITE)
        rec.finish(winner=StoneColor.BLACK)
    """

    def __init__(self, records_dir: str = RECORDS_DIR):
        self.records_dir = records_dir
        os.makedirs(self.records_dir, exist_ok=True)
        self._current: Optional[GameRecord] = None

    # ── Recording lifecycle ──────────────────────────────

    def start_record(
        self,
        mode: str,
        board_size: int = 15,
        black_name: str = "Player 1",
        white_name: str = "Player 2",
    ) -> GameRecord:
        """Begin a new record. Called when a game starts."""
        record = GameRecord(
            id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            mode=mode,
            board_size=board_size,
            players={"black": black_name, "white": white_name},
        )
        self._current = record
        return record

    def add_move(self, row: int, col: int, color: StoneColor) -> None:
        """Record a stone placement."""
        if self._current is None:
            return
        self._current.moves.append({
            "row": row,
            "col": col,
            "color": color.name,
        })

    def add_undo(self, color: StoneColor) -> None:
        """Record an undo (悔棋) action."""
        if self._current is None:
            return
        self._current.moves.append({
            "action": "undo",
            "color": color.name,
        })

    def finish(self, winner: Optional[StoneColor], win_reason: Optional[str] = None) -> Optional[str]:
        """Save the completed record to disk. Returns the file path."""
        if self._current is None:
            return None
        self._current.winner = winner.name if winner else None
        self._current.win_reason = win_reason
        return self._save(self._current)

    def cancel(self) -> None:
        """Discard the current in-progress record."""
        self._current = None

    @property
    def current_record(self) -> Optional[GameRecord]:
        return self._current

    # ── Persistence ──────────────────────────────────────

    def _save(self, record: GameRecord) -> str:
        path = self._path_for(record.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(record), f, ensure_ascii=False, indent=2)
        return path

    def load(self, record_id: str) -> Optional[GameRecord]:
        """Load a single record by ID."""
        path = self._path_for(record_id)
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return GameRecord(**data)

    def list_records(self) -> list[GameRecord]:
        """Return all saved records sorted newest-first."""
        records = []
        if not os.path.isdir(self.records_dir):
            return records
        for filename in sorted(os.listdir(self.records_dir), reverse=True):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.records_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records.append(GameRecord(**data))
            except (json.JSONDecodeError, TypeError):
                continue  # skip corrupted files
        return records

    def delete(self, record_id: str) -> bool:
        """Delete a record file. Returns True on success."""
        path = self._path_for(record_id)
        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            return False

    # ── Helpers ──────────────────────────────────────────

    def _path_for(self, record_id: str) -> str:
        return os.path.join(self.records_dir, f"{record_id}.json")
