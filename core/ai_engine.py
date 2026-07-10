"""
Rapfi AI Engine Wrapper — subprocess via Piskvork protocol.
Uses BOARD command to set up position, then BEGIN for AI move.
Protocol ref: TURN/response use comma format "X,Y".
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from typing import Optional

from core.stone import StoneColor


_AI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AI", "Rapfi-YixinBoard")
_ENGINE_EXE = os.path.join(_AI_DIR, "engine.exe")
_CONFIG_PATH = os.path.join(_AI_DIR, "config_piskvork.toml")

THINK_TIMEOUT = 15.0  # max seconds to wait for engine response
TURN_TIMEOUT = 10000  # milliseconds per move


class RapfiEngine:
    """Manages Rapfi engine subprocess for human-vs-AI play."""

    def __init__(self):
        self._board_size = 15
        self._ai_color: StoneColor = StoneColor.BLACK
        self._proc: Optional[subprocess.Popen] = None
        self._lines: list[str] = []
        self._stop = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._running = False

    # ── Lifecycle ────────────────────────────────────────

    def start(self, ai_color: StoneColor = StoneColor.BLACK) -> bool:
        """Launch engine. ai_color: which color the AI plays."""
        if not os.path.exists(_ENGINE_EXE):
            print(f"[Rapfi] Engine not found: {_ENGINE_EXE}")
            return False

        self._ai_color = ai_color
        self._lines.clear()
        self._stop.clear()

        try:
            self._proc = subprocess.Popen(
                [_ENGINE_EXE, f"--config={_CONFIG_PATH}"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
                cwd=_AI_DIR,
            )
        except Exception as e:
            print(f"[Rapfi] Start failed: {e}")
            return False

        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        # Wait for init
        time.sleep(0.8)
        if not self._has_line("Evaluator set to", 10):
            self.stop()
            return False

        # Send game parameters
        self._send(f"START {self._board_size}")
        time.sleep(0.2)

        # Rule: 1=exactly five + 4=renju = 5 (Free Renju)
        self._send("INFO rule 5")
        # Time limit per move: 10 seconds
        self._send(f"INFO timeout_turn {TURN_TIMEOUT}")

        # If AI is Black, trigger first move immediately
        self._first_move: Optional[tuple[int, int]] = None
        if self._ai_color == StoneColor.BLACK:
            self._send("BEGIN")
            self._first_move = self._wait_for_move()
            if self._first_move is None:
                self.stop()
                return False

        return True

    def stop(self) -> None:
        self._running = False
        self._stop.set()
        if self._proc:
            try:
                self._proc.stdin.write("END\n"); self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.terminate(); self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    # ── Game interface ───────────────────────────────────

    def get_move(self, opponent_row: int, opponent_col: int) -> Optional[tuple[int, int]]:
        """
        Get AI's next move after human played at (row, col).
        For first AI move as Black, pass (-1, -1) — already obtained in start().
        """
        if not self._running or self._proc is None:
            return None

        # First move as Black: return stored result from start()
        if opponent_row < 0 and self._ai_color == StoneColor.BLACK:
            return self._first_move

        # Clear old output so we only see the new response
        self._lines.clear()

        # Tell engine about opponent's move (comma format per Piskvork spec!)
        self._send(f"TURN {opponent_col},{opponent_row}")
        time.sleep(0.3)

        # Trigger search
        self._send("BEGIN")

        return self._wait_for_move()

    # ── Internals ────────────────────────────────────────

    def _wait_for_move(self) -> Optional[tuple[int, int]]:
        """Poll output for comma-separated move response."""
        deadline = time.time() + THINK_TIMEOUT
        while time.time() < deadline:
            move = self._extract_move()
            if move is not None:
                return move
            time.sleep(0.1)
        return self._extract_move()

    def _extract_move(self) -> Optional[tuple[int, int]]:
        """Find the latest X,Y move in engine output. Returns (row,col)."""
        for line in reversed(self._lines):
            m = re.match(r'^(\d+),(\d+)$', line.strip())
            if m:
                return (int(m.group(2)), int(m.group(1)))  # (row, col) from (x, y)
        return None

    def _send(self, cmd: str) -> None:
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write(cmd + "\n")
                self._proc.stdin.flush()
            except Exception:
                pass

    def _read_loop(self) -> None:
        if self._proc is None:
            return
        try:
            for line in iter(self._proc.stdout.readline, ""):
                if self._stop.is_set():
                    break
                self._lines.append(line.rstrip())
        except Exception:
            pass

    def _has_line(self, substring: str, timeout: float) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for line in self._lines:
                if substring in line:
                    return True
            time.sleep(0.2)
        return False


def shutdown_engine() -> None:
    pass
