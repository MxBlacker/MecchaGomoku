"""
Rapfi AI Engine Wrapper — subprocess via Piskvork protocol.
Non-blocking design:
  - Reader thread continuously collects stdout into _lines.
  - request_move() sends TURN + BEGIN and returns immediately.
  - poll_move() checks _lines for a move response each frame.
  - update_init() advances engine init across frames without sleeping.

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

THINK_TIMEOUT = 15.0   # max seconds to wait for engine move response
TURN_TIMEOUT = 10000   # milliseconds per move (tells engine time budget)
INIT_TIMEOUT = 10.0    # max seconds for engine initialization


class RapfiEngine:
    """Manages Rapfi engine subprocess for human-vs-AI play.

    All game-time methods are non-blocking — the caller drives them
    from the pygame main loop, so the UI stays responsive.
    """

    def __init__(self):
        self._board_size = 15
        self._ai_color: StoneColor = StoneColor.BLACK
        self._proc: Optional[subprocess.Popen] = None
        self._lines: list[str] = []
        self._stop = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._running = False

        # ── Non-blocking init state ──
        # Phase 0: not started
        # Phase 1: waiting for "Evaluator set to" message
        # Phase 2: START sent, waiting 0.3s before INFO commands
        # Phase 3: (internal) INFO sent, engine ready
        # Phase 4: waiting for first AI move (only when AI plays Black)
        self._init_phase = 0
        self._init_ready = False
        self._phase_time = 0.0
        self._first_move: Optional[tuple[int, int]] = None

        # ── Non-blocking move-request state ──
        self._waiting_for_move = False
        self._request_time = 0.0
        self._response_start_idx = 0  # only scan _lines from this index for the move

    # ── Lifecycle ────────────────────────────────────────

    def start(self, ai_color: StoneColor = StoneColor.BLACK) -> bool:
        """Launch engine process (non-blocking).

        Call update_init() each frame until it returns "ready".
        """
        if not os.path.exists(_ENGINE_EXE):
            print(f"[Rapfi] Engine not found: {_ENGINE_EXE}")
            return False

        self._ai_color = ai_color
        self._lines.clear()
        self._stop.clear()
        self._init_ready = False
        self._waiting_for_move = False
        self._first_move = None

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

        self._init_phase = 1
        self._phase_time = time.time()
        return True

    def update_init(self) -> str:
        """Non-blocking init step — call once per frame.

        Returns:
            "waiting" — still initializing, call again next frame
            "ready"   — engine is ready for gameplay
            "failed"  — init timed out; caller should stop the engine
        """
        if self._init_ready:
            return "ready"

        # ── Phase 1: wait for evaluator to load ──
        if self._init_phase == 1:
            if self._has_line_substring("Evaluator set to"):
                self._send(f"START {self._board_size}")
                self._init_phase = 2
                self._phase_time = time.time()
            elif time.time() - self._phase_time > INIT_TIMEOUT:
                self.stop()
                return "failed"
            return "waiting"

        # ── Phase 2: brief delay after START, then send INFO ──
        if self._init_phase == 2:
            if time.time() - self._phase_time > 0.3:
                # Rule 2 = free renju (black 三三/四四/长连 forbidden)
                self._send("INFO rule 2")
                self._send(f"INFO timeout_turn {TURN_TIMEOUT}")

                if self._ai_color == StoneColor.BLACK:
                    # AI plays Black — request first move right away
                    self._response_start_idx = len(self._lines)
                    self._send("BEGIN")
                    self._waiting_for_move = True
                    self._request_time = time.time()
                    self._init_phase = 4
                else:
                    self._init_ready = True
                    return "ready"
            return "waiting"

        # ── Phase 4: waiting for first AI move (Black only) ──
        if self._init_phase == 4:
            move = self._extract_move_from(self._response_start_idx)
            if move is not None:
                self._first_move = move
                self._waiting_for_move = False
                self._init_ready = True
                return "ready"
            if time.time() - self._request_time > THINK_TIMEOUT:
                # Timeout — engine may still respond; don't block
                self._waiting_for_move = False
                self._init_ready = True
                return "ready"
            return "waiting"

        return "waiting"

    def stop(self) -> None:
        """Terminate the engine subprocess."""
        self._running = False
        self._init_ready = False
        self._stop.set()
        if self._proc:
            try:
                self._proc.stdin.write("END\n")
                self._proc.stdin.flush()
            except Exception:
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    # ── Game interface ───────────────────────────────────

    def get_first_move(self) -> Optional[tuple[int, int]]:
        """Return the stored first move (only meaningful when AI = Black)."""
        return self._first_move

    def request_move(self, opp_row: int, opp_col: int) -> None:
        """Non-blocking: tell the engine the opponent's move and start search.

        Call poll_move() on subsequent frames to retrieve the result.
        """
        if not self._running or self._proc is None:
            return

        # Mark current line count so poll_move() only scans new output
        self._response_start_idx = len(self._lines)

        # Piskvork protocol: TURN (opponent move) then BEGIN (start search)
        self._send(f"TURN {opp_col},{opp_row}")
        self._send("BEGIN")

        self._waiting_for_move = True
        self._request_time = time.time()

    def poll_move(self) -> Optional[tuple[int, int]]:
        """Non-blocking: check whether the engine has returned a move.

        Returns (row, col) if a move is ready, or None if still thinking.
        """
        if not self._waiting_for_move:
            return None

        move = self._extract_move_from(self._response_start_idx)
        if move is not None:
            self._waiting_for_move = False
            return move

        # Timeout — try one last time, then stop waiting
        if time.time() - self._request_time > THINK_TIMEOUT:
            self._waiting_for_move = False
            return self._extract_move_from(self._response_start_idx)

        return None

    @property
    def is_ready(self) -> bool:
        """True once the engine has finished initialization."""
        return self._init_ready

    @property
    def is_thinking(self) -> bool:
        """True while the engine is searching for a move."""
        return self._waiting_for_move

    # ── Internals ────────────────────────────────────────

    def _extract_move_from(self, start_idx: int) -> Optional[tuple[int, int]]:
        """Scan _lines[start_idx:] for a "X,Y" move response.

        Returns (row, col) or None.  Converts engine (x,y) → board (row,col).
        """
        for i in range(start_idx, len(self._lines)):
            m = re.match(r'^(\d+),(\d+)$', self._lines[i].strip())
            if m:
                return (int(m.group(2)), int(m.group(1)))  # (row, col) from (x, y)
        return None

    def _has_line_substring(self, substring: str) -> bool:
        """Non-blocking check: does any collected output line contain *substring*?"""
        for line in self._lines:
            if substring in line:
                return True
        return False

    def _send(self, cmd: str) -> None:
        """Write a command to the engine's stdin."""
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write(cmd + "\n")
                self._proc.stdin.flush()
            except Exception:
                pass

    def _read_loop(self) -> None:
        """Background thread: continuously read engine stdout into _lines."""
        if self._proc is None:
            return
        try:
            for line in iter(self._proc.stdout.readline, ""):
                if self._stop.is_set():
                    break
                self._lines.append(line.rstrip())
        except Exception:
            pass


def shutdown_engine() -> None:
    """No-op kept for API compatibility."""
    pass
